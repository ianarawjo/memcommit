"""Stable operation discovery metadata shared by MemCommit interfaces."""

from memcommit.help_catalog.catalog import (
    OPERATION_HELP_BY_NAME,
    operation_help,
    operation_summary,
)
from memcommit.help_catalog.composer import (
    ComposedOperationHelp,
    HelpRow,
    compose_operation_help,
)
from memcommit.help_catalog.model import (
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
    "ComposedOperationHelp",
    "DetailDiscovery",
    "ExecutionKind",
    "HelpDetailKind",
    "HelpRow",
    "OPERATION_HELP_BY_NAME",
    "OperationComparisonDetail",
    "OperationComparisonOption",
    "OperationHelp",
    "OperationHelpDetail",
    "OperationTextDetail",
    "compose_operation_help",
    "operation_help",
    "operation_summary",
]
