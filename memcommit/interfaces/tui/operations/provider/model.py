"""Typed process-local values for the Provider configuration screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
)


@dataclass(frozen=True)
class ProviderRouteView:
    """One already-resolved route rendered without contacting a provider."""

    provider_id: str
    model: str | None
    reasoning_effort: str | None
    timeout_seconds: float

    def __post_init__(self) -> None:
        if self.provider_id not in SEMANTIC_PROVIDER_IDS:
            raise ValueError("Provider route view has an unsupported provider.")
        if self.model is not None and (
            not isinstance(self.model, str) or not self.model.strip()
        ):
            raise ValueError("Provider route model must be nonblank when present.")
        if self.provider_id == CODEX_CHATGPT_PROVIDER:
            if (
                self.reasoning_effort is not None
                and self.reasoning_effort not in CODEX_REASONING_EFFORTS
            ):
                raise ValueError("Provider route reasoning effort is invalid.")
        elif self.reasoning_effort is not None:
            raise ValueError("Only Codex routes may carry reasoning effort.")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("Provider route timeout must be positive.")


@dataclass(frozen=True)
class ProviderTuiSetup:
    """Frozen Profile scope and display-only route inventory for one TUI run."""

    profile_name: str
    mode: Literal["GENERAL", "STUDY"]
    default_route: ProviderRouteView
    route_source: str
    operation_routes: tuple[tuple[str, ProviderRouteView], ...] = ()
    has_profile_default: bool = False
    known_models: tuple[tuple[str, str | None], ...] = ()
    ollama_thinking: Literal["auto", "on", "off"] = "auto"
    openrouter_zdr: bool = False
    study_policy_version: str | None = None
    study_policy_digest: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile_name, str) or not self.profile_name.strip():
            raise ValueError("Provider TUI requires a Profile name.")
        if self.mode not in {"GENERAL", "STUDY"}:
            raise ValueError("Provider TUI mode is invalid.")
        if not isinstance(self.default_route, ProviderRouteView):
            raise TypeError("Provider TUI requires one default route view.")
        if not isinstance(self.route_source, str) or not self.route_source.strip():
            raise ValueError("Provider TUI route source is required.")
        operation_names = tuple(name for name, _route in self.operation_routes)
        if (
            len(set(operation_names)) != len(operation_names)
            or any(
                not isinstance(name, str) or not name.strip()
                for name in operation_names
            )
            or any(
                not isinstance(route, ProviderRouteView)
                for _name, route in self.operation_routes
            )
        ):
            raise ValueError("Provider TUI operation routes are invalid.")
        known_ids = tuple(provider for provider, _model in self.known_models)
        if len(set(known_ids)) != len(known_ids) or any(
            provider not in SEMANTIC_PROVIDER_IDS for provider in known_ids
        ):
            raise ValueError("Provider TUI known models are invalid.")
        if any(
            model is not None and (not isinstance(model, str) or not model.strip())
            for _provider, model in self.known_models
        ):
            raise ValueError("Provider TUI known model must be nonblank when present.")
        if self.ollama_thinking not in {"auto", "on", "off"}:
            raise ValueError("Provider TUI Ollama thinking mode is invalid.")
        if not isinstance(self.openrouter_zdr, bool):
            raise TypeError("Provider TUI OpenRouter ZDR state must be boolean.")
        if self.mode == "STUDY" and (
            not self.study_policy_version or not self.study_policy_digest
        ):
            raise ValueError("Study Provider TUI requires its pinned policy identity.")

    def known_model(self, provider_id: str) -> str | None:
        return dict(self.known_models).get(provider_id)


@dataclass(frozen=True)
class ProviderUseDraft:
    """One complete TUI selection before the command revalidates and writes it."""

    provider_id: str
    model: str | None
    reasoning_effort: str | None
    operation: str | None
    ollama_thinking: Literal["auto", "on", "off"] = "auto"
    openrouter_zdr: bool = False

    def __post_init__(self) -> None:
        if self.provider_id not in SEMANTIC_PROVIDER_IDS:
            raise ValueError("Choose a supported semantic provider.")
        if self.model is not None and (
            not isinstance(self.model, str) or not self.model.strip()
        ):
            raise ValueError("Provider model must be nonblank when present.")
        if (
            self.provider_id in {OLLAMA_PROVIDER, OPENROUTER_PROVIDER}
            and not self.model
        ):
            raise ValueError("Enter a model for this provider.")
        if self.provider_id == CODEX_CHATGPT_PROVIDER:
            if self.reasoning_effort not in CODEX_REASONING_EFFORTS:
                raise ValueError("Choose a Codex reasoning effort.")
        elif self.reasoning_effort is not None:
            raise ValueError("Only Codex routes may carry reasoning effort.")
        if self.operation is not None and (
            not isinstance(self.operation, str) or not self.operation.strip()
        ):
            raise ValueError("Provider operation must be nonblank when present.")
        if self.ollama_thinking not in {"auto", "on", "off"}:
            raise ValueError("Ollama thinking mode must be auto, on, or off.")
        if not isinstance(self.openrouter_zdr, bool):
            raise TypeError("OpenRouter ZDR state must be boolean.")


@dataclass(frozen=True)
class ProviderTuiAction:
    """One reviewed action returned to the provider command adapter."""

    kind: Literal["USE", "RESET", "PROBE"]
    draft: ProviderUseDraft | None = None
    operation: str | None = None

    def __post_init__(self) -> None:
        if self.kind == "USE":
            if (
                not isinstance(self.draft, ProviderUseDraft)
                or self.operation is not None
            ):
                raise ValueError("Provider USE requires exactly one typed draft.")
            return
        if self.draft is not None:
            raise ValueError("Provider RESET and PROBE do not carry a USE draft.")
        if self.operation is not None and (
            not isinstance(self.operation, str) or not self.operation.strip()
        ):
            raise ValueError("Provider action operation must be nonblank when present.")
