"""Operation-owned assembly for the public Help discovery lifecycle."""

from __future__ import annotations

from memcommit.api.errors import HelpInputError
from memcommit.api.help import (
    HelpCatalogResult,
    HelpComparisonOptionResult,
    HelpComparisonResult,
    HelpDetailCatalogResult,
    HelpDetailReferenceResult,
    HelpDetailResult,
    HelpTextDetailResult,
    OperationHelpResult,
)
from memcommit.help_application import (
    HelpApplicationInputError,
    describe_operation as describe_application_operation,
    describe_operation_detail as describe_application_detail,
    list_operation_help,
    list_operation_details as list_application_details,
)
from memcommit.help_catalog import (
    OperationComparisonDetail,
    OperationHelp,
    OperationHelpDetail,
    OperationTextDetail,
)


def _project_reference(detail: OperationHelpDetail) -> HelpDetailReferenceResult:
    return HelpDetailReferenceResult(
        id=detail.id,
        operation=detail.operation,
        kind=detail.kind.value,
        title=detail.title,
        use_when=detail.use_when,
        discovery=detail.discovery.value,
        discovery_summary=detail.discovery_summary,
    )


def _project_comparison(
    comparison: OperationComparisonDetail,
) -> HelpComparisonResult:
    return HelpComparisonResult(
        id=comparison.id,
        operation=comparison.operation,
        kind=comparison.kind.value,
        title=comparison.title,
        use_when=comparison.use_when,
        discovery=comparison.discovery.value,
        discovery_summary=comparison.discovery_summary,
        explanation=comparison.explanation,
        options=tuple(
            HelpComparisonOptionResult(
                label=option.label,
                guidance=option.guidance,
            )
            for option in comparison.options
        ),
    )


def _project_detail(detail: OperationHelpDetail) -> HelpDetailResult:
    if isinstance(detail, OperationComparisonDetail):
        return _project_comparison(detail)
    if isinstance(detail, OperationTextDetail):
        return HelpTextDetailResult(
            id=detail.id,
            operation=detail.operation,
            kind=detail.kind.value,
            title=detail.title,
            use_when=detail.use_when,
            discovery=detail.discovery.value,
            discovery_summary=detail.discovery_summary,
            body=detail.body,
        )
    raise TypeError("Unsupported Operation Help detail type.")


def _project(operation: OperationHelp) -> OperationHelpResult:
    return OperationHelpResult(
        name=operation.name,
        summary=operation.summary,
        flow=operation.flow,
        execution=operation.execution.value,
        effect=operation.effect,
        best_for=operation.best_for,
        range=operation.range,
        maturity=operation.maturity,
        details=tuple(_project_reference(detail) for detail in operation.details),
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


def list_operation_details(operation_name: str) -> HelpDetailCatalogResult:
    """List the compact detail index for one exact operation."""

    try:
        details = list_application_details(operation_name)
    except HelpApplicationInputError as error:
        raise HelpInputError(str(error)) from error
    return HelpDetailCatalogResult(
        operation=operation_name,
        details=tuple(_project_reference(detail) for detail in details),
    )


def describe_operation_detail(
    operation_name: str,
    detail_id: str,
) -> HelpDetailResult:
    """Describe one exact typed Help detail without executing an operation."""

    try:
        return _project_detail(describe_application_detail(operation_name, detail_id))
    except HelpApplicationInputError as error:
        raise HelpInputError(str(error)) from error


__all__ = [
    "describe_operation",
    "describe_operation_detail",
    "list_operation_details",
    "list_operations",
]
