"""Terminal-independent Help discovery contract."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memcommit.application.operations.help.application import (
    HelpApplicationInputError,
    describe_operation,
    describe_operation_detail,
    list_operation_help,
    list_operation_help_groups,
    list_operation_details,
)
from memcommit.operation_catalog import (
    OperationFamilyId,
    OperationFamilySectionId,
)


def test_list_returns_one_alphabetized_complete_immutable_snapshot():
    first = list_operation_help()
    second = list_operation_help()

    assert isinstance(first, tuple)
    assert [operation.name for operation in first] == sorted(
        (operation.name for operation in first),
        key=lambda name: (name.casefold(), name),
    )
    assert len(first) == 66
    assert len({operation.name for operation in first}) == len(first)
    assert first == second


def test_grouped_list_preserves_catalog_family_and_section_order():
    groups = list_operation_help_groups()
    search = next(
        group
        for group in groups
        if group.family.id is OperationFamilyId.SEARCH_EXPLAIN
    )
    history = next(
        group
        for group in groups
        if group.family.id is OperationFamilyId.HISTORY_RECOVERY
    )

    assert isinstance(groups, tuple)
    assert len(groups) == 11
    assert tuple(operation.name for operation in search.operations) == (
        "find",
        "search",
        "query",
        "summarize",
        "compare",
    )
    assert tuple(
        (
            section_group.section.id,
            tuple(operation.name for operation in section_group.operations),
        )
        for section_group in search.sections
    ) == (
        (
            OperationFamilySectionId.SEARCH_QUERY,
            ("find", "search", "query"),
        ),
        (
            OperationFamilySectionId.SEARCH_SUMMARY_COMPARISON,
            ("summarize", "compare"),
        ),
    )
    assert tuple(operation.name for operation in history.operations) == (
        "log",
        "diff",
        "trace",
        "rationale",
        "checkpoint",
        "undo",
        "redo",
        "revert",
    )
    assert tuple(
        (
            section_group.section.id,
            tuple(operation.name for operation in section_group.operations),
        )
        for section_group in history.sections
    ) == (
        (
            OperationFamilySectionId.HISTORY_INSPECTION,
            ("log", "diff", "trace", "rationale"),
        ),
        (
            OperationFamilySectionId.HISTORY_RECOVERY,
            ("checkpoint", "undo", "redo", "revert"),
        ),
    )
    assert all(
        not group.sections
        for group in groups
        if group.family.id
        not in {OperationFamilyId.SEARCH_EXPLAIN, OperationFamilyId.HISTORY_RECOVERY}
    )


def test_describe_returns_the_exact_catalog_contract():
    compare = describe_operation("compare")

    assert compare.name == "compare"
    assert compare.flow == "Context <-> Context -> comparison report"
    assert compare.execution.value == "SEMANTIC"
    assert compare.effect == (
        "Default summary is transient and read-only; --ledger saves the exhaustive "
        "relation basis used by Meld"
    )


def test_detail_queries_use_exact_stable_ids_without_runtime_state():
    details = list_operation_details("add")
    detail = describe_operation_detail("add", "copy-or-link")

    assert [item.id for item in details] == ["copy-or-link"]
    assert detail is details[0]
    assert detail.operation == "add"
    assert detail.kind.value == "COMPARISON"
    assert detail.discovery.value == "TOOL_SELECTION"


@pytest.mark.parametrize(
    ("operation_name", "detail_id"),
    [
        ("add", "missing"),
        ("add", " copy-or-link"),
        ("add", "COPY-OR-LINK"),
        ("missing", "copy-or-link"),
        ("add", None),
    ],
)
def test_detail_queries_reject_nonexact_operation_or_detail_ids(
    operation_name,
    detail_id,
):
    with pytest.raises(HelpApplicationInputError):
        describe_operation_detail(operation_name, detail_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("operation_name", [None, "", "   ", " compare", "COMPARE"])
def test_describe_rejects_nonexact_operation_names(operation_name):
    with pytest.raises(HelpApplicationInputError):
        describe_operation(operation_name)  # type: ignore[arg-type]


def test_application_boundary_has_no_store_provider_or_terminal_dependency():
    path = (
        Path(__file__).parents[1]
        / "src" / "memcommit"
        / "application"
        / "operations"
        / "help"
        / "application.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = (
        "memcommit.store",
        "memcommit.adapters.console.commands",
        "memcommit.adapters.interfaces",
        "memcommit.providers",
        "typer",
        "prompt_toolkit",
    )
    assert not any(
        name == prefix or name.startswith(f"{prefix}.")
        for name in imported
        for prefix in forbidden
    )
