"""Capture Distill discovery in both interactive Help projections."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-distill-help-20260815"
BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.ROOT = ROOT
BASE.OUT = OUT


def _close(child) -> None:
    child.send("q")
    child.expect(BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    by_kind, by_kind_recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(by_kind, seconds=0.8)
    # CONTEXTS → MEMORIES → SEARCH & EXPLAIN → ANALYZE & TRANSFORM,
    # then audit → atomize → distill.
    by_kind.send("\t\t\t\x1b[B\x1b[B")
    BASE._pump(by_kind, seconds=0.4)
    screen = BASE._snapshot(by_kind_recorder, "01-by-kind-distill-focused")
    assert "ANALYZE & TRANSFORM" in screen and "▸ mem distill" in screen
    by_kind.send("\x1b[C")
    BASE._pump(by_kind, seconds=0.35)
    screen = BASE._snapshot(by_kind_recorder, "02-by-kind-distill-expanded")
    assert "▾ mem distill" in screen and "Case/Example Context + Goal?" in screen
    BASE._assert_color(by_kind_recorder.getvalue())
    _close(by_kind)

    az, az_recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(az, seconds=0.8)
    # First row → VIEW → A-Z → command list → Home, then add → distill.
    az.send("\x1b[Z\x1b[C\t\x1b[H" + "\x1b[B" * 14)
    BASE._pump(az, seconds=0.45)
    screen = BASE._snapshot(az_recorder, "03-a-z-distill-focused")
    assert "A–Z" in screen and "▸ mem distill" in screen
    az.send("\x1b[C")
    BASE._pump(az, seconds=0.35)
    screen = BASE._snapshot(az_recorder, "04-a-z-distill-expanded")
    assert "▾ mem distill" in screen and "FORM 1 · mem distill" in screen
    BASE._assert_color(az_recorder.getvalue())
    _close(az)

    by_kind_elaborate, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(by_kind_elaborate, seconds=0.8)
    by_kind_elaborate.send("\t\t\t" + "\x1b[B" * 3)
    BASE._pump(by_kind_elaborate, seconds=0.4)
    screen = BASE._snapshot(recorder, "05-by-kind-elaborate-focused")
    assert "ANALYZE & TRANSFORM" in screen and "▸ mem elaborate" in screen
    by_kind_elaborate.send("\x1b[C")
    BASE._pump(by_kind_elaborate, seconds=0.35)
    screen = BASE._snapshot(recorder, "06-by-kind-elaborate-expanded")
    assert "▾ mem elaborate" in screen and "suggested Case propositions" in screen
    BASE._assert_color(recorder.getvalue())
    _close(by_kind_elaborate)

    az_elaborate, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(az_elaborate, seconds=0.8)
    az_elaborate.send("\x1b[Z\x1b[C\t\x1b[H" + "\x1b[B" * 16)
    BASE._pump(az_elaborate, seconds=0.45)
    screen = BASE._snapshot(recorder, "07-a-z-elaborate-focused")
    assert "A–Z" in screen and "▸ mem elaborate" in screen
    az_elaborate.send("\x1b[C")
    BASE._pump(az_elaborate, seconds=0.35)
    screen = BASE._snapshot(recorder, "08-a-z-elaborate-expanded")
    assert "▾ mem elaborate" in screen and "FORM 1 · mem elaborate" in screen
    BASE._assert_color(recorder.getvalue())
    _close(az_elaborate)

    BASE.COLUMNS = 100
    BASE.ROWS = 30
    compact, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(compact, seconds=0.8)
    compact.send("\t\t\t" + "\x1b[B" * 2)
    BASE._pump(compact, seconds=0.4)
    screen = BASE._snapshot(recorder, "09-compact-distill-focused")
    assert "▸ mem distill" in screen and "USE WHEN:" in screen
    compact.send("\x1b[C")
    BASE._pump(compact, seconds=0.35)
    screen = BASE._snapshot(recorder, "10-compact-distill-expanded")
    assert "▾ mem distill" in screen and "Case/Example Context + Goal?" in screen
    compact_raw = recorder.getvalue()
    assert "30 100" in compact_raw
    assert BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", compact_raw) is not None
    assert BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", compact_raw) is not None
    _close(compact)

    compact_elaborate, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(compact_elaborate, seconds=0.8)
    compact_elaborate.send("\t\t\t" + "\x1b[B" * 3)
    BASE._pump(compact_elaborate, seconds=0.4)
    screen = BASE._snapshot(recorder, "11-compact-elaborate-focused")
    assert "▸ mem elaborate" in screen and "USE WHEN:" in screen
    compact_elaborate.send("\x1b[C")
    BASE._pump(compact_elaborate, seconds=0.35)
    screen = BASE._snapshot(recorder, "12-compact-elaborate-expanded")
    assert "▾ mem elaborate" in screen and "suggested Case propositions" in screen
    compact_raw = recorder.getvalue()
    assert "30 100" in compact_raw
    assert BASE.re.search(r"\x1b\[[0-9;]*38;(?:2|5);", compact_raw) is not None
    assert BASE.re.search(r"\x1b\[[0-9;]*48;(?:2|5);", compact_raw) is not None
    _close(compact_elaborate)


if __name__ == "__main__":
    main()
