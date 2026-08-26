"""Dependency and compatibility checks for the relocated Meld TUI."""

from __future__ import annotations

import ast
from pathlib import Path

import memcommit.commands.meld as meld_command
import memcommit.commands.meld_shell as legacy_shell
import memcommit.commands.compare as compare_command
import memcommit.commands.resolution_workbench_shell as legacy_resolution_shell
from memcommit.comparison_present import render_comparison
import memcommit.interfaces.tui.operations.meld.screen as meld_screen
import memcommit.interfaces.tui.workbenches.resolution.session_shell as resolution_shell


def test_meld_command_enters_the_operation_tui_directly() -> None:
    assert meld_command.run_meld_shell is meld_screen.run_meld_shell


def test_legacy_meld_shell_is_an_import_only_facade() -> None:
    assert legacy_shell.MeldShellAction is meld_screen.MeldShellAction
    assert legacy_shell.run_meld_shell is meld_screen.run_meld_shell

    facade_path = Path(legacy_shell.__file__)
    module = ast.parse(facade_path.read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in module.body
    )


def test_meld_uses_the_interface_neutral_compare_presenter() -> None:
    """The command path remains a compatibility export, not the owner."""
    assert compare_command.render_comparison is render_comparison

    module = ast.parse(Path(meld_screen.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom)
    }
    assert "memcommit.interfaces.presentation.comparison" in imported_modules
    assert "memcommit.commands.compare" not in imported_modules


def test_meld_screen_has_one_live_workbench_host() -> None:
    source = Path(meld_screen.__file__).read_text(encoding="utf-8")
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


def test_legacy_resolution_shell_is_an_import_only_facade() -> None:
    assert (
        legacy_resolution_shell.run_resolution_workbench_shell
        is resolution_shell.run_resolution_workbench_shell
    )

    module = ast.parse(
        Path(legacy_resolution_shell.__file__).read_text(encoding="utf-8")
    )
    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in module.body
    )
