"""Public Fit assembly without a dependency on the client facade."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import semantic_provider
from memcommit.api.errors import (
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.api.semantic import FitJudgmentResult, FitPropositionInput
from memcommit.fit_application import FitPropositionsRequest
from memcommit.fit_judgment import FitJudgmentError, FitProposition
from memcommit.fit_runtime import run_proposition_fit
from memcommit.query_provider import QueryProviderError


def _fit_inputs(
    values: Sequence[str | FitPropositionInput],
    *,
    prefix: str,
) -> tuple[tuple[FitPropositionInput, ...], tuple[FitProposition, ...]]:
    if isinstance(values, (str, bytes)):
        raise TypeError("Fit inputs must be a sequence of propositions.")
    public: list[FitPropositionInput] = []
    core: list[FitProposition] = []
    for index, value in enumerate(values, 1):
        item = FitPropositionInput(value) if isinstance(value, str) else value
        if not isinstance(item, FitPropositionInput):
            raise TypeError("Fit inputs must be text or FitPropositionInput values.")
        alias = item.alias or f"{prefix}{index}"
        typed = FitProposition(
            alias=alias,
            content=item.content,
            role=item.role,  # type: ignore[arg-type]
        )
        public.append(
            FitPropositionInput(
                content=typed.content,
                role=typed.role,
                alias=typed.alias,
            )
        )
        core.append(typed)
    return tuple(public), tuple(core)


def fit(
    runtime: ClientRuntime,
    propositions: Sequence[str | FitPropositionInput],
    *,
    background: Sequence[str | FitPropositionInput] = (),
) -> FitJudgmentResult:
    """Judge one complete proposition set without reading or changing Store state."""

    try:
        public_propositions, core_propositions = _fit_inputs(
            propositions,
            prefix="p",
        )
        public_background, core_background = _fit_inputs(background, prefix="k")
        request = FitPropositionsRequest(
            propositions=core_propositions,
            background=core_background,
        )
    except (FitJudgmentError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = run_proposition_fit(
            request,
            provider_factory=lambda: semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FitJudgmentError as error:
        raise_public(SemanticExecutionError, error)
    assessment = result.analysis.assessment
    return FitJudgmentResult(
        analysis_uid=result.analysis.uid,
        verdict=assessment.verdict,
        reason=assessment.reason,
        propositions=public_propositions,
        background=public_background,
        considered_aliases=assessment.considered_proposition_ids,
        material_aliases=assessment.material_proposition_ids,
        consistent_reading=assessment.consistent_reading,
        inconsistent_reading=assessment.inconsistent_reading,
    )


__all__ = ["fit"]
