"""Operation-owned assembly for the public Help discovery lifecycle."""

from __future__ import annotations

from memcommit.api.errors import HelpInputError
from memcommit.api.help import HelpCatalogResult, OperationHelpResult
from memcommit.help_application import (
    HelpApplicationInputError,
    describe_operation as describe_application_operation,
    list_operation_help,
)
from memcommit.help_catalog import OperationHelp


def _project(operation: OperationHelp) -> OperationHelpResult:
    return OperationHelpResult(
        name=operation.name,
        summary=operation.summary,
        flow=operation.flow,
        execution=operation.execution.value,
        effect=operation.effect,
        best_for=operation.best_for,
        range=operation.range,
    )


def list_operations() -> HelpCatalogResult:
    """List every stable operation meaning without Store or provider access."""

    return HelpCatalogResult(
        operations=tuple(_project(operation) for operation in list_operation_help())
    )


def describe_operation(operation_name: str) -> OperationHelpResult:
    """Describe one exact public operation without executing it."""

    try:
        return _project(describe_application_operation(operation_name))
    except HelpApplicationInputError as error:
        raise HelpInputError(str(error)) from error


__all__ = ["describe_operation", "list_operations"]
