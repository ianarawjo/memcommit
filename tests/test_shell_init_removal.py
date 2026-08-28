"""The retired shell-init operation has no remaining public route or module."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app


ROOT = Path(__file__).parents[1]
runner = CliRunner(mix_stderr=False)


def test_shell_init_command_and_modules_are_removed() -> None:
    assert not (ROOT / "src/memcommit/adapters/interfaces/cli/shell_init.py").exists()
    shell_package = ROOT / "src/memcommit/adapters/console/commands/shell_init"
    assert not list(shell_package.glob("*.py"))

    result = runner.invoke(app, ["shell-init"])

    assert result.exit_code == 2
    assert "No such command 'shell-init'" in result.stderr


def test_shell_init_is_absent_from_root_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0, result.output
    assert "shell-init" not in result.output
