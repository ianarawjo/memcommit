"""Capture collapsed and expanded Status Help at wide and compact sizes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-status-help-20260816"
BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.ROOT = ROOT
BASE.OUT = OUT


def _close(child: object) -> None:
    child.send("q")
    child.expect(BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _verify_stream(raw: str, *, rows: int, columns: int) -> None:
    assert f"{rows} {columns}" in raw
    assert re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None


def _capture_wide(executable: str) -> None:
    BASE.COLUMNS = 180
    BASE.ROWS = 52
    child, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(child, seconds=0.8)
    collapsed = BASE._snapshot(recorder, "01-wide-collapsed")
    assert "relationships, and latest checkpoints" in collapsed
    assert "which operations were recently applied" in collapsed

    child.send("\x1b[C")
    BASE._pump(child, seconds=0.5)
    expanded = BASE._snapshot(recorder, "02-wide-expanded")
    assert "Current Context state + history" in expanded
    assert "EFFECT    · Read-only" in expanded
    assert "mem status --recursive" in expanded
    _verify_stream(recorder.getvalue(), rows=52, columns=180)
    _close(child)


def _capture_compact(executable: str) -> None:
    BASE.COLUMNS = 100
    BASE.ROWS = 30
    child, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(child, seconds=0.8)
    child.send("\x1b[B")
    BASE._pump(child, seconds=0.5)
    collapsed = BASE._snapshot(recorder, "03-compact-collapsed")
    assert "relationships, and latest checkpoints" in collapsed
    assert "which operations were recently applied" in collapsed

    child.send("\x1b[A")
    child.send("\x1b[C")
    BASE._pump(child, seconds=0.5)
    expanded = BASE._snapshot(recorder, "04-compact-expanded")
    assert "Current Context state + history" in expanded
    assert "EFFECT    · Read-only" in expanded

    child.send("\x1b[B" * 3)
    BASE._pump(child, seconds=0.5)
    forms = BASE._snapshot(recorder, "05-compact-forms")
    assert "mem status --recursive" in forms
    _verify_stream(recorder.getvalue(), rows=30, columns=100)
    _close(child)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_wide(executable)
    _capture_compact(executable)


if __name__ == "__main__":
    main()
