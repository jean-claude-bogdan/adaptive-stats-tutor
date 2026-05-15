"""Learner state models for the adaptive statistics tutor."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KC(StrEnum):
    """Six knowledge components covered by the tutor."""

    MEAN_MEDIAN = "mean_median"
    VARIANCE = "variance"
    Z_SCORES = "z_scores"
    SAMPLING_DISTRIBUTIONS = "sampling_distributions"
    STANDARD_ERROR = "standard_error"
    CONFIDENCE_INTERVALS = "confidence_intervals"


# Ordered sequence used when advancing to the next KC
KC_SEQUENCE: list[KC] = [
    KC.MEAN_MEDIAN,
    KC.VARIANCE,
    KC.Z_SCORES,
    KC.SAMPLING_DISTRIBUTIONS,
    KC.STANDARD_ERROR,
    KC.CONFIDENCE_INTERVALS,
]

Modality = Literal["explain", "worked_example", "multiple_choice", "free_response"]


class SkillState(BaseModel):
    """Mastery tracking for a single knowledge component."""

    model_config = ConfigDict(validate_assignment=True)

    kc: KC
    mastery: float = Field(default=0.0, ge=0.0, le=1.0)
    stability: float = Field(default=0.0, ge=0.0, le=1.0)
    attempts: int = 0
    consecutive_correct: int = 0
    consecutive_incorrect: int = 0
    last_modality: Modality | None = None
    has_misconception: bool = False


class TurnLog(BaseModel):
    """Record of a single tutor–learner exchange."""

    model_config = ConfigDict(validate_assignment=True)

    turn: int
    kc: KC
    modality: Modality
    item_id: str
    learner_answer: str | None = None
    correct: bool | None = None
    confidence: float | None = None  # learner self-reported, 0.0–1.0
    llm_response: str | None = None


class LearnerState(BaseModel):
    """Top-level state object threaded through the CrewAI Flow."""

    learner_id: str
    current_kc: KC = KC.MEAN_MEDIAN
    skills: dict[KC, SkillState] = Field(default_factory=dict)
    turn: int = 0
    history: list[TurnLog] = Field(default_factory=list)
    session_complete: bool = False

    def model_post_init(self, __context: object) -> None:
        """Ensure every KC has a SkillState entry."""
        for kc in KC:
            if kc not in self.skills:
                self.skills[kc] = SkillState(kc=kc)

    @property
    def current_skill(self) -> SkillState:
        return self.skills[self.current_kc]

    @property
    def last_turn(self) -> TurnLog | None:
        return self.history[-1] if self.history else None

    def advance_kc(self) -> bool:
        """Move to the next KC in sequence. Returns False if already at the last KC."""
        idx = KC_SEQUENCE.index(self.current_kc)
        if idx + 1 >= len(KC_SEQUENCE):
            self.session_complete = True
            return False
        self.current_kc = KC_SEQUENCE[idx + 1]
        return True
