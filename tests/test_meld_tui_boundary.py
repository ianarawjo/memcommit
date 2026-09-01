"""Dependency checks for Meld's Resolve-owned decision surface."""

from __future__ import annotations

import ast
from pathlib import Path

from memcommit.adapters.console.commands.meld import command as meld_command
from memcommit.adapters.console.commands.meld.workflow import workflow


def test_meld_command_does_not_export_the_historical_workbench() -> None:
    assert not hasattr(meld_command, "run_meld_shell")


def test_meld_workflow_imports_resolve_viewer_not_the_historical_shell() -> None:
    module = ast.parse(Path(workflow.__file__).read_text(encoding="utf-8"))
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)
    }
    assert (
        "memcommit.adapters.console.commands.resolve.workbench.screen"
        in imported_modules
    )
    assert "memcommit.adapters.console.commands.meld.workbench" not in imported_modules


def test_meld_labels_the_resolve_viewer_without_cloning_it() -> None:
    source = Path(workflow.__file__).read_text(encoding="utf-8")

    assert 'run_resolve_tui(analysis, header_label="MELD")' in source
    assert "def run_meld_shell(" not in source


def test_meld_workflow_does_not_import_compare_ui() -> None:
    source = Path(workflow.__file__).read_text(encoding="utf-8")

    assert "commands.compare" not in source
