"""Unit tests for src/policy.py — covers each priority branch individually."""

import pytest

from src.policy import (
    CONFIDENCE_LOW,
    CONSECUTIVE_FAIL_MODALITY,
    MASTERY_ADVANCE,
    STABILITY_ADVANCE,
    decide,
    update_skill_after_turn,
)
from src.state import KC, LearnerState, TurnLog


def _state_with_turn(
    kc: KC = KC.MEAN_MEDIAN,
    correct: bool | None = None,
    confidence: float | None = None,
    mastery: float = 0.0,
    stability: float = 0.0,
    consecutive_incorrect: int = 0,
    last_modality: str | None = None,
    attempts: int = 1,
) -> LearnerState:
    """Build a learner state in mid-session (attempts ≥ 1 so P0 doesn't fire)."""
    state = LearnerState(learner_id="t")
    state.current_kc = kc
    skill = state.skills[kc]
    skill.mastery = mastery
    skill.stability = stability
    skill.consecutive_incorrect = consecutive_incorrect
    skill.last_modality = last_modality  # type: ignore[assignment]
    skill.attempts = attempts
    state.history.append(
        TurnLog(
            turn=1, kc=kc, modality="multiple_choice", item_id="x",
            correct=correct, confidence=confidence,
        )
    )
    return state


def test_p1_low_confidence_triggers_re_explain() -> None:
    state = _state_with_turn(confidence=CONFIDENCE_LOW - 0.01, correct=True, mastery=0.5)
    decision = decide(state)
    assert decision.action == "re_explain"


def test_p2_high_mastery_and_stability_advances() -> None:
    state = _state_with_turn(
        confidence=0.80,
        correct=True,
        mastery=MASTERY_ADVANCE + 0.05,
        stability=STABILITY_ADVANCE + 0.05,
    )
    decision = decide(state)
    assert decision.action == "advance_kc"


def test_p3_repeated_modality_failures_change_modality() -> None:
    state = _state_with_turn(
        confidence=0.80,
        correct=False,
        consecutive_incorrect=CONSECUTIVE_FAIL_MODALITY,
        last_modality="multiple_choice",
    )
    decision = decide(state)
    assert decision.action == "change_modality"
    assert decision.suggested_modality != "multiple_choice"


def test_p4_incorrect_answer_re_explains() -> None:
    state = _state_with_turn(confidence=0.80, correct=False, mastery=0.30)
    decision = decide(state)
    assert decision.action == "re_explain"


def test_p5_correct_but_low_mastery_gets_new_question() -> None:
    state = _state_with_turn(confidence=0.80, correct=True, mastery=0.50)
    decision = decide(state)
    assert decision.action == "new_question"


def test_p0_fresh_kc_triggers_intro() -> None:
    """A skill with attempts=0 should always be re-explained as an intro."""
    state = LearnerState(learner_id="t")
    assert state.current_skill.attempts == 0
    decision = decide(state)
    assert decision.action == "re_explain"
    assert "First encounter" in decision.reason


def test_p6_default_light_re_explain() -> None:
    # attempts > 0 so P0 does not fire; no recent turn so other priorities are silent
    state = LearnerState(learner_id="t")
    state.current_skill.attempts = 1
    decision = decide(state)
    assert decision.action == "light_re_explain"


def test_p5b_first_question_after_intro_explain() -> None:
    """After P0 first_introduction, the next decide() must move to a question.

    Without this rule the policy infinite-loops on first_introduction (P0)
    or light_re_explain (P6). Regression for the bug surfaced by the browser
    smoke test on 2026-05-15.
    """
    state = _state_with_turn(
        correct=None,
        confidence=0.7,
        mastery=0.0,
        consecutive_incorrect=0,
        last_modality="explain",
        attempts=1,
    )
    decision = decide(state)
    assert decision.action == "new_question", (
        f"Expected new_question after intro, got {decision.action}"
    )
    assert decision.suggested_modality == "multiple_choice"


def test_p5b_fires_after_re_explain_one_wrong() -> None:
    """After a single wrong answer + P4 re_explain, P5b gives the learner another
    question rather than looping on light_re_explain. P3 still escalates at 2
    consecutive failures (verified separately).
    """
    state = _state_with_turn(
        correct=None,
        confidence=0.7,
        mastery=0.3,
        consecutive_incorrect=1,
        last_modality="explain",
        attempts=2,
    )
    decision = decide(state)
    assert decision.action == "new_question", (
        f"P5b should ask another question after one wrong, got {decision.action}"
    )


def test_p3_still_escalates_at_two_consecutive_failures() -> None:
    """Sanity: relaxing P5b must not stop P3 from firing on persistent failure."""
    state = _state_with_turn(
        correct=False,
        confidence=0.6,
        mastery=0.3,
        consecutive_incorrect=2,
        last_modality="multiple_choice",
        attempts=3,
    )
    decision = decide(state)
    assert decision.action == "change_modality"
    assert decision.suggested_modality == "worked_example"


def test_p5b_also_fires_after_worked_example() -> None:
    """A worked_example is teaching, not testing — next move should be a question."""
    state = _state_with_turn(
        correct=None,
        confidence=None,
        mastery=0.3,
        consecutive_incorrect=0,
        last_modality="worked_example",
        attempts=3,
    )
    decision = decide(state)
    assert decision.action == "new_question"


def test_priority_p1_beats_p2() -> None:
    """Low confidence should override otherwise-passing advance criteria."""
    state = _state_with_turn(
        confidence=0.20,
        correct=True,
        mastery=MASTERY_ADVANCE + 0.05,
        stability=STABILITY_ADVANCE + 0.05,
    )
    assert decide(state).action == "re_explain"


@pytest.mark.parametrize("correct,expected_mastery_delta", [
    (True, "increase"),
    (False, "decrease"),
])
def test_update_skill_after_turn_mastery_direction(
    correct: bool, expected_mastery_delta: str
) -> None:
    state = LearnerState(learner_id="t")
    state.current_skill.mastery = 0.50
    update_skill_after_turn(state, correct)
    if expected_mastery_delta == "increase":
        assert state.current_skill.mastery > 0.50
    else:
        assert state.current_skill.mastery < 0.50


def test_update_skill_streak_tracking() -> None:
    state = LearnerState(learner_id="t")
    update_skill_after_turn(state, True)
    update_skill_after_turn(state, True)
    assert state.current_skill.consecutive_correct == 2
    update_skill_after_turn(state, False)
    assert state.current_skill.consecutive_correct == 0
    assert state.current_skill.consecutive_incorrect == 1
