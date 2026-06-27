"""Two-tier Claude routing for tutor content generation.

Haiku is used by default (cost-efficient).
Sonnet is used when learner confidence < CONFIDENCE_LOW (needs richer explanation).
All responses are validated as JSON; a safe fallback is returned on parse failure.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
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


# --- No-API-key transport: route through the Claude Code CLI -----------------
# When ANTHROPIC_API_KEY is absent we shell out to `claude -p`, which uses the
# user's Claude subscription auth (set up once via `claude setup-token`). This
# lets the demo show real explanations without a billing API key.

def _claude_cli_path() -> str | None:
    """Locate the `claude` CLI executable.

    Prefer the real `claude.exe`: npm's `claude.cmd` is a batch shim that
    mangles multi-line / special-char arguments on Windows, corrupting the
    prompt. Honors TUTOR_CLAUDE_BIN first."""
    override = os.environ.get("TUTOR_CLAUDE_BIN")
    if override:
        return override
    candidates = [
        os.path.expandvars(
            r"%APPDATA%\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
        ),
        shutil.which("claude.exe"),
        shutil.which("claude"),
        os.path.expandvars(r"%APPDATA%\npm\claude.cmd"),
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def _cli_model_alias(model: str) -> str:
    """Map a full model id to a CLI alias the subscription accepts."""
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    if "opus" in m:
        return "opus"
    return model


def _call_via_cli(
    system_prompt: str, user_prompt: str, model: str
) -> dict[str, Any]:
    """Generate a validated response via the Claude Code CLI (subscription auth).

    Returns the safe fallback on any error (CLI missing, not logged in, timeout,
    unparseable output)."""
    claude_bin = _claude_cli_path()
    if not claude_bin:
        logger.error(
            "claude CLI not found; install @anthropic-ai/claude-code or set TUTOR_CLAUDE_BIN"
        )
        return _fallback_response()

    system = (
        f"{system_prompt}\n\n"
        "Respond with ONLY the JSON object specified above. No prose, no code fences."
    )
    cmd = [
        claude_bin,
        "-p",
        user_prompt,
        "--system-prompt",
        system,
        "--model",
        _cli_model_alias(model),
        "--output-format",
        "json",
        "--strict-mcp-config",  # load no MCP servers -> fast, side-effect-free
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",   # claude.exe emits UTF-8; Windows would else use cp1252
            errors="replace",
            timeout=120,
            cwd=tempfile.gettempdir(),  # neutral cwd: skip project CLAUDE.md
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.error("claude CLI call failed: %s", exc)
        return _fallback_response()

    if proc.returncode != 0:
        logger.error("claude CLI exited %d: %s", proc.returncode, (proc.stderr or "")[:300])
        return _fallback_response()

    # `--output-format json` wraps the model text as {"result": "...", ...}.
    text = proc.stdout
    try:
        outer = json.loads(proc.stdout)
        if isinstance(outer, dict):
            if outer.get("is_error"):
                logger.error("claude CLI returned error: %s", str(outer.get("result"))[:300])
                return _fallback_response()
            text = outer.get("result", proc.stdout)
    except json.JSONDecodeError:
        pass  # treat stdout as raw model text

    json_blob = _extract_json_object(text)
    if json_blob is None:
        logger.warning("claude CLI returned no JSON object: %r", text[:200])
        return _fallback_response()
    try:
        data: dict[str, Any] = json.loads(json_blob)
    except json.JSONDecodeError:
        logger.warning("claude CLI returned invalid JSON: %r", json_blob[:200])
        return _fallback_response()
    if not _validate_response(data):
        logger.warning("claude CLI response failed schema validation: %r", data)
        return _fallback_response()
    return data


# --- No-API-key transport #2: Google Gemini REST API -------------------------
# Fast (~2-5s/turn) real LLM text via a Gemini key — no Anthropic key and no
# CLI cold-start. JSON mode returns the tutor schema directly.

def _gemini_model_for(learner_confidence: float | None) -> str:
    """Flash by default; escalate to Pro for struggling learners (mirrors the
    Haiku/Sonnet two-tier routing)."""
    flash = os.environ.get("TUTOR_GEMINI_MODEL", "gemini-2.5-flash")
    pro = os.environ.get("TUTOR_GEMINI_MODEL_STRONG", "gemini-2.5-pro")
    if learner_confidence is not None and learner_confidence < CONFIDENCE_LOW:
        return pro
    return flash


def _call_via_gemini(
    system_prompt: str, user_prompt: str, learner_confidence: float | None
) -> dict[str, Any]:
    """Generate a validated response via the Google Gemini REST API."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY / GOOGLE_API_KEY not set")
        return _fallback_response()

    model = _gemini_model_for(learner_confidence)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    gen_config: dict[str, Any] = {
        "temperature": 0.7,
        "maxOutputTokens": 4096,  # generous headroom so JSON is never truncated
        "responseMimeType": "application/json",
    }
    # Disable "thinking" on Flash: it silently consumed the output budget and
    # truncated the JSON. Pro requires some thinking, so only gate Flash here.
    if "flash" in model:
        gen_config["thinkingConfig"] = {"thinkingBudget": 0}
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": gen_config,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Gemini call failed: %s", exc)
        return _fallback_response()
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned a non-JSON envelope: %s", exc)
        return _fallback_response()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Gemini returned no text: %r", str(data)[:300])
        return _fallback_response()

    json_blob = _extract_json_object(text)
    if json_blob is None:
        logger.warning("Gemini returned no JSON object: %r", text[:200])
        return _fallback_response()
    try:
        result: dict[str, Any] = json.loads(json_blob)
    except json.JSONDecodeError:
        logger.warning("Gemini returned invalid JSON: %r", json_blob[:200])
        return _fallback_response()
    if not _validate_response(result):
        logger.warning("Gemini response failed schema validation: %r", result)
        return _fallback_response()
    return result


