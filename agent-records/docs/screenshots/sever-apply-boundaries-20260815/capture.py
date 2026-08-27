"""Capture Sever Apply, recovery, and compensation in a 180x52 color PTY."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLS = 180
ROWS = 52


def _helpers():
    path = ROOT / "agent-records/docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    spec = importlib.util.spec_from_file_location("sever_capture_helpers", path)
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
    environment["PYTHONPATH"] = str(ROOT / "src")
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


def _wait(child, recorder, *needles: str, seconds: float = 12.0) -> None:
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


def _configure_store(store_root: Path) -> None:
    import memcommit.store as store_module

    for name, value in {
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
    }.items():
        setattr(store_module, name, value)


class _Provider:
    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        if operation != "sever_context":
            raise AssertionError(operation)
        from memcommit.sever_provider import SEVER_PAYLOAD_MARKER

        payload = json.loads(prompt.split(SEVER_PAYLOAD_MARKER, 1)[1])
        source = payload["source"]["memories"][0]
        criterion = payload["criteria"]["memories"][0]
        time.sleep(1.2)
        return json.dumps(
            {
                "overview": "The reviewed Result keeps the access requirement.",
                "application_summary": {
                    "text": "The access requirement is retained.",
                    "source_memory_ids": [],
                    "criterion_memory_ids": [],
                },
                "candidates": [
                    {
                        "source_memory_id": source["memory_id"],
                        "decision": "KEEP_AS_WRITTEN",
                        "proposed_content": source["content"],
                        "rationale": "The criterion permits this requirement.",
                        "criterion_memory_ids": [criterion["memory_id"]],
                    }
                ],
            }
        )


def _initialize(store):
    import memcommit.application.ops as ops

    if store.context_exists("sever/source"):
        return
    source = ops.init("sever/source")
    ops.add(source, "Needs step-free access.")
    criteria = ops.init("sever/criteria")
    ops.add(criteria, "Keep only necessary access requirements.")
    store.create_context(source)
    store.create_context(criteria)
    store.set_current(source.name)


def _child_apply(store_root: Path) -> None:
    import click
    import typer

    import memcommit.commands.shared.command_wait as command_wait
    import memcommit.commands.shared.session_help as session_help
    import memcommit.commands.sever.command as sever_command
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    sever_command.MemoryStore = lambda: store
    sever_command.connect_codex_chatgpt_provider = _Provider
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep the capture in command-group mode."""

    app.command("sever")(sever_command.cmd)
    try:
        app(
            args=[
                "sever",
                "--source",
                "sever/source",
                "--criteria",
                "sever/criteria",
                "--save-as",
                "sever/result",
                "--accept",
            ],
            prog_name="mem",
            standalone_mode=False,
        )
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise
    print(
        "DURABLE VERIFICATION · RESULT",
        store.context_exists("sever/result"),
        "· SOURCE MEMORIES",
        len(store.load_direct("sever/source").memories),
    )


def _child_verify(store_root: Path) -> None:
    from memcommit.commands.sever.command import render_sever
    from memcommit.sever_store import SeverSessionStore
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    session = SeverSessionStore(store).list()[0]
    print(render_sever(session))
    print(
        "READ-ONLY RESULT · MEMORIES",
        len(store.load_direct("sever/result").memories),
        "· CHECKPOINTS",
        len(store.list_checkpoints("sever/result")),
    )


def _child_restore(store_root: Path, direction: str) -> None:
    from memcommit.commands.shared.restoration_present import render_command_restore_receipt
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    result = store.restore_recent_context_command(direction)
    render_command_restore_receipt(result)
    print(
        f"{direction.upper()} VERIFICATION · RESULT",
        store.context_exists("sever/result"),
    )


