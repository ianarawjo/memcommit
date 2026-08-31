"""Contracts for the reserved Eval console shell."""

from typer.testing import CliRunner

import memcommit.adapters.console.commands.system_study_tools.eval.command as command


runner = CliRunner()


def test_eval_route_is_a_non_executable_reserved_shell() -> None:
    result = runner.invoke(command.app, [])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == command.RESERVED_EVAL_MESSAGE


def test_eval_help_exposes_no_campaign_commands() -> None:
    result = runner.invoke(command.app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "Reserved shell for a future evaluation workflow" in result.output
    assert "semantic" not in result.output.lower()
    assert "run" not in result.output.lower()
    assert "status" not in result.output.lower()
    assert "check" not in result.output.lower()


def test_removed_semantic_route_fails_as_an_unknown_command() -> None:
    result = runner.invoke(command.app, ["semantic"])

    assert result.exit_code != 0
    assert "No such command" in result.output
