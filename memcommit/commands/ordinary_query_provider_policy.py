"""Compatibility exports for the shared Find/Query provider policy.

New code imports :mod:`memcommit.commands.find_query_provider_policy`.
"""

from __future__ import annotations

from memcommit.commands.find_query_provider_policy import (
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
