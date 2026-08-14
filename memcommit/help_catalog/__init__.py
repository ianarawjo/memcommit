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
from memcommit.help_catalog.model import ExecutionKind, OperationHelp

__all__ = [
    "ComposedOperationHelp",
    "ExecutionKind",
    "HelpRow",
    "OPERATION_HELP_BY_NAME",
    "OperationHelp",
    "compose_operation_help",
    "operation_help",
    "operation_summary",
]
