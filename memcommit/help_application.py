"""Terminal-independent discovery boundary for public MemCommit operations."""

from __future__ import annotations

from memcommit.help_catalog import OPERATION_HELP_BY_NAME, OperationHelp


class HelpApplicationInputError(ValueError):
    """A Help query did not identify one exact public operation."""


def list_operation_help() -> tuple[OperationHelp, ...]:
    """Return one stable, alphabetized snapshot of every public operation.

    Help discovery intentionally reads only the in-package catalog. It must not
    initialize a Store, connect a provider, or inspect runtime authority merely
    to explain which operations exist.
    """

    return tuple(
        sorted(
            OPERATION_HELP_BY_NAME.values(),
            key=lambda operation: (operation.name.casefold(), operation.name),
        )
    )


def describe_operation(operation_name: str) -> OperationHelp:
    """Return one exact operation contract from the same discovery snapshot."""

    if not isinstance(operation_name, str) or not operation_name.strip():
        raise HelpApplicationInputError(
            "Help operation_name must be nonblank text."
        )
    if operation_name != operation_name.strip():
        raise HelpApplicationInputError(
            "Help operation_name must not contain surrounding whitespace."
        )
    try:
        return OPERATION_HELP_BY_NAME[operation_name]
    except KeyError as error:
        raise HelpApplicationInputError(
            f"No public MemCommit operation is named {operation_name!r}."
        ) from error


__all__ = [
    "HelpApplicationInputError",
    "describe_operation",
    "list_operation_help",
]
