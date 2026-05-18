"""End-to-end tests for the FastAPI app — covers the previously-untested
orchestration in src/app.py: session creation, turn dispatch, error paths,
the worked-example short-circuit, and the per-session lock invariant.

All LLM calls are mocked so these tests run offline.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.app import _sessions, app
from src.primitives import Exercise
from src.state import KC


def _fake_llm(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {
        "message": "<mock tutor message>",
        "action_taken": "explained",
        "confidence_prompt": "rate your confidence 0-10",
    }


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    """Each test starts with an empty session store."""
    _sessions.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/session
# ---------------------------------------------------------------------------


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_create_session_returns_p0_explain(_mock: Any, client: TestClient) -> None:
    """Fresh session must start with an explain (P0), input_mode='explain'."""
    res = client.post("/api/session", json={})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["session_id"]
    assert data["input_mode"] == "explain"
    assert data["current_kc"] == "mean_median"
    assert len(data["progress"]) == 6
    assert all(p["mastery"] == 0.0 for p in data["progress"])
    assert data["message"] == "<mock tutor message>"


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_create_session_with_learner_id(_mock: Any, client: TestClient) -> None:
    res = client.post("/api/session", json={"learner_id": "alice"})
    assert res.status_code == 200
    sid = res.json()["session_id"]

    status = client.get(f"/api/session/{sid}").json()
    assert status["learner_id"] == "alice"


# ---------------------------------------------------------------------------
# /api/turn — happy path & validation
# ---------------------------------------------------------------------------


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_turn_after_explain_progresses(_mock: Any, client: TestClient) -> None:
    """After the P0 explain, submitting confidence advances to the next step."""
    sid = client.post("/api/session", json={}).json()["session_id"]
    res = client.post(f"/api/turn/{sid}", json={"answer": None, "confidence": 0.8})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["input_mode"] in ("question", "explain", "done")


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_unknown_session_returns_404(_mock: Any, client: TestClient) -> None:
    res = client.post("/api/turn/does-not-exist", json={"answer": "x", "confidence": 0.5})
    assert res.status_code == 404
    assert res.json()["detail"] == "session not found"


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_question_turn_requires_answer(_mock: Any, client: TestClient) -> None:
    """If a question is pending, submitting answer=None must 422."""
    sid = client.post("/api/session", json={}).json()["session_id"]

    # Manually transition the session to pending question state by faking it
    session = _sessions[sid]
    session.pending_kind = "question"
    session.pending_item = Exercise(
        item_id="mm_01",
        kc=KC.MEAN_MEDIAN,
        modality="multiple_choice",
        difficulty=0.3,
        question="Q?",
        correct_answer="8",
        worked_example="W",
    )

    res = client.post(f"/api/turn/{sid}", json={"answer": None, "confidence": 0.7})
    assert res.status_code == 422
    assert "answer required" in res.json()["detail"]


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_confidence_out_of_range_rejected(_mock: Any, client: TestClient) -> None:
    sid = client.post("/api/session", json={}).json()["session_id"]
    res = client.post(f"/api/turn/{sid}", json={"answer": None, "confidence": 1.5})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# /api/turn — grading and skill update
# ---------------------------------------------------------------------------


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_correct_answer_updates_mastery(_mock: Any, client: TestClient) -> None:
    """A correct question turn must bump current-KC mastery off 0.0."""
    sid = client.post("/api/session", json={}).json()["session_id"]
    session = _sessions[sid]

    # Stage a known question turn
    session.pending_kind = "question"
    session.pending_item = Exercise(
        item_id="mm_01",
        kc=KC.MEAN_MEDIAN,
        modality="multiple_choice",
        difficulty=0.3,
        question="Q?",
        correct_answer="8",
        worked_example="W",
    )
    # Append a matching TurnLog so the item_id assertion in submit_turn passes
    from src.engine import log_turn
    log_turn(session.state, "multiple_choice", session.pending_item, "Q?")

    res = client.post(f"/api/turn/{sid}", json={"answer": "8", "confidence": 0.7})
    assert res.status_code == 200
    progress = res.json()["progress"]
    mean_median = next(p for p in progress if p["kc"] == "mean_median")
    assert mean_median["mastery"] > 0.0, "Correct answer should raise mastery"
    assert mean_median["attempts"] >= 1


# ---------------------------------------------------------------------------
# /api/session/{sid} — status read
# ---------------------------------------------------------------------------


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_get_session_status(_mock: Any, client: TestClient) -> None:
    sid = client.post("/api/session", json={"learner_id": "bob"}).json()["session_id"]
    res = client.get(f"/api/session/{sid}")
    assert res.status_code == 200
    data = res.json()
    assert data["learner_id"] == "bob"
    assert data["current_kc"] == "mean_median"
    assert data["session_complete"] is False
    assert len(data["progress"]) == 6


def test_get_unknown_session_returns_404(client: TestClient) -> None:
    assert client.get("/api/session/nope").status_code == 404


# ---------------------------------------------------------------------------
# UI route
# ---------------------------------------------------------------------------


def test_index_serves_html(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "Statistics Tutor" in res.text
    assert "<html" in res.text.lower()


# ---------------------------------------------------------------------------
# Concurrency: per-session lock prevents interleaved mutations
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Confidence prompt gating (CPO Decision #9b)
# ---------------------------------------------------------------------------


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_p0_first_introduction_suppresses_confidence_prompt(
    _mock: Any, client: TestClient
) -> None:
    """First-introduction (P0, no prior friction) must not ask for confidence."""
    res = client.post("/api/session", json={}).json()
    assert res["confidence_prompt"] is None, (
        "First-encounter explain shouldn't survey the learner before any friction"
    )


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_re_explain_after_wrong_answer_prompts_confidence(
    _mock: Any, client: TestClient
) -> None:
    """A wrong answer → re_explain must surface a confidence prompt (friction)."""
    sid = client.post("/api/session", json={}).json()["session_id"]
    session = _sessions[sid]

    # Stage a question awaiting an answer
    session.pending_kind = "question"
    session.pending_item = Exercise(
        item_id="mm_01",
        kc=KC.MEAN_MEDIAN,
        modality="multiple_choice",
        difficulty=0.3,
        question="Q?",
        correct_answer="8",
        worked_example="W",
    )
    from src.engine import log_turn
    log_turn(session.state, "multiple_choice", session.pending_item, "Q?")

    res = client.post(f"/api/turn/{sid}", json={"answer": "wrong", "confidence": 0.5})
    assert res.status_code == 200
    data = res.json()
    # After a wrong answer P4 fires → re_explain → confidence prompt expected
    assert data["input_mode"] == "explain"
    assert data["confidence_prompt"] is not None
    assert "0" in data["confidence_prompt"] and "10" in data["confidence_prompt"]


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_first_introduction_emits_friendly_reason(
    _mock: Any, client: TestClient
) -> None:
    """Auditability wedge: the tutor's first move surfaces a learner-facing reason."""
    res = client.post("/api/session", json={}).json()
    assert res["tutor_reason"] is not None
    assert "fresh" in res["tutor_reason"].lower() or "start" in res["tutor_reason"].lower()


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_wrong_answer_reason_explains_the_re_explain(
    _mock: Any, client: TestClient
) -> None:
    """After a wrong answer, the tutor_reason must name the friction."""
    sid = client.post("/api/session", json={}).json()["session_id"]
    session = _sessions[sid]
    session.pending_kind = "question"
    session.pending_item = Exercise(
        item_id="mm_01",
        kc=KC.MEAN_MEDIAN,
        modality="multiple_choice",
        difficulty=0.3,
        question="Q?",
        correct_answer="8",
        worked_example="W",
    )
    from src.engine import log_turn
    log_turn(session.state, "multiple_choice", session.pending_item, "Q?")

    res = client.post(f"/api/turn/{sid}", json={"answer": "wrong", "confidence": 0.5}).json()
    assert res["tutor_reason"] is not None
    assert "right" in res["tutor_reason"].lower() or "re-explain" in res["tutor_reason"].lower()


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_confidence_can_be_omitted(_mock: Any, client: TestClient) -> None:
    """When the UI suppresses the slider, confidence may be null in TurnRequest."""
    sid = client.post("/api/session", json={}).json()["session_id"]
    res = client.post(f"/api/turn/{sid}", json={"answer": None})  # no confidence at all
    assert res.status_code == 200, res.text


