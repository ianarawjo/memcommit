"""Operation-owned discovery boundary for public MemCommit operations."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.operation_catalog import (
    OPERATION_BY_NAME,
    OPERATION_FAMILIES,
    OperationDescriptor,
    OperationFamily,
    OperationFamilySection,
)
from memcommit.operation_catalog.model import OperationHelpDetail


class HelpApplicationInputError(ValueError):
    """A Help query did not identify one exact public operation."""


@dataclass(frozen=True, slots=True)
class OperationHelpSectionGroup:
    """One catalog section with its complete ordered operation records."""

    section: OperationFamilySection
    operations: tuple[OperationDescriptor, ...]


@dataclass(frozen=True, slots=True)
class OperationHelpFamilyGroup:
    """One catalog family projected for renderer-neutral Help discovery."""

    family: OperationFamily
    operations: tuple[OperationDescriptor, ...]
    sections: tuple[OperationHelpSectionGroup, ...]


def list_operation_help() -> tuple[OperationDescriptor, ...]:
    """Return one stable, alphabetized snapshot of every public operation.

    Help discovery intentionally reads only the in-package catalog. It must not
    initialize a Store, connect a provider, or inspect runtime authority merely
    to explain which operations exist.
    """

    return tuple(
        sorted(
            OPERATION_BY_NAME.values(),
            key=lambda operation: (operation.name.casefold(), operation.name),
        )
    )


def list_operation_help_groups() -> tuple[OperationHelpFamilyGroup, ...]:
    """Return the public operations in catalog family and section order."""

    return tuple(
        OperationHelpFamilyGroup(
            family=family,
            operations=tuple(
                OPERATION_BY_NAME[operation_name]
                for operation_name in family.operation_names
            ),
            sections=tuple(
                OperationHelpSectionGroup(
                    section=section,
                    operations=tuple(
                        OPERATION_BY_NAME[operation_name]
                        for operation_name in section.operation_names
                    ),
                )
                for section in family.sections
            ),
        )
        for family in OPERATION_FAMILIES
    )


def describe_operation(operation_name: str) -> OperationDescriptor:
    """Return one exact operation contract from the same discovery snapshot."""

    return _operation(operation_name)


def list_operation_details(operation_name: str) -> tuple[OperationHelpDetail, ...]:
    """List compactly addressable details for one exact public operation."""

    operation = _operation(operation_name)
    return operation.details


def describe_operation_detail(
    operation_name: str,
    detail_id: str,
) -> OperationHelpDetail:
    """Return one exact typed detail without opening runtime state."""

    operation = _operation(operation_name)
    if not isinstance(detail_id, str) or not detail_id.strip():
        raise HelpApplicationInputError("Help detail_id must be nonblank text.")
    if detail_id != detail_id.strip():
        raise HelpApplicationInputError(
            "Help detail_id must not contain surrounding whitespace."
        )
    for detail in operation.details:
        if detail.id == detail_id:
            return detail
    raise HelpApplicationInputError(
        f"Operation {operation.name!r} has no Help detail named {detail_id!r}."
    )


def _operation(operation_name: str) -> OperationDescriptor:
    if not isinstance(operation_name, str) or not operation_name.strip():
        raise HelpApplicationInputError("Help operation_name must be nonblank text.")
    if operation_name != operation_name.strip():
        raise HelpApplicationInputError(
            "Help operation_name must not contain surrounding whitespace."
        )
    try:
        return OPERATION_BY_NAME[operation_name]
    except KeyError as error:
        raise HelpApplicationInputError(
            f"No public MemCommit operation is named {operation_name!r}."
        ) from error


__all__ = [
    "HelpApplicationInputError",
    "OperationHelpFamilyGroup",
    "OperationHelpSectionGroup",
    "describe_operation",
    "describe_operation_detail",
    "list_operation_help_groups",
    "list_operation_help",
    "list_operation_details",
]
