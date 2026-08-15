"""Compatibility exports for the ordinary Query runtime.

New code imports :mod:`memcommit.operations.query.ordinary_runtime`.
"""

from memcommit.operations.query.ordinary_runtime import (
    MemoryStoreOrdinaryQuerySourcePort,
    OrdinaryQueryReadableAccess,
    OrdinaryQueryReadableCatalog,
    execute_ordinary_query,
)

__all__ = [
    "MemoryStoreOrdinaryQuerySourcePort",
    "OrdinaryQueryReadableAccess",
    "OrdinaryQueryReadableCatalog",
    "execute_ordinary_query",
]
