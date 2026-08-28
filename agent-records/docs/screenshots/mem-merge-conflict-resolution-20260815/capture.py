"""Capture conflict-aware Merge paths in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/mem-merge-conflict-resolution-20260815"
COLUMNS = 180
ROWS = 52
SHIFT_TAB = "\x1b[Z"
RIGHT = "\x1b[C"

_BASE_PATH = ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
_SPEC = importlib.util.spec_from_file_location("merge_conflict_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _configure_isolated_store(store_root: Path) -> None:
    import memcommit.persistence.store as store_module

    values = {
        "STORE_DIR": store_root,
        "CONTEXTS_DIR": store_root / "contexts",
        "QUERY_SOURCES_DIR": store_root / "query-sources",
        "STATE_FILE": store_root / "state.json",
        "IMPACT_PLAN_FILE": store_root / "impact-plan.json",
        "STAGED_UPDATE_FILE": store_root / "staged-update.json",
        "REVIEW_SESSION_FILE": store_root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": store_root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": store_root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": store_root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": store_root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": store_root / "ground-sessions",
        "MELD_SESSIONS_DIR": store_root / "meld-sessions",
    }
    for name, value in values.items():
        setattr(store_module, name, value)


def _initialize(kind: str) -> None:
    import memcommit.application.capabilities.ops as ops
    from memcommit.core.context import Context, Memory
    from memcommit.persistence.store import MemoryStore, context_record_digest

    store = MemoryStore()
    shared_uid = "00000000-0000-0000-0000-000000000001"
    source = ops.init("source")
    target = ops.init("target")
    if kind == "noop":
        source.add(Memory(uid=shared_uid, content="identical retained fact"))
        target.add(Memory(uid=shared_uid, content="identical retained fact"))
    elif kind == "protected-context":
        ops.add(source, "source-only structural addition")
    else:
        source.add(Memory(uid=shared_uid, content="source revision: library closes at 6 p.m."))
        ops.add(source, "source-only structural addition")
        target.add(Memory(uid=shared_uid, content="target revision: library closes at 5 p.m."))
    store.create_context(source)
    store.create_context(target)
    if kind == "protected-memory":
        store.set_memory_write_protection(
            target.name,
            shared_uid,
            protected=True,
            expected_context_uid=target.uid,
            expected_context_digest=context_record_digest(target),
        )
    elif kind == "protected-context":
        store.set_context_write_protection(
            target.name,
            protected=True,
            expected_context_uid=target.uid,
            expected_context_digest=context_record_digest(target),
        )
    if kind == "recursive":
        child_uid = "00000000-0000-0000-0000-000000000002"
        source_child = ops.init("source/child")
        source_child.add(Memory(uid=child_uid, content="source child revision"))
        store.create_context(source_child)
        target_child = ops.init("target/child")
        target_child.add(Memory(uid=child_uid, content="target child revision"))
        store.create_context(target_child)
        source_new = ops.init("source/new-path")
        ops.add(source_new, "new descendant fact")
        store.create_context(source_new)
        source.add(Context(uid=source_child.uid, name=source_child.name))
        source.add(Context(uid=source_new.uid, name=source_new.name))
        store.save(source, expected_context_digest=source._store_digest)
        target.add(Context(uid=target_child.uid, name=target_child.name))
        store.save(target, expected_context_digest=target._store_digest)
    store.set_current("target")


def _verification(kind: str) -> str:
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore()
    target = store.load_direct("target")
    contents = [
        item.content for item in target.iter_items() if isinstance(item, Memory)
    ]
    return (
        f"{kind.upper()} VERIFICATION · TARGET {contents!r} · "
        f"CHILD {store.context_exists('target/child')} · "
        f"NEW PATH {store.context_exists('target/new-path')} · "
        f"CHECKPOINTS {len(store.list_checkpoints('target'))}"
    )


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child(kind: str) -> None:
    import click
    import typer

    from memcommit.adapters.console.commands.merge.command import cmd as merge_command

    with tempfile.TemporaryDirectory(prefix="mem-merge-conflict-capture-") as directory:
        _configure_isolated_store(Path(directory) / ".mem")
        _initialize(kind)
        if kind == "stale":
            from memcommit.application.operations.merge.runtime import MemoryStoreMergePort

            original_apply = MemoryStoreMergePort.apply

            def stale_apply(self, plan, resolutions):
                import memcommit.application.capabilities.ops as ops

                source = self.store.load_for_update("source")
                ops.add(source, "late source mutation")
                self.store.save(
                    source,
                    expected_context_digest=source._store_digest,
                )
                return original_apply(self, plan, resolutions)

            MemoryStoreMergePort.apply = stale_apply

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("merge")(merge_command)
        exit_code = 0
        try:
            returned = app(args=["merge"], prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        _pause(_verification(kind))

        if kind == "recursive" and exit_code == 0:
            from memcommit.adapters.console.commands.redo.command import cmd as redo_command
            from memcommit.adapters.console.commands.undo.command import cmd as undo_command

            undo_command()
            _pause(_verification("recursive undo"))
            redo_command()
            print(_verification("recursive redo"), flush=True)


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
    recorder = _BASE._StreamRecorder()
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


def _enter_conflict(child: pexpect.spawn) -> None:
    child.expect("NEW MERGE")
    child.send("\t\r")
    child.expect("RESOLUTION SESSION")
    _BASE._settle(child)


def _capture_direct() -> None:
    child, recorder = _spawn("direct")
    try:
        _enter_conflict(child)
        _snapshot(recorder, "01-direct-conflict-report")
        child.send("\t\r")
        _BASE._settle(child)
        _snapshot(recorder, "02-direct-conflict-detail")
        child.send("\t")
        _BASE._settle(child)
        _snapshot(recorder, "03-direct-responses")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "04-direct-choice-selected")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "05-direct-choice-cleared")
        child.send("\r\t\t")
        _BASE._settle(child)
        _snapshot(recorder, "06-direct-ready-to-review")
        child.send("\r")
        _BASE._settle(child)
        _snapshot(recorder, "07-direct-final-review")
        child.send("\r")
        # Dynamic height changes can interleave cursor-control sequences inside
        # the repainted footer text, so wait for the repaint instead of
        # matching one visually contiguous footer phrase in the raw stream.
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "08-direct-success-receipt")
        assert "STATUS · SUCCESS" in (
            OUT / "08-direct-success-receipt.txt"
        ).read_text(encoding="utf-8")
        child.send("\r")
        child.expect("DIRECT VERIFICATION")
        _snapshot(recorder, "09-direct-read-only-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_bulk() -> None:
    child, recorder = _spawn("bulk")
    try:
        _enter_conflict(child)
        child.send("\t\tk")
        _BASE._settle(child)
        _snapshot(recorder, "10-bulk-keep-whole-set-review")
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "11-bulk-success-receipt")
        assert "STATUS · SUCCESS" in (
            OUT / "11-bulk-success-receipt.txt"
        ).read_text(encoding="utf-8")
        child.send("\r")
        child.expect("BULK VERIFICATION")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_recursive_recovery() -> None:
    child, recorder = _spawn("recursive")
    try:
        child.expect("NEW MERGE")
        child.send(SHIFT_TAB + RIGHT + "\t\t\r")
        child.expect("RESOLUTION SESSION")
        _BASE._settle(child)
        _snapshot(recorder, "12-recursive-multi-mapping-conflicts")
        child.send("\t\ts")
        _BASE._settle(child)
        _snapshot(recorder, "13-recursive-take-source-bulk-review")
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "14-recursive-success-receipt")
        assert "STATUS · SUCCESS" in (
            OUT / "14-recursive-success-receipt.txt"
        ).read_text(encoding="utf-8")
        child.send("\r")
        child.expect("RECURSIVE VERIFICATION")
        _snapshot(recorder, "15-recursive-applied-verification")
        child.send("\r")
        child.expect("RECURSIVE UNDO VERIFICATION")
        _snapshot(recorder, "16-recursive-operation-undo")
        child.send("\r")
        child.expect("RECURSIVE REDO VERIFICATION")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "17-recursive-operation-redo")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel() -> None:
    child, recorder = _spawn("cancel")
    try:
        _enter_conflict(child)
        child.send("q")
        child.expect("CANCEL VERIFICATION")
        _snapshot(recorder, "18-conflict-cancel-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        _enter_conflict(child)
        child.send("\t\tk\r")
        child.expect("Apply failed")
        _BASE._settle(child)
        _snapshot(recorder, "19-stale-plan-failure")
        child.send("q")
        child.expect("STALE VERIFICATION")
        _snapshot(recorder, "20-stale-no-partial-target")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_noop() -> None:
    child, recorder = _spawn("noop")
    try:
        child.expect("NEW MERGE")
        child.send("\t\r")
        child.expect("REVIEW FROZEN PLAN")
        _BASE._settle(child)
        _snapshot(recorder, "21-noop-frozen-classification")
        child.send("\t\r")
        _BASE._settle(child)
        _snapshot(recorder, "22-noop-success-receipt")
        assert "NO TARGET CHANGE" in (
            OUT / "22-noop-success-receipt.txt"
        ).read_text(encoding="utf-8")
        child.send("\r")
        child.expect("NOOP VERIFICATION")
        _snapshot(recorder, "23-noop-read-only-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_write_protection() -> None:
    child, recorder = _spawn("protected-memory")
    try:
        _enter_conflict(child)
        child.send("\t\r\t")
        _BASE._settle(child)
        _snapshot(recorder, "24-protected-memory-keep-only")
        canvas = (OUT / "24-protected-memory-keep-only.txt").read_text(
            encoding="utf-8"
        )
        assert "1. KEEP TARGET" in canvas
        assert "2. TAKE SOURCE" not in canvas
        assert "S TAKE ALL SOURCE" not in canvas
        child.send("q")
        child.expect("PROTECTED-MEMORY VERIFICATION")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _spawn("protected-context")
    try:
        child.expect("NEW MERGE")
        child.send("\t\r")
        child.expect("PROTECTED-CONTEXT VERIFICATION")
        _snapshot(recorder, "25-protected-context-pre-review-failure")
        canvas = (OUT / "25-protected-context-pre-review-failure.txt").read_text(
            encoding="utf-8"
        )
        assert "locked against changes" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_direct()
    _capture_bulk()
    _capture_recursive_recovery()
    _capture_cancel()
    _capture_stale()
    _capture_noop()
    _capture_write_protection()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        sys.path.insert(0, str(ROOT / "src"))
        _run_child(sys.argv[2])
    else:
        main()
