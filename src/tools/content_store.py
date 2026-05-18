"""Content store — abstracted item-bank access.

Loads items.json once at construction time and exposes typed retrieval methods
used by both the CLI flow and the FastAPI web layer.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from src.primitives import Exercise
from src.state import KC, Modality

_ITEMS_PATH = Path(__file__).parent.parent / "content" / "items.json"


class ContentStore:
    """Single source of truth for the exercise item bank."""

    def __init__(self) -> None:
        raw: list[dict[str, object]] = json.loads(_ITEMS_PATH.read_text(encoding="utf-8"))
        self._exercises: list[Exercise] = [Exercise(**item) for item in raw]

    def get_item(
        self,
        kc: KC,
        modality: Modality | None,
        exclude_ids: list[str] | None = None,
    ) -> Exercise | None:
        """Return one Exercise for the given KC, preferring the requested modality.

        `worked_example` is a presentation style, not an item filter — items are
        never filtered by `worked_example` modality.

        Falls back to the full KC pool if `exclude_ids` exhausts the candidate list.
        Returns None only when no items exist for this KC at all.
        """
        pool = [ex for ex in self._exercises if ex.kc == kc]
        if not pool:
            return None

        if exclude_ids:
            filtered = [ex for ex in pool if ex.item_id not in exclude_ids]
            if filtered:
                pool = filtered
            # else: ignore exclude_ids — better to repeat than to return None

        if modality and modality != "worked_example":
            preferred = [ex for ex in pool if ex.modality == modality]
            if preferred:
                return random.choice(preferred)

        return random.choice(pool)

    def get_exercise(self, item_id: str) -> Exercise | None:
        """Return a typed Exercise by item_id, or None if not found."""
        for ex in self._exercises:
            if ex.item_id == item_id:
                return ex
        return None

    def all_for_kc(self, kc: KC) -> list[Exercise]:
        """Return all exercises for a given KC."""
        return [ex for ex in self._exercises if ex.kc == kc]
