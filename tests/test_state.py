"""Unit tests for src/state.py."""

from src.state import KC, KC_SEQUENCE, LearnerState, SkillState, TurnLog


def test_kc_sequence_covers_all_kcs() -> None:
    assert set(KC_SEQUENCE) == set(KC)
    assert len(KC_SEQUENCE) == 6


def test_learner_state_initializes_all_skills() -> None:
    state = LearnerState(learner_id="alice")
    assert len(state.skills) == 6
    for kc in KC:
        assert kc in state.skills
        assert isinstance(state.skills[kc], SkillState)
        assert state.skills[kc].mastery == 0.0


def test_current_skill_returns_active_kc_skill() -> None:
    state = LearnerState(learner_id="bob")
    assert state.current_skill.kc == KC.MEAN_MEDIAN


def test_advance_kc_walks_the_sequence() -> None:
    state = LearnerState(learner_id="carol")
    for expected in KC_SEQUENCE[1:]:
        state.advance_kc()
        assert state.current_kc == expected
    # One more call past the last KC should mark complete
    state.advance_kc()
    assert state.session_complete


def test_last_turn_returns_none_for_empty_history() -> None:
    state = LearnerState(learner_id="dan")
    assert state.last_turn is None
    state.history.append(
        TurnLog(turn=1, kc=KC.MEAN_MEDIAN, modality="multiple_choice", item_id="mm_01")
    )
    assert state.last_turn is not None
    assert state.last_turn.turn == 1


def test_mastery_bounded_to_unit_interval() -> None:
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SkillState(kc=KC.VARIANCE, mastery=1.5)
    with pytest.raises(ValidationError):
        SkillState(kc=KC.VARIANCE, mastery=-0.1)
