"""FastAPI web server for the adaptive statistics tutor.

Request-response API — does NOT use the blocking CLI TutorFlow.
Orchestrates policy → LLM directly, one HTTP request per tutor turn.

Endpoints:
  POST /api/session          — create session, get first tutor message
  POST /api/turn/{sid}       — submit answer + confidence, get next step
  GET  /api/session/{sid}    — read session progress without advancing
  GET  /                     — serve the single-page chat UI
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.engine import build_progress as _engine_build_progress
from src.engine import grade as _engine_grade
from src.engine import log_turn as _engine_log_turn
from src.policy import decide, update_skill_after_turn
from src.primitives import Exercise
from src.prompts import load_prompt, render_prompt
from src.state import KC, KC_LABELS, LearnerState, Modality
from src.tools.content_store import ContentStore
from src.tools.llm_tool import call_llm

app = FastAPI(title="Adaptive Statistics Tutor", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Module-level singletons (loaded once at startup)
# ---------------------------------------------------------------------------

_store = ContentStore()
_system_prompt = load_prompt("system")
_UI_PATH = Path(__file__).parent / "web" / "index.html"

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

InputMode = Literal["question", "explain", "done"]


@dataclass
class SessionData:
    state: LearnerState
    seen_ids: list[str] = field(default_factory=list)
    pending_item: Exercise | None = None
    pending_kind: Literal["explain", "question"] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_seen_at: float = field(default_factory=time.monotonic)


# In-memory session store with idle-eviction.
# SESSION_TTL_SECONDS controls how long a session can sit idle before being
# garbage-collected by _sweep_idle_sessions. Production scale should swap this
# for Redis with a TTL; for v1 a single-process dict is sufficient.
SESSION_TTL_SECONDS = float(os.environ.get("TUTOR_SESSION_TTL", "1800"))  # 30 min default

_sessions: dict[str, SessionData] = {}
_sessions_lock = asyncio.Lock()  # guards _sessions dict itself, not per-session state


def _sweep_idle_sessions(now: float | None = None) -> int:
    """Drop sessions idle longer than SESSION_TTL_SECONDS. Returns count evicted.

    Called opportunistically from request handlers — no background task needed
    for v1 since traffic itself triggers sweeps.
    """
    now = now if now is not None else time.monotonic()
    stale = [
        sid for sid, s in _sessions.items()
        if (now - s.last_seen_at) > SESSION_TTL_SECONDS
    ]
    for sid in stale:
        _sessions.pop(sid, None)
    return len(stale)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    learner_id: str | None = None


class TurnRequest(BaseModel):
    answer: str | None = None
    # Confidence is now OPTIONAL. The server prompts for it only after friction
    # (re_explain, worked_example); routine turns send `confidence: null` so we
    # don't survey-fatigue the learner. See ADR: Product Decision #9b.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class SkillProgress(BaseModel):
    kc: KC
    mastery: float
    stability: float
    attempts: int


class TurnResponse(BaseModel):
    session_id: str
    message: str
    input_mode: InputMode
    confidence_prompt: str | None
    progress: list[SkillProgress]
    current_kc: KC
    # Human-readable rationale for the tutor's next move (from policy.decide).
    # Surfaced in the UI to make adaptation visible — the "auditability wedge".
    tutor_reason: str | None = None


class SessionStatusResponse(BaseModel):
    session_id: str
    learner_id: str
    current_kc: KC
    turn: int
    progress: list[SkillProgress]
    session_complete: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _call_llm_async(
    system: str,
    user: str,
    confidence: float | None,
) -> dict[str, Any]:
    """Run the blocking call_llm in a thread pool so we don't stall the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(call_llm, system, user, confidence))


# Thin wrappers around src/engine.py so the rest of this module stays unchanged.
_grade = _engine_grade


def _log_turn(
    state: LearnerState,
    modality: Modality,
    item: Exercise | None,
    llm_response: str,
) -> None:
    _engine_log_turn(state, modality, item, llm_response)


def _build_progress(state: LearnerState) -> list[SkillProgress]:
    return [SkillProgress(**row) for row in _engine_build_progress(state)]


# Confidence prompts are surfaced ONLY after friction. Routine turns
# (first_introduction, light_re_explain, plain new_question) suppress the
# prompt to avoid survey fatigue — Decision #9b in PRODUCT_DECISIONS.md.
_CONFIDENCE_FRICTION_PROMPT = "On a scale of 0–10, how clearly did that land?"


def _confidence_prompt_for(
    action: str,
    presentation_modality: Modality | None,
    last_was_incorrect: bool,
) -> str | None:
    """Return the friction-only confidence prompt or None.

    Friction is: re_explain after a wrong answer (P1/P4) or any worked_example.
    """
    if presentation_modality == "worked_example":
        return _CONFIDENCE_FRICTION_PROMPT
    if action == "re_explain" and last_was_incorrect:
        return _CONFIDENCE_FRICTION_PROMPT
    return None


