"""Compatibility exports for ordinary Query application contracts.

New code imports :mod:`memcommit.operations.query.ordinary_application`.
"""

from memcommit.operations.query.ordinary_application import (
    FrozenOrdinaryQuerySource,
    OrdinaryQueryObserver,
    OrdinaryQueryProvider,
    OrdinaryQueryProviderFactory,
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
    OrdinaryQuerySourcePort,
    OrdinaryQueryStage,
    run_ordinary_query,
)

__all__ = [
    "FrozenOrdinaryQuerySource",
    "OrdinaryQueryObserver",
    "OrdinaryQueryProvider",
    "OrdinaryQueryProviderFactory",
    "OrdinaryQueryRequest",
    "OrdinaryQueryResponse",
    "OrdinaryQuerySourcePort",
    "OrdinaryQueryStage",
    "run_ordinary_query",
]
