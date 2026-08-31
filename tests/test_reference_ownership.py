"""Ownership and compatibility paths for immutable Reference."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_reference_package_import_is_lazy() -> None:
    program = """
import sys
import memcommit.application.operations.reference

assert "memcommit.application.operations.reference.application" not in sys.modules
assert "memcommit.application.operations.reference.runtime" not in sys.modules
"""

    subprocess.run(
        [sys.executable, "-c", program],
        cwd=REPOSITORY_ROOT,
        check=True,
    )


def test_reference_entrypoint_uses_the_lazy_command_package_surface() -> None:
    path = REPOSITORY_ROOT / "src/memcommit/adapters/console/entrypoint.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    package_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "memcommit.adapters.console.commands"
        for alias in node.names
    }
    reference_attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "reference"
    }

    assert "memcommit.adapters.console.commands.reference.command" not in direct_imports
    assert "reference" in package_imports
    assert "cmd" in reference_attributes


def test_production_reference_consumers_use_the_operation_owner() -> None:
    relative_paths = (
        "src/memcommit/adapters/python_api/_operations/reference.py",
        "src/memcommit/adapters/console/commands/reference/command.py",
        "src/memcommit/adapters/console/commands/reference/workbench/adapter.py",
        "src/memcommit/adapters/console/commands/reference/workbench/screen.py",
        "src/memcommit/application/operations/reference/runtime.py",
    )

    for relative_path in relative_paths:
        path = REPOSITORY_ROOT / relative_path
        source = path.read_text(encoding="utf-8")
        assert "from memcommit.reference_application import" not in source
        assert "from memcommit.reference_runtime import" not in source


def test_reference_cli_has_one_command_owned_implementation() -> None:
    assert not (
        REPOSITORY_ROOT / "src/memcommit/adapters/interfaces/cli/reference.py"
    ).exists()


def test_query_reference_remains_owned_by_the_query_operation() -> None:
    application = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search_explain/retrieve_answer/query/reference_application.py"
    ).read_text(encoding="utf-8")
    runtime = (
        REPOSITORY_ROOT
        / "src/memcommit/application/operations/search_explain/retrieve_answer/query/reference_runtime.py"
    ).read_text(encoding="utf-8")

    assert "memcommit.application.operations.reference" not in application
    assert "memcommit.application.operations.reference" not in runtime
