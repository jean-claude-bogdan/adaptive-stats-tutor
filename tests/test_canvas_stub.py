"""Unit tests for canvas_stub.py."""

from canvas_stub import launch_from_canvas


def test_no_token_returns_dev_fixture() -> None:
    ctx = launch_from_canvas()
    assert ctx.learner_id == "dev-learner-001"
    assert ctx.is_stub is True


def test_same_token_yields_same_learner_id() -> None:
    a = launch_from_canvas("token-x")
    b = launch_from_canvas("token-x")
    assert a.learner_id == b.learner_id


def test_different_tokens_yield_different_learner_ids() -> None:
    a = launch_from_canvas("token-x")
    b = launch_from_canvas("token-y")
    assert a.learner_id != b.learner_id
