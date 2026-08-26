"""Active-Profile provider composition for Find, Query, and Help."""

from __future__ import annotations

from dataclasses import replace

from memcommit.infrastructure.config import Config
from memcommit.infrastructure.providers.types import CODEX_CHATGPT_PROVIDER, SemanticProvider
from memcommit.infrastructure.providers.policy import (
    FIND_PROVIDER_POLICY,
    HELP_PROVIDER_POLICY,
    QUERY_PROVIDER_POLICY,
    OperationProviderPolicy,
    ProviderPolicyOverride,
    resolve_operation_provider_policy,
)
from memcommit.infrastructure.providers.subscription import (
    CodexChatGPTProvider,
    connect_query_provider as _connect_configured_query_provider,
)
from memcommit.infrastructure.command_ledger.study_actions import (
    record_provider_connection_finished,
    record_provider_connection_started,
)


def _connect_active_operation(operation: str) -> SemanticProvider:
    # semantic_provider imports this package's policy module while it starts;
    # defer the reverse dependency so either public module can load first.
    from memcommit.semantic_provider import connect_operation_provider

    provider, _policy = connect_operation_provider(operation)
    return provider


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
    config = Config()
    resolved = resolve_operation_provider_policy(
        policy.operation,
        config=config,
        mode="EVALUATION",
        override=ProviderPolicyOverride(
            provider_id=CODEX_CHATGPT_PROVIDER,
            model=policy.model,
            reasoning_effort=policy.reasoning_effort,
            timeout_seconds=timeout_seconds,
        ),
    )
    started_at = record_provider_connection_started(policy.operation)
    try:
        provider = CodexChatGPTProvider.connect(
            timeout=resolved.timeout_seconds,
            model=resolved.model,
            reasoning_effort=resolved.reasoning_effort,
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
) -> SemanticProvider:
    """Connect active Find routing, or an explicit frozen Codex route."""

    if model is reasoning_effort is timeout_seconds is None:
        return _connect_active_operation("search")

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
) -> SemanticProvider:
    """Connect active Query routing, or an explicit frozen Codex route."""

    if model is reasoning_effort is timeout_seconds is None:
        return _connect_active_operation("query")

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
) -> SemanticProvider:
    """Connect active Help routing, or an explicit frozen Codex route."""

    if model is reasoning_effort is timeout_seconds is None:
        return _connect_active_operation("help")

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
    """Honor one authorized query-only provider route."""

    if provider_id == CODEX_CHATGPT_PROVIDER:
        return _connect_pinned_codex_provider(
            _configured_policy(
                QUERY_PROVIDER_POLICY,
                model=model,
                reasoning_effort=reasoning_effort,
            ),
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