@patch("src.app.call_llm", side_effect=_fake_llm)
def test_per_session_lock_serialises_concurrent_turns(_mock: Any, client: TestClient) -> None:
    """Two concurrent turns on the same session must not corrupt state.

    Without the per-session asyncio.Lock, both turns could read state.turn=N,
    bump it to N+1, and end with one TurnLog lost (or pending_item/seen_ids
    corrupted across awaits).

    With the lock, requests are serialised. One may legitimately return 422
    (if the first request moved the session to question-pending mode and the
    second sent no answer) — that's correct serialised behaviour, not corruption.
    """
    sid = client.post("/api/session", json={}).json()["session_id"]
    initial_turn = _sessions[sid].state.turn
    initial_history_len = len(_sessions[sid].state.history)

    from httpx import ASGITransport, AsyncClient

    async def hit() -> tuple[int, int, list[int]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            results = await asyncio.gather(
                ac.post(f"/api/turn/{sid}", json={"answer": "any", "confidence": 0.5}),
                ac.post(f"/api/turn/{sid}", json={"answer": "any", "confidence": 0.6}),
            )
        statuses = [r.status_code for r in results]
        return _sessions[sid].state.turn, len(_sessions[sid].state.history), statuses

    final_turn, final_history_len, statuses = asyncio.run(hit())

    # Both requests must terminate cleanly (200 or 422 — 422 is a legitimate
    # serialised refusal). No 500s, no hangs.
    for status in statuses:
        assert status in (200, 422), f"Unexpected status {status}"
    assert 200 in statuses, "At least one concurrent turn should have succeeded"

    # State must advance monotonically — no lost turns, no duplicate increments.
    # Successful turns each append exactly one TurnLog; failed turns append none.
    successes = statuses.count(200)
    assert final_history_len == initial_history_len + successes, (
        f"History length corruption: initial={initial_history_len}, "
        f"final={final_history_len}, successes={successes}"
    )
    assert final_turn == initial_turn + successes, (
        f"Turn counter corruption: initial={initial_turn}, "
        f"final={final_turn}, successes={successes}"
    )
