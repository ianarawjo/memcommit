"""Capture Provider's PARTIAL Help maturity in a real color PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = 180
_BASE.ROWS = 52


def _close(child: pexpect.spawn) -> None:
    child.send("q")
    child.expect(pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)

    # Reach the final Help category, settle the viewport at its last row, then
    # return to Provider. This matches keyboard navigation instead of relying
    # on a capture-only cursor shortcut.
    child.send("\t" * 10)
    _BASE._pump(child, seconds=0.2)
    child.send("\x1b[B" * 5)
    _BASE._pump(child, seconds=0.2)
    child.send("\x1b[A" * 4)
    _BASE._pump(child, seconds=0.55)

    row = _BASE._snapshot(recorder, "01-provider-partial-row")
    normalized_row = " ".join(row.split())
    assert "mem provider" in normalized_row
    assert "[PARTIAL]" in normalized_row
    assert "SYSTEM & STUDY TOOLS" in normalized_row

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.7)
    expanded = _BASE._snapshot(recorder, "02-provider-partial-expanded")
    normalized_expanded = " ".join(expanded.split())
    assert "mem provider" in normalized_expanded
    assert "[PARTIAL]" in normalized_expanded
    assert "PROVIDER ACTIONS" in normalized_expanded
    assert "without opening an editor" in normalized_expanded
    _BASE._assert_color(recorder.getvalue())

    _close(child)


if __name__ == "__main__":
    main()
