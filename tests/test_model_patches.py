"""Verify MiniMax <think>-stripping logic in isolation."""
from __future__ import annotations

from signalbags.adapters.model_patches import strip_think


def test_strip_basic_think_block():
    raw = "<think>I should consider...</think>## 判断\n内容"
    assert strip_think(raw) == "## 判断\n内容"


def test_strip_multiline_think():
    raw = (
        "<think>\nstep 1\nstep 2\n"
        "nested observations</think>\n\n"
        "## 实际回复"
    )
    assert strip_think(raw).startswith("## 实际回复")


def test_noop_when_no_think_tag():
    raw = "plain assistant output without reasoning"
    assert strip_think(raw) == raw


def test_handles_none_and_empty():
    assert strip_think(None) == ""
    assert strip_think("") == ""


def test_strips_multiple_blocks():
    raw = "<think>a</think>middle<think>b</think>tail"
    assert strip_think(raw) == "middle tail".replace(" tail", "tail")  # trailing block removed, inner preserved
    # More precise assertion:
    out = strip_think(raw)
    assert "<think>" not in out
    assert "</think>" not in out
    assert "middle" in out
    assert "tail" in out
