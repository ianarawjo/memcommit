"""Capture Add's literal-content and copy-or-link Help boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-add-copy-or-link-20260816"

_BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _capture(executable: str, *, compact: bool) -> None:
    if compact:
        _BASE.COLUMNS = 100
        _BASE.ROWS = 30
        prefix = "compact"
    else:
        _BASE.COLUMNS = 180
        _BASE.ROWS = 52
        prefix = "wide"

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    # Move from the BY KIND selector to A-Z, enter its command surface, and
    # select the first operation. Add is first in the stable alphabetic order.
    child.send("\x1b[Z\x1b[C\t\x1b[H")
    _BASE._pump(child, seconds=0.8)
    collapsed = _BASE._snapshot(recorder, f"01-{prefix}-collapsed")
    assert "▸ mem add" in collapsed
    assert "COPY OR LINK" not in collapsed

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.8)
    expanded = _BASE._snapshot(recorder, f"02-{prefix}-expanded")
    assert "▾ mem add" in expanded
    assert "COPY OR LINK" in expanded
    assert "always stored literally as Memory content" in expanded
    assert "Branch the containing Context" in expanded
    assert "EXACT MEMORY VERSION · Use mem reference" in expanded
    assert "LIVE MEMORY · Use mem embed MEMORY" in expanded
    assert "EXISTING CONTEXT · Use mem embed" in expanded
    assert "* EXACT MEMORY VERSION" not in expanded

    raw = recorder.getvalue()
    expected_size = "30 100" if compact else "52 180"
    assert expected_size in raw
    assert _BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", raw) is not None
    assert _BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", raw) is not None
    _close(child)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    _capture(executable, compact=False)
    _capture(executable, compact=True)


if __name__ == "__main__":
    main()
