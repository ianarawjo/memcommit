"""Compatibility exports for QueryContextRef application contracts.

New code imports :mod:`memcommit.operations.query.reference_application`.
"""

from memcommit.operations.query.reference_application import (
    FrozenQueryReferenceSource,
    QueryReferenceObserver,
    QueryReferenceProvider,
    QueryReferenceProviderFactory,
    QueryReferenceRequest,
    QueryReferenceResponse,
    QueryReferenceSourcePort,
    QueryReferenceStage,
    run_query_reference,
)

__all__ = [
    "FrozenQueryReferenceSource",
    "QueryReferenceObserver",
    "QueryReferenceProvider",
    "QueryReferenceProviderFactory",
    "QueryReferenceRequest",
    "QueryReferenceResponse",
    "QueryReferenceSourcePort",
    "QueryReferenceStage",
    "run_query_reference",
]
