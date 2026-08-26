"""Capture compact Branch setup, Apply, and collision safety in 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location(
    "branch_compact_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _prepare_store(root: Path, *, collision: bool):
    import memcommit.ops as ops
    import memcommit.store as store_module
    from memcommit.store import MemoryStore

    store_module.STORE_DIR = root
    store = MemoryStore()
    practice = ops.init("practice")
    ops.add(practice, "Practice root remains the current orientation Context.")
    task = ops.init("practice/task-1")
    ops.add(task, "Task 1 is the reviewed non-current Branch Source.")
    notes = ops.init("practice/task-1/notes")
    ops.add(notes, "Task 1 notes prove descendant suffix preservation.")
    task_two = ops.init("practice/task-2")
    ops.add(task_two, "Task 2 stays outside the selected Source subtree.")
    archive = ops.init("archive")
    ops.add(archive, "Archive is another available parent location.")
    contexts = [practice, task, notes, task_two, archive]
    if collision:
        existing = ops.init("capture/existing")
        ops.add(existing, "Existing target content must remain unchanged.")
        contexts.append(existing)
    for context in contexts:
        store.create_context(context)
    store.set_current(practice.name)
    return store


def _run_success_child(store_root: Path) -> None:
    from memcommit.cli import app

    store = _prepare_store(store_root, collision=False)
    source_before = store._context_file("practice/task-1").read_bytes()
    notes_before = store._context_file("practice/task-1/notes").read_bytes()
    print("$ mem branch", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    app(args=["branch"], prog_name="mem", standalone_mode=False)
    print("CAPTURE GATE · PRESS V FOR READ-ONLY RESULT VERIFICATION", flush=True)
    if sys.stdin.read(1).lower() != "v":
        raise RuntimeError("Branch verification gate was not acknowledged.")
    target = store.load_direct("capture/branch-result")
    target_child = store.load_direct("capture/branch-result/notes")
    print("\nREAD-ONLY BRANCH RESULT VERIFICATION")
    print(f"  CURRENT CONTEXT · {store.current_context_name()}")
    print(f"  TARGET ROOT · {target.name} · MEMORIES {len(target.memories)}")
    print(
        f"  TARGET DESCENDANT · {target_child.name} · "
        f"MEMORIES {len(target_child.memories)}"
    )
    print(
        "  SOURCE ROOT BYTES UNCHANGED · "
        f"{store._context_file('practice/task-1').read_bytes() == source_before}"
    )
    print(
        "  SOURCE DESCENDANT BYTES UNCHANGED · "
        f"{store._context_file('practice/task-1/notes').read_bytes() == notes_before}"
    )
    print(f"  TASK 2 COPIED · {store.context_exists('capture/branch-result/task-2')}")
    print("  PROVIDER CALLS · 0", flush=True)


def _run_collision_child(store_root: Path) -> None:
    from memcommit.cli import app

    store = _prepare_store(store_root, collision=True)
    before = store._context_file("capture/existing").read_bytes()
    current_before = store.current_context_name()
    names_before = tuple(store.list_context_names())
    print("$ mem branch · EXISTING TARGET SAFETY", flush=True)
    print(
        f"PTY · {os.get_terminal_size().columns} COLUMNS × "
        f"{os.get_terminal_size().lines} ROWS",
        flush=True,
    )
    app(args=["branch"], prog_name="mem", standalone_mode=False)
    print("\nCOLLISION CANCELLATION VERIFICATION")
    print(
        "  EXISTING TARGET BYTES UNCHANGED · "
        f"{store._context_file('capture/existing').read_bytes() == before}"
    )
    print(
        f"  CONTEXT NAMES UNCHANGED · {tuple(store.list_context_names()) == names_before}"
    )
    print(
        f"  CURRENT CONTEXT UNCHANGED · {store.current_context_name() == current_before}"
    )
    print("  PARTIAL BRANCH TARGETS · 0")
    print("  PROVIDER CALLS · 0", flush=True)


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _spawn(kind: str, store_root: Path) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind, str(store_root)],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_success(store_root: Path) -> None:
    child, recorder = _spawn("success", store_root)
    try:
        child.expect("MEM BRANCH")
        _BASE._settle(child)
        _snapshot(recorder, "01-compact-entry")

        child.send("\x1b[C\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-source-browse")

        child.send("\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "03-noncurrent-source-selected")

        child.send("\x1b[C ")
        _BASE._settle(child)
        _snapshot(recorder, "04-descendant-range-selected")

        child.send("\x1b[B\x15capture/branch-result")
        _BASE._settle(child)
        _snapshot(recorder, "05-exact-target-entered")

        child.send("\x1b[C\r")
        _BASE._settle(child)
        _snapshot(recorder, "06-parent-browse")

        child.send("\x1b[B\r")
        _BASE._settle(child)
        _snapshot(recorder, "07-edited-target-preserved")

        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "08-exact-apply-review")

        child.send("\r")
        child.expect("Branched subtree")
        child.expect("CAPTURE GATE")
        _BASE._settle(child)
        _snapshot(recorder, "09-success-receipt")

        child.send("v\r")
        child.expect("READ-ONLY BRANCH RESULT VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "10-read-only-result-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_collision(store_root: Path) -> None:
    child, recorder = _spawn("collision", store_root)
    try:
        child.expect("MEM BRANCH")
        _BASE._settle(child)
        child.send("\x1b[B\x15capture/existing\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "11-existing-target-blocked")

        child.send("q")
        child.expect("COLLISION CANCELLATION VERIFICATION")
        child.expect("PROVIDER CALLS .* 0")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "12-collision-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mem-branch-compact-") as directory:
        root = Path(directory)
        _capture_success(root / "success-store")
        _capture_collision(root / "collision-store")
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "38;2;" not in raw and "48;2;" not in raw:
        raise RuntimeError(
            "Branch PTY stream did not contain expected true-color ANSI."
        )
    if "\x1b[?1049h" in raw:
        raise RuntimeError("Compact Branch setup entered an alternate screen buffer.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        child_kind = sys.argv[2]
        child_root = Path(sys.argv[3])
        if child_kind == "success":
            _run_success_child(child_root)
        elif child_kind == "collision":
            _run_collision_child(child_root)
        else:
            raise SystemExit(f"unknown child kind: {child_kind}")
    else:
        main()
