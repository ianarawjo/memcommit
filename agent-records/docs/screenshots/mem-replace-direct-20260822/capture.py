"""Capture direct and compact Replace execution in a real color PTY."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/context-endpoint-memory-preview-20260810/capture.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "replace_direct_capture_base", _BASE_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _initialize(store) -> None:
    from memcommit.context import Context, Memory

    root = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="replace/demo",
    )
    root.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000001",
            content="The writer signs contracts; every writer revises drafts.",
        )
    )
    child = Context(
        uid="10000000-0000-4000-8000-000000000002",
        name="replace/demo/child",
    )
    child.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000002",
            content="A writer reviews the child draft.",
        )
    )
    store.create_context(root)
    store.create_context(child)
    store.set_current(root.name)


def _verification(store, *, label: str) -> str:
    from memcommit.context import Memory

    lines = [f"{label} · READ-ONLY STORE VERIFICATION"]
    checkpoint_count = 0
    for name in ("replace/demo", "replace/demo/child"):
        context = store.load_direct(name)
        for item in context.iter_items():
            if isinstance(item, Memory):
                lines.append(f"{name} [{item.uid[:8]}] · {item.content}")
        checkpoint_count += len(store.list_checkpoints(name))
    lines.append(f"CHECKPOINTS · {checkpoint_count}")
    return "\n".join(lines)


def _command_args(kind: str) -> list[str]:
    if kind == "direct":
        return ["replace", "writer", "author", "--context", "replace/demo"]
    if kind == "tui":
        return ["replace", "--context", "replace/demo"]
    if kind == "stale":
        return [
            "replace",
            "writer",
            "author",
            "--context",
            "replace/demo",
            "--tui",
        ]
    raise ValueError(f"Unknown capture kind: {kind}")


def _run_child(kind: str) -> None:
    import click
    import typer

    import memcommit.commands.replace.command as replace_command
    from memcommit.context import Context
    from memcommit.application.operations.replace.runtime import execute_replace_plan, plan_replace_with_store
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(
        prefix="memcommit-replace-direct-capture-"
    ) as directory:
        store = MemoryStore(root=Path(directory) / ".mem")
        _initialize(store)
        replace_command.MemoryStore = lambda create=False: store
        if kind == "stale":

            def stale_execute(request, *, store):
                plan, port = plan_replace_with_store(request, store=store)
                store.create_context(
                    Context(
                        uid="10000000-0000-4000-8000-000000000099",
                        name="replace/unrelated",
                    )
                )
                return execute_replace_plan(plan, port=port)

            replace_command.execute_replace_with_store = stale_execute

        args = _command_args(kind)
        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        print("COMMAND · mem " + " ".join(args))
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("replace")(replace_command.cmd)
        exit_code = 0
        try:
            returned = app(
                args=args,
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}", flush=True)
        sys.stdin.readline()
        print(_verification(store, label=kind.upper()), flush=True)
        sys.stdin.readline()


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        }
    )
    return environment


def _spawn(kind: str):
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


def _snapshot(recorder, stem: str) -> None:
    _BASE._snapshot(recorder, stem)


def _capture_direct() -> None:
    child, recorder = _spawn("direct")
    try:
        child.expect("COMMAND EXIT · 0")
        _snapshot(recorder, "01-direct-command-receipt")
        child.send("\r")
        child.expect("DIRECT · READ-ONLY STORE VERIFICATION")
        _snapshot(recorder, "02-direct-read-only-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_tui() -> None:
    child, recorder = _spawn("tui")
    try:
        child.expect("MEM REPLACE")
        _BASE._settle(child)
        _snapshot(recorder, "03-tui-entry")

        child.send("\x1b[Z\x1b[Z\x1b[Z\x1b[C")
        _BASE._settle(child)
        _snapshot(recorder, "04-tui-descendants-selected")

        child.send("\x1b[Z\r")
        _BASE._settle(child)
        _snapshot(recorder, "05-tui-scope-browse")

        # Send Escape separately: an Escape-prefixed Tab is encoded as an
        # alternate-key chord by real terminals rather than two gestures.
        child.send("\x1b")
        _BASE._settle(child)
        child.send("\t\t\t\twriter")
        _BASE._settle(child)
        _snapshot(recorder, "06-tui-find-entered")

        child.send("\rauthor")
        _BASE._settle(child)
        _snapshot(recorder, "07-tui-replacement-entered")

        child.send("\r")
        child.expect("COMMAND EXIT · 0")
        _snapshot(recorder, "08-tui-direct-apply-receipt")

        child.send("\r")
        child.expect("TUI · READ-ONLY STORE VERIFICATION")
        _snapshot(recorder, "09-tui-read-only-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        child.expect("MEM REPLACE")
        _BASE._settle(child)
        child.send("\r\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "10-stale-execution-stopped")

        child.send("\x1b")
        child.expect("COMMAND EXIT · 0")
        child.send("\r")
        child.expect("STALE · READ-ONLY STORE VERIFICATION")
        _snapshot(recorder, "11-stale-no-partial-write-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_direct()
    _capture_tui()
    _capture_stale()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "38;5" in raw or "38;2" in raw
    assert "48;5" in raw or "48;2" in raw
    assert "doesn't support cursor position requests" not in raw
    # Compact Replace stays on the primary screen. The only alternate-screen
    # tokens in this focused set would therefore be a regression.
    assert "\x1b[?1049h" not in raw

    direct = (OUT / "01-direct-command-receipt.txt").read_text(encoding="utf-8")
    assert "Replaced 2 occurrences in 1 Memory" in direct
    direct_verified = (OUT / "02-direct-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "The author signs contracts" in direct_verified
    assert "CHECKPOINTS · 1" in direct_verified
    tui_receipt = (OUT / "08-tui-direct-apply-receipt.txt").read_text(encoding="utf-8")
    assert "Replaced 3 occurrences in 2 Memories across 2 Contexts" in tui_receipt
    tui_verified = (OUT / "09-tui-read-only-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "A author reviews the child draft" in tui_verified
    assert "CHECKPOINTS · 2" in tui_verified
    stale = (OUT / "10-stale-execution-stopped.txt").read_text(encoding="utf-8")
    assert "CONTEXT NAMESPACE CHANGED DURING REPLACE EXECUTION" in stale
    unchanged = (OUT / "11-stale-no-partial-write-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "The writer signs contracts" in unchanged
    assert "CHECKPOINTS · 0" in unchanged


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
