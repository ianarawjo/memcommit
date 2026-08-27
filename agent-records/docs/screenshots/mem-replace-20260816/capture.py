"""Capture deterministic Replace review and stale rejection in a real PTY."""

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
_SPEC = importlib.util.spec_from_file_location("replace_capture_base", _BASE_PATH)
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
            content="Campus access closes at 5 p.m.; Campus parking remains open.",
        )
    )
    child = Context(
        uid="10000000-0000-4000-8000-000000000002",
        name="replace/demo/child",
    )
    child.add(
        Memory(
            uid="20000000-0000-4000-8000-000000000002",
            content="Campus library routes remain accessible.",
        )
    )
    store.create_context(root)
    store.create_context(child)
    store.set_current(root.name)


def _verification(store, *, stale: bool) -> str:
    from memcommit.context import Memory

    contents = []
    checkpoints = []
    for name in ("replace/demo", "replace/demo/child"):
        context = store.load_direct(name)
        contents.extend(
            item.content for item in context.iter_items() if isinstance(item, Memory)
        )
        checkpoints.extend(store.list_checkpoints(name))
    return (
        f"{'STALE' if stale else 'APPLY'} VERIFICATION · "
        f"MEMORIES {contents!r} · CHECKPOINTS {len(checkpoints)}"
    )


def _run_child(kind: str) -> None:
    import click
    import typer

    import memcommit.commands.replace.command as replace_command
    from memcommit.context import Context
    from memcommit.persistence.store import MemoryStore

    with tempfile.TemporaryDirectory(prefix="memcommit-replace-capture-") as directory:
        store = MemoryStore(root=Path(directory) / ".mem")
        _initialize(store)
        replace_command.MemoryStore = lambda create=False: store
        if kind == "stale":
            original_apply = replace_command.execute_replace_plan

            def stale_apply(plan, *, port):
                store.create_context(
                    Context(
                        uid="10000000-0000-4000-8000-000000000099",
                        name="replace/unrelated",
                    )
                )
                return original_apply(plan, port=port)

            replace_command.execute_replace_plan = stale_apply

        print("PTY", os.get_terminal_size().columns, os.get_terminal_size().lines)
        app = typer.Typer()

        @app.callback()
        def capture_root() -> None:
            """Keep Typer in command-group mode for the focused adapter."""

        app.command("replace")(replace_command.cmd)
        exit_code = 0
        try:
            returned = app(
                args=[
                    "replace",
                    "Campus",
                    "University",
                    "--context",
                    "replace/demo",
                    "--tui",
                ],
                prog_name="mem",
                standalone_mode=False,
            )
        except click.exceptions.Exit as error:
            exit_code = error.exit_code
        else:
            if isinstance(returned, int):
                exit_code = returned
        print(f"COMMAND EXIT · {exit_code}")
        print(_verification(store, stale=kind == "stale"), flush=True)
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


def _scope_and_plan(child: pexpect.spawn, recorder) -> None:
    child.expect("MEM REPLACE")
    _BASE._settle(child)
    _snapshot(recorder, "01-entry")

    child.send("\t\t")
    _BASE._settle(child)
    _snapshot(recorder, "02-local-context-target")

    child.send("\t")
    _BASE._settle(child)
    _snapshot(recorder, "03-scope-controls")

    child.send("\x1b[B\x1b[C")
    _BASE._settle(child)
    _snapshot(recorder, "04-descendant-scope-selected")

    child.send("\r")
    _BASE._settle(child)
    _snapshot(recorder, "05-complete-before-after-review")

    child.send("\t")
    _BASE._settle(child)
    _snapshot(recorder, "06-exact-command-approval")


def _capture_apply() -> None:
    child, recorder = _spawn("apply")
    try:
        _scope_and_plan(child, recorder)
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "07-atomic-apply-receipt")
        child.send("\r")
        child.expect("APPLY VERIFICATION")
        _snapshot(recorder, "08-read-only-store-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale_rejection() -> None:
    child, recorder = _spawn("stale")
    try:
        _scope_and_plan(child, recorder)
        child.send("\r")
        _BASE._settle(child, seconds=0.8)
        _snapshot(recorder, "09-stale-namespace-rejected")
        child.send("q")
        child.expect("STALE VERIFICATION")
        _snapshot(recorder, "10-stale-no-partial-write-verification")
        child.send("\r")
        child.expect(pexpect.EOF)
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _capture_apply()
    _capture_stale_rejection()
    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    assert "PTY 180 52" in raw
    assert "38;5" in raw or "38;2" in raw
    assert "48;5" in raw or "48;2" in raw

    receipt = (OUT / "07-atomic-apply-receipt.txt").read_text(encoding="utf-8")
    assert "STATUS · APPLIED" in receipt
    verified = (OUT / "08-read-only-store-verification.txt").read_text(encoding="utf-8")
    assert "University access" in verified
    stale = (OUT / "09-stale-namespace-rejected.txt").read_text(encoding="utf-8")
    assert "CONTEXT NAMESPACE CHANGED AFTER THE COMMAND WAS REVIEWED" in stale
    unchanged = (OUT / "10-stale-no-partial-write-verification.txt").read_text(
        encoding="utf-8"
    )
    assert "Campus access" in unchanged
    assert "CHECKPOINTS 0" in unchanged


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _run_child(sys.argv[2])
    else:
        main()
