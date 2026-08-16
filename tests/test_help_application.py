"""Terminal-independent Help discovery contract."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memcommit.help_application import (
    HelpApplicationInputError,
    describe_operation,
    list_operation_help,
)


def test_list_returns_one_alphabetized_complete_immutable_snapshot():
    first = list_operation_help()
    second = list_operation_help()

    assert isinstance(first, tuple)
    assert [operation.name for operation in first] == sorted(
        (operation.name for operation in first),
        key=lambda name: (name.casefold(), name),
    )
    assert len(first) == 60
    assert len({operation.name for operation in first}) == len(first)
    assert first == second


def test_describe_returns_the_exact_catalog_contract():
    compare = describe_operation("compare")

    assert compare.name == "compare"
    assert compare.flow == "Context <-> Context -> comparison report"
    assert compare.execution.value == "SEMANTIC"
    assert compare.effect == "Read-only; neither Context is treated as authoritative"


@pytest.mark.parametrize("operation_name", [None, "", "   ", " compare", "COMPARE"])
def test_describe_rejects_nonexact_operation_names(operation_name):
    with pytest.raises(HelpApplicationInputError):
        describe_operation(operation_name)  # type: ignore[arg-type]


def test_application_boundary_has_no_store_provider_or_terminal_dependency():
    path = Path(__file__).parents[1] / "memcommit" / "help_application.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.store",
        "memcommit.commands",
        "memcommit.interfaces",
        "memcommit.providers",
        "typer",
        "prompt_toolkit",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )
