"""Capture final-only Atomize Save As and its lifecycle in a 180x52 PTY."""

from __future__ import annotations

import click
import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect
import typer


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _helpers():
    path = ROOT / "docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    spec = importlib.util.spec_from_file_location("atomize_save_as_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load PTY capture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.COLS = COLS
    module.ROWS = ROWS
    return module


HELPERS = _helpers()


def _environment() -> dict[str, str]:
    environment = HELPERS._environment()
    environment["PYTHONPATH"] = str(ROOT)
    environment["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    return environment


def _spawn(mode: str, store_root: Path):
    command = (
        f"stty rows {ROWS} cols {COLS}; stty size; "
        f"exec {shlex.join([sys.executable, str(__file__), '--child', mode, str(store_root)])}"
    )
    recorder = HELPERS._Recorder()
    child = pexpect.spawn(
        "/bin/zsh",
        ["-f", "-c", command],
        cwd=str(ROOT),
        env=_environment(),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLS),
    )
    child.logfile_read = recorder
    child._mem_cpr_responses = 0
    return child, recorder


def _wait(child, recorder, *needles: str, seconds: float = 15.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        HELPERS._pump(child, recorder, seconds=0.1)
        visible = HELPERS._visible_text(recorder)
        if all(needle in visible for needle in needles):
            return
        if not child.isalive():
            break
    raise RuntimeError(
        f"PTY did not reach {needles!r}:\n{HELPERS._visible_text(recorder)}"
    )


class _Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        candidate_id = payload["memories"][0]["candidate_id"]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The Memory states one closing-time fact.",
                        "source_ids": [candidate_id],
                    },
                    "changed": {
                        "text": "No structural split is needed.",
                        "source_ids": [candidate_id],
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "The source has one independently revisable focus.",
                    }
                ],
                "quality_issues": [],
            }
        )


def _review(store) -> None:
    import memcommit.ops as ops
    from memcommit.atomize_workflow import open_or_create_atomize_workbench

    if not store.context_exists("atomize/source"):
        source = ops.init("atomize/source")
        ops.add(source, "The library entrance closes at five.")
        store.save(source)
        store.set_current(source.name)
    source = store.load_direct("atomize/source")
    if store.load_atomize_analysis(source.uid) is None:
        open_or_create_atomize_workbench(
            store=store,
            ctx=source,
            provider_factory=_Provider,
        )


