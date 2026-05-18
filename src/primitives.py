"""Platform primitives — canonical data models for the content catalog.

These five classes describe *what the tutor teaches*, not how a learner is doing.
Session-level mastery tracking lives in state.py.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.state import KC, Modality


class Competency(BaseModel):
    """Career-relevant skill cluster grouping one or more knowledge components."""

    model_config = ConfigDict(frozen=True)

    competency_id: str
    title: str
    description: str
    kcs: list[KC] = Field(default_factory=list)


class Concept(BaseModel):
    """Atomic knowledge component — maps 1-to-1 to the KC enum."""

    model_config = ConfigDict(frozen=True)

    kc: KC
    title: str
    description: str
    prerequisites: list[KC] = Field(default_factory=list)


class Exercise(BaseModel):
    """Specific task with grading metadata — mirrors the items.json schema."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    kc: KC
    modality: Modality
    difficulty: float = Field(ge=0.0, le=1.0)
    question: str
    choices: list[str] = Field(default_factory=list)
    correct_answer: str
    worked_example: str
    misconceptions: list[str] = Field(default_factory=list)


class Rubric(BaseModel):
    """Grading criteria attached to an exercise."""

    model_config = ConfigDict(frozen=True)

    rubric_id: str
    item_id: str
    criteria: list[str] = Field(default_factory=list)
    tolerance: float = 0.0


class Evidence(BaseModel):
    """Learner mastery demonstration record — captures one completed learning event."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    learner_id: str
    kc: KC
    item_id: str
    correct: bool | None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: datetime
