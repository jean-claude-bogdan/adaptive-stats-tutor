"""Two-tier Claude routing for tutor content generation.

Haiku is used by default (cost-efficient).
Sonnet is used when learner confidence < CONFIDENCE_LOW (needs richer explanation).
All responses are validated as JSON; a safe fallback is returned on parse failure.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from src.policy import CONFIDENCE_LOW

logger = logging.getLogger(__name__)
_dotenv_loaded = False


def _ensure_env_loaded() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True

# Model IDs
_HAIKU = "claude-haiku-4-5-20251001"
_SONNET = "claude-sonnet-4-6"

_MAX_TOKENS = 1024

_VALID_ACTIONS = {"explained", "asked_question", "gave_feedback"}


def _get_client() -> anthropic.Anthropic:
    _ensure_env_loaded()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise OSError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key)


def _select_model(learner_confidence: float | None) -> str:
    """Return Sonnet for low-confidence learners, Haiku otherwise."""
    if learner_confidence is not None and learner_confidence < CONFIDENCE_LOW:
        return _SONNET
    return _HAIKU


def _validate_response(data: dict[str, Any]) -> bool:
    """Return True if data matches the required response schema."""
    if not isinstance(data.get("message"), str) or not data["message"].strip():
        return False
    if data.get("action_taken") not in _VALID_ACTIONS:
        return False
    confidence_prompt = data.get("confidence_prompt")
    if confidence_prompt is not None and not isinstance(confidence_prompt, str):
        return False
    return True


def _fallback_response(action: str = "explained") -> dict[str, Any]:
    """Safe response returned when the LLM output cannot be parsed."""
    return {
        "message": (
            "I'm having a little trouble right now. "
            "Let's try that again — could you re-read the question and let me know your answer?"
        ),
        "action_taken": action,
        "confidence_prompt": None,
    }


def call_llm(
    system_prompt: str,
    user_prompt: str,
    learner_confidence: float | None = None,
) -> dict[str, Any]:
    """Call the appropriate Claude model and return a validated response dict.

    Args:
        system_prompt: The rendered system/instruction prompt.
        user_prompt: The rendered user-facing prompt (explain / question / feedback).
        learner_confidence: Last reported learner confidence (0.0–1.0). Drives model selection.

    Returns:
        Validated dict with keys: message, action_taken, confidence_prompt.
    """
    model = _select_model(learner_confidence)
    logger.debug("LLM call | model=%s | confidence=%s", model, learner_confidence)

    try:
        client = _get_client()
        response = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except (anthropic.APIError, OSError) as exc:
        logger.error("LLM call failed: %s", exc)
        return _fallback_response()

    raw_text = ""
    for block in response.content:
        if isinstance(block, anthropic.types.TextBlock):
            raw_text = block.text.strip()
            break

    # Strip markdown code fences if the model wrapped JSON in ```json ... ```
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines if not line.startswith("```")
        ).strip()

    try:
        data: dict[str, Any] = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON: %r", raw_text[:200])
        return _fallback_response()

    if not _validate_response(data):
        logger.warning("LLM response failed schema validation: %r", data)
        return _fallback_response()

    return data