def _invoke_atomize(store) -> None:
    import memcommit.commands.atomize as atomize_command

    atomize_command.MemoryStore = lambda *args, **kwargs: store
    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture command in group mode."""

    app.command("atomize")(atomize_command.cmd)
    try:
        app(
            args=[
                "atomize",
                "--context",
                "atomize/source",
                "--save-as",
                "atomize/output",
            ],
            prog_name="mem",
            standalone_mode=False,
        )
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _invoke_restore(store, direction: str) -> None:
    if direction == "undo":
        import memcommit.commands.undo as command
    else:
        import memcommit.commands.redo as command
    command.MemoryStore = lambda *args, **kwargs: store
    command.cmd()


def _status(store, label: str) -> None:
    source = store.load_direct("atomize/source")
    source_analysis = store.load_atomize_analysis(source.uid)
    workbench = store.load_atomize_workbench(source_analysis)
    exists = store.context_exists("atomize/output")
    checkpoints = len(store.list_checkpoints("atomize/output")) if exists else 0
    print(
        label,
        "· OUTPUT",
        exists,
        "· CHECKPOINTS",
        checkpoints,
        "· RECEIPT",
        workbench is not None and workbench.application is not None,
        "· CURRENT",
        store.current_context_name(),
    )


def _child_apply(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _review(store)
    _invoke_atomize(store)
    _status(store, "SAVE AS VERIFIED")


def _child_verify(store_root: Path) -> None:
    from memcommit.provenance import build_trace
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    source = store.load_direct("atomize/source")
    output = store.load_direct("atomize/output")
    memory_uid = next(iter(output.memories))
    trace = build_trace(store, output, memory_uid)
    print("READ-ONLY OUTPUT")
    print("  SOURCE UID", source.uid)
    print("  OUTPUT UID", output.uid)
    print("  MEMORIES", len(output.memories))
    print("  CHECKPOINT COMMANDS", ", ".join(
        checkpoint["command"] for checkpoint in store.list_checkpoints(output.name)
    ))
    print("  TRACE", " -> ".join(event.kind for event in trace.events))
    _status(store, "READ-ONLY VERIFIED")


def _child_undo(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke_restore(store, "undo")
    _status(store, "UNDO VERIFIED")


def _child_redo(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke_restore(store, "redo")
    _status(store, "REDO VERIFIED")


def _child_prepublication_failure(store_root: Path) -> None:
    from memcommit.atomize import AtomizeImpactError
    import memcommit.atomize_runtime as runtime
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _review(store)

    def reject(*_args, **_kwargs):
        raise AtomizeImpactError("injected prepublication failure")

    runtime.apply_atomize_analysis = reject
    try:
        _invoke_atomize(store)
    except click.exceptions.Exit:
        pass
    _status(store, "PREPUBLICATION FAILURE VERIFIED")


def _child_retry(store_root: Path) -> None:
    import memcommit.atomize_runtime as runtime
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _review(store)
    original = runtime.MemoryStoreAtomizeSessionRepository.replace_application
    failed_once = False

    def reject_once(repository, *args, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("injected Source receipt failure")
        return original(repository, *args, **kwargs)

    runtime.MemoryStoreAtomizeSessionRepository.replace_application = reject_once
    try:
        _invoke_atomize(store)
    except click.exceptions.Exit:
        pass
    _status(store, "RETAINED OUTPUT")
    print("RETRY READY")
    input("> press Enter to retry the exact retained output: ")
    _invoke_atomize(store)
    _status(store, "RETRY VERIFIED")


def _run_child(mode: str, store_root: Path) -> None:
    {
        "apply": _child_apply,
        "verify": _child_verify,
        "undo": _child_undo,
        "redo": _child_redo,
        "prepublication-failure": _child_prepublication_failure,
        "retry": _child_retry,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    HELPERS._pump(child, recorder, seconds=20, require_eof=True)
    if expected not in recorder.getvalue():
        raise RuntimeError(
            f"Capture {stem} missed {expected!r}:\n{HELPERS._visible_text(recorder)}"
        )
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-save-as-") as directory:
        root = Path(directory) / ".mem"
        child, recorder = _spawn("apply", root)
        _wait(child, recorder, "SAVE LOCATION", "NOT CREATED", "y = create atomized Context")
        HELPERS._snapshot(recorder, "01-exact-save-location-review")
        child.sendline("y")
        HELPERS._pump(child, recorder, seconds=20, require_eof=True)
        if "SAVE AS VERIFIED · OUTPUT True · CHECKPOINTS 1 · RECEIPT True" not in recorder.getvalue():
            raise RuntimeError("Final Save As did not publish one complete command.")
        HELPERS._snapshot(recorder, "02-one-checkpoint-success")

        _capture_finished(
            "verify",
            root,
            "03-read-only-final-result",
            "CHECKPOINT COMMANDS atomize",
        )
        _capture_finished(
            "undo",
            root,
            "04-one-command-undo",
            "UNDO VERIFIED · OUTPUT False · CHECKPOINTS 0 · RECEIPT False",
        )
        _capture_finished(
            "redo",
            root,
            "05-one-command-redo",
            "REDO VERIFIED · OUTPUT True · CHECKPOINTS 3 · RECEIPT True",
        )

        failure_root = Path(directory) / "prepublication"
        child, recorder = _spawn("prepublication-failure", failure_root)
        _wait(child, recorder, "SAVE LOCATION", "NOT CREATED")
        child.sendline("y")
        HELPERS._pump(child, recorder, seconds=20, require_eof=True)
        if "PREPUBLICATION FAILURE VERIFIED · OUTPUT False" not in recorder.getvalue():
            raise RuntimeError("Prepublication failure exposed a Context.")
        HELPERS._snapshot(recorder, "06-prepublication-failure")

        retry_root = Path(directory) / "retry"
        child, recorder = _spawn("retry", retry_root)
        _wait(child, recorder, "SAVE LOCATION", "NOT CREATED")
        child.sendline("y")
        _wait(child, recorder, "RETAINED OUTPUT", "RETRY READY", "press Enter to retry")
        HELPERS._snapshot(recorder, "07-retained-output-retry-review")
        child.sendline("")
        HELPERS._pump(child, recorder, seconds=20, require_eof=True)
        if "RETRY VERIFIED · OUTPUT True · CHECKPOINTS 1 · RECEIPT True" not in recorder.getvalue():
            raise RuntimeError("Retry did not adopt the one exact checkpoint.")
        HELPERS._snapshot(recorder, "08-retry-recovered")

    raw = "".join(
        path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript")
    )
    if "52 180" not in raw or "\x1b[" not in raw:
        raise RuntimeError("Capture did not preserve the required color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