def _friendly_reason(
    action: str,
    presentation_modality: Modality | None,
    last_was_incorrect: bool,
    first_encounter: bool,
) -> str | None:
    """Translate the policy's machine-readable rationale into a learner-facing line.

    This is the "auditability wedge" the CPO flagged — surface *why* the tutor
    chose this next move so the adaptation is visible, not invisible. Returns
    None for routine turns (avoid noise on every line).
    """
    if presentation_modality == "worked_example":
        return "We've stumbled a couple of times — let me walk through one step by step."
    if action == "re_explain":
        if first_encounter:
            return "Let's start fresh on this topic."
        if last_was_incorrect:
            return "That answer wasn't quite right — let me re-explain."
        return "You weren't sure last time — let's go through this carefully."
    if action == "advance_kc":
        return "Nice work — you've got this one. Moving on to the next topic."
    if action == "session_complete":
        return "All topics complete."
    # light_re_explain, new_question, change_modality (non-worked) → no banner.
    return None


# ---------------------------------------------------------------------------
# Core turn executor (shared by create_session and submit_turn)
# ---------------------------------------------------------------------------


async def _execute_next_step(
    session: SessionData,
) -> tuple[str, InputMode, str | None, str | None]:
    """Run decide → LLM and return (message, input_mode, confidence_prompt, tutor_reason).

    advance_kc triggers a second decide() call so the new KC's P0 fires.
    """
    state = session.state
    last_was_incorrect = bool(state.last_turn and state.last_turn.correct is False)
    decision = decide(state)

    if decision.action == "advance_kc":
        state.advance_kc()
        decision = decide(state)  # new KC has attempts==0 → P0 fires

    if decision.action == "session_complete":
        state.session_complete = True
        session.pending_kind = None
        session.pending_item = None
        return (
            "Great work! You've completed all topics in this session.",
            "done",
            None,
            _friendly_reason("session_complete", None, False, False),
        )

    kc = state.current_kc
    kc_label = KC_LABELS[kc]
    modality: Modality = decision.suggested_modality or "explain"
    first_encounter = state.current_skill.attempts == 0

    if decision.action in ("re_explain", "light_re_explain"):
        explain_type = (
            "first_introduction"
            if first_encounter
            else ("re_explain" if decision.action == "re_explain" else "light_re_explain")
        )
        item = _store.get_item(kc, None)
        user_prompt = render_prompt(
            "explain",
            kc_label=kc_label,
            mastery=f"{state.current_skill.mastery:.2f}",
            misconceptions=", ".join(item.misconceptions) if item else "none",
            explain_type=explain_type,
            worked_example=item.worked_example if item else "",
        )
        llm_out = await _call_llm_async(
            _system_prompt,
            user_prompt,
            state.last_turn.confidence if state.last_turn else None,
        )
        _log_turn(state, "explain", item, llm_out["message"])
        session.pending_kind = "explain"
        session.pending_item = None
        confidence_prompt = _confidence_prompt_for(
            decision.action, presentation_modality=None, last_was_incorrect=last_was_incorrect
        )
        tutor_reason = _friendly_reason(
            decision.action, None, last_was_incorrect, first_encounter
        )
        return llm_out["message"], "explain", confidence_prompt, tutor_reason

    if decision.action in ("new_question", "change_modality"):
        item = _store.get_item(kc, modality, exclude_ids=session.seen_ids)
        if item is None:
            item = _store.get_item(kc, None)
        if item is None:
            # No items at all for this KC — fall back to an explain
            session.pending_kind = "explain"
            session.pending_item = None
            return (
                f"Let's review {kc_label} a bit more.",
                "explain",
                None,
                None,
            )

        session.seen_ids.append(item.item_id)
        presentation_modality: Modality = (
            modality if modality == "worked_example" else item.modality
        )

        user_prompt = render_prompt(
            "question",
            kc_label=kc_label,
            item_id=item.item_id,
            modality=presentation_modality,
            difficulty=item.difficulty,
            question=item.question,
            choices="\n".join(item.choices),
        )
        llm_out = await _call_llm_async(
            _system_prompt,
            user_prompt,
            state.last_turn.confidence if state.last_turn else None,
        )
        _log_turn(state, presentation_modality, item, llm_out["message"])

        if presentation_modality == "worked_example":
            skill = state.current_skill
            skill.attempts += 1
            skill.consecutive_incorrect = 0
            skill.last_modality = "worked_example"
            session.pending_kind = "explain"
            session.pending_item = None
            # Worked example = friction by definition (we got here via P3).
            return (
                llm_out["message"],
                "explain",
                _confidence_prompt_for(decision.action, "worked_example", False),
                _friendly_reason(
                    decision.action, "worked_example", last_was_incorrect, first_encounter
                ),
            )

        session.pending_kind = "question"
        session.pending_item = item
        # Plain question (MC / FR) — confidence comes bundled with the answer,
        # so suppress a separate prompt here.
        return llm_out["message"], "question", None, None

    # Shouldn't reach here; treat as explain
    session.pending_kind = "explain"
    session.pending_item = None
    return "Let's keep going!", "explain", None, None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/session", response_model=TurnResponse)
