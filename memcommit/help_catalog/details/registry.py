"""Canonical registry of individually addressable operation Help details."""

from types import MappingProxyType

from memcommit.help_catalog.details.add import ADD_DETAILS
from memcommit.help_catalog.details.import_operation import IMPORT_DETAILS
from memcommit.help_catalog.details.init import INIT_DETAILS
from memcommit.help_catalog.details.query import QUERY_DETAILS
from memcommit.help_catalog.model import OperationHelpDetail


_DETAIL_GROUPS = (
    ADD_DETAILS,
    IMPORT_DETAILS,
    INIT_DETAILS,
    QUERY_DETAILS,
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