def _review(store, output_name: str):
    from memcommit.sever_application import SeverAnalysisRequest
    from memcommit.sever_runtime import (
        execute_sever_analysis,
        execute_sever_session_start,
    )

    analysis = execute_sever_analysis(
        SeverAnalysisRequest(
            source_locator="sever/source",
            criteria_locator="sever/criteria",
            output_name=output_name,
        ),
        store=store,
        provider_factory=_Provider,
    )
    return execute_sever_session_start(analysis, store=store)


def _child_compensation(store_root: Path) -> None:
    import memcommit.sever_runtime as runtime
    from memcommit.sever_application import SeverPersistedApplyRequest
    from memcommit.sever_store import SeverSessionStore
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    started = _review(store, "sever/compensated")

    def fail_replace(self, session, *, expected_version):
        raise RuntimeError("injected session receipt failure")

    runtime.MemoryStoreSeverSessionRepository.replace = fail_replace
    try:
        runtime.execute_sever_session_apply(
            SeverPersistedApplyRequest(snapshot=started.snapshot),
            store=store,
        )
    except RuntimeError as error:
        print("APPLY FAILURE ·", error)
    print(
        "COMPENSATION · RESULT",
        store.context_exists("sever/compensated"),
        "· SESSION",
        SeverSessionStore(store).load(started.snapshot.session.uid).state,
    )


def _child_recovery(store_root: Path) -> None:
    from memcommit.commands.sever.command import render_sever
    from memcommit.sever_application import (
        SeverApplyRequest,
        SeverPersistedApplyRequest,
    )
    from memcommit.sever_runtime import (
        execute_sever_apply,
        execute_sever_session_apply,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    _initialize(store)
    started = _review(store, "sever/recovered")
    orphaned = execute_sever_apply(
        SeverApplyRequest(started.snapshot.session),
        store=store,
    )
    before_uid = orphaned.session.application.output_context_uid
    recovered = execute_sever_session_apply(
        SeverPersistedApplyRequest(snapshot=started.snapshot),
        store=store,
    )
    print(render_sever(recovered.snapshot.session))
    print(
        "INTERRUPTED APPLY RECOVERY · CREATED THIS TURN",
        recovered.created,
        "· SAME RESULT UID",
        recovered.snapshot.session.application.output_context_uid == before_uid,
    )


def _run_child(mode: str, store_root: Path) -> None:
    _configure_store(store_root)
    {
        "apply": _child_apply,
        "verify": _child_verify,
        "undo": lambda root: _child_restore(root, "undo"),
        "redo": lambda root: _child_restore(root, "redo"),
        "compensation": _child_compensation,
        "recovery": _child_recovery,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    HELPERS._pump(child, recorder, seconds=25, require_eof=True)
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-sever-apply-") as directory:
        root = Path(directory) / ".mem"
        child, recorder = _spawn("apply", root)
        _wait(child, recorder, "SEVER", "PENDING")
        HELPERS._snapshot(recorder, "01-analysis-pending")
        HELPERS._pump(child, recorder, seconds=25, require_eof=True)
        if "DURABLE VERIFICATION · RESULT True" not in recorder.getvalue():
            raise RuntimeError("Sever did not auto-apply its local Result.")
        HELPERS._snapshot(recorder, "02-all-keep-application-receipt")

        _capture_finished(
            "verify",
            root,
            "03-read-only-result-verification",
            "READ-ONLY RESULT · MEMORIES 1 · CHECKPOINTS 1",
        )
        _capture_finished("undo", root, "04-operation-undo", "RESULT False")
        _capture_finished("redo", root, "05-operation-redo", "RESULT True")

        _capture_finished(
            "compensation",
            Path(directory) / "compensation",
            "06-session-failure-compensated",
            "COMPENSATION · RESULT False · SESSION REVIEWING",
        )
        _capture_finished(
            "recovery",
            Path(directory) / "recovery",
            "07-interrupted-apply-recovered",
            "CREATED THIS TURN False · SAME RESULT UID True",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "52 180" not in raw or "\x1b[" not in raw:
        raise RuntimeError("Capture did not preserve the required color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
