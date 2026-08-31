"""Capture the catalog-family Help topology in a real 180x52 PTY."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "agent-records/docs/screenshots/mem-help-operation-family-relocation-20260831"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-help-command-naming-20260813/capture.py"
_SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.ROOT = ROOT
_BASE.OUT = OUT
_BASE.COLUMNS = 180
_BASE.ROWS = 52


def _close(child: object) -> None:
    child.send("q")
    child.expect(_BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def _capture_family(
    executable: str,
    *,
    stem: str,
    tabs: int,
    downs: int = 0,
    expected: tuple[str, ...],
) -> None:
    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    if tabs:
        child.send("\t" * tabs)
        _BASE._pump(child, seconds=0.8)
    if downs:
        child.send("\x1b[B" * downs)
        _BASE._pump(child, seconds=0.8)
    plain = _BASE._snapshot(recorder, stem)
    for token in expected:
        assert token in plain
    _BASE._assert_color(recorder.getvalue())
    _close(child)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    _capture_family(
        executable,
        stem="01-search-explain",
        tabs=2,
        downs=3,
        expected=("SEARCH & EXPLAIN", "RETRIEVE & ANSWER", "SYNTHESIZE"),
    )
    _capture_family(
        executable,
        stem="02-direct-changes",
        tabs=3,
        downs=6,
        expected=("DIRECT CHANGES", "mem edit", "mem merge"),
    )
    _capture_family(
        executable,
        stem="03-semantic-updates",
        tabs=4,
        downs=5,
        expected=("SEMANTIC UPDATES", "FOUNDATION", "DERIVE", "CURATE & INTEGRATE"),
    )
    _capture_family(
        executable,
        stem="04-translation",
        tabs=5,
        expected=("TRANSLATION", "mem translate"),
    )
    _capture_family(
        executable,
        stem="05-quality-resolution",
        tabs=6,
        downs=8,
        expected=("QUALITY & RESOLUTION", "DIAGNOSE", "REPAIR", "VALIDATE"),
    )
    _capture_family(
        executable,
        stem="06-operation-lifecycle",
        tabs=7,
        expected=("OPERATION LIFECYCLE", "mem impact", "mem review"),
    )
    _capture_family(
        executable,
        stem="07-history-recovery",
        tabs=9,
        downs=4,
        expected=("HISTORY & RECOVERY", "INSPECTION", "RECOVERY"),
    )

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    child.send("\x1b[Z\x1b[C")
    _BASE._pump(child, seconds=0.8)
    plain = _BASE._snapshot(recorder, "08-a-z-flat")
    assert "A–Z" in plain
    assert "── RETRIEVE & ANSWER" not in plain
    assert "── FOUNDATION" not in plain
    _BASE._assert_color(recorder.getvalue())
    _close(child)


if __name__ == "__main__":
    main()
