"""Policy engine — pure deterministic Python, no LLM.

Decides what the tutor should do next based on learner state.
Priority order is fixed; do not reorder without updating golden traces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.state import LearnerState, Modality

Action = Literal[
    "re_explain",          # full re-explanation of current KC
    "light_re_explain",    # brief clarification nudge
    "new_question",        # fresh question in same modality
    "change_modality",     # switch presentation style, then question
    "advance_kc",          # learner has mastered this KC, move on
    "session_complete",    # all KCs mastered
]

# Thresholds — single source of truth, referenced in tests
MASTERY_ADVANCE = 0.80
STABILITY_ADVANCE = 0.70
CONFIDENCE_LOW = 0.45
CONSECUTIVE_FAIL_MODALITY = 2  # failures in same modality before switching

# Mastery / stability learning rates used by update_skill_after_turn
MASTERY_GAIN = 0.15            # EMA step toward 1.0 on correct
MASTERY_LOSS = 0.10            # flat step toward 0.0 on incorrect
STABILITY_GAIN_PER_STREAK = 0.10
STABILITY_LOSS = 0.05


@dataclass(frozen=True)
class PolicyDecision:
    action: Action
    reason: str
    suggested_modality: Modality | None = None


def decide(state: LearnerState) -> PolicyDecision:
    """Return the next pedagogical action for the given learner state.

    Priority 0 → 6. First matching rule wins.
    """
    if state.session_complete:
        return PolicyDecision(action="session_complete", reason="All KCs completed")

    skill = state.current_skill
    last = state.last_turn

    # Priority 0: never-attempted KC → introduce it before anything else.
    # Triggers naturally on session start AND on every KC transition.
    if skill.attempts == 0:
        return PolicyDecision(
            action="re_explain",
            reason=f"First encounter with KC '{state.current_kc.value}'",
            suggested_modality="explain",
        )

    # Priority 1: low learner confidence → full re-explain
    if last is not None and last.confidence is not None and last.confidence < CONFIDENCE_LOW:
        return PolicyDecision(
            action="re_explain",
            reason=f"Learner confidence {last.confidence:.2f} below threshold {CONFIDENCE_LOW}",
            suggested_modality="explain",
        )

    # Priority 2: high mastery + stability → advance to next KC
    if skill.mastery >= MASTERY_ADVANCE and skill.stability >= STABILITY_ADVANCE:
        if state.current_kc == list(state.skills.keys())[-1]:
            return PolicyDecision(
                action="session_complete",
                reason="Final KC mastered",
            )
        return PolicyDecision(
            action="advance_kc",
            reason=(
                f"Mastery {skill.mastery:.2f} ≥ {MASTERY_ADVANCE} "
                f"and stability {skill.stability:.2f} ≥ {STABILITY_ADVANCE}"
            ),
        )

    # Priority 3: repeated failures in the same modality → change presentation style
    if (
        skill.consecutive_incorrect >= CONSECUTIVE_FAIL_MODALITY
        and skill.last_modality is not None
    ):
        new_modality = _alternate_modality(skill.last_modality)
        return PolicyDecision(
            action="change_modality",
            reason=(
                f"{skill.consecutive_incorrect} consecutive failures "
                f"in modality '{skill.last_modality}'"
            ),
            suggested_modality=new_modality,
        )

    # Priority 4: last answer was incorrect → re-explain
    if last is not None and last.correct is False:
        return PolicyDecision(
            action="re_explain",
            reason="Incorrect answer on last turn",
            suggested_modality="explain",
        )

    # Priority 5: correct/partial but mastery still low → new question
    if last is not None and last.correct is True and skill.mastery < MASTERY_ADVANCE:
        return PolicyDecision(
            action="new_question",
            reason=f"Correct answer but mastery {skill.mastery:.2f} still below {MASTERY_ADVANCE}",
            suggested_modality=skill.last_modality or "multiple_choice",
        )

    # Priority 5b: after any non-graded turn (intro, re-explain, worked example),
    # if mastery is still below threshold, ask a question to gather signal.
    # P3 still wins on 2+ consecutive failures so this doesn't prevent escalation.
    # Without this rule the flow would loop on light_re_explain after every explain
    # — graded answers are the only way to bump mastery.
    if (
        last is not None
        and last.correct is None
        and skill.last_modality in ("explain", "worked_example")
        and skill.mastery < MASTERY_ADVANCE
    ):
        return PolicyDecision(
            action="new_question",
            reason="Ready to test understanding after explanation",
            suggested_modality="multiple_choice",
        )

    # Priority 6: default — light re-explanation to consolidate
    return PolicyDecision(
        action="light_re_explain",
        reason="Default: consolidation nudge",
        suggested_modality="explain",
    )


def _alternate_modality(current: Modality) -> Modality:
    """Rotate to a different modality when the learner is stuck."""
    rotation: dict[Modality, Modality] = {
        "multiple_choice": "worked_example",
        "free_response": "worked_example",
        "worked_example": "multiple_choice",
        "explain": "multiple_choice",
    }
    return rotation[current]


def update_skill_after_turn(state: LearnerState, correct: bool | None) -> None:
    """Mutate skill state based on the outcome of the last turn.

    Called by the flow after each learner response before the next policy call.
    """
    skill = state.current_skill
    skill.attempts += 1

    if correct is True:
        skill.consecutive_correct += 1
        skill.consecutive_incorrect = 0
        # Incremental mastery update — exponential moving average toward 1.0
        skill.mastery = min(1.0, skill.mastery + MASTERY_GAIN * (1.0 - skill.mastery))
        # Stability grows with the current consecutive-correct streak
        skill.stability = min(
            1.0, skill.stability + STABILITY_GAIN_PER_STREAK * skill.consecutive_correct
        )
    elif correct is False:
        skill.consecutive_incorrect += 1
        skill.consecutive_correct = 0
        skill.mastery = max(0.0, skill.mastery - MASTERY_LOSS)
        skill.stability = max(0.0, skill.stability - STABILITY_LOSS)
    # correct is None → no answer yet (explain/worked_example turns)
