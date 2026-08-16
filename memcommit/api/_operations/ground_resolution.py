"""Stable Python assembly for revision-bound Ground Fit and Resolve."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import (
    raise_semantic_execution_error,
    safe_semantic_provider,
)
from memcommit.api.errors import (
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.semantic import (
    DistillProposal,
    ElaborateProposal,
    GroundFitJudgmentResult,
    GroundFitReceiptResult,
    GroundResolutionActionResult,
    GroundResolutionApplyResult,
    GroundResolutionPlanResult,
)
from memcommit.fit import FitError
from memcommit.fit_application import FitRequest
from memcommit.fit_runtime import run_fit_with_store
from memcommit.fit_store import GroundFitReceipt
from memcommit.ground import GroundError
from memcommit.ground_resolution import (
    GroundFitResolutionChoice,
    GroundResolutionError,
    GroundResolutionPlan,
)
from memcommit.ground_resolution_application import (
    apply_ground_resolution as apply_plan,
    resolve_distill_rule,
    resolve_elaborate_candidate,
    resolve_fit_issue,
)
from memcommit.query_provider import QueryProviderError
from memcommit.store import ConcurrentGroundUpdateError


def _project_fit(result) -> GroundFitReceiptResult:
    report = result.report
    examples = {example.uid: example for example in report.examples}
    receipt = GroundFitReceipt(report=report, current=result.current)
    return GroundFitReceiptResult(
        receipt_uid=report.uid,
        receipt_digest=report.digest,
        ground_uid=report.ground_uid,
        ground_name=report.ground_name,
        ground_revision=report.ground_revision,
        ground_digest=report.ground_digest,
        overview=report.overview,
        current=result.current,
        judgments=tuple(
            GroundFitJudgmentResult(
                example_uid=judgment.example_uid,
                example_alias=examples[judgment.example_uid].alias,
                proposition=examples[judgment.example_uid].statement,
                status=judgment.status,
                reason=judgment.reason,
                rule_uids=judgment.rule_uids,
            )
            for judgment in report.judgments
        ),
        _receipt=receipt,
    )


def fit_ground(
    runtime: ClientRuntime,
    ground_name: str,
    *,
    receipt_uid: str | None = None,
) -> GroundFitReceiptResult:
    """Run or reopen one immutable Ground Fit receipt."""

    try:
        request = FitRequest(ground_name=ground_name, receipt_uid=receipt_uid)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = run_fit_with_store(
            request,
            store=runtime.store,
            provider_factory=lambda: safe_semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except FitError as error:
        message = str(error).casefold()
        if "was not found" in message:
            raise_public(SemanticContextError, error)
        if "changed" in message or "different ground" in message:
            raise_public(SemanticConflictError, error)
        raise_public(SemanticExecutionError, error)
    return _project_fit(result)


def _project_plan(
    plan: GroundResolutionPlan,
    *,
    artifact: object,
) -> GroundResolutionPlanResult:
    action = plan.action
    identity = plan.source.identity
    return GroundResolutionPlanResult(
        plan_digest=plan.digest,
        artifact_kind=plan.source.kind,
        artifact_uid=plan.source.artifact_uid,
        artifact_digest=plan.source.artifact_digest,
        source_verification=plan.source.verification,
        candidate_verification=plan.candidate_verification,
        ground_uid=identity.ground_uid,
        ground_name=identity.ground_name,
        ground_revision=identity.ground_revision,
        ground_digest=identity.ground_digest,
        explanation=plan.explanation,
        action=GroundResolutionActionResult(
            kind=action.kind,
            content=action.content,
            rationale=action.rationale,
            selector=action.selector,
            source_item_uid=action.source_item_uid,
            case_role=action.case_role,
            use=action.use,
            rule_provenance=action.rule_provenance,
        ),
        _plan=plan,
        _artifact=artifact,
    )


def plan_ground_resolution(
    runtime: ClientRuntime,
    source: DistillProposal | ElaborateProposal | GroundFitReceiptResult,
    *,
    candidate_uid: str | None = None,
    example_uid: str | None = None,
    action: str | None = None,
    content: str = "",
    rationale: str = "",
    rule_uid: str = "",
    use: str = "",
) -> GroundResolutionPlanResult:
    """Plan one reviewable action from one exact Ground semantic artifact."""

    try:
        if isinstance(source, DistillProposal):
            artifact = source._ground_result
            if artifact is None:
                raise GroundResolutionError(
                    "Resolve requires a Ground Distill proposal, not a standalone one."
                )
            if candidate_uid is None or any(
                (example_uid, action, content, rationale, rule_uid, use)
            ):
                raise GroundResolutionError(
                    "Distill Resolve requires only one candidate_uid."
                )
            session = runtime.store.load_ground_session(artifact.frozen.ground_name)
            if session is None:
                raise GroundResolutionError("Resolve Ground was not found.")
            plan = resolve_distill_rule(
                session,
                artifact,
                rule_uid=candidate_uid,
            )
        elif isinstance(source, ElaborateProposal):
            artifact = source._ground_result
            if artifact is None:
                raise GroundResolutionError(
                    "Resolve requires a Ground Elaborate proposal, not a standalone one."
                )
            if candidate_uid is None or any(
                (example_uid, action, content, rationale, rule_uid, use)
            ):
                raise GroundResolutionError(
                    "Elaborate Resolve requires only one candidate_uid."
                )
            session = runtime.store.load_ground_session(artifact.frozen.ground_name)
            if session is None:
                raise GroundResolutionError("Resolve Ground was not found.")
            plan = resolve_elaborate_candidate(
                session,
                artifact,
                candidate_uid=candidate_uid,
            )
        elif isinstance(source, GroundFitReceiptResult):
            artifact = source._receipt
            if candidate_uid is not None or example_uid is None or action is None:
                raise GroundResolutionError(
                    "Fit Resolve requires example_uid and action."
                )
            session = runtime.store.load_ground_session(source.ground_name)
            if session is None:
                raise GroundResolutionError("Resolve Ground was not found.")
            plan = resolve_fit_issue(
                session,
                artifact,
                choice=GroundFitResolutionChoice(
                    example_uid=example_uid,
                    action=action,  # type: ignore[arg-type]
                    content=content,
                    rationale=rationale,
                    rule_uid=rule_uid,
                    use=use,
                ),
            )
        else:
            raise TypeError("Resolve source has an unsupported public type.")
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except GroundResolutionError as error:
        message = str(error).casefold()
        if "was not found" in message:
            raise_public(SemanticContextError, error)
        if "changed" in message or "stale" in message:
            raise_public(SemanticConflictError, error)
        raise_public(SemanticInputError, error)
    except (GroundError, TypeError, ValueError) as error:
        raise_semantic_execution_error(error)
    return _project_plan(plan, artifact=artifact)


def apply_ground_resolution(
    runtime: ClientRuntime,
    plan: GroundResolutionPlanResult,
) -> GroundResolutionApplyResult:
    """Apply one separately reviewed public plan through the same Ground CAS."""

    if not isinstance(plan, GroundResolutionPlanResult):
        raise SemanticInputError(
            "plan must be a GroundResolutionPlanResult from this client boundary."
        )
    try:
        receipt = apply_plan(
            runtime.store,
            plan._plan,
            artifact=plan._artifact,  # type: ignore[arg-type]
        )
    except ConcurrentGroundUpdateError as error:
        raise_public(SemanticConflictError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (GroundResolutionError, GroundError, TypeError, ValueError) as error:
        raise_semantic_execution_error(error)
    return GroundResolutionApplyResult(
        plan_digest=receipt.plan_digest,
        artifact_uid=receipt.artifact_uid,
        action_kind=receipt.action_kind,
        previous_revision=receipt.previous_identity.ground_revision,
        resulting_revision=receipt.resulting_identity.ground_revision,
        resulting_ground_digest=receipt.resulting_identity.ground_digest,
        mutated=receipt.mutated,
    )


__all__ = [
    "apply_ground_resolution",
    "fit_ground",
    "plan_ground_resolution",
]
