"""Load prompt templates from Markdown files at runtime."""

from __future__ import annotations

import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Return raw Markdown content for the named prompt template."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: object) -> str:
    """Load a template and substitute {{ var }} placeholders with kwargs values."""
    raw = load_prompt(name)
    for key, value in kwargs.items():
        raw = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), raw)
    return raw
