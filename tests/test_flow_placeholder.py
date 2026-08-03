"""Flow Circular terminal placeholder rendering."""

from __future__ import annotations

import pytest

import memcommit.flow_placeholder as flow_placeholder
from memcommit.flow_placeholder import (
    FlowPlaceholderError,
    render_flow_circular_placeholder,
)


def test_flow_placeholder_uses_only_word_lengths_and_braille_pixels():
    first = render_flow_circular_placeholder("cat doors")
    second = render_flow_circular_placeholder("any words")

    assert first == second
    assert len(first) == 1
    rendered_words = first[0].split(" ")
    assert [len(word) for word in rendered_words] == [3, 5]
    assert all(
        0x2801 <= ord(character) <= 0x28FF
        for word in rendered_words
        for character in word
    )
    assert "cat" not in first[0]
    assert "x" not in first[0]


def test_flow_placeholder_wraps_without_changing_disclosed_lengths():
    lines = render_flow_circular_placeholder(
        "abcdefghij klmno",
        max_columns=5,
    )

    assert [len(line) for line in lines] == [5, 5, 5]
    assert all(" " not in line for line in lines)


def test_flow_placeholder_fails_closed_when_bundled_font_is_missing(
    tmp_path,
    monkeypatch,
):
    flow_placeholder._flow_font.cache_clear()
    flow_placeholder._render_word.cache_clear()
    monkeypatch.setattr(
        flow_placeholder,
        "_FONT_PATH",
        tmp_path / "missing.ttf",
    )

    with pytest.raises(FlowPlaceholderError, match="font is unavailable"):
        render_flow_circular_placeholder("private source")

    flow_placeholder._flow_font.cache_clear()
    flow_placeholder._render_word.cache_clear()
