"""Content guardrails — fail if the item bank thins out or schema drifts.

Catches the CPO's HIGH-impact concern (too few items per KC means questions
repeat within a session, killing demo credibility) at CI time rather than
during a live pilot.
"""

from __future__ import annotations

from collections import Counter

import pytest

from src.state import KC_SEQUENCE
from src.tools.content_store import ContentStore

# Minimum items per KC to support a credible session at mastery threshold ~10.
# Pilot floor; raise as content team produces more.
_MIN_ITEMS_PER_KC = 8


@pytest.fixture(scope="module")
def store() -> ContentStore:
    return ContentStore()


def test_every_kc_has_minimum_item_coverage(store: ContentStore) -> None:
    counts = Counter(ex.kc for ex in store._exercises)
    short = {kc.value: counts[kc] for kc in KC_SEQUENCE if counts[kc] < _MIN_ITEMS_PER_KC}
    assert not short, (
        f"KCs below the {_MIN_ITEMS_PER_KC}-item floor: {short}. "
        f"Add more items before pilot — see PRODUCT_DECISIONS.md #4."
    )


def test_all_item_ids_are_unique(store: ContentStore) -> None:
    ids = [ex.item_id for ex in store._exercises]
    dupes = [x for x, n in Counter(ids).items() if n > 1]
    assert not dupes, f"Duplicate item_id values: {dupes}"


def test_every_item_has_misconceptions(store: ContentStore) -> None:
    """Misconception tagging is the pedagogical wedge — every item must list at least one."""
    missing = [ex.item_id for ex in store._exercises if not ex.misconceptions]
    assert not missing, f"Items lacking misconception tags: {missing}"


def test_multiple_choice_items_have_choices(store: ContentStore) -> None:
    """MC items must list >=2 choices including the correct answer."""
    bad = []
    for ex in store._exercises:
        if ex.modality == "multiple_choice":
            if len(ex.choices) < 2:
                bad.append((ex.item_id, "fewer than 2 choices"))
            elif ex.correct_answer not in ex.choices:
                bad.append((ex.item_id, f"correct_answer {ex.correct_answer!r} not in choices"))
    assert not bad, f"Malformed MC items: {bad}"


def test_difficulty_in_valid_range(store: ContentStore) -> None:
    out_of_range = [
        (ex.item_id, ex.difficulty)
        for ex in store._exercises
        if not (0.0 <= ex.difficulty <= 1.0)
    ]
    assert not out_of_range, f"Items with difficulty outside [0,1]: {out_of_range}"


def test_modality_mix_includes_free_response(store: ContentStore) -> None:
    """At least some free_response items per KC — string-match grading needs variety."""
    fr_counts = Counter(
        ex.kc for ex in store._exercises if ex.modality == "free_response"
    )
    no_fr = [kc.value for kc in KC_SEQUENCE if fr_counts[kc] == 0]
    assert not no_fr, f"KCs without any free_response items: {no_fr}"
