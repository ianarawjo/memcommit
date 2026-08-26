"""Capture the reviewed Merge Help copy at wide and compact sizes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-merge-20260815"

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


def _assert_merge_copy(rendered: str) -> None:
    assert "mem merge" in rendered
    assert "Add Source-only items to a selected Target" in rendered
    assert "WHEN · Appending Source-only items or bringing a copied" in rendered


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(child, seconds=0.8)
    # Contexts -> Memories -> Search & Explain -> Analyze & Transform, then
    # Use the A-Z projection and focus Profile so the preceding Merge row is
    # completely visible while remaining collapsed.
    child.send("\x1b[Z\x1b[C")
    _BASE._pump(child, seconds=0.3)
    child.send("\t\x1b[H" + "\x1b[B" * 38)
    _BASE._pump(child, seconds=0.8)
    collapsed = _BASE._snapshot(recorder, "01-wide-collapsed")
    assert "▸ mem merge" in collapsed
    _assert_merge_copy(collapsed)
    assert "FORM 1" not in collapsed
    _BASE._assert_color(recorder.getvalue())

    child.send("\x1b[A\x1b[C\x1b[B")
    _BASE._pump(child, seconds=0.8)
    expanded = _BASE._snapshot(recorder, "02-wide-expanded")
    assert "▾ mem merge" in expanded
    _assert_merge_copy(expanded)
    assert "Source Context -> selected Target Context" in expanded
    assert "EXECUTION · DETERMINISTIC" in expanded
    assert "--into [target_context]" in expanded
    assert "FORM 1" in expanded
    _close(child)

    _BASE.COLUMNS = 100
    _BASE.ROWS = 30
    compact_child, compact_recorder = _BASE._spawn(executable, interactive=True)
    _BASE._pump(compact_child, seconds=0.8)
    compact_child.send("\x1b[Z\x1b[C")
    _BASE._pump(compact_child, seconds=0.3)
    compact_child.send("\t\x1b[H" + "\x1b[B" * 38)
    _BASE._pump(compact_child, seconds=0.8)
    compact = _BASE._snapshot(compact_recorder, "03-compact-collapsed")
    assert "30 100" in compact_recorder.getvalue()
    assert "▸ mem merge" in compact
    _assert_merge_copy(compact)
    assert "FORM 1" not in compact

    compact_child.send("\x1b[A\x1b[C\x1b[B")
    _BASE._pump(compact_child, seconds=0.8)
    compact_expanded = _BASE._snapshot(compact_recorder, "04-compact-expanded")
    assert "▾ mem merge" in compact_expanded
    _assert_merge_copy(compact_expanded)
    assert "EXECUTION · DETERMINISTIC" in compact_expanded
    assert "--into [target_context]" in compact_expanded
    assert "FORM 1" in compact_expanded
    assert (
        _BASE.re.search(
            r"\x1b\[[0-9;]*38;(?:2|5);",
            compact_recorder.getvalue(),
        )
        is not None
    )
    assert (
        _BASE.re.search(
            r"\x1b\[[0-9;]*48;(?:2|5);",
            compact_recorder.getvalue(),
        )
        is not None
    )
    _close(compact_child)


if __name__ == "__main__":
    main()
