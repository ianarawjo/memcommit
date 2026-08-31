"""Capture History Inspection/Recovery sections in the real Help browser."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil

import pexpect


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-history-sections-20260830"
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
    row = next(
        index for index, line in enumerate(screen.display) if command in line
    )
    start = screen.display[row].index(command)
    assert any(
        screen.buffer[row][column].bg != "default"
        for column in range(start, start + len(command))
    )


def _assert_section_labels_are_not_focus_stops(
    recorder: object,
    labels: tuple[str, ...],
) -> None:
    screen = _BASE._screen(recorder.getvalue())
    for label in labels:
        row = next(
            index for index, line in enumerate(screen.display) if label in line
        )
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

        child.send("\t" * 7)
        _BASE._wait_for_visible(child, recorder, "┏ HISTORY & RECOVERY ")
        _BASE._wait_for_visible(child, recorder, "── INSPECTION ")
        assert "MIXED · Inspect provenance and recorded changes." in _visible_text(
            recorder
        )
        _assert_focused_command(recorder, "mem log")
        _assert_section_labels_are_not_focus_stops(recorder, ("INSPECTION",))
        _BASE._snapshot(recorder, "02-history-inspection-focused")

        child.send("\x1b[B" * 4)
        _BASE._wait_for_visible(child, recorder, "── RECOVERY ")
        _assert_focused_command(recorder, "mem checkpoint")
        _assert_section_labels_are_not_focus_stops(
            recorder,
            ("INSPECTION", "RECOVERY"),
        )
        _BASE._snapshot(recorder, "03-history-recovery-focused")

        child.send("\x1b[A" * 2)
        child.send("\x1b[C")
        _BASE._wait_for_visible(child, recorder, "Memory -> retained lineage")
        _BASE._wait_for_visible(
            child,
            recorder,
            "FORM 2 · mem trace [memory_selector]",
        )
        assert "▾ mem trace" in _visible_text(recorder)
        _BASE._snapshot(recorder, "04-trace-expanded")

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
