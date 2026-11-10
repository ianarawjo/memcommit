"""User-facing provider failures shared by all transports and clients."""


class QueryProviderError(RuntimeError):
    """Safe, user-facing error from a query provider."""


class QueryProviderTimeoutError(QueryProviderError):
    """A bounded provider process exceeded its effective transport timeout."""
