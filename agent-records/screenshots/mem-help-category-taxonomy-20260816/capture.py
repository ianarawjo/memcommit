"""Capture the intent-based Help category taxonomy at wide and compact sizes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-category-taxonomy-20260816"

_BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
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


def _capture_sequence(executable: str, *, compact: bool) -> None:
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
    top = _BASE._snapshot(recorder, f"01-{prefix}-top")
    assert "BROWSE & NAVIGATE" in top
    assert "NO LLM · Inspect the current location" in top
    if not compact:
        assert "CREATE, COPY & CONNECT" in top

    child.send("\x1b[C")
    _BASE._pump(child, seconds=0.5)
    expanded = _BASE._snapshot(recorder, f"01a-{prefix}-status-expanded")
    assert "Current Context state + history" in expanded
    assert "DETERMINISTIC" in expanded
    assert "EFFECT    · Read-only" in expanded
    if compact:
        child.send("\x1b[B" * 3)
        _BASE._pump(child, seconds=0.5)
        forms = _BASE._snapshot(recorder, "01aa-compact-status-forms")
        assert "mem status --recursive" in forms
        child.send("\x1b[A" * 3)
        _BASE._pump(child, seconds=0.3)
    else:
        assert "mem status --recursive" in expanded
    child.send("\x1b[D")
    _BASE._pump(child, seconds=0.4)

    if compact:
        # The 30-row entry viewport ends on the first Status summary row.
        # Move one row so the complete wrapped Summary and USE WHEN copy are
        # recorded rather than treating a clipped entry state as verification.
        child.send("\x1b[B")
        _BASE._pump(child, seconds=0.5)
        status = _BASE._snapshot(recorder, "01b-compact-status")
        assert "relationships, and latest checkpoints" in status
        assert "which operations were recently applied" in status

    child.send("\t" * 4)
    _BASE._pump(child, seconds=0.8)
    middle = _BASE._snapshot(recorder, f"02-{prefix}-middle")
    assert "SEMANTIC TRANSFORMATIONS" in middle
    assert "Uses LLM semantic analysis" in middle

    child.send("\t" * 6)
    _BASE._pump(child, seconds=0.8)
    bottom = _BASE._snapshot(recorder, f"03-{prefix}-bottom")
    assert "PROFILES" in bottom
    assert "SHARING & PROTECTION" in bottom
    assert "SYSTEM & STUDY TOOLS" in bottom
    assert "Configure MemCommit and prepare or run study" in bottom
    assert "MIXED · Configure MemCommit" not in bottom

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

    _capture_sequence(executable, compact=False)
    _capture_sequence(executable, compact=True)


if __name__ == "__main__":
    main()
