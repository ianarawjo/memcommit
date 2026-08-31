"""Stable public-operation affordances shared across MemCommit layers."""

from memcommit.operation_catalog.catalog import (
    OPERATION_HELP_BY_NAME,
    OPERATION_BY_NAME,
    operation_descriptor,
    operation_help,
    operation_summary,
)
from memcommit.operation_catalog.families import (
    OPERATION_FAMILIES,
    OPERATION_FAMILY_BY_ID,
    OPERATION_FAMILY_BY_OPERATION,
    OPERATION_FAMILY_BY_TITLE,
    OperationFamily,
    OperationFamilyId,
    operation_family,
)
from memcommit.operation_catalog.family_localization import (
    localized_family_description,
    validate_family_translation_coverage,
)
from memcommit.operation_catalog.model import (
    DetailDiscovery,
    ExecutionKind,
    HelpDetailKind,
    OperationComparisonDetail,
    OperationComparisonOption,
    OperationDescriptor,
    OperationHelp,
    OperationHelpDetail,
    OperationTextDetail,
)

__all__ = [
    "DetailDiscovery",
    "ExecutionKind",
    "HelpDetailKind",
    "OPERATION_BY_NAME",
    "OPERATION_FAMILIES",
    "OPERATION_FAMILY_BY_ID",
    "OPERATION_FAMILY_BY_OPERATION",
    "OPERATION_FAMILY_BY_TITLE",
    "OPERATION_HELP_BY_NAME",
    "OperationComparisonDetail",
    "OperationComparisonOption",
    "OperationDescriptor",
    "OperationFamily",
    "OperationFamilyId",
    "OperationHelp",
    "OperationHelpDetail",
    "OperationTextDetail",
    "operation_descriptor",
    "operation_family",
    "operation_help",
    "operation_summary",
    "localized_family_description",
    "validate_family_translation_coverage",
]
