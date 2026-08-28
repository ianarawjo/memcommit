"""Contract tests for the operation-neutral launcher boundary."""

from __future__ import annotations

from dataclasses import fields

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.terminal.components.operation_launcher import (
    LauncherAction,
    LauncherActionSelection,
    LauncherEntry,
    LauncherEntrySelection,
    LauncherOrientation,
    OperationLauncherSpec,
    run_operation_launcher,
)


def _entry(key: str, *, timestamp: float) -> LauncherEntry:
    return LauncherEntry(
        kind="recent-report",
        key=key,
        title=key.title(),
        status="READ-ONLY",
        subtitle="current + descendants",
        group="task-1/participant",
        sort_timestamp=timestamp,
        detail=f"Recent report for {key}.",
    )


def test_launcher_models_have_no_argv_or_execution_callback_fields():
    model_fields = {
        field.name
        for model in (LauncherEntry, LauncherAction, OperationLauncherSpec)
        for field in fields(model)
    }

    assert "argv" not in model_fields
    assert "reopen_argv" not in model_fields
    assert "callback" not in model_fields


def test_launcher_returns_only_the_selected_entry_identity():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        selected = run_operation_launcher(
            OperationLauncherSpec(
                title="MEM SUMMARIZE · RECENT",
                entries=(_entry("older", timestamp=1), _entry("newer", timestamp=2)),
                orientation=LauncherOrientation(
                    rows=(("PROFILE", "study"), ("CURRENT", "task-1"))
                ),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == LauncherEntrySelection(
        kind="recent-report",
        key="older",
    )


def test_launcher_returns_only_the_pinned_action_identity():
    action = LauncherAction(
        uid="select-context",
        label="SELECT A CONTEXT",
        description="Leave recent results and choose a new Context scope.",
    )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[A\r")
        selected = run_operation_launcher(
            OperationLauncherSpec(
                title="MEM TRACE · RECENT",
                entries=(_entry("last", timestamp=1),),
                action=action,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == LauncherActionSelection(uid="select-context")
