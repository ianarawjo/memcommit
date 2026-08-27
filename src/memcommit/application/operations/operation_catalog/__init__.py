"""Stable public-operation metadata shared by application consumers."""

from memcommit.application.operations.operation_catalog.catalog import (
    OPERATION_HELP_BY_NAME,
    operation_help,
    operation_summary,
)
from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    ExecutionKind,
    HelpDetailKind,
    OperationComparisonDetail,
    OperationComparisonOption,
    OperationHelp,
    OperationHelpDetail,
    OperationTextDetail,
)

__all__ = [
    "DetailDiscovery",
    "ExecutionKind",
    "HelpDetailKind",
    "OPERATION_HELP_BY_NAME",
    "OperationComparisonDetail",
    "OperationComparisonOption",
    "OperationHelp",
    "OperationHelpDetail",
    "OperationTextDetail",
    "operation_help",
    "operation_summary",
]
