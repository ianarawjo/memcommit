"""Dependency and compatibility checks for the relocated Meld TUI."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.adapters.console.commands.meld as meld_command
import memcommit.adapters.console.commands.compare.command as compare_command
from memcommit.adapters.console.commands.compare.presentation import render_comparison
import memcommit.adapters.console.commands.meld.workbench.workbench as meld_workbench


def test_meld_command_enters_the_operation_tui_directly() -> None:
    assert meld_command.run_meld_shell is meld_workbench.run_meld_shell


def test_meld_uses_compare_owned_console_presentation() -> None:
    """Meld reuses Compare's console projection without importing its entrypoint."""
    assert compare_command.render_comparison is render_comparison

    module = ast.parse(Path(meld_workbench.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
    }
    assert "memcommit.adapters.console.commands.compare.presentation" in imported_modules
    assert "memcommit.adapters.console.commands.compare.command" not in imported_modules


def test_meld_workbench_has_one_live_host() -> None:
    source = Path(meld_workbench.__file__).read_text(encoding="utf-8")
    module = ast.parse(source)
    hosts = [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "run_meld_shell"
    ]

    assert len(hosts) == 1
    assert "_run_legacy_meld_shell" not in source
    assert "def _screen_text" not in source


def test_meld_has_no_legacy_tui_or_shell_facade() -> None:
    package = Path(meld_workbench.__file__).parent
    meld_package = package.parent
    legacy_package = (
        meld_package.parents[2] / "interfaces" / "tui" / "operations" / "meld"
    )

    assert not (package / "shell.py").exists()
    assert not any(legacy_package.glob("*.py"))
