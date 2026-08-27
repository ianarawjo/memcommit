"""Ownership gates for Query's CLI/TUI interface extraction."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_query_tui_package_has_no_command_dependency():
    operation = PACKAGE / "adapters" / "interfaces" / "tui" / "operations" / "query"
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in operation.rglob("*.py")
        for module in _imports(path)
        if module.startswith("memcommit.adapters.console.commands")
    ]

    assert offenders == []


def test_query_command_imports_interface_owner_directly():
    source = (PACKAGE / "commands" / "query" / "command.py").read_text(encoding="utf-8")

    assert "from memcommit.adapters.interfaces.tui.operations.query import (" in source
    assert "from memcommit.adapters.console.commands.query.workbench import" not in source


def test_query_workbench_compatibility_exports_are_object_identical():
    compatibility = importlib.import_module("memcommit.adapters.console.commands.query.workbench")
    owner = importlib.import_module("memcommit.adapters.interfaces.tui.operations.query")

    assert compatibility.__all__ == owner.__all__
    for name in owner.__all__:
        assert getattr(compatibility, name) is getattr(owner, name)


def test_query_workbench_compatibility_module_has_no_implementation():
    path = PACKAGE / "commands" / "query" / "workbench.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    assert not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in ast.walk(tree)
    )
