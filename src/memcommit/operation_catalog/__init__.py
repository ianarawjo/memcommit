"""Stable public-operation affordances shared across MemCommit layers."""

from memcommit.operation_catalog.catalog import (
    OPERATION_BY_NAME,
    operation_descriptor,
    operation_summary,
)
from memcommit.operation_catalog.families import (
    OPERATION_FAMILIES,
    OPERATION_FAMILY_BY_OPERATION,
    OPERATION_FAMILY_SECTION_BY_OPERATION,
    OperationFamily,
    OperationFamilyId,
    OperationFamilySection,
    OperationFamilySectionId,
    operation_family,
)
from memcommit.operation_catalog.model import (
    ExecutionKind,
    OperationComparisonDetail,
    OperationDescriptor,
    OperationTextDetail,
)

__all__ = [
    "ExecutionKind",
    "OPERATION_BY_NAME",
    "OPERATION_FAMILIES",
    "OPERATION_FAMILY_BY_OPERATION",
    "OPERATION_FAMILY_SECTION_BY_OPERATION",
    "OperationComparisonDetail",
    "OperationDescriptor",
    "OperationFamily",
    "OperationFamilyId",
    "OperationFamilySection",
    "OperationFamilySectionId",
    "OperationTextDetail",
    "operation_descriptor",
    "operation_family",
    "operation_summary",
]
