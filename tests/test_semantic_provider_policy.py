"""One provider-policy resolution plane for runtime and Study."""

from __future__ import annotations

import pytest

from memcommit.infrastructure.providers.policy import (
    POLICY_VERSION,
    ProviderPolicyError,
    ProviderPolicyOverride,
    resolve_operation_provider_policy,
)


class ConfigStub:
    def __init__(
        self,
        *,
        provider: str = "codex_chatgpt",
        model: str | None = "global-model",
        reasoning: str | None = "medium",
        timeout: float = 123.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.reasoning = reasoning
        self.timeout = timeout

    def semantic_provider(self) -> str:
        return self.provider

    def model_for_provider(self, provider: str) -> str | None:
        return self.model

    def codex_reasoning_effort(self) -> str | None:
        return self.reasoning

    def semantic_timeout_seconds(self) -> float:
        return self.timeout


def test_participant_study_uses_the_same_effective_identity_as_production():
    config = ConfigStub()

    production = resolve_operation_provider_policy(
        "compare_summary",
        config=config,
    )
    study = resolve_operation_provider_policy(
        "compare_summary",
        config=config,
        mode="STUDY_PARTICIPANT",
    )

    assert (
        production.provider_id,
        production.model,
        production.reasoning_effort,
        production.timeout_seconds,
    ) == (
        study.provider_id,
        study.model,
        study.reasoning_effort,
        study.timeout_seconds,
    )
    assert production.source == study.source == "GLOBAL_DEFAULT"
    assert production.version == study.version == POLICY_VERSION


def test_operation_pins_and_timeout_floor_are_resolved_centrally():
    config = ConfigStub(timeout=100.0)

    find = resolve_operation_provider_policy("search", config=config)
    ledger = resolve_operation_provider_policy("compare_contexts", config=config)

    assert (find.provider_id, find.model, find.reasoning_effort) == (
        "codex_chatgpt",
        "gpt-5.6-terra",
        "low",
    )
    assert find.source == "OPERATION_POLICY"
    assert ledger.timeout_seconds == 900.0
    assert ledger.source == "OPERATION_POLICY"


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
