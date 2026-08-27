"""General Profiles and Study runs resolve through distinct policy modes."""

from __future__ import annotations

import pytest

from memcommit.providers.policy import (
    LEGACY_STUDY_PROVIDER_POLICY_VERSION,
    POLICY_VERSION,
    STUDY_PROVIDER_POLICY_VERSION,
    ConfiguredProviderRoute,
    ProviderPolicyError,
    ProviderPolicyOverride,
    ProviderRoute,
    resolve_operation_provider_policy,
    study_provider_config,
)


class ConfigStub:
    def __init__(
        self,
        *,
        provider: str = "codex_chatgpt",
        model: str | None = "global-model",
        reasoning: str | None = "medium",
        timeout: float = 123.0,
        default: ProviderRoute | None = None,
        operations: dict[str, ProviderRoute] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.reasoning = reasoning
        self.timeout = timeout
        self.default = default
        self.operations = operations or {}

    def semantic_provider(self) -> str:
        return self.provider

    def model_for_provider(self, provider: str) -> str | None:
        return self.model

    def codex_reasoning_effort(self) -> str | None:
        return self.reasoning

    def semantic_timeout_seconds(self) -> float:
        return self.timeout

    def provider_route(self, operation: str) -> ConfiguredProviderRoute | None:
        if operation in self.operations:
            return ConfiguredProviderRoute(
                self.operations[operation],
                "PROFILE_OPERATION",
            )
        if self.default is not None:
            return ConfiguredProviderRoute(self.default, "PROFILE_DEFAULT")
        return None


def test_general_profile_inherits_machine_default_without_an_authored_pin():
    resolved = resolve_operation_provider_policy(
        "search",
        config=ConfigStub(),
    )

    assert resolved.provider_id == "codex_chatgpt"
    assert resolved.model == "global-model"
    assert resolved.reasoning_effort == "medium"
    assert resolved.timeout_seconds == 123.0
    assert resolved.service_tier is None
    assert resolved.source == "GLOBAL_DEFAULT"
    assert resolved.version == POLICY_VERSION


def test_general_profile_default_and_operation_routes_are_composable():
    default = ProviderRoute("ollama", "qwen:latest", None, 300.0)
    query = ProviderRoute("codex_chatgpt", "gpt-5.6-luna", "low", 45.0)
    config = ConfigStub(default=default, operations={"query": query})

    search = resolve_operation_provider_policy("search", config=config)
    resolved_query = resolve_operation_provider_policy("query", config=config)

    assert search.provider_id == "ollama"
    assert search.source == "PROFILE_DEFAULT"
    assert resolved_query.model == "gpt-5.6-luna"
    assert resolved_query.reasoning_effort == "low"
    assert resolved_query.source == "PROFILE_OPERATION"


def test_study_uses_versioned_routes_independent_of_general_configuration():
    config = ConfigStub(
        provider="ollama",
        model="mutable-local-model",
        reasoning=None,
        timeout=12.0,
    )

    search = resolve_operation_provider_policy(
        "search",
        config=config,
        mode="STUDY_PARTICIPANT",
        study_policy_version=STUDY_PROVIDER_POLICY_VERSION,
    )
    ledger = resolve_operation_provider_policy(
        "compare_contexts",
        config=config,
        mode="STUDY_PARTICIPANT",
        study_policy_version=STUDY_PROVIDER_POLICY_VERSION,
    )

    assert (search.provider_id, search.model, search.reasoning_effort) == (
        "codex_chatgpt",
        "gpt-5.6-terra",
        "low",
    )
    assert search.timeout_seconds == 600.0
    assert search.source == "STUDY_POLICY"
    assert search.configuration_version == STUDY_PROVIDER_POLICY_VERSION
    assert search.service_tier == "fast"
    assert ledger.model == "gpt-5.6-sol"
    assert ledger.timeout_seconds == 900.0


def test_legacy_study_policy_retains_standard_tier_and_original_digest():
    legacy = study_provider_config(LEGACY_STUDY_PROVIDER_POLICY_VERSION)

    assert legacy.service_tier is None
    assert (
        legacy.digest
        == "9faa8cea3634d393e3b2f724077b1db14f8628ee7243de2ab75c93d22c816702"
    )


def test_unknown_study_configuration_fails_closed():
    with pytest.raises(ProviderPolicyError, match="Unsupported Study"):
        resolve_operation_provider_policy(
            "query",
            config=ConfigStub(),
            mode="STUDY_PARTICIPANT",
            study_policy_version="study-provider-config-v999",
        )


def test_only_evaluation_can_apply_an_explicit_override():
    config = ConfigStub()
    override = ProviderPolicyOverride(
        model="evaluation-model",
        reasoning_effort="low",
        timeout_seconds=42.0,
    )

    with pytest.raises(ProviderPolicyError, match="only in EVALUATION"):
        resolve_operation_provider_policy(
            "summarize_context",
            config=config,
            override=override,
        )

    resolved = resolve_operation_provider_policy(
        "summarize_context",
        config=config,
        mode="EVALUATION",
        override=override,
    )
    assert resolved.model == "evaluation-model"
    assert resolved.reasoning_effort == "low"
    assert resolved.timeout_seconds == 42.0
    assert resolved.source == "EVALUATION_OVERRIDE"
    assert len(resolved.digest) == 64
