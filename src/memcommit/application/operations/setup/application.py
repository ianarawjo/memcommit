"""Publish checked machine defaults without assuming an existing Store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.setup.provider_probe import (
    verify_provider_response,
)
from memcommit.configuration.config import Config
from memcommit.providers.clients.codex import CodexChatGPTProvider
from memcommit.providers.clients.completion import model_name
from memcommit.providers.types import CODEX_CHATGPT_PROVIDER


@dataclass(frozen=True)
class SetupProviderOption:
    uid: str
    label: str
    command: str
    default_model: str


SETUP_PROVIDERS = (
    SetupProviderOption(CODEX_CHATGPT_PROVIDER, "OpenAI Codex", "codex", "gpt-6.1-sol"),
)


def setup_provider_option(provider_id: str) -> SetupProviderOption:
    for option in SETUP_PROVIDERS:
        if option.uid == provider_id:
            return option
    raise ValueError(
        "First setup currently supports codex_chatgpt. Claude Code and Copilot are planned."
    )


def connect_setup_provider(provider_id: str, model: str, *, binary: Path | None = None):
    setup_provider_option(provider_id)
    model_name(model)
    timeout = Config().semantic_timeout_seconds()
    provider = CodexChatGPTProvider.connect(
        model=model,
        reasoning_effort="low",
        timeout=timeout,
        candidates=[binary] if binary else None,
    )
    verify_provider_response(provider)
    return provider


def save_checked_provider(provider) -> None:
    """Only the caller's successfully probed provider becomes a machine default."""
    provider_id = provider.identity.provider
    setup_provider_option(provider_id)
    values = {
        "semantic_provider": provider_id,
        f"{provider_id}_model": provider.identity.model,
    }
    values["codex_chatgpt_reasoning_effort"] = "low"
    Config().update(values)


def setup_status() -> dict:
    from memcommit.application.operations.profile.config import load_profile_registry

    registry = load_profile_registry()
    settings = Config().all()
    return {
        "setup_complete": settings.get("setup_complete") is True
        and registry.generation > 0,
        "provider": settings.get("semantic_provider"),
        "model": settings.get(f"{settings.get('semantic_provider')}_model"),
        "profile": registry.active.name if registry.generation else None,
        "root": registry.active.root_dir if registry.generation else None,
    }
