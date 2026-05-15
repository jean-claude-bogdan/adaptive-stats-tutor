"""Golden trace tests — CI fails if policy accuracy < 100%.

Each line of golden_traces.jsonl is a frozen state + expected policy action.
This is the canonical regression suite for the policy engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.policy import decide
from src.state import KC, LearnerState, TurnLog

_TRACES_PATH = Path(__file__).parent.parent / "src" / "evals" / "golden_traces.jsonl"


def _load_traces() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in _TRACES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _build_state(payload: dict[str, Any]) -> LearnerState:
    state = LearnerState(learner_id="golden")
    state.current_kc = KC(payload["current_kc"])
    for kc_value, skill_data in payload["skills"].items():
        kc = KC(kc_value)
        skill = state.skills[kc]
        for key, value in skill_data.items():
            setattr(skill, key, value)
    for turn_data in payload.get("history", []):
        turn_data = dict(turn_data)
        turn_data["kc"] = KC(turn_data["kc"])
        state.history.append(TurnLog(**turn_data))
    return state


TRACES = _load_traces()


def test_we_have_at_least_ten_traces() -> None:
    assert len(TRACES) >= 10, f"Expected ≥10 golden traces, found {len(TRACES)}"


@pytest.mark.parametrize("trace", TRACES, ids=lambda t: t["id"])
def test_golden_trace(trace: dict[str, Any]) -> None:
    state = _build_state(trace["state"])
    decision = decide(state)
    assert decision.action == trace["expected_action"], (
        f"Trace {trace['id']}: expected {trace['expected_action']}, "
        f"got {decision.action}. Reason: {decision.reason}"
    )
    if "expected_modality" in trace:
        assert decision.suggested_modality == trace["expected_modality"]


def test_golden_trace_accuracy_is_100_percent() -> None:
    """CI gate: every trace must pass for the build to be green."""
    failures = []
    for trace in TRACES:
        state = _build_state(trace["state"])
        decision = decide(state)
        if decision.action != trace["expected_action"]:
            failures.append(
                f"{trace['id']}: expected {trace['expected_action']}, got {decision.action}"
            )
    assert not failures, "Policy accuracy below 100%:\n" + "\n".join(failures)
