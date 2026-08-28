"""Capture START, TURN, and commandless Apply boundaries in 180x52 PTYs."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = ROOT / "agent-records/docs/screenshots/atomize-memory-selection-20260814/capture.py"
_SPEC = importlib.util.spec_from_file_location("semantic_command_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLUMNS = COLUMNS
_BASE.ROWS = ROWS


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PROMPT_TOOLKIT_COLOR_DEPTH": "DEPTH_24_BIT",
            "PROMPT_TOOLKIT_NO_CPR": "1",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
            "PYTHONPATH": str(ROOT / "src"),
        }
    )
    return environment


def _print_terminal() -> None:
    size = os.get_terminal_size()
    print(f"PTY · {size.columns} columns × {size.lines} rows", flush=True)
    if (size.columns, size.lines) != (COLUMNS, ROWS):
        raise RuntimeError("Capture PTY dimensions are not 180×52.")


def _meld_start() -> None:
    from memcommit.adapters.interfaces.tui.operations.meld import (
        MeldTuiSetup,
        choose_meld_endpoint_setup,
    )

    _print_terminal()
    result = choose_meld_endpoint_setup(
        MeldTuiSetup(
            names=("capture/incoming", "capture/baseline", "capture/empty"),
            left_name="capture/incoming",
            right_name="capture/baseline",
            eligible_target_names=frozenset({"capture/empty"}),
            current_context="capture/incoming",
        ),
        memory_loader=lambda _role, _name: (),
    )
    print(f"\nSTART RECEIPT · MELD · {result!r}")
    print("DURABLE STATE · UNCHANGED · PROVIDER CALLS 0", flush=True)


def _update_start() -> None:
    from memcommit.adapters.interfaces.tui.operations.update import (
        UpdateTuiSetup,
        choose_update_endpoint_setup,
    )

    _print_terminal()
    result = choose_update_endpoint_setup(
        UpdateTuiSetup(
            names=("capture/source", "capture/target"),
            source_name="capture/source",
            target_name="capture/target",
            current_context="capture/source",
        ),
        memory_loader=lambda _role, _name: (),
    )
    print(f"\nSTART RECEIPT · UPDATE · {result!r}")
    print("DURABLE STATE · UNCHANGED · PROVIDER CALLS 0", flush=True)


def _sever_start() -> None:
    from memcommit.adapters.console.commands.sever.setup import choose_sever_setup

    _print_terminal()
    result = choose_sever_setup(
        ("capture/source", "capture/criteria"),
        current="capture/source",
    )
    print(f"\nSTART RECEIPT · SEVER · {result!r}")
    print("DURABLE STATE · UNCHANGED · PROVIDER CALLS 0", flush=True)


def _update_view(*, accept_only: bool = False):
    from memcommit.application.capabilities.resolution.workbench import (
        ResolutionItem,
        ResolutionWorkbenchView,
    )

    items = ()
    capabilities = frozenset({"ACCEPT"})
    if not accept_only:
        items = (
            ResolutionItem(
                uid="change-1",
                kind="EDIT",
                status="OPEN",
                priority="CHANGE",
                title="capture/target Memory [11111111]",
                summary="The staged wording can be narrowed before Apply.",
                role="CHANGE",
                obligation="NONE",
                response_state="NOT_APPLICABLE",
                commentable=True,
            ),
        )
        capabilities = frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"})
    return ResolutionWorkbenchView(
        operation="UPDATE",
        artifact_uid="capture-update",
        revision="capture-revision-1",
        title="MEM UPDATE",
        route="SOURCE capture/source → TARGET capture/target",
        status="STAGED",
        metrics=(),
        overview="Review the exact staged target change. Nothing has been applied.",
        list_label="PLANNED CHANGES",
        items=items,
        empty_message="No planned changes.",
        results_label="APPLICATION",
        results=(),
        capabilities=capabilities,
        accept_enabled=True,
        accept_mode="AS_IS" if accept_only else "CHANGES",
    )


def _turn() -> None:
    from memcommit.adapters.console.coordination.command_review import (
        update as update_command_review,
    )
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        ResolutionGlobalStrategy,
        run_resolution_workbench_shell,
    )

    _print_terminal()
    action = run_resolution_workbench_shell(
        _update_view(),
        split_viewer_items=True,
        review_and_apply=True,
        decision_free_behavior="REPORT_FIRST",
        global_strategies=(
            ResolutionGlobalStrategy(
                "Revise from comments",
                "SUBMIT_ALL",
                "Revise the complete Update proposal from saved comments.",
            ),
        ),
        turn_command_review=lambda proposed: (
            update_command_review.build_turn_review(
                source_name="capture/source",
                target_name="capture/target",
                source_descendants=False,
                target_descendants=False,
                source_memory_uid=None,
                target_memory_uid=None,
                comment=proposed.comment,
                expected_session="a" * 64,
            )
            if proposed.kind == "SUBMIT_ALL"
            else None
        ),
    )
    print(f"\nTURN RECEIPT · {action.kind}")
    print("SAVED SESSION REVISION · WOULD REBUILD AFTER EXECUTION")
    print("FINAL APPLY · NOT RUN · DURABLE CONTEXT STATE UNCHANGED", flush=True)


def _apply_review() -> None:
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        run_resolution_workbench_shell,
    )

    _print_terminal()
    action = run_resolution_workbench_shell(
        _update_view(accept_only=True),
        split_viewer_items=True,
        review_and_apply=True,
        decision_free_behavior="FINAL_REVIEW",
        turn_command_review=lambda _proposed: None,
    )
    print(f"\nFINAL REVIEW RECEIPT · {action.kind}")
    print("COMMAND SECTION · INTENTIONALLY ABSENT")
    print("APPLY · NOT RUN AFTER ESCAPE · DURABLE CONTEXT STATE UNCHANGED", flush=True)


def _configure_store(root: Path) -> None:
    import memcommit.persistence.store as store_module

    for name, value in {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }.items():
        setattr(store_module, name, value)


def _stale_turn() -> None:
    import click

    with tempfile.TemporaryDirectory(prefix="stale-update-command-") as directory:
        _configure_store(Path(directory) / ".mem")
        import memcommit.application.capabilities.ops as ops
        from memcommit.adapters.console.entrypoint import app
        from memcommit.persistence.store import MemoryStore
        from memcommit.application.operations.update.model import plan_update, update_session_record_digest
        from tests.test_update import PlanProvider, _one_edit_response

        store = MemoryStore()
        source = ops.init("capture/source")
        ops.add(source, "New verified wording.")
        target = ops.init("capture/target")
        ops.add(target, "Old wording.")
        store.create_context(source)
        store.create_context(target)
        staged = plan_update(
            source,
            target,
            lambda: PlanProvider(_one_edit_response),
            status="staged",
        )
        store.save_staged_update(staged, expected_current=None)
        before = update_session_record_digest(staged)
        argv = [
            "update",
            "--from",
            source.name,
            "--to",
            target.name,
            "--comment",
            "Use a narrower claim.",
            "--expect-session",
            "0" * 64,
        ]
        _print_terminal()
        print("$ mem " + " ".join(argv), flush=True)
        try:
            app(args=argv, prog_name="mem", standalone_mode=False)
        except click.exceptions.Exit as error:
            if error.exit_code != 1:
                raise
        after = store.load_staged_update()
        print("STALE TURN RECEIPT · REJECTED BEFORE PROVIDER", flush=True)
        print(
            "SAVED SESSION UNCHANGED ·",
            after is not None and update_session_record_digest(after) == before,
        )
        print("TARGET CONTEXT UNCHANGED · CHECKPOINTS 0", flush=True)


def _child(kind: str) -> None:
    {
        "meld-start": _meld_start,
        "update-start": _update_start,
        "sever-start": _sever_start,
        "turn": _turn,
        "apply": _apply_review,
        "stale": _stale_turn,
    }[kind]()


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


def _capture_start(
    kind: str,
    title: str,
    command_keys: str,
    stems: tuple[str, str, str],
) -> None:
    child, recorder = _spawn(kind)
    try:
        child.expect(title)
        _BASE._settle(child)
        _snapshot(recorder, stems[0])
        child.send(command_keys)
        child.expect("COMMAND .* RUNNABLE")
        _BASE._settle(child)
        _snapshot(recorder, stems[1])
        child.send("\r")
        child.expect("START RECEIPT")
        child.expect("DURABLE STATE .* UNCHANGED")
        child.expect(pexpect.EOF)
        _snapshot(recorder, stems[2])
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_turn() -> None:
    child, recorder = _spawn("turn")
    try:
        child.expect("MEM UPDATE")
        _BASE._settle(child)
        _snapshot(recorder, "10-turn-entry")
        child.send("\t\x1b[B\r\t\rUse a narrower claim.\r")
        _BASE._settle(child)
        _snapshot(recorder, "11-turn-response-staged")
        child.send("\t\t\r")
        child.expect("REVIEW AND APPLY")
        _BASE._settle(child)
        child.send("\x1b[F")
        _BASE._settle(child)
        _snapshot(recorder, "12-turn-command-reviewed")
        child.send("\r")
        child.expect("TURN RECEIPT .* SUBMIT_ALL")
        child.expect("FINAL APPLY .* NOT RUN")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "13-turn-receipt-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_apply() -> None:
    child, recorder = _spawn("apply")
    try:
        child.expect("REVIEW AND APPLY")
        _BASE._settle(child)
        child.send("\x1b[B")
        _BASE._settle(child)
        _snapshot(recorder, "14-final-apply-commandless")
        child.send("\x1bq")
        child.expect("FINAL REVIEW RECEIPT .* CLOSE")
        child.expect("COMMAND SECTION .* INTENTIONALLY ABSENT")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "15-final-apply-cancel-verification")
    finally:
        if child.isalive():
            child.close(force=True)


def _capture_stale() -> None:
    child, recorder = _spawn("stale")
    try:
        child.expect("Update error: The staged Update session changed")
        child.expect("STALE TURN RECEIPT .* REJECTED BEFORE PROVIDER")
        child.expect("SAVED SESSION UNCHANGED .* True")
        child.expect(pexpect.EOF)
        _snapshot(recorder, "16-stale-turn-rejected")
    finally:
        if child.isalive():
            child.close(force=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="interactive-semantic-command-capture-"):
        _capture_start(
            "meld-start",
            "NEW MELD",
            "\t" * 7 + "\x15capture/result\r",
            (
                "01-meld-entry",
                "02-meld-start-command",
                "03-meld-receipt-verification",
            ),
        )
        _capture_start(
            "update-start",
            "NEW UPDATE",
            "\t" * 6,
            (
                "04-update-entry",
                "05-update-start-command",
                "06-update-receipt-verification",
            ),
        )
        _capture_start(
            "sever-start",
            "MEM SEVER",
            "\r\x1b[B\r\r",
            (
                "07-sever-entry",
                "08-sever-start-command",
                "09-sever-receipt-verification",
            ),
        )
        _capture_turn()
        _capture_apply()
        _capture_stale()
    raw = (OUT / "01-meld-entry.typescript").read_text(encoding="utf-8")
    if "\x1b[" not in raw or "38;" not in raw:
        raise RuntimeError("Capture did not retain expected ANSI foreground styles.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        _child(sys.argv[2])
    else:
        main()