# --- No-API-key transport #3: offline content responder ---------------------
# Generates coherent, topic-specific tutor text straight from the vetted content
# already embedded in the rendered prompt (worked examples, question text,
# correct answers). No network, no auth — lets the prototype run in a browser
# with zero setup. The app surfaces the 💡 reason line and confidence slider
# itself, so we only need a sensible `message` + a valid `action_taken`.

def _section_after(prompt: str, header: str) -> str:
    """Return the text under a markdown `header`, up to the next section marker."""
    idx = prompt.find(header)
    if idx == -1:
        return ""
    rest = prompt[idx + len(header):]
    end = len(rest)
    for marker in ("\n## ", "\n{%"):
        m = rest.find(marker)
        if m != -1:
            end = min(end, m)
    return rest[:end].strip()


def _offline_response(user_prompt: str) -> dict[str, Any]:
    """Build a content-grounded response without any LLM call."""
    p = user_prompt

    if "Explain the concept of" in p:
        m = re.search(r"Explain the concept of \*\*(.+?)\*\*", p)
        kc = m.group(1) if m else "this topic"
        et_match = re.search(r"This is a (first_introduction|re_explain|light_re_explain)", p)
        et = et_match.group(1) if et_match else "first_introduction"
        worked = _section_after(p, "## Worked example to draw from")
        if et == "light_re_explain":
            first_line = worked.splitlines()[0] if worked else ""
            msg = (
                f"Quick recap on {kc}: keep the core idea in mind. {first_line}\n\n"
                "Ready to try another question?"
            )
        elif et == "re_explain":
            msg = (
                f"No worries — {kc} trips up a lot of people. Let's take it from a "
                f"different angle and walk through an example together:\n\n{worked}\n\n"
                "Take your time — you've got this."
            )
        else:  # first_introduction
            msg = (
                f"Let's get started with {kc}. Here's the idea, walked through with a "
                f"concrete example:\n\n{worked}\n\n"
                "Does that make sense? When you're ready, I'll give you a practice problem."
            )
        return {"message": msg, "action_taken": "explained", "confidence_prompt": None}

    if "Present a practice question" in p:
        mod_match = re.search(r"Modality:\s*(\w+)", p)
        modality = mod_match.group(1) if mod_match else "free_response"
        question = _section_after(p, "## Question text")
        if modality == "worked_example":
            msg = (
                f"Let's walk through this one together, step by step:\n\n{question}\n\n"
                "Does this approach make sense? Let me know when you're ready for a "
                "practice problem."
            )
            return {"message": msg, "action_taken": "explained", "confidence_prompt": None}
        msg = (
            f"Here's a practice question for you:\n\n{question}\n\n"
            "Take your time — show your working if you'd like, and there's no penalty "
            "for trying."
        )
        return {"message": msg, "action_taken": "asked_question", "confidence_prompt": None}

    if "Give the learner feedback" in p:
        res_match = re.search(r"Result:\s*(\w+)", p)
        result = res_match.group(1) if res_match else "incorrect"
        ca_match = re.search(r"Correct answer:\s*(.+)", p)
        correct_answer = ca_match.group(1).strip() if ca_match else ""
        worked = _section_after(p, "## Worked example")
        if result == "correct":
            msg = (
                "Nice work — that's exactly right, and you applied the right approach "
                "rather than guessing. Let's keep the momentum going."
            )
        elif result == "partial":
            msg = (
                f"You're on the right track. The full answer is {correct_answer}. "
                f"Here's the complete approach:\n\n{worked}"
            )
        else:
            msg = (
                f"Not quite — let's look at this again. The answer we're after is "
                f"{correct_answer}. Here's how to get there:\n\n{worked}\n\n"
                "Give the next one a try when you're ready."
            )
        return {"message": msg, "action_taken": "gave_feedback", "confidence_prompt": None}

    # Unknown template — keep the session moving rather than crashing.
    return {
        "message": "Let's keep going — try the next step when you're ready.",
        "action_taken": "explained",
        "confidence_prompt": None,
    }


def call_llm(
    system_prompt: str,
    user_prompt: str,
    learner_confidence: float | None = None,
) -> dict[str, Any]:
    """Call the appropriate Claude model and return a validated response dict.

    Retries once on transient APIError before returning the safe fallback.
    """
    _ensure_env_loaded()
    model = _select_model(learner_confidence)
    logger.debug("LLM call | model=%s | confidence=%s", model, learner_confidence)

    # No billing API key? Pick a keyless transport.
    #   TUTOR_LLM_TRANSPORT=cli      -> Claude Code CLI (subscription auth via
    #                                   `claude setup-token`); real AI phrasing.
    #   TUTOR_LLM_TRANSPORT=offline  -> content-grounded responder (default);
    #                                   no auth, no network, runs anywhere.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        transport = os.environ.get("TUTOR_LLM_TRANSPORT", "offline").lower()
        if transport == "gemini":
            logger.info(
                "No API key — routing via Gemini (model=%s)",
                _gemini_model_for(learner_confidence),
            )
            return _call_via_gemini(system_prompt, user_prompt, learner_confidence)
        if transport == "cli":
            logger.info("No API key — routing via Claude CLI (model=%s)", model)
            return _call_via_cli(system_prompt, user_prompt, model)
        logger.info("No API key — using offline content responder")
        return _offline_response(user_prompt)

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
