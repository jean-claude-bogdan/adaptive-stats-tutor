"""Unit tests for src/tools/llm_tool.py — no network calls."""

from src.tools.llm_tool import (
    _HAIKU,
    _SONNET,
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
