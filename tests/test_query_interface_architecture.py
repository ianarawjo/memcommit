"""Ownership gates for Query's command-owned workbench."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
COMMAND_ROOT = (
    PACKAGE
    / "adapters"
    / "console"
    / "commands"
    / "search_explain"
    / "retrieve_answer"
    / "query"
)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def test_query_workbench_has_no_foreign_command_dependency() -> None:
    workbench = COMMAND_ROOT / "workbench"
    owner_prefix = "memcommit.adapters.console.commands.search_explain.retrieve_answer.query.workbench"
    family_component_prefix = (
        "memcommit.adapters.console.commands.search_explain.retrieve_answer.components"
    )
    offenders = [
        (str(path.relative_to(ROOT)), module)
        for path in workbench.rglob("*.py")
        for module in _imports(path)
        if module.startswith("memcommit.adapters.console.commands.")
        and not module.startswith((owner_prefix, family_component_prefix))
    ]

    assert offenders == []


def test_query_command_imports_workbench_owner_directly() -> None:
    source = (COMMAND_ROOT / "command.py").read_text(encoding="utf-8")

    assert "from memcommit.adapters.console.commands.search_explain.retrieve_answer.query.workbench import (" in source
    assert "memcommit.adapters.interfaces.tui.operations.query" not in source


def test_query_workbench_package_replaces_the_compatibility_facade() -> None:
    workbench = COMMAND_ROOT / "workbench"
    retired = PACKAGE / "adapters" / "interfaces" / "tui" / "operations" / "query"

    assert not (COMMAND_ROOT / "workbench.py").exists()
    assert (workbench / "model.py").is_file()
    assert (workbench / "presentation.py").is_file()
    assert (workbench / "scope.py").is_file()
    assert (workbench / "screen.py").is_file()
    assert not tuple(retired.glob("*.py"))


def test_query_workbench_exports_its_owned_implementations() -> None:
    owner = importlib.import_module("memcommit.adapters.console.commands.search_explain.retrieve_answer.query.workbench")

    assert owner.run_query_workbench.__module__.endswith(".workbench.screen")
    assert owner.QueryWorkbenchResult.__module__.endswith(".workbench.model")
    assert owner.project_query_answer_clipboard.__module__.endswith(
        ".workbench.presentation"
    )
