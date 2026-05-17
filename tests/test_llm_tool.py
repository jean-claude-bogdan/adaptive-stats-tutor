"""Unit tests for src/tools/llm_tool.py — no network calls."""

import json

from src.tools.llm_tool import (
    _HAIKU,
    _SONNET,
    _extract_json_object,
    _fallback_response,
    _select_model,
    _validate_response,
)


def test_select_model_default_is_haiku() -> None:
    assert _select_model(None) == _HAIKU
    assert _select_model(0.90) == _HAIKU


def test_select_model_low_confidence_escalates_to_sonnet() -> None:
    assert _select_model(0.30) == _SONNET


def test_validate_response_accepts_valid_payload() -> None:
    payload = {"message": "Hello", "action_taken": "explained", "confidence_prompt": None}
    assert _validate_response(payload)


def test_validate_response_rejects_empty_message() -> None:
    assert not _validate_response(
        {"message": "", "action_taken": "explained", "confidence_prompt": None}
    )


def test_validate_response_rejects_unknown_action() -> None:
    assert not _validate_response(
        {"message": "x", "action_taken": "freestyled", "confidence_prompt": None}
    )


def test_validate_response_allows_string_confidence_prompt() -> None:
    payload = {"message": "x", "action_taken": "gave_feedback", "confidence_prompt": "Rate 0-10"}
    assert _validate_response(payload)


def test_fallback_response_is_self_validating() -> None:
    fb = _fallback_response()
    assert _validate_response(fb)
    assert fb["action_taken"] in {"explained", "asked_question", "gave_feedback"}


# ---------- JSON extraction ------------------------------------------------


def test_extract_json_handles_plain_object() -> None:
    raw = '{"message": "hello", "action_taken": "explained"}'
    assert json.loads(_extract_json_object(raw) or "") == {
        "message": "hello",
        "action_taken": "explained",
    }


def test_extract_json_handles_code_fenced_object() -> None:
    raw = '```json\n{"message": "x", "action_taken": "explained"}\n```'
    extracted = _extract_json_object(raw)
    assert extracted is not None
    assert json.loads(extracted)["message"] == "x"


def test_extract_json_preserves_code_blocks_inside_message() -> None:
    """Regression: the old line-stripper corrupted JSON whose message contained ``` fences."""
    raw = (
        '{"message": "Try: ```python\\nprint(1)\\n```", '
        '"action_taken": "explained", "confidence_prompt": null}'
    )
    extracted = _extract_json_object(raw)
    assert extracted is not None
    data = json.loads(extracted)
    assert "print(1)" in data["message"]


def test_extract_json_handles_leading_prose() -> None:
    raw = 'Sure! Here is my response:\n{"message": "ok", "action_taken": "explained"}'
    extracted = _extract_json_object(raw)
    assert extracted is not None
    assert json.loads(extracted)["message"] == "ok"


def test_extract_json_returns_none_when_absent() -> None:
    assert _extract_json_object("no json here") is None
