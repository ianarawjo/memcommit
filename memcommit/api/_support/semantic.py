"""Shared provider and DTO projection for public semantic operations."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticProviderFailure,
)
from memcommit.api.semantic import (
    DistillProposal,
    DistillRuleProposal,
    ElaborateCaseProposal,
    ElaborateProposal,
    ElaborateRuleProposal,
)


class SafeSemanticProvider:
    """Map caller-supplied provider failures into the public taxonomy."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def complete(self, prompt, *, operation, output_schema=None):
        try:
            complete = getattr(self._delegate, "complete")
            return complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        except SemanticProviderFailure:
            raise
        except Exception as error:
            raise_public(SemanticProviderFailure, error)


def safe_semantic_provider(runtime: ClientRuntime) -> SafeSemanticProvider:
    try:
        return SafeSemanticProvider(runtime.semantic_provider_factory())
    except SemanticProviderFailure:
        raise
    except Exception as error:
        raise_public(SemanticProviderFailure, error)


def raise_semantic_execution_error(error: BaseException) -> None:
    """Project domain failures without leaking operation-specific errors."""

    message = str(error).casefold()
    if "was not found" in message or "no longer exists" in message:
        raise_public(SemanticContextError, error)
    if "authorized" in message or "granted" in message:
        raise_public(SemanticAuthorityError, error)
    if "changed" in message or "concurrent" in message:
        raise_public(SemanticConflictError, error)
    raise_public(SemanticExecutionError, error)


def project_distill(result, *, apply_allowed: bool) -> DistillProposal:
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


def project_elaborate(result) -> ElaborateProposal:
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


__all__ = [
    "project_distill",
    "project_elaborate",
    "raise_semantic_execution_error",
    "safe_semantic_provider",
]
