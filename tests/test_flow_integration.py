"""Integration tests for src/flow.py — drives the full pipeline with the LLM mocked.

These tests catch wiring bugs that unit tests on individual modules miss:
    - whether KC advances trigger a re-introduction (bug #1 from review)
    - whether worked_example items terminate the P3 loop (bug #2 from review)
    - whether the mastery loop can actually complete a session
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.flow import TutorFlow
from src.state import KC, KC_SEQUENCE


def _fake_llm(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    """Replacement for call_llm — never touches the network."""
    return {
        "message": "<mock tutor message>",
        "action_taken": "explained",
        "confidence_prompt": None,
    }


def _build_flow(answers: list[str], confidences: list[str] | None = None) -> TutorFlow:
    """Build a flow whose I/O is scripted from the given answer queue."""
    flow = TutorFlow(learner_id="integration-test")
    answers_iter = iter(answers)
    confidences_iter = iter(confidences or [])

    def fake_input(prompt: str) -> str:
        if "answer" in prompt.lower():
            return next(answers_iter, "")
        # confidence prompt
        return next(confidences_iter, "")

    flow._get_input = fake_input  # type: ignore[method-assign]
    flow._display = lambda _text: None  # type: ignore[method-assign]
    return flow


@patch("src.flow.call_llm", side_effect=_fake_llm)
def test_fresh_kc_after_advance_triggers_intro(_mock_llm: Any) -> None:
    """Bug #1 regression: advancing to a new KC must re-introduce, not jump to a question."""
    flow = _build_flow(answers=[])
    # Mastered the first KC
    flow.state.skills[KC.MEAN_MEDIAN].mastery = 0.95
    flow.state.skills[KC.MEAN_MEDIAN].stability = 0.85
    flow.state.skills[KC.MEAN_MEDIAN].attempts = 5
    # And then advance to variance (which has attempts=0)
    flow.state.advance_kc()
    assert flow.state.current_kc == KC.VARIANCE
    assert flow.state.current_skill.attempts == 0

    from src.policy import decide
    decision = decide(flow.state)
    assert decision.action == "re_explain", (
        f"Expected re-introduction on fresh KC, got {decision.action}"
    )


@patch("src.flow.call_llm", side_effect=_fake_llm)
def test_worked_example_terminates_p3_loop(_mock_llm: Any) -> None:
    """Bug #2 regression: after a worked_example, the next policy call must NOT refire P3."""
    flow = _build_flow(answers=[])
    skill = flow.state.skills[KC.VARIANCE]
    skill.attempts = 3
    skill.consecutive_incorrect = 2  # P3 threshold
    skill.last_modality = "multiple_choice"
    flow.state.current_kc = KC.VARIANCE

    from src.policy import PolicyDecision, decide

    decision_before = decide(flow.state)
    assert decision_before.action == "change_modality"
    assert decision_before.suggested_modality == "worked_example"

    # Simulate executing the worked_example branch
    decision = PolicyDecision(
        action="change_modality",
        reason="test",
        suggested_modality="worked_example",
    )
    flow._execute_decision(decision)

    # Now the SAME decide() call should NOT return change_modality again
    decision_after = decide(flow.state)
    assert decision_after.action != "change_modality", (
        f"P3 fired again after worked_example — infinite loop bug. "
        f"Got: {decision_after.action} | {decision_after.reason}"
    )
    assert skill.consecutive_incorrect == 0
    assert skill.last_modality == "worked_example"


@patch("src.flow.call_llm", side_effect=_fake_llm)
def test_initial_policy_decision_is_introduction(_mock_llm: Any) -> None:
    """Fresh session, no prior history → P0 should fire."""
    flow = _build_flow(answers=[])
    from src.policy import decide
    decision = decide(flow.state)
    assert decision.action == "re_explain"
    assert "First encounter" in decision.reason


def test_kc_sequence_advances_through_all_six() -> None:
    """The full session can walk through all 6 KCs via advance_kc()."""
    flow = _build_flow(answers=[])
    visited = [flow.state.current_kc]
    while flow.state.advance_kc():
        visited.append(flow.state.current_kc)
    assert visited == KC_SEQUENCE
    assert flow.state.session_complete


@patch("src.flow.call_llm", side_effect=_fake_llm)
def test_grader_handles_numerical_formatting_variants(_mock_llm: Any) -> None:
    flow = _build_flow(answers=[])
    # Exact match
    assert flow._grade("70", "70")
    # Extra whitespace and case
    assert flow._grade("  Median ", "median")
    # Parens vs no parens, same numbers
    assert flow._grade("46.08, 53.92", "(46.08, 53.92)")
    # Genuinely different numbers
    assert not flow._grade("46.08, 54.00", "(46.08, 53.92)")
    # Wrong answer entirely
    assert not flow._grade("garbage", "70")


@pytest.mark.parametrize("learner_confidence,expected_model", [
    (None, "haiku"),
    (0.90, "haiku"),
    (0.30, "sonnet"),
])
def test_model_routing_threshold(learner_confidence: float | None, expected_model: str) -> None:
    """Two-tier routing: confidence < 0.45 escalates to Sonnet."""
    from src.tools.llm_tool import _HAIKU, _SONNET, _select_model
    actual = _select_model(learner_confidence)
    if expected_model == "haiku":
        assert actual == _HAIKU
    else:
        assert actual == _SONNET


@patch("src.flow.call_llm", side_effect=_fake_llm)
def test_execute_decision_advance_kc_does_not_crash(_mock_llm: Any) -> None:
    """Regression: advance_kc branch in _execute_decision references KC_LABELS.

    Catches the F1 NameError flagged in the tech-lead review — if the symbol
    in flow.py:_execute_decision drifts from the import in state.py, this fails.
    """
    flow = _build_flow(answers=["8"], confidences=["7"])
    # Mastered KC0 so advance_kc is the next sane move
    flow.state.skills[KC.MEAN_MEDIAN].mastery = 0.95
    flow.state.skills[KC.MEAN_MEDIAN].stability = 0.85
    flow.state.skills[KC.MEAN_MEDIAN].attempts = 5

    from src.policy import PolicyDecision
    decision = PolicyDecision(action="advance_kc", reason="test")

    # Must not raise NameError on KC_LABELS lookup.
    result = flow._execute_decision(decision)

    # After advance_kc, the new KC is fresh (attempts==0) → P0 intro is rendered
    # in the same call, so flow returns "policy_loop" to continue the session.
    assert result == "policy_loop"
    assert flow.state.current_kc == KC.VARIANCE
