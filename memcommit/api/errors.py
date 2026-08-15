"""Stable exception hierarchy for the public MemCommit Python API."""


class MemCommitError(RuntimeError):
    """Base class for failures exposed by the public Python API."""


class QueryError(MemCommitError):
    """Base class for public Query failures."""


class QueryInputError(QueryError):
    """The caller supplied an invalid Query request."""


class QueryConfigurationError(QueryError):
    """The client or provider configuration is invalid."""


class QueryContextError(QueryError):
    """A requested Context or query reference is unavailable."""


class QueryAuthorityError(QueryError):
    """The requested operation is not authorized by the active Profile."""


class QueryProviderFailure(QueryError):
    """The configured semantic provider could not complete the request."""


class QueryExecutionError(QueryError):
    """Authorized Query execution failed before a durable publication."""


class QueryPublicationError(QueryError):
    """A granted Query answered, but its requested session was not published."""


class QueryStorageError(QueryError):
    """Query could not safely read or publish local durable state."""


__all__ = [
    "MemCommitError",
    "QueryAuthorityError",
    "QueryConfigurationError",
    "QueryContextError",
    "QueryError",
    "QueryExecutionError",
    "QueryInputError",
    "QueryProviderFailure",
    "QueryPublicationError",
    "QueryStorageError",
]
