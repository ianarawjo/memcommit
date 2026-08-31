"""Shared provider and DTO projection for public semantic operations."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticProviderFailure,
)
from memcommit.adapters.python_api.semantic import (
    DistillProposal,
    DistillRuleProposal,
    MakemoreCaseProposal,
    MakemoreCaseValidationProposal,
    MakemoreProposal,
    MakemoreRuleCheckProposal,
    MakemoreRuleProposal,
    MakemoreTargetContextItemProposal,
)


class SafeSemanticProvider:
    """Map caller-supplied provider failures into the public taxonomy."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    @property
    def identity(self):
        """Preserve provider provenance required by durable semantic records."""

        return getattr(self._delegate, "identity", None)

    @property
    def last_run(self):
        """Expose the delegate's latest exact call after completion."""

        return getattr(self._delegate, "last_run", None)

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


def project_makemore(result) -> MakemoreProposal:
    analysis = result.analysis
    return MakemoreProposal(
        analysis_uid=analysis.uid,
        mode=analysis.mode.value,
        inputs=analysis.inputs,
        overview=analysis.overview,
        rules=tuple(
            MakemoreRuleProposal(
                uid=rule.uid,
                content=rule.content,
                rationale=rule.rationale,
                target_context_refs=rule.target_context_refs,
            )
            for rule in analysis.rules
        ),
        cases=tuple(
            MakemoreCaseProposal(
                uid=case.uid,
                proposition=case.proposition,
                expected=case.expected,
                rationale=case.rationale,
                case_role=case.case_role,
                rule_checks=tuple(
                    MakemoreRuleCheckProposal(
                        source_rule_index=check.source_rule_index,
                        evidence=check.evidence,
                    )
                    for check in case.rule_checks
                ),
                validation=(
                    None
                    if case.validation is None
                    else MakemoreCaseValidationProposal(
                        source_fit=case.validation.source_fit,
                        source_fit_reason=case.validation.source_fit_reason,
                        rule_conformance=case.validation.rule_conformance,
                        conforming_source_rule_indexes=(
                            case.validation.conforming_source_rule_indexes
                        ),
                    )
                ),
                target_context_refs=case.target_context_refs,
            )
            for case in analysis.cases
        ),
        origin=result.origin,
        quality_policy=analysis.quality_policy.value,
        target_context_name=(
            analysis.target_context.context_name
            if analysis.target_context is not None
            else None
        ),
        target_context_items=(
            tuple(
                MakemoreTargetContextItemProposal(
                    alias=item.alias,
                    kind=item.kind,
                    context_name=item.context_name,
                    memory_uid=item.memory_uid,
                    content=item.content,
                )
                for item in analysis.target_context.items
            )
            if analysis.target_context is not None
            else ()
        ),
    )


__all__ = [
    "project_distill",
    "project_makemore",
    "raise_semantic_execution_error",
    "safe_semantic_provider",
]
