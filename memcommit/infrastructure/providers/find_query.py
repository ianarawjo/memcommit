"""Pinned provider composition for Find, Query, and Help lookup."""

from __future__ import annotations

from dataclasses import dataclass, replace

from memcommit.config import Config
from memcommit.provider_types import CODEX_CHATGPT_PROVIDER, SemanticProvider
from memcommit.query_provider import (
    CodexChatGPTProvider,
    connect_query_provider as _connect_configured_query_provider,
)
from memcommit.study_action_log import (
    record_provider_connection_finished,
    record_provider_connection_started,
)


@dataclass(frozen=True)
class OperationProviderPolicy:
    """One explicit model/reasoning choice for a semantic operation."""

    operation: str
    model: str
    reasoning_effort: str


FIND_PROVIDER_POLICY = OperationProviderPolicy(
    operation="search",
    model="gpt-5.6-terra",
    reasoning_effort="low",
)
QUERY_PROVIDER_POLICY = OperationProviderPolicy(
    operation="query",
    model="gpt-5.6-sol",
    reasoning_effort="none",
)
HELP_PROVIDER_POLICY = OperationProviderPolicy(
    operation="help",
    model="gpt-5.6-sol",
    reasoning_effort="none",
)


def _configured_policy(
    policy: OperationProviderPolicy,
    *,
    model: str | None,
    reasoning_effort: str | None,
) -> OperationProviderPolicy:
    return replace(
        policy,
        model=policy.model if model is None else model,
        reasoning_effort=(
            policy.reasoning_effort
            if reasoning_effort is None
            else reasoning_effort
        ),
    )


def _connect_pinned_codex_provider(
    policy: OperationProviderPolicy,
    *,
    timeout_seconds: float | None = None,
) -> CodexChatGPTProvider:
    """Connect one evaluated policy while retaining shared auth and logging."""

    timeout = (
        Config().semantic_timeout_seconds()
        if timeout_seconds is None
        else timeout_seconds
    )
    started_at = record_provider_connection_started(policy.operation)
    try:
        provider = CodexChatGPTProvider.connect(
            timeout=timeout,
            model=policy.model,
            reasoning_effort=policy.reasoning_effort,
        )
    except BaseException as error:
        record_provider_connection_finished(
            policy.operation,
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        policy.operation,
        started_at,
        provider=provider.identity.provider,
    )
    return provider


def connect_find_provider(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> CodexChatGPTProvider:
    """Connect the evaluated Find policy, optionally from a frozen config."""

    return _connect_pinned_codex_provider(
        _configured_policy(
            FIND_PROVIDER_POLICY,
            model=model,
            reasoning_effort=reasoning_effort,
        ),
        timeout_seconds=timeout_seconds,
    )


def connect_ordinary_query_provider(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> CodexChatGPTProvider:
    """Connect the Query policy, optionally from a frozen public config."""

    return _connect_pinned_codex_provider(
        _configured_policy(
            QUERY_PROVIDER_POLICY,
            model=model,
            reasoning_effort=reasoning_effort,
        ),
        timeout_seconds=timeout_seconds,
    )


def connect_help_provider(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> CodexChatGPTProvider:
    """Connect the pinned natural-language Help lookup policy."""

    return _connect_pinned_codex_provider(
        _configured_policy(
            HELP_PROVIDER_POLICY,
            model=model,
            reasoning_effort=reasoning_effort,
        ),
        timeout_seconds=timeout_seconds,
    )


def connect_query_route_provider(
    provider_id: str,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> SemanticProvider:
    """Pin Codex Query routes without overriding authorized other routes."""

    if provider_id == CODEX_CHATGPT_PROVIDER:
        if model is reasoning_effort is timeout_seconds is None:
            return connect_ordinary_query_provider()
        return connect_ordinary_query_provider(
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        )
    return _connect_configured_query_provider(provider_id)  # type: ignore[return-value]


__all__ = [
    "FIND_PROVIDER_POLICY",
    "HELP_PROVIDER_POLICY",
    "QUERY_PROVIDER_POLICY",
    "OperationProviderPolicy",
    "connect_find_provider",
    "connect_help_provider",
    "connect_ordinary_query_provider",
    "connect_query_route_provider",
]
