"""Shared turn-execution primitives used by both the CLI flow and the FastAPI app.

Anything that is genuinely pedagogical and orchestrator-agnostic lives here so
that flow.py and app.py do not drift in their behaviour (grading rules,
turn logging, progress snapshots, item dispatch).

This module deliberately has NO knowledge of CrewAI or FastAPI — it operates on
plain LearnerState / TurnLog objects.
"""

from __future__ import annotations

import re
from typing import Any

from src.primitives import Exercise
from src.state import KC_SEQUENCE, LearnerState, Modality, TurnLog


def grade(learner_answer: str, correct_answer: str) -> bool:
    """Case-insensitive match with numeric-token tolerance.

    Handles:
      - exact (case/whitespace insensitive) string match
      - same numeric tokens regardless of surrounding punctuation,
        so "(46.08, 53.92)" == "46.08, 53.92"

    Production should replace this with an LLM rubric grader.
    """
    a = learner_answer.strip().lower()
    b = correct_answer.strip().lower()
    if a == b:
        return True
    nums_a = re.findall(r"-?\d+\.?\d*", a)
    nums_b = re.findall(r"-?\d+\.?\d*", b)
    if nums_a and nums_a == nums_b:
        return True
    return False


def log_turn(
    state: LearnerState,
    modality: Modality,
    item: Exercise | None,
    llm_response: str,
) -> TurnLog:
    """Append a new TurnLog entry to the learner's history and return it."""
    state.turn += 1
    log = TurnLog(
        turn=state.turn,
        kc=state.current_kc,
        modality=modality,
        item_id=item.item_id if item else "none",
        llm_response=llm_response,
    )
    state.history.append(log)
    return log


def build_progress(state: LearnerState) -> list[dict[str, Any]]:
    """Snapshot the per-KC progress array used by the web layer."""
    return [
        {
            "kc": kc,
            "mastery": state.skills[kc].mastery,
            "stability": state.skills[kc].stability,
            "attempts": state.skills[kc].attempts,
        }
        for kc in KC_SEQUENCE
    ]
