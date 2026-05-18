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

import re

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

# Model IDs — overridable via env so we can flip versions without a deploy.
_HAIKU = os.environ.get("TUTOR_HAIKU_MODEL", "claude-haiku-4-5-20251001")
_SONNET = os.environ.get("TUTOR_SONNET_MODEL", "claude-sonnet-4-6")

_MAX_TOKENS = 1024
_MAX_RETRIES = 1  # one retry on transient APIError before falling back

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


def _extract_json_object(raw: str) -> str | None:
    """Pull the outermost JSON object out of an LLM response.

    The old implementation dropped every line starting with backticks, which
    corrupted any JSON whose `message` field happened to contain a code block.
    This grabs the first balanced ``{ ... }`` span instead.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return match.group(0) if match else None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    learner_confidence: float | None = None,
) -> dict[str, Any]:
    """Call the appropriate Claude model and return a validated response dict.

    Retries once on transient APIError before returning the safe fallback.
    """
    model = _select_model(learner_confidence)
    logger.debug("LLM call | model=%s | confidence=%s", model, learner_confidence)

    last_exc: Exception | None = None
    response = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            client = _get_client()
            response = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            break
        except anthropic.APIError as exc:
            last_exc = exc
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, exc)
        except OSError as exc:
            # Missing API key etc — no point retrying.
            logger.error("LLM call failed (no retry): %s", exc)
            return _fallback_response()
    if response is None:
        logger.error("LLM call failed after retries: %s", last_exc)
        return _fallback_response()

    raw_text = ""
    for block in response.content:
        if isinstance(block, anthropic.types.TextBlock):
            raw_text = block.text.strip()
            break

    # Pull out the JSON object — robust to leading/trailing prose or code fences.
    json_blob = _extract_json_object(raw_text)
    if json_blob is None:
        logger.warning("LLM returned no JSON object: %r", raw_text[:200])
        return _fallback_response()

    try:
        data: dict[str, Any] = json.loads(json_blob)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON: %r", json_blob[:200])
        return _fallback_response()

    if not _validate_response(data):
        logger.warning("LLM response failed schema validation: %r", data)
        return _fallback_response()

    return data
