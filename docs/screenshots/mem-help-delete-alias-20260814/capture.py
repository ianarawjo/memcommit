"""Capture Delete's canonical Help row and hidden Remove spelling."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/screenshots/mem-help-delete-alias-20260814"
BASE_PATH = ROOT / "docs/screenshots/mem-help-command-naming-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.ROOT = ROOT
BASE.OUT = OUT


def main() -> None:
    executable = shutil.which("mem")
    if executable is None:
        raise RuntimeError("mem executable is unavailable")
    OUT.mkdir(parents=True, exist_ok=True)

    child, recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(child, seconds=0.8)
    entry = BASE._snapshot(recorder, "01-help-entry")
    assert "mem help · command inventory" in entry
    assert "INVENTORY VIEW" in entry

    # Tab enters the next category (Memories) at Add. Five Down presses reach
    # canonical Delete after Reference, Edit, Chunk, and Forget.
    child.send("\t" + "\x1b[B" * 5)
    BASE._pump(child)
    selected = BASE._snapshot(recorder, "02-delete-remove-row")
    assert "▸ mem delete (remove)" in selected
    assert "▸ mem remove " not in selected

    child.send("\x1b[C")
    BASE._pump(child)
    detail = BASE._snapshot(recorder, "03-delete-detail")
    assert "▾ mem delete (remove)" in detail
    assert "Context or direct item -> removed" in detail
    assert "FORM 1 · mem delete [item]" in detail
    BASE._assert_color(recorder.getvalue())

    child.send("q")
    child.expect(BASE.pexpect.EOF, timeout=5)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)


if __name__ == "__main__":
    main()
