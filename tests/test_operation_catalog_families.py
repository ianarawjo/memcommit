"""Product-level operation-family catalog contracts."""

from memcommit.adapters.console.commands.help.inventory import HELP_CATEGORY_GROUPS
from memcommit.operation_catalog import (
    OPERATION_BY_NAME,
    OPERATION_FAMILIES,
    OPERATION_FAMILY_BY_OPERATION,
    OperationFamilyId,
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


def test_history_family_preserves_the_reviewed_affordance_order() -> None:
    assert operation_family("trace").operation_names == (
        "log",
        "diff",
        "trace",
        "rationale",
        "checkpoint",
        "undo",
        "redo",
        "revert",
    )


def test_console_help_projects_the_shared_family_catalog() -> None:
    assert HELP_CATEGORY_GROUPS == tuple(
        (family.title, family.operation_names) for family in OPERATION_FAMILIES
    )


def test_family_translations_cover_the_shared_catalog() -> None:
    validate_family_translation_coverage()
