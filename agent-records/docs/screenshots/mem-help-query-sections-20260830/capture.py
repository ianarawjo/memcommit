"""Capture Query and Summary/Comparison sections in the real Help browser."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-query-sections-20260830"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT
    / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _visible_text(recorder: object) -> str:
    return "\n".join(_BASE._screen(recorder.getvalue()).display)


def _assert_focused_command(recorder: object, command: str) -> None:
    screen = _BASE._screen(recorder.getvalue())
    row = next(index for index, line in enumerate(screen.display) if command in line)
    start = screen.display[row].index(command)
    assert any(
        screen.buffer[row][column].bg != "default"
        for column in range(start, start + len(command))
    )


def _assert_neutral_section(recorder: object, label: str) -> None:
    screen = _BASE._screen(recorder.getvalue())
    row = next(index for index, line in enumerate(screen.display) if label in line)
    start = screen.display[row].index(label)
    assert all(
        screen.buffer[row][column].bg == "default"
        for column in range(start, start + len(label))
    )


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")

    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.typescript", "*.txt", "*.png"):
        for path in OUT.glob(suffix):
            path.unlink()

    recorder = _BASE._StreamRecorder()
    command = (
        f"stty rows {ROWS} cols {COLUMNS}; stty size; "
        f"exec {executable} help"
    )
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=10,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    try:
        _BASE._wait_for_visible(child, recorder, "CORE CONCEPTS")
        _BASE._wait_for_visible(child, recorder, "BROWSE & NAVIGATE")
        _BASE._snapshot(recorder, "01-by-kind-entry")

        child.send("\t" * 2)
        _BASE._wait_for_visible(child, recorder, "┏ SEARCH & EXPLAIN ")
        _BASE._wait_for_visible(child, recorder, "── QUERY ")
        assert "summarization, and comparison" in _visible_text(recorder)
        _assert_focused_command(recorder, "mem find")
        _assert_neutral_section(recorder, "QUERY")
        _BASE._snapshot(recorder, "02-query-focused")

        child.send("\x1b[B" * 3)
        _BASE._wait_for_visible(child, recorder, "── SUMMARY & COMPARISON ")
        _assert_focused_command(recorder, "mem summarize")
        _assert_neutral_section(recorder, "QUERY")
        _assert_neutral_section(recorder, "SUMMARY & COMPARISON")
        _BASE._snapshot(recorder, "03-summary-focused")

        child.send("\x1b[B")
        _BASE._pump(child, seconds=0.5)
        _assert_focused_command(recorder, "mem compare")
        _BASE._snapshot(recorder, "04-compare-focused")

        child.send("\x1b[C")
        _BASE._wait_for_visible(
            child,
            recorder,
            "Context <-> Context -> comparison report",
        )
        _BASE._wait_for_visible(
            child,
            recorder,
            "FORM 1 · mem compare",
        )
        assert "▾ mem compare" in _visible_text(recorder)
        _BASE._snapshot(recorder, "05-compare-expanded")

        child.send("\t" * 3)
        _BASE._wait_for_visible(child, recorder, "┏ CHECK & REVIEW ")
        visible = _visible_text(recorder)
        assert "Check compatibility, quality, or expected impact." in visible
        _assert_focused_command(recorder, "mem find-")
        _BASE._snapshot(recorder, "06-check-review-focused")

        raw = recorder.getvalue()
        assert f"{ROWS} {COLUMNS}" in raw
        assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
        assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None

        child.send("q")
        child.expect(pexpect.EOF, timeout=5)
        child.close()
        assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    finally:
        if child.isalive():
            child.close(force=True)


if __name__ == "__main__":
    main()
