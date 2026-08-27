"""Capture Atomize in-place Apply boundaries in a 180x52 color PTY."""

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
    path = ROOT / "agent-records/docs/screenshots/study-full-replay-20260811/capture_init_study.py"
    spec = importlib.util.spec_from_file_location("atomize_capture_helpers", path)
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


class _Provider:
    """Return one exhaustive, deterministic assessment with one open issue."""

    def complete(self, prompt, *, operation, output_schema=None):
        if operation != "impact_atomize" or output_schema is None:
            raise AssertionError(operation)
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        ids = [item["candidate_id"] for item in payload["memories"]]
        source_id = ids[0]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The note states one closing-time instruction.",
                        "source_ids": ids,
                    },
                    "changed": {
                        "text": "The original Memory remains intact.",
                        "source_ids": ids,
                    },
                    "unresolved": {
                        "text": "The applicable day remains unresolved.",
                        "source_ids": ids,
                    },
                },
                "items": [
                    {
                        "candidate_id": candidate_id,
                        "classification": "UNCERTAIN",
                        "reason_codes": ["A06_NO_HIDDEN_CONTEXT"],
                        "children": [],
                        "reason": "The statement does not identify the applicable day.",
                    }
                    for candidate_id in ids
                ],
                "quality_issues": [
                    {
                        "kind": "AMBIGUITY",
                        "source_ids": [source_id],
                        "interpretation": "DOMINANT",
                        "clarification": "REQUIRED",
                        "conflict": "NONE",
                        "ordinary_readings": [
                            {
                                "label": "Every day",
                                "text": "The entrance closes at five every day.",
                            },
                            {
                                "label": "Weekdays",
                                "text": "The entrance closes at five on weekdays.",
                            },
                        ],
                        "scope_dimensions": [],
                        "reason": "The day scope is omitted.",
                        "question": "Does the closing time apply every day or on weekdays?",
                    }
                ],
            }
        )


def _initialize(store):
    import memcommit.application.ops as ops

    if store.context_exists("atomize/apply-boundary"):
        return
    context = ops.init("atomize/apply-boundary")
    ops.add(context, "The library entrance closes at five.")
    store.save(context)
    store.set_current(context.name)


def _review(store):
    from memcommit.atomize_workflow import open_or_create_atomize_workbench

    _initialize(store)
    context = store.load_direct("atomize/apply-boundary")
    return open_or_create_atomize_workbench(
        store=store,
        ctx=context,
        provider_factory=_Provider,
    )


def _invoke_save(store) -> None:
    import memcommit.commands.atomize.command as atomize_command
    import memcommit.commands.shared.command_wait as command_wait
    import memcommit.commands.shared.session_help as session_help

    atomize_command.MemoryStore = lambda *args, **kwargs: store
    command_wait.current_help_entries = lambda: ()
    session_help.current_help_entries = lambda: ()
    app = typer.Typer()

    @app.callback()
    def capture_root() -> None:
        """Keep this capture in command-group mode."""

    app.command("atomize")(atomize_command.cmd)
    try:
        app(
            args=[
                "atomize",
                "--context",
                "atomize/apply-boundary",
                "--save",
            ],
            prog_name="mem",
            standalone_mode=False,
        )
    except click.exceptions.Exit as error:
        if error.exit_code:
            raise


