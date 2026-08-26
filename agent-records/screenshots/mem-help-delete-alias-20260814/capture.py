"""Capture Delete's canonical Help row and hidden Remove spelling."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "agent-records/screenshots/mem-help-delete-alias-20260814"
BASE_PATH = ROOT / "agent-records/screenshots/mem-help-command-naming-20260813/capture.py"
SPEC = importlib.util.spec_from_file_location("mem_help_capture_base", BASE_PATH)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BASE.ROOT = ROOT
BASE.OUT = OUT


def _label_cells(raw: str, label: str):
    screen = BASE._screen(raw)
    for row_index, line in enumerate(screen.display):
        if label not in line:
            continue
        column = line.index(label)
        return tuple(
            screen.buffer[row_index][column + offset] for offset in range(len(label))
        )
    raise AssertionError(f"label is not visible: {label}")


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
    memory_cells = _label_cells(recorder.getvalue(), "MEMORY")
    # prompt-toolkit may project the true-color token to the nearest 256-color
    # lavender in a PTY; either value records the same shared semantic token.
    assert {cell.fg for cell in memory_cells} <= {"cad3f5", "d7d7ff"}
    assert {cell.bg for cell in memory_cells} == {"default"}

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

    focus_child, focus_recorder = BASE._spawn(executable, interactive=True)
    BASE._pump(focus_child, seconds=0.8)
    # From the first Context command, Up enters Checkpoint and then walks the
    # six concepts in reverse order until Memory owns focus.
    focus_child.send("\x1b[A" * 6)
    BASE._pump(focus_child)
    focused = BASE._snapshot(focus_recorder, "04-memory-concept-focused")
    assert "MEMORY      An atomic unit of information" in focused
    focused_cells = _label_cells(focus_recorder.getvalue(), "MEMORY")
    assert {cell.bg for cell in focused_cells} != {"default"}
    assert not {cell.fg for cell in focused_cells} <= {"cad3f5", "d7d7ff"}
    BASE._assert_color(focus_recorder.getvalue())

    focus_child.send("q")
    focus_child.expect(BASE.pexpect.EOF, timeout=5)
    focus_child.close()
    assert focus_child.exitstatus == 0, (
        focus_child.exitstatus,
        focus_child.signalstatus,
    )


if __name__ == "__main__":
    main()
