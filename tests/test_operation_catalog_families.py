"""Product-level operation-family catalog contracts."""

from memcommit.adapters.console.commands.help.inventory import (
    HELP_CATEGORY_GROUPS,
    HELP_CATEGORY_SECTIONS,
    HELP_SECTION_BY_COMMAND,
)
from memcommit.operation_catalog import (
    OPERATION_BY_NAME,
    OPERATION_FAMILIES,
    OPERATION_FAMILY_BY_OPERATION,
    OPERATION_FAMILY_SECTION_BY_OPERATION,
    OperationFamilyId,
    OperationFamilySectionId,
    operation_family,
    validate_family_translation_coverage,
)


def test_every_public_operation_belongs_to_exactly_one_family() -> None:
    assert len(OPERATION_BY_NAME) == 66
    assert len(OPERATION_FAMILIES) == 11
    assert set(OPERATION_FAMILY_BY_OPERATION) == set(OPERATION_BY_NAME)
    assert sum(
        len(family.operation_names) for family in OPERATION_FAMILIES
    ) == len(OPERATION_BY_NAME)


def test_operation_descriptors_carry_their_catalog_family_identity() -> None:
    assert all(
        descriptor.family is OPERATION_FAMILY_BY_OPERATION[name].id
        for name, descriptor in OPERATION_BY_NAME.items()
    )
    assert operation_family("trace").id is OperationFamilyId.HISTORY_RECOVERY
    assert (
        OPERATION_BY_NAME["trace"].section
        is OperationFamilySectionId.HISTORY_INSPECTION
    )
    assert (
        OPERATION_BY_NAME["checkpoint"].section
        is OperationFamilySectionId.HISTORY_RECOVERY
    )
    assert (
        OPERATION_BY_NAME["compare"].section
        is OperationFamilySectionId.SEARCH_SUMMARY_COMPARISON
    )


def test_search_family_groups_query_before_summary_and_comparison() -> None:
    search = operation_family("query")

    assert search.id is OperationFamilyId.SEARCH_EXPLAIN
    assert search.operation_names == (
        "find",
        "search",
        "query",
        "summarize",
        "compare",
    )
    assert tuple(
        (section.id, section.title, section.operation_names)
        for section in search.sections
    ) == (
        (
            OperationFamilySectionId.SEARCH_QUERY,
            "QUERY",
            ("find", "search", "query"),
        ),
        (
            OperationFamilySectionId.SEARCH_SUMMARY_COMPARISON,
            "SUMMARY & COMPARISON",
            ("summarize", "compare"),
        ),
    )
    assert operation_family("compare") is search
    assert "compare" not in operation_family("review").operation_names
    assert operation_family("review").title == "CHECK & REVIEW"


def test_history_family_preserves_the_reviewed_affordance_order() -> None:
    history = operation_family("trace")

    assert history.operation_names == (
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
        (section.id, section.title, section.operation_names)
        for section in history.sections
    ) == (
        (
            OperationFamilySectionId.HISTORY_INSPECTION,
            "INSPECTION",
            ("log", "diff", "trace", "rationale"),
        ),
        (
            OperationFamilySectionId.HISTORY_RECOVERY,
            "RECOVERY",
            ("checkpoint", "undo", "redo", "revert"),
        ),
    )
    sectioned_operations = set(history.operation_names) | set(
        operation_family("query").operation_names
    )
    assert set(OPERATION_FAMILY_SECTION_BY_OPERATION) == sectioned_operations
    assert all(
        not family.sections
        for family in OPERATION_FAMILIES
        if family.id
        not in {OperationFamilyId.SEARCH_EXPLAIN, OperationFamilyId.HISTORY_RECOVERY}
    )


def test_console_help_projects_the_shared_family_catalog() -> None:
    assert HELP_CATEGORY_GROUPS == tuple(
        (family.title, family.operation_names) for family in OPERATION_FAMILIES
    )
    assert HELP_CATEGORY_SECTIONS == {
        "SEARCH & EXPLAIN": (
            ("QUERY", ("find", "search", "query")),
            ("SUMMARY & COMPARISON", ("summarize", "compare")),
        ),
        "HISTORY & RECOVERY": (
            ("INSPECTION", ("log", "diff", "trace", "rationale")),
            ("RECOVERY", ("checkpoint", "undo", "redo", "revert")),
        )
    }
    assert HELP_SECTION_BY_COMMAND["trace"] == (
        "HISTORY & RECOVERY",
        "INSPECTION",
    )
    assert HELP_SECTION_BY_COMMAND["revert"] == (
        "HISTORY & RECOVERY",
        "RECOVERY",
    )
    assert HELP_SECTION_BY_COMMAND["query"] == ("SEARCH & EXPLAIN", "QUERY")
    assert HELP_SECTION_BY_COMMAND["summarize"] == (
        "SEARCH & EXPLAIN",
        "SUMMARY & COMPARISON",
    )
    assert HELP_SECTION_BY_COMMAND["compare"] == (
        "SEARCH & EXPLAIN",
        "SUMMARY & COMPARISON",
    )


def test_family_translations_cover_the_shared_catalog() -> None:
    validate_family_translation_coverage()
