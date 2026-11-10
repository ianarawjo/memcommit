"""Connect the shared user-selected provider and freeze it for one command."""

from __future__ import annotations

import os
from threading import Lock

from memcommit.configuration.config import Config
from memcommit.llm_providers.errors import QueryProviderError
from memcommit.llm_providers.types import (
    CODEX_CHATGPT_PROVIDER,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SemanticProvider,
)
from memcommit.llm_providers.clients.codex import CodexChatGPTProvider
from memcommit.llm_providers.clients.ollama import OllamaProvider
from memcommit.llm_providers.clients.openrouter import OpenRouterProvider
from memcommit.llm_providers.settings import resolve_provider_settings
from memcommit.persistence.command_ledger.study_actions import (
    record_provider_connection_started,
    record_provider_connection_finished,
)

_provider_cache_lock = Lock()
_provider_cache: SemanticProvider | None = None


def _connect_configured_provider(
    *,
    config: Config | None = None,
    env: dict[str, str] | None = None,
) -> SemanticProvider:
    settings = config or Config()
    resolved = resolve_provider_settings(settings)
    environment = os.environ if env is None else env
    started_at = record_provider_connection_started("semantic")
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
                raise QueryProviderError("The resolved Ollama settings have no model.")
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
                    "The resolved OpenRouter settings have no model."
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
            "semantic",
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        "semantic",
        started_at,
        provider=resolved.provider_id,
    )
    return provider


def connect_semantic_provider(
    *,
    config: Config | None = None,
    env: dict[str, str] | None = None,
) -> SemanticProvider:
    """Reuse one shared-settings snapshot until the next root CLI invocation."""
    global _provider_cache
    # Diagnostic inputs must not replace the command's real provider snapshot.
    if config is not None or env is not None:
        return _connect_configured_provider(config=config, env=env)
    with _provider_cache_lock:
        if _provider_cache is None:
            _provider_cache = _connect_configured_provider()
        return _provider_cache


def reset_semantic_provider_cache() -> None:
    """Start a fresh provider snapshot for one root CLI invocation."""
    global _provider_cache
    with _provider_cache_lock:
        _provider_cache = None
