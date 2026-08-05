"""Contracts for shared blocking-command progress feedback."""
from __future__ import annotations

import io

import pytest

from memcommit.commands.command_progress import (
    CommandProgress,
    busy_suffix,
    render_progress_line,
)


class TTYBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_shared_busy_suffix_cycles_deterministically():
    assert [busy_suffix(index) for index in range(5)] == [
        ".",
        "..",
        "…",
        ".",
        "..",
    ]


def test_progress_line_reports_honest_stage_elapsed_time_and_escapes_controls():
    line = render_progress_line(
        "compare\nspoofed",
        "analyzing\rrelations",
        step=2,
        total=3,
        elapsed_seconds=18.9,
        frame_index=2,
    )

    assert line == (
        "MEM COMPARE\\nSPOOFED · 2/3 · "
        "ANALYZING\\rRELATIONS … · 18s"
    )


@pytest.mark.parametrize("step,total", [(0, 1), (2, 1), (1, 0)])
def test_progress_line_rejects_impossible_steps(step, total):
    with pytest.raises(ValueError):
        render_progress_line(
            "FIND",
            "ranking",
            step=step,
            total=total,
            elapsed_seconds=0,
            frame_index=0,
        )


def test_command_progress_renders_updates_and_clears_one_tty_line():
    stream = TTYBuffer()

    with CommandProgress(
        "find",
        "connecting provider",
        total=2,
        stream=stream,
        interval=60,
    ) as progress:
        progress.update("ranking candidates", step=2)

    output = stream.getvalue()
    assert "MEM FIND · 1/2 · CONNECTING PROVIDER . · 0s" in output
    assert "MEM FIND · 2/2 · RANKING CANDIDATES . · 0s" in output
    assert output.endswith("\r")


def test_command_progress_is_silent_for_non_tty_streams():
    stream = io.StringIO()

    with CommandProgress("find", "ranking", total=1, stream=stream):
        pass

    assert stream.getvalue() == ""
