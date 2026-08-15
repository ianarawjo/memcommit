"""Benchmark-selected provider policy for Find and Query."""
from __future__ import annotations

from dataclasses import dataclass

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
    operation="find",
    model="gpt-5.6-terra",
    reasoning_effort="low",
)
QUERY_PROVIDER_POLICY = OperationProviderPolicy(
    operation="query",
    model="gpt-5.6-sol",
    reasoning_effort="none",
)


def _connect_pinned_codex_provider(
    policy: OperationProviderPolicy,
) -> CodexChatGPTProvider:
    """Connect one evaluated policy while retaining shared auth and timeout."""

    started_at = record_provider_connection_started(policy.operation)
    try:
        provider = CodexChatGPTProvider.connect(
            timeout=Config().semantic_timeout_seconds(),
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


def connect_find_provider() -> CodexChatGPTProvider:
    """Connect the evaluated Terra/low policy for all Find provider turns."""

    return _connect_pinned_codex_provider(FIND_PROVIDER_POLICY)


def connect_ordinary_query_provider() -> CodexChatGPTProvider:
    """Connect Sol/none for one-shot ordinary and Codex query-route turns."""

    return _connect_pinned_codex_provider(QUERY_PROVIDER_POLICY)


def connect_query_route_provider(provider_id: str) -> SemanticProvider:
    """Pin Codex query routes without overriding an authorized non-Codex route."""

    if provider_id == CODEX_CHATGPT_PROVIDER:
        return connect_ordinary_query_provider()
    return _connect_configured_query_provider(provider_id)  # type: ignore[return-value]
