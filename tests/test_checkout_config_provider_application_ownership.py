"""Application ownership for formerly console-only operations."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from memcommit.application.operations.checkout import (
    CheckoutAction,
    CheckoutRequest,
    plan_checkout,
)
from memcommit.application.operations.config import (
    list_configuration,
    set_configuration,
)
from memcommit.application.operations.provider import (
    ConfigureProviderRouteRequest,
    ProviderRouteInputError,
    plan_provider_route,
)
from memcommit.providers.policy import ResolvedProviderPolicy


@dataclass
class _Configuration:
    values: dict[str, object] = field(default_factory=dict)

    def all(self) -> dict[str, object]:
        return dict(self.values)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value

    def model_for_provider(self, provider: str) -> str | None:
        return {"ollama": "llama-test"}.get(provider)


def _current_provider() -> ResolvedProviderPolicy:
    return ResolvedProviderPolicy(
        operation="semantic_default",
        mode="GENERAL",
        provider_id="codex_chatgpt",
        model=None,
        reasoning_effort="none",
        timeout_seconds=60.0,
        source="PROFILE_DEFAULT",
    )


def test_checkout_application_selects_existing_effect_operations() -> None:
    assert plan_checkout(CheckoutRequest("notes")).action is CheckoutAction.SWITCH
    branch = plan_checkout(
        CheckoutRequest("notes", create_branch=True, recursive=True)
    )
    assert branch.action is CheckoutAction.BRANCH
    assert branch.recursive is True
    with pytest.raises(ValueError, match="require -b"):
        plan_checkout(CheckoutRequest("notes", direct=True))


def test_config_application_owns_public_key_aliases() -> None:
    configuration = _Configuration()
    stored = set_configuration(configuration, "provider", "ollama")
    assert stored.key == "semantic_provider"
    assert list_configuration(configuration) == (stored,)


def test_provider_application_separates_route_and_machine_transport() -> None:
    planned = plan_provider_route(
        ConfigureProviderRouteRequest(
            provider="ollama",
            context_tokens=4096,
            thinking="off",
        ),
        current=_current_provider(),
        machine_config=_Configuration(),
    )
    assert planned.route.provider_id == "ollama"
    assert planned.route.model == "llama-test"
    assert planned.machine_values == {
        "llm_model": "llama-test",
        "semantic_thinking": "false",
        "semantic_context_tokens": "4096",
    }

    with pytest.raises(ProviderRouteInputError, match="apply only to Codex"):
        plan_provider_route(
            ConfigureProviderRouteRequest(
                provider="ollama",
                reasoning="low",
            ),
            current=_current_provider(),
            machine_config=_Configuration(),
        )
