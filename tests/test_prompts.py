"""Unit tests for src/prompts/__init__.py."""

import pytest

from src.prompts import load_prompt, render_prompt


def test_all_required_templates_exist() -> None:
    for name in ["system", "explain", "question", "feedback"]:
        content = load_prompt(name)
        assert content.strip(), f"{name}.md is empty"


def test_render_prompt_substitutes_braces() -> None:
    rendered = render_prompt(
        "explain",
        kc_label="Variance",
        mastery="0.42",
        misconceptions="forgetting to square",
        explain_type="re_explain",
        worked_example="example here",
    )
    assert "Variance" in rendered
    assert "0.42" in rendered
    assert "{{" not in rendered.replace("{{ choice }}", "")  # placeholders consumed


def test_missing_template_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nonexistent_template")
