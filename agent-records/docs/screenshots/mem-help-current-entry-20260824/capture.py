"""Capture the current ``mem help`` BY KIND entry screen in a real color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import re
import shutil

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-current-entry-20260824"
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
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


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")

    OUT.mkdir(parents=True, exist_ok=True)
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
