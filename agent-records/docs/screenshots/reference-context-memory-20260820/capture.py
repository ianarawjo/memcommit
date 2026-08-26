"""Capture Context/Memory Reference selection and safety boundaries."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/reference-context-memory-20260820"
COLUMNS = 180
ROWS = 52
RIGHT = "\x1b[C"
DOWN = "\x1b[B"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/mem-add-tui-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("reference_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS
_BASE._BASE.OUT = OUT
_BASE._BASE.COLUMNS = COLUMNS
_BASE._BASE.ROWS = ROWS


def _configure(store_root: Path) -> None:
    _BASE._configure_isolated_store(store_root)


def _initialize_context() -> None:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    source = ops.init("a-source")
    ops.add(source, "Root snapshot fact.")
    descendant = ops.init("a-source/child")
    ops.add(descendant, "Lexical descendant fact.")
    embedded = ops.init("z-library")
    ops.add(embedded, "Embedded Context fact.")
    ops.embed(embedded, source)
    target = ops.init("target")
    for context in (source, descendant, embedded, target):
        store.save(context)
    store.set_current("target")


def _initialize_memory() -> None:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "Exact Memory wording.")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current("target")


def _initialize_rejection() -> None:
    import memcommit.ops as ops
    from memcommit.store import MemoryStore

    store = MemoryStore()
    only = ops.init("only")
    ops.add(only, "Must remain unchanged.")
    store.save(only)
    store.set_current("only")


def _contents(context) -> tuple[str, ...]:
    from memcommit.context import Context, Memory

    found: list[str] = []
    seen: set[str] = set()

    def visit(current: Context) -> None:
        if current.uid in seen:
            return
        seen.add(current.uid)
        for item in current.iter_items():
            if isinstance(item, Memory):
                found.append(item.content)
            elif isinstance(item, Context):
                visit(item)

    visit(context)
    return tuple(found)


def _run_child(kind: str) -> None:
    from memcommit.cli import app
    from memcommit.context import MemoryRef
    from memcommit.context_snapshot import ContextSnapshotRef
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-reference-capture-") as directory:
        _configure(Path(directory) / ".mem")
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        if kind == "context":
            _initialize_context()
            app(args=["reference"], prog_name="mem", standalone_mode=False)
            print("CONTEXT VERIFICATION GATE · PRESS V")
            sys.stdin.read(1)
            store = MemoryStore()
            for name in ("a-source", "a-source/child", "z-library"):
                store.delete(name)
            target = store.load("target")
            snapshots = [
                item
                for item in target.iter_items()
                if isinstance(item, ContextSnapshotRef)
            ]
            assert len(snapshots) == 1
            print(
                "CONTEXT SNAPSHOT VERIFIED · SOURCES DELETED · "
                f"CONTEXTS {len(snapshots[0].snapshot_package['contexts'])} · "
                f"CONTENTS {_contents(snapshots[0])!r}"
            )
            return
        if kind == "memory":
            _initialize_memory()
            app(args=["reference"], prog_name="mem", standalone_mode=False)
            print("MEMORY VERIFICATION GATE · PRESS V")
            sys.stdin.read(1)
            store = MemoryStore()
            snapshots = [
                item
                for item in store.load("target").iter_items()
                if isinstance(item, MemoryRef) and item.is_snapshot
            ]
            assert len(snapshots) == 1 and snapshots[0].target is not None
            print(
                "MEMORY SNAPSHOT VERIFIED · "
                f"CONTENT {snapshots[0].target.content!r} · SOURCE UNCHANGED"
            )
            return

        _initialize_rejection()
        app(args=["reference"], prog_name="mem", standalone_mode=False)
        store = MemoryStore()
        checkpoints = [
            record
            for record in store.list_checkpoints("only")
            if record["command"] == "reference"
        ]
        print(
            "SELF REFERENCE REJECTION VERIFIED · DIRECT ITEMS 1 · "
            f"REFERENCE CHECKPOINTS {len(checkpoints)}"
        )


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _spawn(kind: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _BASE._BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child", kind],
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


def _settle(child: pexpect.spawn) -> None:
    _BASE._BASE._settle(child)


def _capture_context() -> None:
    child, recorder = _spawn("context")
    try:
        child.expect("SNAPSHOT UNIT")
        _settle(child)
        _snapshot(recorder, "01-context-entry")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "02-context-source")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "03-context-direct-scope")

        child.send(RIGHT)
        _settle(child)
        _snapshot(recorder, "04-context-recursive-scope")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "05-context-target")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "06-context-exact-command")

        child.send("\r")
        child.expect("CONTEXT VERIFICATION GATE")
        _snapshot(recorder, "07-context-success")

        child.send("v\r")
        child.expect("CONTEXT SNAPSHOT VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "08-context-source-deletion-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_memory() -> None:
    child, recorder = _spawn("memory")
    try:
        child.expect("SNAPSHOT UNIT")
        child.send(RIGHT)
        _settle(child)
        _snapshot(recorder, "09-memory-mode")

        child.send("\t" + DOWN + "\r")
        _settle(child)
        _snapshot(recorder, "10-memory-selected")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "11-memory-target")

        child.send("\t")
        _settle(child)
        _snapshot(recorder, "12-memory-exact-command")

        child.send("\r")
        child.expect("MEMORY VERIFICATION GATE")
        _snapshot(recorder, "13-memory-success")

        child.send("v\r")
        child.expect("MEMORY SNAPSHOT VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "14-memory-read-only-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_rejection() -> None:
    child, recorder = _spawn("rejection")
    try:
        child.expect("SNAPSHOT UNIT")
        child.send("\t\t\t\t\r")
        _settle(child)
        _snapshot(recorder, "15-self-reference-blocked")
        child.send("\x1b")
        child.expect("SELF REFERENCE REJECTION VERIFIED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "16-self-reference-no-partial-state")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_context()
    _capture_memory()
    _capture_rejection()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "\x1b[" in raw
    assert "38;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