async def create_session(body: CreateSessionRequest) -> TurnResponse:
    """Create a new session and return the first tutor message (P0 intro)."""
    async with _sessions_lock:
        _sweep_idle_sessions()
        learner_id = body.learner_id or f"learner-{uuid.uuid4().hex[:8]}"
        session_id = uuid.uuid4().hex
        session = SessionData(state=LearnerState(learner_id=learner_id))
        _sessions[session_id] = session

    async with session.lock:
        message, input_mode, confidence_prompt, tutor_reason = await _execute_next_step(
            session
        )
        session.last_seen_at = time.monotonic()
        return TurnResponse(
            session_id=session_id,
            message=message,
            input_mode=input_mode,
            confidence_prompt=confidence_prompt,
            progress=_build_progress(session.state),
            current_kc=session.state.current_kc,
            tutor_reason=tutor_reason,
        )


@app.post("/api/turn/{session_id}", response_model=TurnResponse)
async def submit_turn(session_id: str, body: TurnRequest) -> TurnResponse:
    """Submit a learner answer + confidence; receive feedback and next step."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    # Per-session lock serialises concurrent turns from the same client so that
    # state.turn, history, seen_ids and pending_item can't interleave across
    # `await` points inside _execute_next_step.
    async with session.lock:
        state = session.state
        if state.session_complete:
            session.last_seen_at = time.monotonic()
            return TurnResponse(
                session_id=session_id,
                message="This session is already complete. Well done!",
                input_mode="done",
                confidence_prompt=None,
                progress=_build_progress(state),
                current_kc=state.current_kc,
            )

        feedback_message: str = ""

        if session.pending_kind == "question":
            if not body.answer:
                raise HTTPException(status_code=422, detail="answer required for question turns")

            item = session.pending_item
            correct = _grade(body.answer, item.correct_answer) if item else False

            feedback_prompt = render_prompt(
                "feedback",
                kc_label=KC_LABELS[state.current_kc],
                question=item.question if item else "",
                correct_answer=item.correct_answer if item else "",
                learner_answer=body.answer,
                result="correct" if correct else "incorrect",
                worked_example=item.worked_example if item else "",
                misconceptions=", ".join(item.misconceptions) if item else "",
            )
            fb_out = await _call_llm_async(_system_prompt, feedback_prompt, body.confidence)
            feedback_message = fb_out["message"]

            # Update the matching question turn rather than blindly mutating
            # history[-1] (which could be a feedback log on retry).
            if item is not None and state.last_turn and state.last_turn.item_id == item.item_id:
                state.last_turn.learner_answer = body.answer
                state.last_turn.correct = correct
                # body.confidence may be None when the UI suppressed the slider
                # for a routine question — only persist it when supplied.
                if body.confidence is not None:
                    state.last_turn.confidence = body.confidence

            update_skill_after_turn(state, correct)
            if item:
                state.current_skill.last_modality = item.modality

        elif session.pending_kind == "explain":
            if state.last_turn and body.confidence is not None:
                state.last_turn.confidence = body.confidence

        # Determine and execute next pedagogical step
        message, input_mode, confidence_prompt, tutor_reason = await _execute_next_step(
            session
        )

        combined = (
            f"{feedback_message}\n\n{message}".strip() if feedback_message else message
        )
        session.last_seen_at = time.monotonic()
        return TurnResponse(
            session_id=session_id,
            message=combined,
            input_mode=input_mode,
            confidence_prompt=confidence_prompt,
            progress=_build_progress(state),
            current_kc=state.current_kc,
            tutor_reason=tutor_reason,
        )


@app.get("/api/session/{session_id}", response_model=SessionStatusResponse)
async def get_session(session_id: str) -> SessionStatusResponse:
    """Return current learner progress without advancing state."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    state = session.state
    return SessionStatusResponse(
        session_id=session_id,
        learner_id=state.learner_id,
        current_kc=state.current_kc,
        turn=state.turn,
        progress=_build_progress(state),
        session_complete=state.session_complete,
    )


@app.get("/", response_class=HTMLResponse)
async def serve_ui() -> str:
    """Serve the single-page chat UI."""
    if not _UI_PATH.exists():
        return "<h1>UI not found</h1><p>src/web/index.html is missing.</p>"
    return _UI_PATH.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)
