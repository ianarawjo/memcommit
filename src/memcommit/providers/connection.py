"""Connect clients from explicit routes or frozen Profile and Study policies."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import replace
from threading import Lock
from typing import TYPE_CHECKING

from memcommit.configuration.config import Config
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.http import JsonRequester, request_json
from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SemanticProvider,
    QueryProvider,
)
from memcommit.providers.clients.codex import CodexChatGPTProvider
from memcommit.providers.clients.ollama import OllamaProvider
from memcommit.providers.clients.openrouter import OpenRouterProvider
from memcommit.providers.clients.jev import JevClient
from memcommit.providers.policy import (
    SEARCH_PROVIDER_POLICY,
    QUERY_PROVIDER_POLICY,
    HELP_PROVIDER_POLICY,
    OperationProviderPolicy,
    ProviderPolicyMode,
    ProviderPolicyOverride,
    ResolvedProviderPolicy,
    resolve_operation_provider_policy,
)
from memcommit.persistence.command_ledger.study_actions import (
    record_provider_connection_started,
    record_provider_connection_finished,
)

if TYPE_CHECKING:
    from memcommit.application.operations.profile.config import ProfileRegistry

_provider_cache_lock = Lock()
_provider_cache: SemanticProvider | None = None


def connect_provider(
    provider_id: str,
    *,
    config: Config | None = None,
    env: dict[str, str] | None = None,
) -> SemanticProvider:
    """Connect one allowlisted provider; never interpret config as executable."""
    started_at = record_provider_connection_started("semantic")
    try:
        provider = _connect_provider(provider_id, config=config, env=env)
    except BaseException as error:
        record_provider_connection_finished(
            "semantic",
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        "semantic",
        started_at,
        provider=getattr(
            getattr(provider, "identity", None),
            "provider",
            provider_id,
        ),
    )
    return provider


def connect_operation_provider(
    operation: str,
    *,
    mode: ProviderPolicyMode | None = None,
    override: ProviderPolicyOverride | None = None,
    config: Config | None = None,
    env: dict[str, str] | None = None,
    profile_registry: ProfileRegistry | None = None,
) -> tuple[SemanticProvider, ResolvedProviderPolicy]:
    """Connect the one centrally resolved policy for an operation.

    The returned receipt is intentionally separate from mutable provider state:
    production telemetry and Study artifacts can retain the exact policy even
    when a provider object is later reused for another completion.
    """

    settings = config or Config()
    if mode is None and config is None and override is None:
        # Import lazily so the core provider adapter does not make Profile
        # selection part of module import. One command freezes one active
        # Profile route before any provider connection.
        from memcommit.providers.profile_routes import (
            resolve_active_provider_policy,
        )

        resolved, scope = resolve_active_provider_policy(
            operation,
            machine_config=settings,
            registry=profile_registry,
        )
        settings = scope.config  # type: ignore[assignment]
    else:
        resolved = resolve_operation_provider_policy(
            operation,
            config=settings,
            mode=mode or "PRODUCTION",
            override=override,
        )
    environment = os.environ if env is None else env
    started_at = record_provider_connection_started(operation)
    try:
        if resolved.provider_id == CODEX_CHATGPT_PROVIDER:
            provider: SemanticProvider = CodexChatGPTProvider.connect(
                env=dict(environment),
                timeout=resolved.timeout_seconds,
                model=resolved.model,
                reasoning_effort=resolved.reasoning_effort,
                service_tier=resolved.service_tier,
            )
        elif resolved.provider_id == OLLAMA_PROVIDER:
            if not resolved.model:
                raise QueryProviderError(
                    "The resolved Ollama operation policy has no model."
                )
            provider = OllamaProvider.connect(
                model=resolved.model,
                base_url=settings.ollama_base_url(),
                timeout=resolved.timeout_seconds,
                context_tokens=settings.semantic_context_tokens(),
                max_output_tokens=settings.semantic_max_output_tokens(),
                thinking=settings.semantic_thinking(),
            )
        elif resolved.provider_id == OPENROUTER_PROVIDER:
            if not resolved.model:
                raise QueryProviderError(
                    "The resolved OpenRouter operation policy has no model."
                )
            provider = OpenRouterProvider.connect(
                model=resolved.model,
                api_key=environment.get("OPENROUTER_API_KEY", ""),
                timeout=resolved.timeout_seconds,
                max_output_tokens=settings.semantic_max_output_tokens(),
                zdr=settings.openrouter_zdr(),
            )
        else:  # pragma: no cover - resolver has already closed this boundary.
            raise QueryProviderError(
                f"Unsupported semantic provider {resolved.provider_id!r}."
            )
    except BaseException as error:
        record_provider_connection_finished(
            operation,
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        operation,
        started_at,
        provider=resolved.provider_id,
    )
    return provider, resolved


def _connect_provider(
    provider_id: str,
    *,
    config: Config | None = None,
    env: dict[str, str] | None = None,
) -> SemanticProvider:
    """Connect after the caller has opened the provider-audit phase."""
    settings = config or Config()
    environment = os.environ if env is None else env
    if provider_id == CODEX_CHATGPT_PROVIDER:
        provider = CodexChatGPTProvider.connect(
            env=dict(environment),
            timeout=settings.semantic_timeout_seconds(),
            model=settings.model_for_provider(CODEX_CHATGPT_PROVIDER),
            reasoning_effort=settings.codex_reasoning_effort(),
        )
        return provider  # type: ignore[return-value]
    if provider_id not in {OLLAMA_PROVIDER, OPENROUTER_PROVIDER}:
        raise QueryProviderError(f"Unsupported semantic provider {provider_id!r}.")
    model = settings.require_semantic_model(provider_id)
    if provider_id == OLLAMA_PROVIDER:
        return OllamaProvider.connect(
            model=model,
            base_url=settings.ollama_base_url(),
            timeout=settings.semantic_timeout_seconds(),
            context_tokens=settings.semantic_context_tokens(),
            max_output_tokens=settings.semantic_max_output_tokens(),
            thinking=settings.semantic_thinking(),
        )
    if provider_id == OPENROUTER_PROVIDER:
        return OpenRouterProvider.connect(
            model=model,
            api_key=environment.get("OPENROUTER_API_KEY", ""),
            timeout=settings.semantic_timeout_seconds(),
            max_output_tokens=settings.semantic_max_output_tokens(),
            zdr=settings.openrouter_zdr(),
        )
    raise AssertionError("allowlisted semantic provider was not connected")


def connect_semantic_provider(
    *,
    config: Config | None = None,
    env: dict[str, str] | None = None,
) -> SemanticProvider:
    """Resolve the shared inherited policy once for one command process."""
    global _provider_cache
    # Injected config/env calls are diagnostics and tests; they should never
    # populate the CLI-process cache with an artificial provider.
    if config is not None or env is not None:
        provider, _policy = connect_operation_provider(
            "semantic_default",
            config=config,
            env=env,
        )
        return provider
    with _provider_cache_lock:
        if _provider_cache is None:
            _provider_cache, _policy = connect_operation_provider(
                "semantic_default",
            )
        return _provider_cache


def reset_semantic_provider_cache() -> None:
    """Start a fresh provider snapshot for one root CLI invocation."""
    global _provider_cache
    with _provider_cache_lock:
        _provider_cache = None


def connect_codex_subscription_provider() -> CodexChatGPTProvider:
    """Connect the exact subscription-only Codex provider."""
    started_at = record_provider_connection_started("query")
    try:
        provider = CodexChatGPTProvider.connect()
    except BaseException as error:
        record_provider_connection_finished(
            "query",
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        "query",
        started_at,
        provider=getattr(
            getattr(provider, "identity", None),
            "provider",
            CODEX_CHATGPT_PROVIDER,
        ),
    )
    return provider


def connect_query_provider(provider: str) -> QueryProvider:
    """Connect an allowlisted provider without treating metadata as executable."""
    if provider == CODEX_CHATGPT_PROVIDER:
        return connect_codex_subscription_provider()
    # A persisted query route remains authoritative and is never replaced by
    # active-Profile semantic selection. Additional allowlisted adapters still
    # perform their own authentication/service probe before source load.
    if provider in {OLLAMA_PROVIDER, OPENROUTER_PROVIDER}:
        return connect_provider(provider)  # type: ignore[return-value]
    raise QueryProviderError(f"Unsupported query provider '{provider}'.")


def _connect_active_operation(operation: str) -> SemanticProvider:
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
            policy.reasoning_effort if reasoning_effort is None else reasoning_effort
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


def connect_search_provider(
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> SemanticProvider:
    """Connect active Search routing, or an explicit frozen Codex route."""

    if model is reasoning_effort is timeout_seconds is None:
        return _connect_active_operation("search")

    return _connect_pinned_codex_provider(
        _configured_policy(
            SEARCH_PROVIDER_POLICY,
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
    return connect_query_provider(provider_id)  # type: ignore[return-value]


def connect_jev(
    *,
    env: Mapping[str, str] | None = None,
    timeout: float = 15.0,
    requester: JsonRequester = request_json,
) -> JevClient:
    """Freeze credentials locally; the first choose call performs authentication."""
    environment = os.environ if env is None else env
    return JevClient(environment.get("OPENROUTER_API_KEY", ""), timeout, requester)
