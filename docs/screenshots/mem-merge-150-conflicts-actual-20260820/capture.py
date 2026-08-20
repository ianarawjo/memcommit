"""Reproduce 150 real Merge conflicts and apply one reviewed bulk decision."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "docs/screenshots/mem-merge-150-conflicts-actual-20260820"
MERGE_CAPTURE = (
    ROOT / "docs/screenshots/mem-merge-conflict-resolution-20260815/capture.py"
)
UP = "\x1b[A"
RIGHT = "\x1b[C"
PAGE_DOWN = "\x1b[6~"
SHIFT_TAB = "\x1b[Z"

_SPEC = importlib.util.spec_from_file_location("merge_150_capture_base", MERGE_CAPTURE)
assert _SPEC is not None and _SPEC.loader is not None
_CAPTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CAPTURE)
_CAPTURE.OUT = OUT
_CAPTURE._BASE.OUT = OUT


def _memory_uid(index: int) -> str:
    return f"{index:08d}-0000-4000-8000-{index:012d}"


def _run_child() -> None:
    import click
    import typer

    import memcommit.ops as ops
    from memcommit.commands.merge import cmd as merge_command
    from memcommit.context import Memory
    from memcommit.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="mem-merge-150-capture-") as directory:
        _CAPTURE._configure_isolated_store(Path(directory) / ".mem")
        store = MemoryStore()
        source = ops.init("source")
        target = ops.init("target")
        for index in range(1, 151):
            uid = _memory_uid(index)
            source.add(
                Memory(
                    uid=uid,
                    content=f"SOURCE conflict {index:03d} · exact Source value",
                )
            )
            target.add(
                Memory(
                    uid=uid,
                    content=f"TARGET conflict {index:03d} · exact Target value",
                )
            )
        store.create_context(source)
        store.create_context(target)
        store.set_current("target")

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        print(
            "PRE-MERGE · SOURCE MEMORIES 150 · TARGET MEMORIES 150 · "
            "SAME UIDS 150 · DIVERGENT BODIES 150",
            flush=True,
        )
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
        merged = store.load_direct("target")
        all_source = all(
            merged.memories[_memory_uid(index)].content
            == f"SOURCE conflict {index:03d} · exact Source value"
            for index in range(1, 151)
        )
        print(
            "POST-MERGE VERIFICATION\n"
            f"TARGET MEMORIES · {len(merged.memories)}\n"
            f"ALL 150 SOURCE VALUES · {all_source}\n"
            f"FIRST · {merged.memories[_memory_uid(1)].content!r}\n"
            f"LAST · {merged.memories[_memory_uid(150)].content!r}\n"
            f"CHECKPOINTS · {len(store.list_checkpoints('target'))}",
            flush=True,
        )
        sys.stdin.readline()


def _spawn() -> tuple[pexpect.spawn, io.StringIO]:
    recorder = _CAPTURE._BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(ROOT),
        env=_CAPTURE._environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=40,
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
        child.expect("NEW MERGE")
        child.send("\t\t\t\r")
        child.expect("MERGE REVIEW · 150 conflicts")
        _CAPTURE._BASE._settle(child, seconds=1.0)
        canvas = _snapshot(recorder, "01-conflicts-1-through-viewport")
        assert "MERGE REVIEW · 150 conflicts" in canvas
        assert '1 · [00000001]   SOURCE "SOURCE conflict 001' in canvas
        assert '✓ TARGET "TARGET conflict 001' in canvas
        assert "CONTROLS" in canvas
        assert "BULK DECISION · ✓ KEEP ALL TARGET" in canvas
        assert "APPLY · READY" in canvas

        child.send("\t")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "02-tab-direct-to-apply")
        assert "› APPLY · READY" in canvas
        assert '1 · [00000001]   SOURCE "SOURCE conflict 001' in canvas

        child.send(SHIFT_TAB)
        child.send(PAGE_DOWN)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "03-conflicts-middle-page")
        assert "SOURCE conflict 0" in canvas
        assert "✓ TARGET" in canvas

        child.send(PAGE_DOWN)
        _CAPTURE._BASE._settle(child)
        child.send(PAGE_DOWN)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "04-conflict-150-and-controls")
        assert '150 · [00000150]   SOURCE "SOURCE conflict 150' in canvas
        assert '✓ TARGET "TARGET conflict 150' in canvas
        assert "BULK DECISION · ✓ KEEP ALL TARGET /   TAKE ALL SOURCE" in canvas
        assert "APPLY · READY" in canvas

        child.send("\t")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "05-tab-from-bottom-to-apply")
        assert "› APPLY · READY" in canvas
        assert '150 · [00000150]   SOURCE "SOURCE conflict 150' in canvas

        child.send(UP)
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "06-bulk-row-focused")
        assert "› BULK DECISION · ✓ KEEP ALL TARGET" in canvas

        child.send(RIGHT + "\r")
        _CAPTURE._BASE._settle(child, seconds=1.0)
        canvas = _snapshot(recorder, "07-all-150-source-staged")
        assert '150 · [00000150] ✓ SOURCE "SOURCE conflict 150' in canvas
        assert "BULK DECISION ·   KEEP ALL TARGET / ✓ TAKE ALL SOURCE" in canvas
        assert "› APPLY · READY" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child)
        canvas = _snapshot(recorder, "08-exact-take-all-review")
        assert "APPLY CONFIRMATION · EXACT WHOLE SET" in canvas
        assert "--take-source-all" in canvas
        assert "KEEP TARGET 0 · TAKE SOURCE 150" in canvas
        assert "› APPLY EXACT WHOLE SET" in canvas

        child.send("\r")
        _CAPTURE._BASE._settle(child, seconds=2.0)
        canvas = _snapshot(recorder, "09-applied-150-receipt")
        assert "MERGE RECORDED" in canvas
        assert "KEPT TARGET · 0" in canvas
        assert "TOOK SOURCE · 150" in canvas
        assert "TARGET CHANGED · YES" in canvas
        assert "CHECKPOINTS · 1" in canvas

        child.send("\r")
        child.expect("POST-MERGE VERIFICATION")
        canvas = _snapshot(recorder, "10-read-only-verification")
        assert "TARGET MEMORIES · 150" in canvas
        assert "ALL 150 SOURCE VALUES · True" in canvas
        assert "SOURCE conflict 001" in canvas
        assert "SOURCE conflict 150" in canvas
        assert "CHECKPOINTS 1" in canvas
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "\x1b[" in raw
    assert "38;" in raw
    assert "48;" in raw


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        sys.path.insert(0, str(ROOT))
        _run_child()
    else:
        main()
