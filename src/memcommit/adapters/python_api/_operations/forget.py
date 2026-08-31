"""Operation-owned assembly for the public process-local Forget lifecycle."""

from __future__ import annotations

from typing import NoReturn

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api.errors import (
    ForgetAuthorityError,
    ForgetConflictError,
    ForgetContextError,
    ForgetExecutionError,
    ForgetInputError,
    ForgetProviderFailure,
    ForgetStorageError,
)
from memcommit.adapters.python_api.forget import (
    ForgetApplyResult,
    ForgetCandidateResult,
    ForgetReviewResult,
)
from memcommit.application.operations.semantic_updates.curate_integrate.forget.application import (
    ForgetAnalysisRequest,
    ForgetApplicationError,
    ForgetApplyRequest,
    ForgetRevisionRequest,
    ForgetSelectionRequest,
    ForgetSessionSnapshot,
    run_forget_analysis,
    run_forget_apply,
    run_forget_revision,
    run_forget_selection,
)
from memcommit.application.operations.semantic_updates.curate_integrate.forget.review import ForgetReviewError
from memcommit.application.operations.semantic_updates.curate_integrate.forget.runtime import MemoryStoreForgetSourcePort
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import QueryProviderError
from memcommit.persistence.store import ConcurrentContextUpdateError


def _raise(error_type: type[Exception], error: BaseException) -> NoReturn:
    raise error_type(str(error)) from error


def _project_review(
    runtime: ClientRuntime,
    snapshot: ForgetSessionSnapshot,
    *,
    provider_used: bool,
) -> ForgetReviewResult:
    candidates = []
    for candidate in snapshot.review.candidates:
        selected_action, selected_content = candidate.selected_action()
        candidates.append(
            ForgetCandidateResult(
                uid=candidate.uid,
                source_memory_uid=candidate.source.uid,
                source_content=candidate.source.content,
                recommendation=candidate.decision.variant,
                proposed_content=candidate.decision.proposed_content,
                rationale=candidate.decision.rationale,
                selection=candidate.selection,
                selected_action=selected_action,
                selected_content=selected_content,
            )
        )
    return ForgetReviewResult(
        review_uid=snapshot.review.uid,
        version=snapshot.version_token,
        source_context=snapshot.source.display_name,
        source_context_uid=snapshot.source.context.uid,
        instruction=snapshot.review.instruction,
        overview=snapshot.review.overview,
        candidates=tuple(candidates),
        provider_used=provider_used,
        _snapshot=snapshot,
        _store_root=runtime.store_root,
    )


def _review_snapshot(
    runtime: ClientRuntime,
    review: ForgetReviewResult,
) -> ForgetSessionSnapshot:
    if not isinstance(review, ForgetReviewResult):
        raise ForgetInputError("review must be a ForgetReviewResult.")
    if review._store_root != runtime.store_root:
        raise ForgetInputError(
            "Forget review belongs to a different MemCommit Store."
        )
    if (
        review.review_uid != review._snapshot.review.uid
        or review.version != review._snapshot.version_token
    ):
        raise ForgetInputError("Forget review identity is invalid.")
    return review._snapshot


def analyze_forget_context(
    runtime: ClientRuntime,
    instruction: str,
    *,
    context_name: str | None = None,
) -> ForgetReviewResult:
    """Analyze one complete direct Source without mutating it."""

    try:
        request = ForgetAnalysisRequest(context_name, instruction)
    except (ForgetApplicationError, TypeError, ValueError) as error:
        _raise(ForgetInputError, error)
    source_port = MemoryStoreForgetSourcePort(runtime.store)
    try:
        result = run_forget_analysis(
            request,
            source_port=source_port,
            provider_factory=runtime.semantic_provider_factory,
        )
    except FileNotFoundError as error:
        _raise(ForgetContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        _raise(ForgetAuthorityError, error)
    except QueryProviderError as error:
        _raise(ForgetProviderFailure, error)
    except OSError as error:
        _raise(ForgetStorageError, error)
    except (ForgetApplicationError, ForgetReviewError, RuntimeError, ValueError) as error:
        _raise(ForgetExecutionError, error)
    return _project_review(
        runtime,
        result.snapshot,
        provider_used=result.provider_used,
    )


def select_forget_review(
    runtime: ClientRuntime,
    review: ForgetReviewResult,
    candidate_uid: str,
    selection: str,
    *,
    custom_content: str = "",
) -> ForgetReviewResult:
    """Change one process-local review decision without provider or Store effects."""

    snapshot = _review_snapshot(runtime, review)
    if selection not in {"RECOMMENDED", "KEEP", "DELETE", "CUSTOM"}:
        raise ForgetInputError(
            "selection must be RECOMMENDED, KEEP, DELETE, or CUSTOM."
        )
    try:
        selected = run_forget_selection(
            ForgetSelectionRequest(
                snapshot=snapshot,
                candidate_uid=candidate_uid,
                selection=selection,  # type: ignore[arg-type]
                custom_content=custom_content,
            )
        )
    except (ForgetApplicationError, ForgetReviewError, TypeError, ValueError) as error:
        _raise(ForgetInputError, error)
    return _project_review(runtime, selected, provider_used=False)


def revise_forget_review(
    runtime: ClientRuntime,
    review: ForgetReviewResult,
    guidance: str,
) -> ForgetReviewResult:
    """Run one provider revision over the original frozen Source and dialogue."""

    snapshot = _review_snapshot(runtime, review)
    try:
        revised = run_forget_revision(
            ForgetRevisionRequest(snapshot=snapshot, feedback=guidance),
            provider_factory=runtime.semantic_provider_factory,
        )
    except QueryProviderError as error:
        _raise(ForgetProviderFailure, error)
    except (ForgetApplicationError, ForgetReviewError, TypeError) as error:
        _raise(ForgetInputError, error)
    except OSError as error:
        _raise(ForgetStorageError, error)
    except (RuntimeError, ValueError) as error:
        _raise(ForgetExecutionError, error)
    return _project_review(runtime, revised, provider_used=True)


def apply_forget_review(
    runtime: ClientRuntime,
    review: ForgetReviewResult,
) -> ForgetApplyResult:
    """Apply the exact process-local review or return its explicit no-op."""

    snapshot = _review_snapshot(runtime, review)
    try:
        result = run_forget_apply(
            ForgetApplyRequest(snapshot),
            source_port=MemoryStoreForgetSourcePort(runtime.store),
        )
    except ConcurrentContextUpdateError as error:
        _raise(ForgetConflictError, error)
    except (ProfileConfigError, ProfileError) as error:
        _raise(ForgetAuthorityError, error)
    except FileNotFoundError as error:
        _raise(ForgetContextError, error)
    except OSError as error:
        _raise(ForgetStorageError, error)
    except (ForgetApplicationError, RuntimeError, TypeError, ValueError) as error:
        _raise(ForgetExecutionError, error)
    receipt = result.receipt
    return ForgetApplyResult(
        review_uid=snapshot.review.uid,
        version=snapshot.version_token,
        source_context=receipt.source_name,
        source_context_uid=receipt.source_context_uid,
        removed_count=receipt.removed_count,
        edited_count=receipt.edited_count,
        checkpoint_uid=receipt.checkpoint_uid,
        undo_available=receipt.undo_available,
        granted=receipt.granted,
        applied=result.applied,
    )


__all__ = [
    "analyze_forget_context",
    "apply_forget_review",
    "revise_forget_review",
    "select_forget_review",
]
