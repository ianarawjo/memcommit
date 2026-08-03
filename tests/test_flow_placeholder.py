"""Flow Circular terminal placeholder rendering."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import textwrap

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


def test_missing_pillow_does_not_disable_the_whole_cli():
    script = textwrap.dedent(
        """
        import importlib.abc
        import sys

        class BlockPillow(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "PIL" or fullname.startswith("PIL."):
                    raise ImportError("Pillow intentionally unavailable")
                return None

        sys.meta_path.insert(0, BlockPillow())

        from typer.testing import CliRunner
        from memcommit.cli import app
        from memcommit.flow_placeholder import (
            FlowPlaceholderError,
            render_flow_circular_placeholder,
        )

        result = CliRunner(mix_stderr=False).invoke(app, ["profile", "--help"])
        assert result.exit_code == 0, result.output

        try:
            render_flow_circular_placeholder("private source")
        except FlowPlaceholderError as error:
            assert "requires Pillow" in str(error)
            assert isinstance(error.__cause__, ImportError)
        else:
            raise AssertionError("renderer did not fail closed without Pillow")
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
