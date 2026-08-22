"""Single resolution plane for production and Study semantic providers.

The user configuration stores defaults.  This module owns the operation-level
policy that may deliberately pin or bound those defaults, and it records the
source of every effective value so Study artifacts can reproduce production
without inheriting an evaluation-only override by accident.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    SEMANTIC_PROVIDER_IDS,
)


ProviderPolicyMode = Literal[
    "PRODUCTION",
    "STUDY_PARTICIPANT",
    "EVALUATION",
]
ProviderPolicySource = Literal[
    "GLOBAL_DEFAULT",
    "OPERATION_POLICY",
    "EVALUATION_OVERRIDE",
]

POLICY_VERSION = "semantic-provider-policy-v1"


class ProviderPolicyError(ValueError):
    """An effective semantic-provider policy could not be resolved safely."""


class ProviderPolicyConfig(Protocol):
    def semantic_provider(self) -> str: ...

    def model_for_provider(self, provider: str) -> str | None: ...

    def codex_reasoning_effort(self) -> str | None: ...

    def semantic_timeout_seconds(self) -> float: ...


@dataclass(frozen=True)
class OperationProviderPolicy:
    """Version-controlled policy for one provider-visible operation."""

    operation: str
    provider_id: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    timeout_floor_seconds: float | None = None


@dataclass(frozen=True)
class ProviderPolicyOverride:
    """One explicit evaluation selection; never written to global config."""

    provider_id: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class ResolvedProviderPolicy:
    """Complete effective identity shared by runtime and Study artifacts."""

    operation: str
    mode: ProviderPolicyMode
    provider_id: str
    model: str | None
    reasoning_effort: str | None
    timeout_seconds: float
    source: ProviderPolicySource
    version: str = POLICY_VERSION

    @property
    def digest(self) -> str:
        payload = json.dumps(
            {
                "version": self.version,
                "operation": self.operation,
                "mode": self.mode,
                "provider": self.provider_id,
                "model": self.model,
                "reasoning": self.reasoning_effort,
                "timeout_seconds": self.timeout_seconds,
                "source": self.source,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


# These are evaluated exceptions to the global default, not user preferences.
# Every other semantic operation deliberately inherits the same resolved global
# identity in production and in a participant Study run.
FIND_PROVIDER_POLICY = OperationProviderPolicy(
    operation="search",
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-5.6-terra",
    reasoning_effort="low",
)
QUERY_PROVIDER_POLICY = OperationProviderPolicy(
    operation="query",
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-5.6-sol",
    reasoning_effort="none",
)
HELP_PROVIDER_POLICY = OperationProviderPolicy(
    operation="help",
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-5.6-sol",
    reasoning_effort="none",
)
FORGET_PROVIDER_POLICY = OperationProviderPolicy(
    operation="forget",
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-5.6-sol",
    reasoning_effort="none",
)
COMPARE_LEDGER_PROVIDER_POLICY = OperationProviderPolicy(
    operation="compare_contexts",
    timeout_floor_seconds=900.0,
)
MELD_PROVIDER_POLICY = OperationProviderPolicy(
    operation="meld_contexts",
    timeout_floor_seconds=900.0,
)

OPERATION_PROVIDER_POLICIES: dict[str, OperationProviderPolicy] = {
    policy.operation: policy
    for policy in (
        FIND_PROVIDER_POLICY,
        QUERY_PROVIDER_POLICY,
        HELP_PROVIDER_POLICY,
        FORGET_PROVIDER_POLICY,
        COMPARE_LEDGER_PROVIDER_POLICY,
        MELD_PROVIDER_POLICY,
    )
}


def operation_provider_policy(operation: str) -> OperationProviderPolicy:
    """Return the authored rule, or an explicit inherit-global rule."""

    if not isinstance(operation, str) or not operation.strip():
        raise ProviderPolicyError("Semantic provider operation must be non-empty.")
    return OPERATION_PROVIDER_POLICIES.get(
        operation,
        OperationProviderPolicy(operation=operation),
    )


def _config_value(config: object, method: str, *args: object) -> object:
    reader = getattr(config, method, None)
    if not callable(reader):
        raise ProviderPolicyError(
            f"Semantic provider configuration lacks {method}()."
        )
    return reader(*args)


def resolve_operation_provider_policy(
    operation: str,
    *,
    config: ProviderPolicyConfig,
    mode: ProviderPolicyMode = "PRODUCTION",
    override: ProviderPolicyOverride | None = None,
) -> ResolvedProviderPolicy:
    """Resolve one operation identically for production and participant Study.

    Evaluation may override the frozen identity explicitly.  Production and
    participant Study reject that route so an experiment cannot silently alter
    the behavior being studied.
    """

    if mode not in {"PRODUCTION", "STUDY_PARTICIPANT", "EVALUATION"}:
        raise ProviderPolicyError("Unknown semantic provider policy mode.")
    if override is not None and mode != "EVALUATION":
        raise ProviderPolicyError(
            "Semantic provider overrides are available only in EVALUATION mode."
        )

    rule = operation_provider_policy(operation)
    configured_provider = (
        str(_config_value(config, "semantic_provider"))
        if rule.provider_id is None
        else rule.provider_id
    )
    selected_provider = (
        override.provider_id
        if override is not None and override.provider_id is not None
        else configured_provider
    )
    if selected_provider not in SEMANTIC_PROVIDER_IDS:
        raise ProviderPolicyError(
            f"Unsupported semantic provider {selected_provider!r}."
        )

    if override is not None and override.model is not None:
        model = override.model
    elif rule.model is not None and selected_provider == rule.provider_id:
        model = rule.model
    else:
        model = _config_value(
            config,
            "model_for_provider",
            selected_provider,
        )
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ProviderPolicyError("Semantic provider model must be non-empty.")

    reasoning: str | None = None
    if selected_provider == CODEX_CHATGPT_PROVIDER:
        if override is not None and override.reasoning_effort is not None:
            reasoning = override.reasoning_effort
        elif (
            rule.reasoning_effort is not None
            and selected_provider == rule.provider_id
        ):
            reasoning = rule.reasoning_effort
        else:
            reasoning = _config_value(config, "codex_reasoning_effort")
        # Do not let the Codex CLI silently choose a changing model default.
        # None is the common latency baseline unless a person or an evaluated
        # operation policy deliberately selects a stronger reasoning tier.
        reasoning = reasoning or "none"
        if reasoning is not None and reasoning not in CODEX_REASONING_EFFORTS:
            raise ProviderPolicyError(
                f"Unsupported Codex reasoning effort {reasoning!r}."
            )
    elif override is not None and override.reasoning_effort is not None:
        raise ProviderPolicyError(
            "Reasoning effort applies only to the Codex ChatGPT provider."
        )

    configured_timeout = float(
        _config_value(config, "semantic_timeout_seconds")
    )
    timeout = (
        override.timeout_seconds
        if override is not None and override.timeout_seconds is not None
        else configured_timeout
    )
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ProviderPolicyError("Semantic provider timeout must be positive.")
    if rule.timeout_floor_seconds is not None:
        timeout = max(float(timeout), rule.timeout_floor_seconds)

    source: ProviderPolicySource = (
        "EVALUATION_OVERRIDE"
        if override is not None
        else "OPERATION_POLICY"
        if any(
            value is not None
            for value in (
                rule.provider_id,
                rule.model,
                rule.reasoning_effort,
                rule.timeout_floor_seconds,
            )
        )
        else "GLOBAL_DEFAULT"
    )
    return ResolvedProviderPolicy(
        operation=operation,
        mode=mode,
        provider_id=selected_provider,
        model=model,
        reasoning_effort=reasoning,
        timeout_seconds=float(timeout),
        source=source,
    )


def resolve_codex_evaluation_policy(
    operation: str,
    *,
    config: ProviderPolicyConfig,
    model: str | None = None,
    reasoning_effort: str | None = None,
    timeout_seconds: float | None = None,
) -> ResolvedProviderPolicy:
    """Resolve a reproducible Codex-only offline evaluation selection."""

    return resolve_operation_provider_policy(
        operation,
        config=config,
        mode="EVALUATION",
        override=ProviderPolicyOverride(
            provider_id=CODEX_CHATGPT_PROVIDER,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
        ),
    )


__all__ = [
    "COMPARE_LEDGER_PROVIDER_POLICY",
    "FIND_PROVIDER_POLICY",
    "FORGET_PROVIDER_POLICY",
    "HELP_PROVIDER_POLICY",
    "MELD_PROVIDER_POLICY",
    "OPERATION_PROVIDER_POLICIES",
    "POLICY_VERSION",
    "QUERY_PROVIDER_POLICY",
    "OperationProviderPolicy",
    "ProviderPolicyConfig",
    "ProviderPolicyError",
    "ProviderPolicyMode",
    "ProviderPolicyOverride",
    "ProviderPolicySource",
    "ResolvedProviderPolicy",
    "operation_provider_policy",
    "resolve_codex_evaluation_policy",
    "resolve_operation_provider_policy",
]


__all__ = [
    "COMPARE_LEDGER_PROVIDER_POLICY",
    "FIND_PROVIDER_POLICY",
    "FORGET_PROVIDER_POLICY",
    "HELP_PROVIDER_POLICY",
    "MELD_PROVIDER_POLICY",
    "OPERATION_PROVIDER_POLICIES",
    "OperationProviderPolicy",
    "POLICY_VERSION",
    "ProviderPolicyError",
    "ProviderPolicyMode",
    "ProviderPolicyOverride",
    "ProviderPolicySource",
    "QUERY_PROVIDER_POLICY",
    "ResolvedProviderPolicy",
    "operation_provider_policy",
    "resolve_operation_provider_policy",
]
