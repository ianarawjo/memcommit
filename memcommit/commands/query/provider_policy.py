"""Compatibility exports for the infrastructure-owned Query policy."""

from __future__ import annotations

from memcommit.infrastructure.providers.find_query import (
    QUERY_PROVIDER_POLICY,
    connect_ordinary_query_provider,
    connect_query_route_provider,
)


ORDINARY_QUERY_MODEL = QUERY_PROVIDER_POLICY.model
ORDINARY_QUERY_REASONING_EFFORT = QUERY_PROVIDER_POLICY.reasoning_effort

__all__ = [
    "ORDINARY_QUERY_MODEL",
    "ORDINARY_QUERY_REASONING_EFFORT",
    "connect_ordinary_query_provider",
    "connect_query_route_provider",
]
