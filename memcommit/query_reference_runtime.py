"""Compatibility exports for the QueryContextRef runtime.

New code imports :mod:`memcommit.operations.query.reference_runtime`.
"""

from memcommit.operations.query.reference_runtime import (
    MemoryStoreQueryReferenceSourcePort,
    execute_query_reference,
)

__all__ = [
    "MemoryStoreQueryReferenceSourcePort",
    "execute_query_reference",
]
