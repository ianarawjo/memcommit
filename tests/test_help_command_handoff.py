"""Editable Help command handoff without shell-function integration."""

from __future__ import annotations

import subprocess

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.adapters.console.commands.help.command as help_inventory
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.help.command_handoff import (
    edit_help_command,
    run_help_command,
)
from memcommit.adapters.console.commands.help.command import HelpSelection


runner = CliRunner(mix_stderr=False)


def test_selected_command_can_be_accepted_without_parent_shell() -> None:
    with create_pipe_input() as app_input:
        app_input.send_text("\r")
        argv = edit_help_command(
            "status",
            "mem status --short",
            app_input=app_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert argv == ("mem", "status", "--short")


def test_selected_command_arguments_remain_editable_before_enter() -> None:
    with create_pipe_input() as app_input:
        app_input.send_text("\x15coffee-run\r")
        argv = edit_help_command(
            "init-study",
            "mem init-study [profile_name]",
            app_input=app_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert argv == ("mem", "init-study", "coffee-run")


def test_help_command_execution_uses_exact_argv_without_a_shell() -> None:
    calls = []

    def fake_runner(argv, *, check):
        calls.append((argv, check))
        return subprocess.CompletedProcess(argv, 0)

    exit_code = run_help_command(
        ("mem", "status", "--short"),
        runner=fake_runner,
    )

    assert exit_code == 0
    assert calls == [(("mem", "status", "--short"), False)]


def test_help_command_keeps_the_selected_operation_fixed() -> None:
    with create_pipe_input() as app_input:
        app_input.send_text("\x15../other\r")
        argv = edit_help_command(
            "status",
            "mem status --short",
            app_input=app_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert argv == ("mem", "status", "../other")


def test_help_routes_selection_through_editor_then_child(monkeypatch) -> None:
    observed = []
    monkeypatch.setattr(help_inventory, "_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        help_inventory,
        "run_help_selector",
        lambda _entries: HelpSelection(
            command_name="status",
            command_line="mem status --short",
        ),
    )
    monkeypatch.setattr(
        help_inventory,
        "edit_help_command",
        lambda name, line: ("mem", name, "--short"),
    )
    monkeypatch.setattr(
        help_inventory,
        "run_help_command",
        lambda argv: observed.append(argv) or 0,
    )

    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0, result.output
    assert observed == [("mem", "status", "--short")]


def test_retired_emit_selection_transport_is_not_a_help_option() -> None:
    result = runner.invoke(app, ["help", "--emit-selection"])

    assert result.exit_code == 2
    assert "No such option: --emit-selection" in result.stderr
