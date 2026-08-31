"""Ownership checks for Undo, Redo, and their shared restoration core."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

from memcommit.application.operations.redo import runtime as redo_runtime
from memcommit.application.operations.undo import runtime as undo_runtime


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_operation_adapters_preserve_distinct_directions(monkeypatch) -> None:
    calls: list[tuple[object, str]] = []
    token = object()

    def restore(store, direction, *, restore_granted):
        calls.append((store, direction))
        assert callable(restore_granted)
        return token

    undo_store = object()
    redo_store = object()
    monkeypatch.setattr(undo_runtime, "restore_context_command", restore)
    monkeypatch.setattr(redo_runtime, "restore_context_command", restore)

    assert undo_runtime.execute_undo(undo_store) is token
    assert redo_runtime.execute_redo(redo_store) is token
    assert calls == [(undo_store, "undo"), (redo_store, "redo")]


def test_commands_do_not_own_restoration_route_selection() -> None:
    for operation in ("undo", "redo"):
        path = REPOSITORY_ROOT / f"src/memcommit/adapters/console/commands/{operation}/command.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert f"memcommit.application.operations.{operation}.runtime" in imports
        assert "memcommit.granted_update_application" not in imports


def test_restoration_modules_have_no_terminal_dependency() -> None:
    for relative_path in (
        "src/memcommit/application/capabilities/command_recovery/execution.py",
        "src/memcommit/application/capabilities/command_recovery/update.py",
        "src/memcommit/application/operations/revert/application.py",
        "src/memcommit/application/operations/revert/restoration.py",
        "src/memcommit/application/operations/revert/runtime.py",
        "src/memcommit/application/operations/undo/runtime.py",
        "src/memcommit/application/operations/redo/runtime.py",
    ):
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        assert "import typer" not in source
        assert "memcommit.adapters.console.commands" not in source


def test_operation_packages_import_lazily() -> None:
    for package in ("revert", "undo", "redo"):
        program = f"""
import sys
import memcommit.application.operations.{package}

assert not [
    name
    for name in sys.modules
    if name.startswith("memcommit.application.operations.{package}.")
]
"""
        subprocess.run(
            [sys.executable, "-c", program],
            cwd=REPOSITORY_ROOT,
            check=True,
        )