def _child_review(store_root: Path) -> None:
    from memcommit.interfaces.tui.operations.atomize.screen import (
        run_atomize_workbench_shell,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    opened = _review(store)
    action = run_atomize_workbench_shell(
        opened.workbench,
        opened.analysis,
        save=store.save_atomize_workbench,
        workflow_actions=False,
    )
    print("REVIEW CLOSED · SESSION RETAINED", action is opened.workbench)
    print(
        "DURABLE BEFORE APPLY · CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
    )


def _child_apply(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    _invoke_save(store)
    workbench = store.load_atomize_workbench(
        store.load_atomize_analysis(store.load_direct("atomize/apply-boundary").uid)
    )
    print(
        "DURABLE APPLY · CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
        "· RECEIPT",
        workbench is not None and workbench.application is not None,
    )


def _child_verify(store_root: Path) -> None:
    from memcommit.interfaces.tui.operations.atomize.screen import (
        render_atomize_workbench_snapshot,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root, create=False)
    context = store.load_direct("atomize/apply-boundary")
    analysis = store.load_atomize_analysis(context.uid)
    workbench = store.load_atomize_workbench(analysis)
    print(render_atomize_workbench_snapshot(workbench, analysis, show_all=True))
    print(
        "READ-ONLY VERIFICATION · MEMORIES",
        len(context.memories),
        "· CHECKPOINTS",
        len(store.list_checkpoints(context.name)),
        "· RECEIPT",
        workbench is not None and workbench.application is not None,
    )


def _child_compensation(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    opened = _review(store)
    original = MemoryStore._save_atomize_workbench_locked

    def reject_terminal(self, session):
        if session.application is not None:
            raise OSError("injected terminal receipt failure")
        return original(self, session)

    MemoryStore._save_atomize_workbench_locked = reject_terminal
    try:
        _invoke_save(store)
    except click.exceptions.Exit as error:
        print("APPLY EXIT ·", error.exit_code)
    retained = store.load_atomize_workbench(opened.analysis)
    print(
        "COMPENSATION · CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
        "· RECEIPT",
        retained is not None and retained.application is not None,
    )


def _child_late_success(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    opened = _review(store)
    original = MemoryStore._save_atomize_workbench_locked

    def commit_then_fail(self, session):
        result = original(self, session)
        if session.application is not None:
            raise OSError("injected late receipt failure")
        return result

    MemoryStore._save_atomize_workbench_locked = commit_then_fail
    _invoke_save(store)
    terminal = store.load_atomize_workbench(opened.analysis)
    print(
        "LATE SUCCESS · CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
        "· RECEIPT",
        terminal is not None and terminal.application is not None,
    )


def _child_recovery(store_root: Path) -> None:
    from memcommit.atomize_application import atomize_application_audit
    from memcommit.atomize_runtime import (
        MemoryStoreAtomizeOutputPort,
        capture_atomize_session_snapshot,
    )
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    opened = _review(store)
    snapshot = capture_atomize_session_snapshot(
        store=store,
        analysis=opened.analysis,
        expected_workbench=opened.workbench,
    )
    orphaned = MemoryStoreAtomizeOutputPort(store).materialize(
        snapshot,
        atomize_application_audit(snapshot.analysis, snapshot.workbench),
    )
    print(
        "INTERRUPTED PRECONDITION · CHECKPOINT",
        orphaned.checkpoint_uid[:8],
        "· RECEIPT False",
    )
    _invoke_save(store)
    terminal = store.load_atomize_workbench(opened.analysis)
    print(
        "RECOVERY · SAME CHECKPOINT",
        terminal.application.checkpoint_uid == orphaned.checkpoint_uid,
        "· CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
    )


def _child_race(store_root: Path) -> None:
    from memcommit.store import MemoryStore

    store = MemoryStore(root=store_root)
    opened = _review(store)
    original = MemoryStore._save_command_locked

    def save_then_revise(self, *args, **kwargs):
        checkpoint = original(self, *args, **kwargs)
        auto_checkpoint = args[1] if len(args) > 1 else None
        if auto_checkpoint is not None and auto_checkpoint.command == "atomize":
            analysis = self.load_atomize_analysis(opened.analysis.context_uid)
            revised = self.load_atomize_workbench(analysis)
            revised.toggle_sort()
            self.save_atomize_workbench(revised)
        return checkpoint

    MemoryStore._save_command_locked = save_then_revise
    try:
        _invoke_save(store)
    except click.exceptions.Exit as error:
        print("APPLY EXIT ·", error.exit_code)
    latest = store.load_atomize_workbench(opened.analysis)
    print(
        "CAS COMPENSATION · CHECKPOINTS",
        len(store.list_checkpoints("atomize/apply-boundary")),
        "· NEWER REVIEW PRESERVED",
        latest is not None and latest.sort_mode != opened.workbench.sort_mode,
    )


def _run_child(mode: str, store_root: Path) -> None:
    {
        "review": _child_review,
        "apply": _child_apply,
        "verify": _child_verify,
        "compensation": _child_compensation,
        "late-success": _child_late_success,
        "recovery": _child_recovery,
        "race": _child_race,
    }[mode](store_root)


def _capture_finished(mode: str, root: Path, stem: str, expected: str) -> None:
    child, recorder = _spawn(mode, root)
    try:
        HELPERS._pump(child, recorder, seconds=25, require_eof=True)
    except RuntimeError as error:
        raise RuntimeError(
            f"Capture {stem} failed:\n{HELPERS._visible_text(recorder)}"
        ) from error
    if expected not in recorder.getvalue():
        raise RuntimeError(f"Capture {stem} missed {expected!r}.")
    HELPERS._snapshot(recorder, stem)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memcommit-atomize-apply-") as directory:
        root = Path(directory) / ".mem"
        child, recorder = _spawn("review", root)
        _wait(child, recorder, "WHAT MEM UNDERSTOOD", "ACTIONABLE FINDINGS")
        HELPERS._snapshot(recorder, "01-reviewed-analysis")
        child.send("q")
        HELPERS._pump(child, recorder, seconds=15, require_eof=True)
        if "REVIEW CLOSED · SESSION RETAINED True" not in recorder.getvalue():
            raise RuntimeError("Atomize review did not retain its saved session.")

        _capture_finished(
            "apply",
            root,
            "02-application-receipt",
            "DURABLE APPLY · CHECKPOINTS 1 · RECEIPT True",
        )
        _capture_finished(
            "verify",
            root,
            "03-read-only-verification",
            "READ-ONLY VERIFICATION · MEMORIES 1 · CHECKPOINTS 1 · RECEIPT True",
        )
        _capture_finished(
            "compensation",
            Path(directory) / "compensation",
            "04-receipt-failure-compensated",
            "COMPENSATION · CHECKPOINTS 0 · RECEIPT False",
        )
        _capture_finished(
            "late-success",
            Path(directory) / "late-success",
            "05-late-success-reread",
            "LATE SUCCESS · CHECKPOINTS 1 · RECEIPT True",
        )
        recovery_root = Path(directory) / "recovery"
        _capture_finished(
            "recovery",
            recovery_root,
            "06-interrupted-checkpoint-recovered",
            "RECOVERY · SAME CHECKPOINT True · CHECKPOINTS 1",
        )
        _capture_finished(
            "verify",
            recovery_root,
            "07-recovery-read-only-verification",
            "READ-ONLY VERIFICATION · MEMORIES 1 · CHECKPOINTS 1 · RECEIPT True",
        )
        _capture_finished(
            "race",
            Path(directory) / "race",
            "08-workbench-race-compensated",
            "CAS COMPENSATION · CHECKPOINTS 0 · NEWER REVIEW PRESERVED True",
        )

    raw = "".join(path.read_text(encoding="utf-8") for path in OUT.glob("*.typescript"))
    if "52 180" not in raw or "\x1b[" not in raw or "38;2" not in raw:
        raise RuntimeError("Capture did not preserve the required true-color PTY.")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _run_child(sys.argv[2], Path(sys.argv[3]))
    else:
        main()
