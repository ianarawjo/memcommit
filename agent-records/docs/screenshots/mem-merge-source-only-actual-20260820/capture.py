"""Capture an actual Source-only Memory copied into Target by Merge."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/docs/screenshots/mem-merge-source-only-actual-20260820"
MERGE_CAPTURE = (
    ROOT / "agent-records/docs/screenshots/mem-merge-conflict-resolution-20260815/capture.py"
)

_SPEC = importlib.util.spec_from_file_location(
    "actual_merge_capture_base", MERGE_CAPTURE
)
assert _SPEC is not None and _SPEC.loader is not None
_CAPTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CAPTURE)
_CAPTURE.OUT = OUT
_CAPTURE._BASE.OUT = OUT


def _pause(label: str) -> None:
    print(label, flush=True)
    sys.stdin.readline()


def _run_child() -> None:
    import click
    import typer

    import memcommit.application.ops as ops
    from memcommit.adapters.console.commands.merge.command import cmd as merge_command
    from memcommit.adapters.console.commands.show.command import cmd as show_command
    from memcommit.context import Memory
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-merge-actual-capture-") as directory:
        _CAPTURE._configure_isolated_store(Path(directory) / ".mem")
        store = MemoryStore()
        memory_uid = "4f8f9b10-1111-4222-8333-123456789abc"
        memory_content = (
            "This Memory existed only in Source before Merge.\n"
            "Merge copies this exact body into Target.\n"
            "Final line: copied byte-for-byte."
        )
        source = ops.init("source")
        source.add(Memory(uid=memory_uid, content=memory_content))
        target = ops.init("target")
        store.create_context(source)
        store.create_context(target)
        store.set_current("target")

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        print("PRE-MERGE · SOURCE MEMORIES 1 · TARGET MEMORIES 0")
        print("RUN · mem merge source --into target --direct", flush=True)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapters."""

        app.command("merge")(merge_command)
        app.command("show")(show_command)
        exit_code = 0
        try:
            returned = app(
                args=["merge", "source", "--into", "target", "--direct"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        _pause("MERGE RECEIPT COMPLETE")

        print("RUN · mem show --context target", flush=True)
        show_exit = 0
        try:
            returned = app(
                args=["show", "--context", "target"],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            show_exit = error.exit_code
        else:
            if isinstance(returned, int):
                show_exit = returned
        print(f"SHOW EXIT · {show_exit}")
        copied = store.load_direct("target").memories[memory_uid]
        print(
            f"POST-MERGE · TARGET UID {copied.uid[:8]} · "
            f"CHECKPOINTS {len(store.list_checkpoints('target'))}",
            flush=True,
        )
        _pause("SHOW VERIFICATION COMPLETE")


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _CAPTURE._BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_CAPTURE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=20,
        dimensions=(_CAPTURE.ROWS, _CAPTURE.COLUMNS),
    )
    child.logfile_read = recorder
    return child, recorder


def _snapshot(recorder: io.StringIO, stem: str) -> str:
    _CAPTURE._snapshot(recorder, stem)
    return (OUT / f"{stem}.txt").read_text(encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    child, recorder = _spawn()
    try:
        child.expect("MERGE RECEIPT COMPLETE")
        canvas = _snapshot(recorder, "01-actual-merge-receipt")
        assert "PRE-MERGE · SOURCE MEMORIES 1 · TARGET MEMORIES 0" in canvas
        assert "NEW 1 (1 memory)" in canvas
        assert "TARGET CHANGED YES" in canvas
        assert "CHECKPOINTS 1" in canvas

        child.send("\r")
        child.expect("SHOW VERIFICATION COMPLETE")
        canvas = _snapshot(recorder, "02-actual-target-show")
        assert "This Memory existed only in Source before Merge." in canvas
        assert "Merge copies this exact body into Target." in canvas
        assert "Final line: copied byte-for-byte." in canvas
        assert "POST-MERGE · TARGET UID 4f8f9b10 · CHECKPOINTS 1" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "\x1b[32m" in raw
    assert "\x1b[1m" in raw


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        sys.path.insert(0, str(ROOT / "src"))
        _run_child()
    else:
        main()
