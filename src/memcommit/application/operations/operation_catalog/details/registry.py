"""Canonical registry of individually addressable operation Help details."""

from types import MappingProxyType

from memcommit.application.operations.operation_catalog.details.add import ADD_DETAILS
from memcommit.application.operations.operation_catalog.details.atomize import ATOMIZE_DETAILS
from memcommit.application.operations.operation_catalog.details.check_conformance import CHECK_CONFORMANCE_DETAILS
from memcommit.application.operations.operation_catalog.details.dedun import DEDUN_DETAILS
from memcommit.application.operations.operation_catalog.details.distill import DISTILL_DETAILS
from memcommit.application.operations.operation_catalog.details.eval import EVAL_DETAILS
from memcommit.application.operations.operation_catalog.details.fit import FIT_DETAILS
from memcommit.application.operations.operation_catalog.details.impact import IMPACT_DETAILS
from memcommit.application.operations.operation_catalog.details.import_operation import IMPORT_DETAILS
from memcommit.application.operations.operation_catalog.details.init import INIT_DETAILS
from memcommit.application.operations.operation_catalog.details.log import LOG_DETAILS
from memcommit.application.operations.operation_catalog.details.merge import MERGE_DETAILS
from memcommit.application.operations.operation_catalog.details.profile import PROFILE_DETAILS
from memcommit.application.operations.operation_catalog.details.provider import PROVIDER_DETAILS
from memcommit.application.operations.operation_catalog.details.query import QUERY_DETAILS
from memcommit.application.operations.operation_catalog.details.revert import REVERT_DETAILS
from memcommit.application.operations.operation_catalog.details.semantic_session_commands import (
    SEMANTIC_SESSION_COMMAND_DETAILS,
)
from memcommit.application.operations.operation_catalog.details.translate import TRANSLATE_DETAILS
from memcommit.application.operations.operation_catalog.details.update_meld import UPDATE_MELD_DETAILS
from memcommit.application.operations.operation_catalog.model import OperationHelpDetail


_DETAIL_GROUPS = (
    ADD_DETAILS,
    ATOMIZE_DETAILS,
    CHECK_CONFORMANCE_DETAILS,
    DEDUN_DETAILS,
    DISTILL_DETAILS,
    EVAL_DETAILS,
    FIT_DETAILS,
    IMPACT_DETAILS,
    IMPORT_DETAILS,
    INIT_DETAILS,
    LOG_DETAILS,
    MERGE_DETAILS,
    PROFILE_DETAILS,
    PROVIDER_DETAILS,
    QUERY_DETAILS,
    REVERT_DETAILS,
    SEMANTIC_SESSION_COMMAND_DETAILS,
    TRANSLATE_DETAILS,
    UPDATE_MELD_DETAILS,
)

_by_operation: dict[str, list[OperationHelpDetail]] = {}
_seen: set[tuple[str, str]] = set()
for group in _DETAIL_GROUPS:
    for detail in group:
        key = (detail.operation, detail.id)
        if key in _seen:  # pragma: no cover - import-time catalog invariant
            raise RuntimeError(f"Duplicate Operation Help detail: {key!r}.")
        _seen.add(key)
        _by_operation.setdefault(detail.operation, []).append(detail)

DETAILS_BY_OPERATION = MappingProxyType(
    {name: tuple(details) for name, details in _by_operation.items()}
)
ALL_OPERATION_DETAILS = tuple(
    detail for details in DETAILS_BY_OPERATION.values() for detail in details
)


__all__ = ["ALL_OPERATION_DETAILS", "DETAILS_BY_OPERATION"]
