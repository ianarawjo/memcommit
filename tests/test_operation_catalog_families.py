"""Product-level operation-family catalog contracts."""

from memcommit.adapters.console.commands.system_study_tools.help.inventory import (
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
    assert len(OPERATION_FAMILIES) == 13
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
        is OperationFamilySectionId.SEARCH_SYNTHESIZE
    )


def test_search_family_groups_retrieval_and_answering_before_synthesis() -> None:
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
            OperationFamilySectionId.SEARCH_RETRIEVE_ANSWER,
            "RETRIEVE & ANSWER",
            ("find", "search", "query"),
        ),
        (
            OperationFamilySectionId.SEARCH_SYNTHESIZE,
            "SYNTHESIZE",
            ("summarize", "compare"),
        ),
    )
    assert operation_family("compare") is search
    assert "compare" not in operation_family("review").operation_names
    assert operation_family("review").title == "OPERATION LIFECYCLE"


def test_update_is_the_foundation_for_specialized_semantic_updates() -> None:
    family = operation_family("update")

    assert family.id is OperationFamilyId.SEMANTIC_UPDATES
    assert family.operation_names == (
        "update",
        "atomize",
        "distill",
        "elaborate",
        "makemore",
        "forget",
        "sever",
        "meld",
    )
    assert tuple(
        (section.id, section.title, section.operation_names)
        for section in family.sections
    ) == (
        (
            OperationFamilySectionId.SEMANTIC_UPDATE_FOUNDATION,
            "FOUNDATION",
            ("update",),
        ),
        (
            OperationFamilySectionId.SEMANTIC_UPDATE_DERIVE,
            "DERIVE",
            ("atomize", "distill", "elaborate", "makemore"),
        ),
        (
            OperationFamilySectionId.SEMANTIC_UPDATE_CURATE_INTEGRATE,
            "CURATE & INTEGRATE",
            ("forget", "sever", "meld"),
        ),
    )
    assert operation_family("translate").id is OperationFamilyId.TRANSLATION


def test_quality_pairs_diagnosis_with_repair_and_validation() -> None:
    family = operation_family("find-duplicates")

    assert family.id is OperationFamilyId.QUALITY_RESOLUTION
    assert tuple(
        (section.id, section.title, section.operation_names)
        for section in family.sections
    ) == (
        (
            OperationFamilySectionId.QUALITY_RESOLUTION_DIAGNOSE,
            "DIAGNOSE",
            (
                "find-duplicates",
                "find-redundancies",
                "find-ambiguities",
                "find-conflicts",
                "audit",
            ),
        ),
        (
            OperationFamilySectionId.QUALITY_RESOLUTION_REPAIR,
            "REPAIR",
            ("dedup", "dedun", "resolve"),
        ),
        (
            OperationFamilySectionId.QUALITY_RESOLUTION_VALIDATE,
            "VALIDATE",
            ("fit", "check-conformance"),
        ),
    )
    assert operation_family("dedup") is family
    assert operation_family("dedun") is family
    assert operation_family("resolve") is family


def test_impact_and_review_are_unsplit_operation_lifecycle_peers() -> None:
    family = operation_family("impact")

    assert family.id is OperationFamilyId.OPERATION_LIFECYCLE
    assert family.operation_names == ("impact", "review")
    assert not family.sections
    assert operation_family("review") is family


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
    sectioned_families = (
        operation_family("query"),
        operation_family("update"),
        operation_family("find-duplicates"),
        history,
    )
    sectioned_operations = {
        name for family in sectioned_families for name in family.operation_names
    }
    assert set(OPERATION_FAMILY_SECTION_BY_OPERATION) == sectioned_operations
    assert all(
        not family.sections
        for family in OPERATION_FAMILIES
        if family not in sectioned_families
    )


def test_console_help_projects_the_shared_family_catalog() -> None:
    assert HELP_CATEGORY_GROUPS == tuple(
        (family.title, family.operation_names) for family in OPERATION_FAMILIES
    )
    assert HELP_CATEGORY_SECTIONS == {
        "SEARCH & EXPLAIN": (
            ("RETRIEVE & ANSWER", ("find", "search", "query")),
            ("SYNTHESIZE", ("summarize", "compare")),
        ),
        "SEMANTIC UPDATES": (
            ("FOUNDATION", ("update",)),
            ("DERIVE", ("atomize", "distill", "elaborate", "makemore")),
            ("CURATE & INTEGRATE", ("forget", "sever", "meld")),
        ),
        "QUALITY & RESOLUTION": (
            (
                "DIAGNOSE",
                (
                    "find-duplicates",
                    "find-redundancies",
                    "find-ambiguities",
                    "find-conflicts",
                    "audit",
                ),
            ),
            ("REPAIR", ("dedup", "dedun", "resolve")),
            ("VALIDATE", ("fit", "check-conformance")),
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
    assert HELP_SECTION_BY_COMMAND["query"] == (
        "SEARCH & EXPLAIN",
        "RETRIEVE & ANSWER",
    )
    assert HELP_SECTION_BY_COMMAND["summarize"] == (
        "SEARCH & EXPLAIN",
        "SYNTHESIZE",
    )
    assert HELP_SECTION_BY_COMMAND["compare"] == (
        "SEARCH & EXPLAIN",
        "SYNTHESIZE",
    )
    assert HELP_SECTION_BY_COMMAND["update"] == (
        "SEMANTIC UPDATES",
        "FOUNDATION",
    )
    assert HELP_SECTION_BY_COMMAND["meld"] == (
        "SEMANTIC UPDATES",
        "CURATE & INTEGRATE",
    )
    assert HELP_SECTION_BY_COMMAND["find-redundancies"] == (
        "QUALITY & RESOLUTION",
        "DIAGNOSE",
    )
    assert HELP_SECTION_BY_COMMAND["dedun"] == (
        "QUALITY & RESOLUTION",
        "REPAIR",
    )
    assert HELP_SECTION_BY_COMMAND["fit"] == (
        "QUALITY & RESOLUTION",
        "VALIDATE",
    )
    assert "impact" not in HELP_SECTION_BY_COMMAND
    assert "review" not in HELP_SECTION_BY_COMMAND


def test_family_translations_cover_the_shared_catalog() -> None:
    validate_family_translation_coverage()
