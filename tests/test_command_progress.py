"""Contracts for shared blocking-command progress feedback."""
from __future__ import annotations

import io

import pytest

from memcommit.adapters.console.terminal.components.progress import (
    CommandProgress,
    busy_suffix,
    progressing_provider_factory,
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


def test_command_progress_can_start_lazily_and_close_without_starting():
    stream = TTYBuffer()
    progress = CommandProgress(
        "update",
        "connecting provider",
        total=2,
        stream=stream,
        interval=60,
    )

    progress.close()

    assert stream.getvalue() == ""


def test_progressing_provider_factory_starts_only_when_provider_is_requested(
    monkeypatch,
):
    stream = TTYBuffer()

    def build_progress(operation, stage, *, total):
        return CommandProgress(
            operation,
            stage,
            total=total,
            stream=stream,
            interval=60,
        )

    monkeypatch.setattr(
        "memcommit.adapters.console.terminal.components.progress.CommandProgress",
        build_progress,
    )
    calls = []
    with progressing_provider_factory(
        "update",
        "planning changes",
        lambda: calls.append("connected") or object(),
    ):
        pass
    assert stream.getvalue() == ""
    assert calls == []

    with progressing_provider_factory(
        "update",
        "planning changes",
        lambda: calls.append("connected") or object(),
    ) as connect:
        connect()

    output = stream.getvalue()
    assert calls == ["connected"]
    assert "MEM UPDATE · 1/2 · CONNECTING PROVIDER . · 0s" in output
    assert "MEM UPDATE · 2/2 · PLANNING CHANGES . · 0s" in output


def test_progressing_provider_factory_spans_repeated_provider_requests(
    monkeypatch,
):
    stream = TTYBuffer()

    def build_progress(operation, stage, *, total):
        return CommandProgress(
            operation,
            stage,
            total=total,
            stream=stream,
            interval=60,
        )

    monkeypatch.setattr(
        "memcommit.adapters.console.terminal.components.progress.CommandProgress",
        build_progress,
    )
    calls = []
    with progressing_provider_factory(
        "atomize",
        "normalizing atomized output",
        lambda: calls.append("connected") or object(),
    ) as connect:
        connect()
        connect()
        connect()

    output = stream.getvalue()
    assert calls == ["connected", "connected", "connected"]
    assert output.count("NORMALIZING ATOMIZED OUTPUT") == 3
    assert output.endswith("\r")
