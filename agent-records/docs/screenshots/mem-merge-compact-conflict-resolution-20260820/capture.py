"""Capture the inline Merge conflict review in a real 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/mem-merge-compact-conflict-resolution-20260820"
OLD_CAPTURE = (
    ROOT / "agent-records/docs/screenshots/mem-merge-conflict-resolution-20260815/capture.py"
)
DOWN = "\x1b[B"
LEFT = "\x1b[D"
RIGHT = "\x1b[C"
PAGE_DOWN = "\x1b[6~"

_SPEC = importlib.util.spec_from_file_location("merge_conflict_capture", OLD_CAPTURE)
assert _SPEC is not None and _SPEC.loader is not None
_CAPTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CAPTURE)
_CAPTURE.OUT = OUT
_CAPTURE._BASE.OUT = OUT


def _snapshot(recorder, stem: str) -> str:
    _CAPTURE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def _enter_conflict(child) -> None:
    child.expect("NEW MERGE")
    # MODE -> Source -> Target -> Continue; both endpoints are already checked.
    child.send("\t\t\t\r")
    child.expect("MERGE REVIEW")
    _CAPTURE._BASE._settle(child)


def _run_long_child() -> None:
    """Create one viewport-tall real conflict for scroll evidence."""

    import click
    import typer

    import memcommit.application.ops as ops
    from memcommit.adapters.console.commands.merge.command import cmd as merge_command
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-merge-long-capture-") as directory:
        _CAPTURE._configure_isolated_store(Path(directory) / ".mem")
        store = MemoryStore()
        shared_uid = "00000000-0000-0000-0000-000000000003"
        source_content = (
            "SOURCE START\n"
            + "\n".join(f"source complete line {index:02d}" for index in range(1, 61))
            + "\nSOURCE END"
        )
        target_content = (
            "TARGET START\n"
            + "\n".join(f"target complete line {index:02d}" for index in range(1, 61))
            + "\nTARGET END"
        )
        source = ops.init("source")
        source.add(Memory(uid=shared_uid, content=source_content))
        target = ops.init("target")
        target.add(Memory(uid=shared_uid, content=target_content))
        store.create_context(source)
        store.create_context(target)
        store.set_current("target")

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
        print(
            f"LONG VERIFICATION · CHECKPOINTS {len(store.list_checkpoints('target'))}",
            flush=True,
        )
        sys.stdin.readline()


def _run_zero_delta_child() -> None:
    """Reproduce the motivating kept-Target-only receipt without a TUI."""

    import click
    import typer

    import memcommit.application.ops as ops
    from memcommit.adapters.console.commands.merge.command import cmd as merge_command
    from memcommit.core.context import Memory
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-merge-zero-capture-") as directory:
        _CAPTURE._configure_isolated_store(Path(directory) / ".mem")
        store = MemoryStore()
        source = ops.init("source")
        source.add(
            Memory(
                uid="00000000-0000-0000-0000-000000000004", content="source revision"
            )
        )
        target = ops.init("target")
        target.add(
            Memory(
                uid="00000000-0000-0000-0000-000000000004", content="target revision"
            )
        )
        store.create_context(source)
        store.create_context(target)
        store.set_current("target")

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("merge")(merge_command)
        exit_code = 0
        try:
            returned = app(
                args=["merge", "source", "--keep-target-all"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        print("ZERO DELTA RECEIPT COMPLETE", flush=True)
        sys.stdin.readline()
        checkpoint = store.list_checkpoints("target")[0]
        print(
            "ZERO DELTA VERIFICATION · "
            f"TARGET {store.load_direct('target').memories['00000000-0000-0000-0000-000000000004'].content!r} · "
            f"CHECKPOINTS {len(store.list_checkpoints('target'))} · "
            f"DESCRIPTION {checkpoint['description']}",
            flush=True,
        )
        sys.stdin.readline()


def _spawn_local_child(argument: str) -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _CAPTURE._BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), argument],
        cwd=str(ROOT),
        env=_CAPTURE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_CAPTURE.ROWS, _CAPTURE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _spawn_long() -> tuple[pexpect.spawn, io.StringIO]:
    return _spawn_local_child("--child-long")


def _capture_direct() -> None:
    child, recorder = _CAPTURE._spawn("direct")
    try:
        _enter_conflict(child)
        canvas = _snapshot(recorder, "01-inline-conflict-entry")
        assert "MERGE REVIEW · 1 conflict" in canvas
        assert 'SOURCE "source revision: library closes at 6 p.m."' in canvas
        assert '✓ TARGET "target revision: library closes at 5 p.m."' in canvas
        assert "BULK DECISION · ✓ KEEP ALL TARGET" in canvas
        assert "APPLY · READY" in canvas
        assert "…" not in canvas

        child.send(LEFT)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "02-source-selected")
        assert '✓ SOURCE "source revision: library closes at 6 p.m."' in canvas
        assert "BULK DECISION ·   KEEP ALL TARGET / ✓ TAKE ALL SOURCE" in canvas

        child.send(RIGHT)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "03-target-restored")
        assert '✓ TARGET "target revision: library closes at 5 p.m."' in canvas
        assert "BULK DECISION · ✓ KEEP ALL TARGET" in canvas

        child.send("\t")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "04-apply-ready-focused")
        assert "› APPLY · READY" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "05-exact-whole-set-review")
        assert "APPLY CONFIRMATION · EXACT WHOLE SET" in canvas
        assert "--keep-target-all" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child, seconds=0.8)
        canvas = _snapshot(recorder, "06-success-receipt")
        assert "MERGE RECORDED" in canvas
        assert "KEPT TARGET · 1" in canvas
        assert "TOOK SOURCE · 0" in canvas

        child.send("\r")
        child.expect("DIRECT VERIFICATION")
        canvas = _snapshot(recorder, "07-read-only-target-verification")
        assert "target revision: library closes at 5 p.m." in canvas
        assert "CHECKPOINTS 1" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_multiple_and_bulk() -> None:
    child, recorder = _CAPTURE._spawn("recursive")
    try:
        child.expect("NEW MERGE")
        child.send(RIGHT + "\t\t\t\r")
        child.expect("MERGE REVIEW")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "08-multiple-conflicts-entry")
        assert "MERGE REVIEW · 2 conflicts" in canvas
        assert "1 · [00000000]" in canvas
        assert "2 · [00000000]" in canvas
        assert canvas.count("✓ TARGET") == 2
        assert "BULK DECISION · ✓ KEEP ALL TARGET" in canvas

        child.send(LEFT + DOWN)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "09-mixed-individual-choices")
        assert canvas.count("✓ SOURCE") == 1
        assert canvas.count("✓ TARGET") == 1
        assert "✓ KEEP ALL TARGET" not in canvas
        assert "✓ TAKE ALL SOURCE" not in canvas

        child.send(DOWN + RIGHT)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "10-take-all-source-focused")
        assert "› BULK DECISION ·   KEEP ALL TARGET /   TAKE ALL SOURCE" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "11-bulk-staged-apply-ready")
        assert canvas.count("✓ SOURCE") == 2
        assert "BULK DECISION ·   KEEP ALL TARGET / ✓ TAKE ALL SOURCE" in canvas
        assert "› APPLY · READY" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "12-bulk-exact-review")
        assert "APPLY CONFIRMATION · EXACT WHOLE SET" in canvas
        assert "--take-source-all" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child, seconds=0.8)
        canvas = _snapshot(recorder, "13-recursive-success-receipt")
        assert "MERGE RECORDED" in canvas
        assert "TOOK SOURCE · 2" in canvas

        child.send("\r")
        child.expect("RECURSIVE VERIFICATION")
        canvas = _snapshot(recorder, "14-recursive-read-only-verification")
        assert "source revision: library closes at 6 p.m." in canvas
        assert "CHILD True" in canvas
        assert "NEW PATH True" in canvas
        child.send("\r")
        child.expect("RECURSIVE UNDO VERIFICATION")
        child.send("\r")
        child.expect("RECURSIVE REDO VERIFICATION")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_failure_and_capability() -> None:
    child, recorder = _CAPTURE._spawn("stale")
    try:
        _enter_conflict(child)
        child.send("\t\r\r")
        child.expect("Apply failed")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "15-stale-apply-failure")
        assert "Apply failed" in canvas
        child.send("q")
        child.expect("STALE VERIFICATION")
        canvas = _snapshot(recorder, "16-stale-no-partial-target")
        assert "CHECKPOINTS 0" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    child, recorder = _CAPTURE._spawn("protected-memory")
    try:
        _enter_conflict(child)
        canvas = _snapshot(recorder, "17-protected-memory-source-unavailable")
        assert '× SOURCE "source revision: library closes at 6 p.m."' in canvas
        assert '✓ TARGET "target revision: library closes at 5 p.m."' in canvas
        assert "TAKE ALL SOURCE" not in canvas
        child.send("q")
        child.expect("PROTECTED-MEMORY VERIFICATION")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_cancel() -> None:
    child, recorder = _CAPTURE._spawn("cancel")
    try:
        _enter_conflict(child)
        child.send("q")
        child.expect("CANCEL VERIFICATION")
        canvas = _snapshot(recorder, "18-cancel-read-only-verification")
        assert "CHECKPOINTS 0" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_complete_long_values() -> None:
    child, recorder = _spawn_long()
    try:
        _enter_conflict(child)
        canvas = _snapshot(recorder, "19-long-memory-start")
        assert "SOURCE START" in canvas
        assert "source complete line 01" in canvas

        child.send(PAGE_DOWN)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "20-long-memory-middle")
        assert "SOURCE END" in canvas or "TARGET START" in canvas

        child.send(PAGE_DOWN + PAGE_DOWN)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "21-long-memory-end")
        assert "target complete line 60" in canvas
        assert "TARGET END" in canvas

        child.send("q")
        child.expect("LONG VERIFICATION · CHECKPOINTS 0")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_zero_delta_receipt() -> None:
    child, recorder = _spawn_local_child("--child-zero-delta")
    try:
        child.expect("ZERO DELTA RECEIPT COMPLETE")
        canvas = _snapshot(recorder, "22-zero-delta-receipt")
        assert "NEW 0" in canvas
        assert "ALREADY PRESENT 0" in canvas
        assert "KEPT TARGET 1" in canvas
        assert "TOOK SOURCE 0" in canvas
        assert "TARGET CHANGED NO" in canvas

        child.send("\r")
        child.expect("ZERO DELTA VERIFICATION")
        canvas = _snapshot(recorder, "23-zero-delta-verification")
        assert "TARGET 'target revision'" in canvas
        assert "CHECKPOINTS 1" in canvas
        assert "kept Target 1; took Source 0" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_direct()
    _capture_multiple_and_bulk()
    _capture_failure_and_capability()
    _capture_cancel()
    _capture_complete_long_values()
    _capture_zero_delta_receipt()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if sys.argv[1:] == ["--child-long"]:
        sys.path.insert(0, str(ROOT / "src"))
        _run_long_child()
    elif sys.argv[1:] == ["--child-zero-delta"]:
        sys.path.insert(0, str(ROOT / "src"))
        _run_zero_delta_child()
    else:
        main()
