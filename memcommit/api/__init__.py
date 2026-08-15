"""Stable public Python API for MemCommit."""

from memcommit.api.client import MemCommitClient
from memcommit.api.errors import (
    MemCommitError,
    QueryAuthorityError,
    QueryConfigurationError,
    QueryContextError,
    QueryError,
    QueryExecutionError,
    QueryInputError,
    QueryProviderFailure,
    QueryPublicationError,
    QueryStorageError,
)
from memcommit.api.query import (
    GrantedQueryResult,
    OrdinaryQueryResult,
    QueryCatalogEntry,
    QueryCitation,
    QueryProviderConfig,
    QuerySessionReceipt,
    ReferenceQueryResult,
)

__all__ = [
    "GrantedQueryResult",
    "MemCommitClient",
    "MemCommitError",
    "OrdinaryQueryResult",
    "QueryAuthorityError",
    "QueryCatalogEntry",
    "QueryCitation",
    "QueryConfigurationError",
    "QueryContextError",
    "QueryError",
    "QueryExecutionError",
    "QueryInputError",
    "QueryProviderConfig",
    "QueryProviderFailure",
    "QueryPublicationError",
    "QuerySessionReceipt",
    "QueryStorageError",
    "ReferenceQueryResult",
]
