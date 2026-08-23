"""Resolve editable ordinary-Profile routes and versioned Study routes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Mapping, Protocol

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
    "PROFILE_DEFAULT",
    "PROFILE_OPERATION",
    "STUDY_POLICY",
    "EVALUATION_OVERRIDE",
]

POLICY_VERSION = "semantic-provider-policy-v2"
STUDY_PROVIDER_POLICY_VERSION = "study-provider-config-v1"


class ProviderPolicyError(ValueError):
    """An effective semantic-provider policy could not be resolved safely."""


class ProviderPolicyConfig(Protocol):
    """Machine defaults, optionally decorated with Profile-local routes."""

    def semantic_provider(self) -> str: ...

    def model_for_provider(self, provider: str) -> str | None: ...

    def codex_reasoning_effort(self) -> str | None: ...

    def semantic_timeout_seconds(self) -> float: ...


@dataclass(frozen=True)
class ProviderRoute:
    """One complete provider/model/reasoning/timeout combination."""

    provider_id: str
    model: str | None
    reasoning_effort: str | None
    timeout_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider_id,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass(frozen=True)
class ConfiguredProviderRoute:
    """One ordinary route together with its editable configuration scope."""

    route: ProviderRoute
    source: Literal[
        "GLOBAL_DEFAULT",
        "PROFILE_DEFAULT",
        "PROFILE_OPERATION",
    ]


@dataclass(frozen=True)
class StudyProviderConfig:
    """One immutable provider matrix retained for Study reproducibility."""

    version: str
    default: ProviderRoute
    operations: Mapping[str, ProviderRoute]

    def route_for(self, operation: str) -> ProviderRoute:
        return self.operations.get(operation, self.default)

    @property
    def digest(self) -> str:
        payload = json.dumps(
            {
                "version": self.version,
                "default": self.default.to_dict(),
                "operations": {
                    operation: route.to_dict()
                    for operation, route in sorted(self.operations.items())
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class OperationProviderPolicy:
    """Compatibility projection of one fixed Study route."""

    operation: str
    provider_id: str | None = None
    model: str | None = None
    reasoning_effort: str | None = None
    timeout_floor_seconds: float | None = None


@dataclass(frozen=True)
class ProviderPolicyOverride:
    """One explicit evaluation selection; never written to Profile config."""

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
    configuration_version: str | None = None

    @property
    def digest(self) -> str:
        payload = json.dumps(
            {
                "version": self.version,
                "configuration_version": self.configuration_version,
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


_STUDY_DEFAULT_ROUTE = ProviderRoute(
    provider_id=CODEX_CHATGPT_PROVIDER,
    model="gpt-5.6-sol",
    reasoning_effort="none",
    timeout_seconds=600.0,
)
_STUDY_ROUTES = {
    "search": ProviderRoute(
        provider_id=CODEX_CHATGPT_PROVIDER,
        model="gpt-5.6-terra",
        reasoning_effort="low",
        timeout_seconds=600.0,
    ),
    "query": _STUDY_DEFAULT_ROUTE,
    "help": _STUDY_DEFAULT_ROUTE,
    "forget": _STUDY_DEFAULT_ROUTE,
    "compare_contexts": ProviderRoute(
        provider_id=CODEX_CHATGPT_PROVIDER,
        model="gpt-5.6-sol",
        reasoning_effort="none",
        timeout_seconds=900.0,
    ),
    "meld_contexts": ProviderRoute(
        provider_id=CODEX_CHATGPT_PROVIDER,
        model="gpt-5.6-sol",
        reasoning_effort="none",
        timeout_seconds=900.0,
    ),
}
STUDY_PROVIDER_CONFIGS: Mapping[str, StudyProviderConfig] = {
    STUDY_PROVIDER_POLICY_VERSION: StudyProviderConfig(
        version=STUDY_PROVIDER_POLICY_VERSION,
        default=_STUDY_DEFAULT_ROUTE,
        operations=_STUDY_ROUTES,
    )
}
STUDY_PROVIDER_POLICY_DIGEST = STUDY_PROVIDER_CONFIGS[
    STUDY_PROVIDER_POLICY_VERSION
].digest


def study_provider_config(version: str | None = None) -> StudyProviderConfig:
    selected = version or STUDY_PROVIDER_POLICY_VERSION
    try:
        return STUDY_PROVIDER_CONFIGS[selected]
    except KeyError as error:
        raise ProviderPolicyError(
            f"Unsupported Study provider policy version {selected!r}."
        ) from error


def _compatibility_policy(operation: str) -> OperationProviderPolicy:
    route = STUDY_PROVIDER_CONFIGS[STUDY_PROVIDER_POLICY_VERSION].route_for(operation)
    return OperationProviderPolicy(
        operation=operation,
        provider_id=route.provider_id,
        model=route.model,
        reasoning_effort=route.reasoning_effort,
        timeout_floor_seconds=(
            route.timeout_seconds
            if operation in {"compare_contexts", "meld_contexts"}
            else None
        ),
    )


# These names remain for frozen public/evaluation adapters. They are projections
# of the Study matrix, not production overrides for an ordinary Profile.
FIND_PROVIDER_POLICY = _compatibility_policy("search")
QUERY_PROVIDER_POLICY = _compatibility_policy("query")
HELP_PROVIDER_POLICY = _compatibility_policy("help")
FORGET_PROVIDER_POLICY = _compatibility_policy("forget")
COMPARE_LEDGER_PROVIDER_POLICY = _compatibility_policy("compare_contexts")
MELD_PROVIDER_POLICY = _compatibility_policy("meld_contexts")
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
    """Return the compatibility Study projection for one operation."""

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


def _global_route(config: ProviderPolicyConfig) -> ConfiguredProviderRoute:
    provider = str(_config_value(config, "semantic_provider"))
    model = _config_value(config, "model_for_provider", provider)
    reasoning = (
        _config_value(config, "codex_reasoning_effort")
        if provider == CODEX_CHATGPT_PROVIDER
        else None
    )
    return ConfiguredProviderRoute(
        route=ProviderRoute(
            provider_id=provider,
            model=model if isinstance(model, str) else None,
            reasoning_effort=reasoning if isinstance(reasoning, str) else None,
            timeout_seconds=float(
                _config_value(config, "semantic_timeout_seconds")
            ),
        ),
        source="GLOBAL_DEFAULT",
    )


def _configured_route(
    operation: str,
    config: ProviderPolicyConfig,
) -> ConfiguredProviderRoute:
    reader = getattr(config, "provider_route", None)
    if callable(reader):
        configured = reader(operation)
        if configured is not None:
            if not isinstance(configured, ConfiguredProviderRoute):
                raise ProviderPolicyError(
                    "Profile provider route has an invalid configuration value."
                )
            return configured
    return _global_route(config)


def validate_provider_route(route: ProviderRoute) -> ProviderRoute:
    if route.provider_id not in SEMANTIC_PROVIDER_IDS:
        raise ProviderPolicyError(
            f"Unsupported semantic provider {route.provider_id!r}."
        )
    model = route.model
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ProviderPolicyError("Semantic provider model must be non-empty.")
    if route.provider_id != CODEX_CHATGPT_PROVIDER and model is None:
        raise ProviderPolicyError(
            f"The {route.provider_id} provider route requires an explicit model."
        )
    reasoning = route.reasoning_effort
    if route.provider_id == CODEX_CHATGPT_PROVIDER:
        reasoning = reasoning or "none"
        if reasoning not in CODEX_REASONING_EFFORTS:
            raise ProviderPolicyError(
                f"Unsupported Codex reasoning effort {reasoning!r}."
            )
    elif reasoning is not None:
        raise ProviderPolicyError(
            "Reasoning effort applies only to the Codex ChatGPT provider."
        )
    timeout = route.timeout_seconds
    if (
        not isinstance(timeout, (int, float))
        or isinstance(timeout, bool)
        or timeout <= 0
    ):
        raise ProviderPolicyError("Semantic provider timeout must be positive.")
    return ProviderRoute(
        provider_id=route.provider_id,
        model=model,
        reasoning_effort=reasoning,
        timeout_seconds=float(timeout),
    )


def resolve_operation_provider_policy(
    operation: str,
    *,
    config: ProviderPolicyConfig,
    mode: ProviderPolicyMode = "PRODUCTION",
    override: ProviderPolicyOverride | None = None,
    study_policy_version: str | None = None,
) -> ResolvedProviderPolicy:
    """Resolve an editable general route or one immutable Study route."""

    if not isinstance(operation, str) or not operation.strip():
        raise ProviderPolicyError("Semantic provider operation must be non-empty.")
    if mode not in {"PRODUCTION", "STUDY_PARTICIPANT", "EVALUATION"}:
        raise ProviderPolicyError("Unknown semantic provider policy mode.")
    if override is not None and mode != "EVALUATION":
        raise ProviderPolicyError(
            "Semantic provider overrides are available only in EVALUATION mode."
        )

    configuration_version: str | None = None
    if mode == "STUDY_PARTICIPANT":
        study = study_provider_config(study_policy_version)
        route = study.route_for(operation)
        source: ProviderPolicySource = "STUDY_POLICY"
        configuration_version = study.version
    else:
        configured = _configured_route(operation, config)
        route = configured.route
        source = configured.source

    if override is not None:
        provider = override.provider_id or route.provider_id
        if override.model is not None:
            model: str | None = override.model
        elif provider == route.provider_id:
            model = route.model
        else:
            configured_model = _config_value(config, "model_for_provider", provider)
            model = configured_model if isinstance(configured_model, str) else None
        route = ProviderRoute(
            provider_id=provider,
            model=model,
            reasoning_effort=(
                override.reasoning_effort
                if override.reasoning_effort is not None
                else route.reasoning_effort
                if provider == route.provider_id
                else None
            ),
            timeout_seconds=(
                override.timeout_seconds
                if override.timeout_seconds is not None
                else route.timeout_seconds
            ),
        )
        source = "EVALUATION_OVERRIDE"

    route = validate_provider_route(route)
    return ResolvedProviderPolicy(
        operation=operation,
        mode=mode,
        provider_id=route.provider_id,
        model=route.model,
        reasoning_effort=route.reasoning_effort,
        timeout_seconds=route.timeout_seconds,
        source=source,
        configuration_version=configuration_version,
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
    "ConfiguredProviderRoute",
    "FIND_PROVIDER_POLICY",
    "FORGET_PROVIDER_POLICY",
    "HELP_PROVIDER_POLICY",
    "MELD_PROVIDER_POLICY",
    "OPERATION_PROVIDER_POLICIES",
    "OperationProviderPolicy",
    "POLICY_VERSION",
    "ProviderPolicyConfig",
    "ProviderPolicyError",
    "ProviderPolicyMode",
    "ProviderPolicyOverride",
    "ProviderPolicySource",
    "ProviderRoute",
    "QUERY_PROVIDER_POLICY",
    "ResolvedProviderPolicy",
    "STUDY_PROVIDER_CONFIGS",
    "STUDY_PROVIDER_POLICY_DIGEST",
    "STUDY_PROVIDER_POLICY_VERSION",
    "StudyProviderConfig",
    "operation_provider_policy",
    "resolve_codex_evaluation_policy",
    "resolve_operation_provider_policy",
    "study_provider_config",
    "validate_provider_route",
]
