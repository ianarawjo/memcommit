"""Discover and validate Codex model/reasoning choices and checked first use."""

from dataclasses import dataclass
from pathlib import Path

from memcommit.configuration.config import Config
from memcommit.llm_providers.clients.codex import CodexChatGPTProvider
from memcommit.llm_providers.clients.codex_model_catalog import (
    CodexModelOption,
    load_codex_model_catalog,
)
from memcommit.llm_providers.clients.completion import model_name
from memcommit.llm_providers.errors import QueryProviderError
from memcommit.llm_providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
)
from memcommit.application.operations.llm_provider.probe import verify_provider_response


@dataclass(frozen=True)
class CodexConfiguration:
    model: str
    reasoning_effort: str | None

    def __post_init__(self):
        model_name(self.model)
        if (
            self.reasoning_effort is not None
            and self.reasoning_effort not in CODEX_REASONING_EFFORTS
        ):
            raise ValueError("Unsupported Codex reasoning effort.")


def load_codex_configuration_catalog(provider_id: str, *, binary: Path):
    require_configurable_provider(provider_id)
    provider = CodexChatGPTProvider.connect(candidates=[binary])
    return load_codex_model_catalog(provider)


def select_codex_configuration(
    catalog: tuple[CodexModelOption, ...],
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> CodexConfiguration:
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
    return CodexConfiguration(model=chosen.model, reasoning_effort=effort)


def require_configurable_provider(provider_id: str) -> None:
    if provider_id != CODEX_CHATGPT_PROVIDER:
        raise ValueError("Configuration currently supports codex_chatgpt only.")


def connect_checked_codex_provider(
    provider_id: str,
    model: str,
    *,
    reasoning_effort: str | None = None,
    binary: Path | None = None,
):
    require_configurable_provider(provider_id)
    model_name(model)
    config = Config()
    timeout = config.semantic_timeout_seconds()
    provider = CodexChatGPTProvider.connect(
        model=model,
        reasoning_effort=reasoning_effort,
        timeout=timeout,
        service_tier=config.codex_service_tier(),
        candidates=[binary] if binary else None,
    )
    verify_provider_response(provider)
    return provider


def save_checked_provider(provider: CodexChatGPTProvider) -> None:
    """Only the caller's successfully probed provider becomes a machine default."""
    provider_id = provider.identity.provider
    require_configurable_provider(provider_id)
    values = {
        "semantic_provider": provider_id,
        f"{provider_id}_model": provider.identity.model,
    }
    values["codex_chatgpt_reasoning_effort"] = provider.identity.reasoning_effort
    values["codex_chatgpt_service_tier"] = provider.service_tier or "standard"
    Config().update(values)
