"""Interface-independent orchestration for Elaborate."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.elaborate import (
    ElaborateAnalysis,
    ElaborateError,
    ElaborateProvider,
    ElaborateQualityPolicy,
    ElaborateTargetContext,
    normalize_elaborate_inputs,
    normalize_elaborate_number,
    analyze_elaborate,
    validate_elaborate_analysis,
    validate_elaborate_provider_plan,
)
from memcommit.elaborate_config import (
    DEFAULT_ELABORATE_SEMANTIC_CONFIG,
    ElaborateSemanticConfig,
)


@dataclass(frozen=True)
class ElaborateRequest:
    """Exactly one Goal-to-Rules or Rules-to-Cases request."""

    goal: str | None = None
    rules: tuple[str, ...] = ()
    number: int | None = None
    strict: bool = False

    def __post_init__(self) -> None:
        if self.goal is not None and (
            not isinstance(self.goal, str) or not self.goal.strip()
        ):
            raise ElaborateError("Elaborate Goal must be nonempty text.")
        if not isinstance(self.rules, tuple) or any(
            not isinstance(rule, str) or not rule.strip() for rule in self.rules
        ):
            raise ElaborateError("Elaborate Rules must be nonempty text.")
        if self.goal is not None and self.rules:
            raise ElaborateError("Elaborate accepts either one Goal or Rules, not both.")
        if self.goal is None and not self.rules:
            raise ElaborateError("Elaborate requires one Goal or at least one Rule.")
        if self.number is not None and (
            type(self.number) is not int or self.number <= 0
        ):
            raise ElaborateError("Elaborate number must be a positive integer.")
        if type(self.strict) is not bool:
            raise ElaborateError("Elaborate strict must be a boolean.")
        if self.strict and self.goal is not None:
            raise ElaborateError("Strict Elaborate applies only to Rules-to-Cases.")


@dataclass(frozen=True)
class ElaborateResult:
    analysis: ElaborateAnalysis
    origin: Literal["LIVE", "PREPARED_EXACT"] = "LIVE"

    def __post_init__(self) -> None:
        if self.origin not in {"LIVE", "PREPARED_EXACT"}:
            raise ValueError("Elaborate result origin is invalid.")


class ElaborateProviderSessionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[ElaborateProvider]:
        """Open one provider only after request validation and cache lookup."""


class ElaboratePreparedLookup(Protocol):
    def __call__(
        self,
        request: ElaborateRequest,
        config: ElaborateSemanticConfig,
    ) -> ElaborateAnalysis | None:
        """Return one exact prepared analysis or a miss."""


def run_elaborate(
    request: ElaborateRequest,
    *,
    provider_session_factory: ElaborateProviderSessionFactory,
    config: ElaborateSemanticConfig = DEFAULT_ELABORATE_SEMANTIC_CONFIG,
    prepared_lookup: ElaboratePreparedLookup | None = None,
    target_context: ElaborateTargetContext | None = None,
) -> ElaborateResult:
    """Run the same bounded use case for every public adapter."""

    if not isinstance(request, ElaborateRequest):
        raise TypeError("Elaborate requires an ElaborateRequest.")
    mode, inputs = normalize_elaborate_inputs(
        goal=request.goal,
        rules=request.rules,
        config=config,
    )
    number = normalize_elaborate_number(
        mode=mode,
        number=request.number,
        config=config,
    )
    normalized = ElaborateRequest(
        goal=inputs[0] if mode.value == "GOAL_TO_RULES" else None,
        rules=inputs if mode.value == "RULES_TO_CASES" else (),
        number=number,
        strict=request.strict,
    )
    analysis = (
        prepared_lookup(normalized, config)
        if prepared_lookup is not None and target_context is None
        else None
    )
    origin: Literal["LIVE", "PREPARED_EXACT"] = "PREPARED_EXACT"
    if analysis is None:
        origin = "LIVE"
        validate_elaborate_provider_plan(
            mode=mode,
            inputs=inputs,
            target_context=target_context,
            number=number,
            strict=normalized.strict,
            config=config,
        )
        with provider_session_factory() as provider:
            analysis = analyze_elaborate(
                goal=normalized.goal,
                rules=normalized.rules,
                provider=provider,
                target_context=target_context,
                number=number,
                strict=normalized.strict,
                config=config,
            )
    elif (
        analysis.mode is not mode
        or analysis.inputs != inputs
        or analysis.target_context != target_context
        or analysis.number != number
        or analysis.quality_policy
        is not (
            ElaborateQualityPolicy.STRICT
            if normalized.strict
            else ElaborateQualityPolicy.BEST_EFFORT
        )
    ):
        raise ElaborateError(
            "The prepared Elaborate analysis does not exactly match the request."
        )
    validate_elaborate_analysis(analysis, config=config)
    return ElaborateResult(analysis=analysis, origin=origin)


__all__ = [
    "ElaboratePreparedLookup",
    "ElaborateProviderSessionFactory",
    "ElaborateRequest",
    "ElaborateResult",
    "run_elaborate",
]
