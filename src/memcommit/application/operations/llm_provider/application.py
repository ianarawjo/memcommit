"""Select a provider independently from editing its saved configuration."""

from memcommit.configuration.config import Config
from memcommit.llm_providers.settings import DEFAULT_PROVIDER_SETTINGS
from memcommit.llm_providers.types import CODEX_CHATGPT_PROVIDER
from .codex_configuration import CodexConfiguration, require_configurable_provider


def read_codex_configuration(config: Config) -> CodexConfiguration:
    """Keep explicit provider-default reasoning distinct from an absent setting."""
    values = config.all()
    return CodexConfiguration(
        model=config.model_for_provider(CODEX_CHATGPT_PROVIDER)
        or DEFAULT_PROVIDER_SETTINGS.model,
        reasoning_effort=(
            config.codex_reasoning_effort()
            if "codex_chatgpt_reasoning_effort" in values
            else DEFAULT_PROVIDER_SETTINGS.reasoning_effort
        ),
    )


def save_codex_configuration(config: Config, configuration: CodexConfiguration) -> None:
    """Only the edited model/reasoning change; selection and hidden options survive."""
    config.update(
        {
            "codex_chatgpt_model": configuration.model,
            "codex_chatgpt_reasoning_effort": configuration.reasoning_effort,
        }
    )


def select_provider(config: Config, provider_id: str) -> None:
    require_configurable_provider(provider_id)
    config.update({"semantic_provider": provider_id})


def reset_codex_configuration(config: Config) -> None:
    save_codex_configuration(
        config,
        CodexConfiguration(
            model=DEFAULT_PROVIDER_SETTINGS.model,
            reasoning_effort=DEFAULT_PROVIDER_SETTINGS.reasoning_effort,
        ),
    )
