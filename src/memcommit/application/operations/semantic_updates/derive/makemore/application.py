"""Operation-owned orchestration for Makemore."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.application.operations.semantic_updates.derive.makemore.model import (
    MakemoreAnalysis,
    MakemoreError,
    MakemoreProvider,
    MakemoreQualityPolicy,
    MakemoreTargetContext,
    normalize_makemore_inputs,
    normalize_makemore_number,
    validate_makemore_analysis,
)
from memcommit.application.operations.semantic_updates.derive.makemore.generation import analyze_makemore
from memcommit.application.operations.semantic_updates.derive.makemore.provider_contract import (
    validate_makemore_provider_plan,
)
from memcommit.application.operations.semantic_updates.derive.makemore.config import (
    DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    MakemoreSemanticConfig,
)
from memcommit.application.capabilities.semantic.goal_focus import FrozenGoalFocus


@dataclass(frozen=True)
class MakemoreRequest:
    """Exactly one Goal-to-Rules or Rules-to-Cases request."""

    goal: str | None = None
    rules: tuple[str, ...] = ()
    goal_focus: FrozenGoalFocus | None = None
    number: int | None = None
    strict: bool = False

    def __post_init__(self) -> None:
        if self.goal is not None and (
            not isinstance(self.goal, str) or not self.goal.strip()
        ):
            raise MakemoreError("Makemore Goal must be nonempty text.")
        if not isinstance(self.rules, tuple) or any(
            not isinstance(rule, str) or not rule.strip() for rule in self.rules
        ):
            raise MakemoreError("Makemore Rules must be nonempty text.")
        if self.goal is not None and self.rules:
            raise MakemoreError("Makemore accepts either one Goal or Rules, not both.")
        if self.goal is None and not self.rules:
            raise MakemoreError("Makemore requires one Goal or at least one Rule.")
        if self.goal_focus is not None and not isinstance(
            self.goal_focus,
            FrozenGoalFocus,
        ):
            raise MakemoreError("Makemore Goal focus must be a typed frame.")
        if self.number is not None and (
            type(self.number) is not int or self.number <= 0
        ):
            raise MakemoreError("Makemore number must be a positive integer.")
        if type(self.strict) is not bool:
            raise MakemoreError("Makemore strict mode must be boolean.")
        if self.strict and self.goal is not None:
            raise MakemoreError(
                "Strict Makemore applies only when generating Cases from Rules."
            )


@dataclass(frozen=True)
class MakemoreResult:
    analysis: MakemoreAnalysis
    origin: Literal["LIVE", "PREPARED_EXACT"] = "LIVE"

    def __post_init__(self) -> None:
        if self.origin not in {"LIVE", "PREPARED_EXACT"}:
            raise ValueError("Makemore result origin is invalid.")


class MakemoreProviderSessionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[MakemoreProvider]:
        """Open one provider only after request validation and cache lookup."""


class MakemorePreparedLookup(Protocol):
    def __call__(
        self,
        request: MakemoreRequest,
        config: MakemoreSemanticConfig,
    ) -> MakemoreAnalysis | None:
        """Return one exact prepared analysis or a miss."""


def run_makemore(
    request: MakemoreRequest,
    *,
    provider_session_factory: MakemoreProviderSessionFactory,
    config: MakemoreSemanticConfig = DEFAULT_MAKEMORE_SEMANTIC_CONFIG,
    prepared_lookup: MakemorePreparedLookup | None = None,
    target_context: MakemoreTargetContext | None = None,
) -> MakemoreResult:
    """Run the same bounded use case for every public adapter."""

    if not isinstance(request, MakemoreRequest):
        raise TypeError("Makemore requires an MakemoreRequest.")
    mode, inputs = normalize_makemore_inputs(
        goal=request.goal,
        rules=request.rules,
        config=config,
    )
    number = normalize_makemore_number(
        mode=mode,
        number=request.number,
        config=config,
    )
    normalized = MakemoreRequest(
        goal=inputs[0] if mode.value == "GOAL_TO_RULES" else None,
        rules=inputs if mode.value == "RULES_TO_CASES" else (),
        goal_focus=request.goal_focus,
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
        validate_makemore_provider_plan(
            mode=mode,
            inputs=inputs,
            goal_focus=normalized.goal_focus,
            target_context=target_context,
            number=number,
            strict=normalized.strict,
            config=config,
        )
        with provider_session_factory() as provider:
            analysis = analyze_makemore(
                goal=normalized.goal,
                rules=normalized.rules,
                goal_focus=normalized.goal_focus,
                provider=provider,
                target_context=target_context,
                number=number,
                strict=normalized.strict,
                config=config,
            )
    elif (
        analysis.mode is not mode
        or analysis.inputs != inputs
        or analysis.goal_focus != normalized.goal_focus
        or analysis.target_context != target_context
        or analysis.number != number
        or analysis.quality_policy
        is not (
            MakemoreQualityPolicy.STRICT
            if normalized.strict
            else MakemoreQualityPolicy.BEST_EFFORT
        )
    ):
        raise MakemoreError(
            "The prepared Makemore analysis does not exactly match the request."
        )
    validate_makemore_analysis(analysis, config=config)
    return MakemoreResult(analysis=analysis, origin=origin)


__all__ = [
    "MakemorePreparedLookup",
    "MakemoreProviderSessionFactory",
    "MakemoreRequest",
    "MakemoreResult",
    "run_makemore",
]
