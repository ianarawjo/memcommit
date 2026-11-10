"""Validate one user's shared LLM-provider settings, independent of Profiles."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from memcommit.llm_providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    SEMANTIC_PROVIDER_IDS,
)


class ProviderSettingsError(ValueError):
    """The shared provider settings cannot form a valid connection."""


class ProviderConfiguration(Protocol):
    def semantic_provider(self) -> str: ...
    def model_for_provider(self, provider: str) -> str | None: ...
    def codex_reasoning_effort(self) -> str | None: ...
    def codex_service_tier(self) -> str | None: ...
    def semantic_timeout_seconds(self) -> float: ...


@dataclass(frozen=True)
class ProviderSettings:
    """One complete connection selection shared by every Profile and operation."""

    provider_id: str
    model: str | None
    reasoning_effort: str | None
    timeout_seconds: float
    service_tier: str | None = None


DEFAULT_PROVIDER_SETTINGS = ProviderSettings(
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-6.1-sol",
    reasoning_effort="low",
    timeout_seconds=600.0,
    service_tier="fast",
)


def validate_provider_settings(settings: ProviderSettings) -> ProviderSettings:
    if settings.provider_id not in SEMANTIC_PROVIDER_IDS:
        raise ProviderSettingsError(
            f"Unsupported semantic provider {settings.provider_id!r}."
        )
    if settings.model is not None and (
        not isinstance(settings.model, str) or not settings.model.strip()
    ):
        raise ProviderSettingsError("LLM provider model must be non-empty.")
    if settings.provider_id != CODEX_CHATGPT_PROVIDER:
        if settings.model is None:
            raise ProviderSettingsError("This LLM provider requires an explicit model.")
        if settings.reasoning_effort is not None or settings.service_tier is not None:
            raise ProviderSettingsError(
                "Reasoning and service tier apply only to Codex."
            )
    else:
        if settings.reasoning_effort is not None and settings.reasoning_effort not in CODEX_REASONING_EFFORTS:
            raise ProviderSettingsError("Unsupported Codex reasoning effort.")
        if settings.service_tier not in {None, "fast"}:
            raise ProviderSettingsError("Codex service tier must be standard or fast.")
    timeout = settings.timeout_seconds
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ProviderSettingsError("LLM provider timeout must be positive and finite.")
    return settings


def resolve_provider_settings(config: ProviderConfiguration) -> ProviderSettings:
    provider = config.semantic_provider()
    is_codex = provider == CODEX_CHATGPT_PROVIDER
    return validate_provider_settings(
        ProviderSettings(
            provider_id=provider,
            model=(
                config.model_for_provider(provider)
                or (DEFAULT_PROVIDER_SETTINGS.model if is_codex else None)
            ),
            reasoning_effort=config.codex_reasoning_effort() if is_codex else None,
            timeout_seconds=config.semantic_timeout_seconds(),
            service_tier=config.codex_service_tier() if is_codex else None,
        )
    )
