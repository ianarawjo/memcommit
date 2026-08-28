"""Lazy default provider connectors owned below the public client facade."""

from __future__ import annotations

from memcommit.adapters.python_api.query import QueryProviderConfig


def connect_ordinary_provider(config: QueryProviderConfig) -> object:
    from memcommit.providers.operation_connections import (
        connect_ordinary_query_provider,
    )

    return connect_ordinary_query_provider(
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        timeout_seconds=config.timeout_seconds,
    )


def connect_route_provider(
    config: QueryProviderConfig,
    provider_name: str,
) -> object:
    from memcommit.providers.operation_connections import (
        connect_query_route_provider,
    )

    return connect_query_route_provider(
        provider_name,
        model=config.model,
        reasoning_effort=config.reasoning_effort,
        timeout_seconds=config.timeout_seconds,
    )


__all__ = ["connect_ordinary_provider", "connect_route_provider"]
