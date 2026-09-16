"""Plan one validated provider-route update without console dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.providers.policy import ProviderRoute, ResolvedProviderPolicy
from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_LUNA_LOW_PRESET,
    CODEX_LUNA_MODEL,
    CODEX_PROVIDER_PRESETS,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
)


class ProviderRouteInputError(ValueError):
    """A caller supplied an invalid provider-route combination."""


class ProviderMachineConfiguration(Protocol):
    """Machine-local provider defaults needed while planning one route."""

    def model_for_provider(self, provider: str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class ConfigureProviderRouteRequest:
    """Adapter-neutral inputs accepted by ``provider use``."""

    provider: str
    model: str | None = None
    preset: str | None = None
    reasoning: str | None = None
    timeout_seconds: float | None = None
    context_tokens: int | None = None
    max_output_tokens: int | None = None
    thinking: str = "auto"
    zdr: bool = False


@dataclass(frozen=True, slots=True)
class PlannedProviderRoute:
    """Validated Profile route plus separate machine-local transport updates."""

    route: ProviderRoute
    selected_preset: str | None
    machine_values: dict[str, object]


def plan_provider_route(
    request: ConfigureProviderRouteRequest,
    *,
    current: ResolvedProviderPolicy,
    machine_config: ProviderMachineConfiguration,
) -> PlannedProviderRoute:
    """Validate route inputs and keep machine transport settings separate."""

    selected_provider = request.provider.strip().lower()
    if selected_provider not in SEMANTIC_PROVIDER_IDS:
        raise ProviderRouteInputError(
            "choose one of: " + ", ".join(SEMANTIC_PROVIDER_IDS)
        )
    thinking_mode = request.thinking.strip().lower()
    if thinking_mode not in {"auto", "on", "off"}:
        raise ProviderRouteInputError("--thinking must be auto, on, or off")
    selected_preset = (
        request.preset.strip().lower() if request.preset is not None else None
    )
    selected_reasoning = (
        request.reasoning.strip().lower()
        if request.reasoning is not None
        else None
    )
    if selected_preset is not None and selected_preset not in CODEX_PROVIDER_PRESETS:
        raise ProviderRouteInputError(
            "--preset must be one of: " + ", ".join(CODEX_PROVIDER_PRESETS)
        )
    if (
        selected_reasoning is not None
        and selected_reasoning not in CODEX_REASONING_EFFORTS
    ):
        raise ProviderRouteInputError(
            "--reasoning must be one of: " + ", ".join(CODEX_REASONING_EFFORTS)
        )
    if selected_provider != CODEX_CHATGPT_PROVIDER and (
        selected_preset is not None or selected_reasoning is not None
    ):
        raise ProviderRouteInputError(
            "--preset and --reasoning apply only to Codex"
        )
    if selected_preset is not None and (
        request.model is not None or request.reasoning is not None
    ):
        raise ProviderRouteInputError(
            "--preset cannot be combined with --model or --reasoning"
        )

    if selected_preset == CODEX_LUNA_LOW_PRESET:
        selected_model = CODEX_LUNA_MODEL
        selected_reasoning = "low"
    elif selected_provider == CODEX_CHATGPT_PROVIDER:
        selected_model = request.model
        selected_reasoning = selected_reasoning or "none"
    else:
        selected_model = request.model
        if selected_model is None and current.provider_id == selected_provider:
            selected_model = current.model
        if selected_model is None:
            selected_model = machine_config.model_for_provider(selected_provider)
    if selected_provider != CODEX_CHATGPT_PROVIDER and not selected_model:
        raise ProviderRouteInputError("--model is required for this provider")

    route = ProviderRoute(
        provider_id=selected_provider,
        model=selected_model,
        reasoning_effort=selected_reasoning,
        timeout_seconds=(
            request.timeout_seconds
            if request.timeout_seconds is not None
            else current.timeout_seconds
        ),
    )
    values: dict[str, object] = {}
    if selected_provider == OLLAMA_PROVIDER:
        values["llm_model"] = selected_model
        values["semantic_thinking"] = {
            "auto": "auto",
            "on": "true",
            "off": "false",
        }[thinking_mode]
    if selected_provider == OPENROUTER_PROVIDER:
        values["openrouter_zdr"] = str(request.zdr).lower()
    if request.context_tokens is not None:
        values["semantic_context_tokens"] = str(request.context_tokens)
    if request.max_output_tokens is not None:
        values["semantic_max_output_tokens"] = str(request.max_output_tokens)
    return PlannedProviderRoute(route, selected_preset, values)


__all__ = [
    "ConfigureProviderRouteRequest",
    "PlannedProviderRoute",
    "ProviderMachineConfiguration",
    "ProviderRouteInputError",
    "plan_provider_route",
]
