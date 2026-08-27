"""Provider connection adapters for semantic operations.

The public names are resolved lazily so foundational provider contracts can
import independently of the higher-level connection policy.  This matters now
that configuration and provider types share this infrastructure package: eager
policy loading would send ``types -> package -> policy -> config -> types``
through a partially initialized module.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memcommit.providers.find_query import (
        FIND_PROVIDER_POLICY,
        QUERY_PROVIDER_POLICY,
        OperationProviderPolicy,
        connect_find_provider,
        connect_ordinary_query_provider,
        connect_query_route_provider,
    )

__all__ = [
    "FIND_PROVIDER_POLICY",
    "QUERY_PROVIDER_POLICY",
    "OperationProviderPolicy",
    "connect_find_provider",
    "connect_ordinary_query_provider",
    "connect_query_route_provider",
]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(name)
    policy = import_module("memcommit.providers.find_query")
    value = getattr(policy, name)
    globals()[name] = value
    return value
