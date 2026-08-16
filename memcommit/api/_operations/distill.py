"""Public Distill assembly without a dependency on the client facade."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import (
    raise_semantic_execution_error,
    semantic_provider,
)
from memcommit.api.errors import (
    SemanticConflictError,
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.semantic import (
    DistillApplyResult,
    DistillProposal,
    DistillRuleProposal,
)
from memcommit.distill import DistillError
from memcommit.distill_application import DistillApplyRequest, DistillRequest
from memcommit.distill_runtime import execute_distill, execute_distill_apply
from memcommit.query_provider import QueryProviderError


def _project_distill(result, *, apply_allowed: bool) -> DistillProposal:
    analysis = result.analysis
    return DistillProposal(
        analysis_uid=analysis.uid,
        source_context=analysis.source.context_name,
        source_digest=analysis.source.digest,
        goal=analysis.goal,
        overview=analysis.overview,
        rules=tuple(
            DistillRuleProposal(
                uid=rule.uid,
                content=rule.content,
                rationale=rule.rationale,
                support_memory_uids=rule.support_memory_uids,
                boundary_memory_uids=rule.boundary_memory_uids,
            )
            for rule in analysis.rules
        ),
        outside_memory_uids=analysis.outside_memory_uids,
        origin=result.origin,
        apply_allowed=apply_allowed,
        _application_result=result,
    )


def distill_context(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    goal: str | None = None,
    include_descendants: bool = False,
    follow_embeds: bool = False,
) -> DistillProposal:
    """Propose evidence-bound Rules from one exact local Context frame."""

    try:
        if context_name is not None and (
            not isinstance(context_name, str) or not context_name.strip()
        ):
            raise ValueError("context_name must be nonblank text.")
        if goal is not None and (not isinstance(goal, str) or not goal.strip()):
            raise ValueError("goal must be nonblank text when supplied.")
        if not isinstance(include_descendants, bool) or not isinstance(
            follow_embeds,
            bool,
        ):
            raise TypeError("Distill traversal options must be booleans.")
        request = DistillRequest(
            context_locator=context_name,
            goal=goal,
            include_descendants=include_descendants,
            follow_embeds=follow_embeds,
        )
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = execute_distill(
            request,
            store=runtime.store,
            provider_factory=lambda: semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except DistillError as error:
        raise_semantic_execution_error(error)
    return _project_distill(result, apply_allowed=True)


def distill_ground(runtime: ClientRuntime, ground_name: str) -> DistillProposal:
    """Distill one exact bound Ground frame without mutating the Ground."""

    if not isinstance(ground_name, str) or not ground_name.strip():
        raise SemanticInputError("ground_name must be nonblank text.")
    # Keep the standalone public path physically independent from Ground.
    # Ground composition is loaded only when the caller selects this route.
    from memcommit.ground_distill import (
        execute_ground_distill,
        freeze_ground_distill,
    )

    try:
        frozen = freeze_ground_distill(runtime.store, ground_name=ground_name)
        result = execute_ground_distill(
            frozen,
            store=runtime.store,
            provider_factory=lambda: semantic_provider(runtime),
        ).distill
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except DistillError as error:
        raise_semantic_execution_error(error)
    return _project_distill(result, apply_allowed=False)


def apply_distill(
    runtime: ClientRuntime,
    proposal: DistillProposal,
    *,
    output_name: str,
) -> DistillApplyResult:
    """Materialize one exact reviewed standalone proposal into a new Context."""

    if not isinstance(proposal, DistillProposal):
        raise SemanticInputError("proposal must be a DistillProposal.")
    if not isinstance(output_name, str) or not output_name.strip():
        raise SemanticInputError("output_name must be nonblank text.")
    if not proposal.apply_allowed:
        raise SemanticInputError(
            "Ground Distill proposals cannot be materialized by this call."
        )
    try:
        receipt = execute_distill_apply(
            DistillApplyRequest(
                result=proposal._application_result,
                output_name=output_name,
            ),
            store=runtime.store,
        )
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (DistillError, RuntimeError, TypeError, ValueError) as error:
        raise_public(SemanticConflictError, error)
    return DistillApplyResult(
        output_name=receipt.output_name,
        output_context_uid=receipt.output_context_uid,
        checkpoint_uid=receipt.checkpoint_uid,
        result_memory_uids=receipt.result_memory_uids,
    )


__all__ = ["apply_distill", "distill_context", "distill_ground"]
