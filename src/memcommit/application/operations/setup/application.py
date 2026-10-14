"""Publish checked machine defaults without assuming an existing Store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memcommit.application.operations.setup.provider_probe import (
    verify_provider_response,
)
from memcommit.configuration.config import Config
from memcommit.providers.clients.codex import CodexChatGPTProvider
from memcommit.providers.clients.codex_model_catalog import (
    CodexModelOption,
    load_codex_model_catalog,
)
from memcommit.providers.clients.completion import model_name
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.types import CODEX_CHATGPT_PROVIDER


@dataclass(frozen=True)
class SetupProviderOption:
    uid: str
    label: str
    command: str


SETUP_PROVIDERS = (
    SetupProviderOption(CODEX_CHATGPT_PROVIDER, "OpenAI Codex", "codex"),
)


@dataclass(frozen=True)
class SetupModelSelection:
    model: str
    reasoning_effort: str | None


def load_setup_model_catalog(provider_id: str, *, binary: Path):
    setup_provider_option(provider_id)
    provider = CodexChatGPTProvider.connect(candidates=[binary])
    return load_codex_model_catalog(provider)


def select_setup_model(
    catalog: tuple[CodexModelOption, ...],
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> SetupModelSelection:
    if not catalog:
        raise QueryProviderError("No visible models are available for setup.")
    chosen = next((option for option in catalog if option.model == model), None)
    if model is not None and chosen is None:
        raise QueryProviderError(
            "The requested model is not in Codex's visible catalog. Choose another model."
        )
    chosen = chosen or next(
        (option for option in catalog if option.is_default), catalog[0]
    )
    effort = (
        reasoning_effort
        if reasoning_effort is not None
        else chosen.default_reasoning_effort
    )
    if effort is not None and effort not in {
        option.effort for option in chosen.supported_reasoning_efforts
    }:
        raise QueryProviderError(
            "The selected model does not support that reasoning setting."
        )
    return SetupModelSelection(chosen.model, effort)


def setup_provider_option(provider_id: str) -> SetupProviderOption:
    for option in SETUP_PROVIDERS:
        if option.uid == provider_id:
            return option
    raise ValueError(
        "First setup currently supports codex_chatgpt. Claude Code and Copilot are planned."
    )


def connect_setup_provider(
    provider_id: str,
    model: str,
    *,
    reasoning_effort: str | None = None,
    binary: Path | None = None,
):
    setup_provider_option(provider_id)
    model_name(model)
    timeout = Config().semantic_timeout_seconds()
    provider = CodexChatGPTProvider.connect(
        model=model,
        reasoning_effort=reasoning_effort,
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
    values["codex_chatgpt_reasoning_effort"] = provider.identity.reasoning_effort
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
        "reasoning_effort": settings.get("codex_chatgpt_reasoning_effort"),
        "profile": registry.active.name if registry.generation else None,
        "root": registry.active.root_dir if registry.generation else None,
    }
