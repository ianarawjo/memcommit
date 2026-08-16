"""Public Elaborate assembly without a dependency on the client facade."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import (
    raise_semantic_execution_error,
    semantic_provider,
)
from memcommit.api.errors import (
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.semantic import (
    ElaborateCaseProposal,
    ElaborateProposal,
    ElaborateRuleProposal,
)
from memcommit.elaborate import ElaborateError
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.query_provider import QueryProviderError


def _project_elaborate(result) -> ElaborateProposal:
    analysis = result.analysis
    return ElaborateProposal(
        analysis_uid=analysis.uid,
        mode=analysis.mode.value,
        inputs=analysis.inputs,
        overview=analysis.overview,
        rules=tuple(
            ElaborateRuleProposal(
                uid=rule.uid,
                content=rule.content,
                rationale=rule.rationale,
            )
            for rule in analysis.rules
        ),
        cases=tuple(
            ElaborateCaseProposal(
                uid=case.uid,
                proposition=case.proposition,
                expected=case.expected,
                rationale=case.rationale,
                case_role=case.case_role,
                source_rule_index=case.source_rule_index,
            )
            for case in analysis.cases
        ),
        origin=result.origin,
    )


def elaborate(
    runtime: ClientRuntime,
    *,
    goal: str | None = None,
    rules: Sequence[str] | None = None,
) -> ElaborateProposal:
    """Propose unverified Rules from a Goal or Cases from Rules."""

    try:
        if isinstance(rules, (str, bytes)):
            raise TypeError("rules must be a sequence of Rule texts.")
        request = ElaborateRequest(goal=goal, rules=tuple(rules or ()))
    except (ElaborateError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = execute_elaborate(
            request,
            provider_factory=lambda: semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except ElaborateError as error:
        raise_public(SemanticExecutionError, error)
    return _project_elaborate(result)


def elaborate_ground(
    runtime: ClientRuntime,
    ground_name: str,
    *,
    direction: str,
) -> ElaborateProposal:
    """Project one exact Ground Goal or Rule set through Elaborate."""

    if not isinstance(ground_name, str) or not ground_name.strip():
        raise SemanticInputError("ground_name must be nonblank text.")
    if direction not in {"GOAL_TO_RULES", "RULES_TO_CASES"}:
        raise SemanticInputError(
            "direction must be GOAL_TO_RULES or RULES_TO_CASES."
        )
    # Keep standalone Elaborate importable and callable without Ground.
    from memcommit.ground_elaborate import (
        execute_ground_elaborate,
        freeze_ground_elaborate,
    )

    try:
        frozen = freeze_ground_elaborate(
            runtime.store,
            ground_name=ground_name,
            direction=direction,  # type: ignore[arg-type]
        )
        result = execute_ground_elaborate(
            frozen,
            store=runtime.store,
            provider_factory=lambda: semantic_provider(runtime),
        ).elaborate
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except ElaborateError as error:
        raise_semantic_execution_error(error)
    return _project_elaborate(result)


__all__ = ["elaborate", "elaborate_ground"]
