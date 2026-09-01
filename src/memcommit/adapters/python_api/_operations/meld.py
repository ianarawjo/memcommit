"""Operation-owned assembly for the public Meld lifecycle."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.errors import (
    MeldAuthorityError,
    MeldConflictError,
    MeldContextError,
    MeldExecutionError,
    MeldInputError,
    MeldProviderFailure,
    MeldStorageError,
)
from memcommit.adapters.python_api.meld import (
    MeldDecisionInput,
    MeldIssueResult,
    MeldOptionResult,
    MeldProposalResult,
    MeldSessionResult,
)
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.meld.model import (
    MELD_CANDIDATE_SCHEMA_VERSION,
    MeldError as CoreMeldError,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.resolution import (
    MeldResolutionError,
    plan_meld_candidate_update,
)
from memcommit.application.operations.resolve.decisions import ResolveDecision
from memcommit.application.operations.meld.provider.contract import (
    MeldProviderError,
)
from memcommit.application.operations.meld.preparation import (
    MeldRestartError,
    MeldRestartRequest,
)
from memcommit.application.operations.meld.runtime import (
    execute_meld_candidate_proposal,
    execute_meld_restart,
    execute_meld_start,
    load_meld_source,
    open_meld_candidate_session,
)
from memcommit.application.operations.meld.session import (
    MeldSessionVersionError,
    MeldSessionVersionInputError,
    require_meld_session_version,
)
from memcommit.application.operations.meld.preparation import MeldStartError, MeldStartRequest
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError


def _raise(error_type: type[Exception], error: BaseException) -> None:
    raise_public(error_type, error)


def _current_context_name(runtime: ClientRuntime) -> str | None:
    if not runtime.store.state_file.exists():
        return None
    try:
        return runtime.store.current_context_name()
    except (OSError, ValueError) as error:
        _raise(MeldStorageError, error)


def _safe_semantic_provider(runtime: ClientRuntime) -> object:
    try:
        return runtime.semantic_provider_factory()
    except MeldProviderFailure:
        raise
    except Exception as error:
        _raise(MeldProviderFailure, error)


def _project_meld(session, *, origin: str | None = None) -> MeldSessionResult:
    assessment = session.current_assessment
    application = session.application
    candidate_review = (
        getattr(session, "candidate_review", None)
        if getattr(session, "schema_version", None) == MELD_CANDIDATE_SCHEMA_VERSION
        else None
    )
    return MeldSessionResult(
        session_uid=session.uid,
        version=meld_canonical_digest(session.to_dict()),
        mode=session.mode,
        state=session.state,
        left_context=session.frames[0].context_name,
        right_context=session.frames[1].context_name,
        target_context=session.target.context_name,
        turn_count=(
            candidate_review.round + 1
            if candidate_review is not None
            else len(session.turns)
        ),
        overview=(
            (
                f"Audit-backed candidate with {len(candidate_review.source_claims)} "
                "frozen Source claims."
            )
            if candidate_review is not None
            else assessment.overview
            if assessment is not None
            else None
        ),
        ready_to_apply=(
            session.state == "APPLIED"
            if candidate_review is not None
            else assessment.ready_to_apply
            if assessment is not None
            else False
        ),
        issues=(
            tuple(
                MeldIssueResult(
                    uid=issue.uid,
                    priority="REQUIRED",
                    title=f"{issue.kind} · {issue.classification}",
                    question=issue.question,
                    why_it_matters=issue.reason,
                    options=(
                        MeldOptionResult(
                            uid=f"{issue.uid}:confirm",
                            label="CONFIRM THIS UNDERSTANDING",
                            text=issue.proposed_direction,
                        ),
                        MeldOptionResult(
                            uid=f"{issue.uid}:intent",
                            label="PROVIDE YOUR INTENT",
                            text="Supply a different resolution direction.",
                        ),
                        MeldOptionResult(
                            uid=f"{issue.uid}:force",
                            label="FORCE CONTINUE",
                            text="Keep this Audit item explicitly unresolved.",
                        ),
                    ),
                )
                for issue in candidate_review.issues
            )
            if candidate_review is not None
            else tuple(
                MeldIssueResult(
                    uid=issue.uid,
                    priority=issue.priority,
                    title=issue.title,
                    question=issue.question,
                    why_it_matters=issue.why_it_matters,
                    options=tuple(
                        MeldOptionResult(
                            uid=option.uid,
                            label=option.label,
                            text=option.text,
                        )
                        for option in issue.options
                    ),
                )
                for issue in assessment.issues
            )
            if assessment is not None
            else ()
        ),
        proposals=(
            tuple(
                MeldProposalResult(
                    uid=proposal.uid,
                    operation=proposal.operation,
                    disposition=proposal.disposition,
                    content=proposal.content,
                    reason=proposal.reason,
                )
                for proposal in assessment.proposals
            )
            if assessment is not None
            else ()
        ),
        origin=origin,
        checkpoint_uid=(
            application.checkpoint_uid if application is not None else None
        ),
        unresolved_count=(
            len(candidate_review.forced_audit_keys)
            if candidate_review is not None
            else 0
        ),
    )


def _meld_snapshot(runtime: ClientRuntime, target_name: str):
    current_name = _current_context_name(runtime)
    canonical = resolve_context_locator(target_name, current=current_name)
    access = resolve_context_access(
        runtime.store,
        canonical,
        current_name=current_name,
        required_permission="READ",
    )
    target = load_meld_source(access, project=False)
    return open_meld_candidate_session(target.uid, store=runtime.store)


def _expected_meld_snapshot(
    runtime: ClientRuntime,
    target_name: str,
    expected_version: str,
):
    """Load once and bind a public mutation to the caller's reviewed version."""

    snapshot = _meld_snapshot(runtime, target_name)
    return require_meld_session_version(
        snapshot,
        expected_version,
    )


def start_meld(
    runtime: ClientRuntime,
    left_context: str,
    right_context: str,
    *,
    mode: str = "directional",
    target_context: str | None = None,
    create_target: bool = False,
    left_descendants: bool = False,
    right_descendants: bool = False,
) -> MeldSessionResult:
    """Create one durable reviewed Meld without opening a terminal UI."""

    try:
        if mode not in {"directional", "symmetric"}:
            raise ValueError("mode must be directional or symmetric.")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (left_context, right_context)
        ):
            raise ValueError("Meld source names must be nonblank text.")
        if (
            not isinstance(create_target, bool)
            or not isinstance(
                left_descendants,
                bool,
            )
            or not isinstance(right_descendants, bool)
        ):
            raise TypeError("Meld scope and creation controls must be booleans.")
        current_name = _current_context_name(runtime)
        left = resolve_context_locator(left_context, current=current_name)
        right = resolve_context_locator(right_context, current=current_name)
        if mode == "directional":
            if target_context is not None and target_context != right:
                raise ValueError("Directional target must be the BASELINE.")
            target = right
        else:
            if target_context is None:
                raise ValueError("Symmetric Meld requires target_context.")
            target = (
                target_context
                if create_target
                else resolve_context_locator(
                    target_context,
                    current=current_name,
                )
            )
        request = MeldStartRequest(
            mode=mode.upper(),  # type: ignore[arg-type]
            left_name=left,
            right_name=right,
            target_name=target,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
            create_target=create_target,
        )
    except (TypeError, ValueError, CoreMeldError, MeldStartError) as error:
        _raise(MeldInputError, error)
    try:
        result = execute_meld_start(
            request,
            store=runtime.store,
            provider_factory=lambda: _safe_semantic_provider(runtime),
        )
    except MeldProviderFailure:
        raise
    except MeldProviderError as error:
        _raise(MeldProviderFailure, error)
    except FileNotFoundError as error:
        _raise(MeldContextError, error)
    except ProfileError as error:
        _raise(MeldAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        _raise(MeldConflictError, error)
    except OSError as error:
        _raise(MeldStorageError, error)
    except (
        CoreMeldError,
        MeldStartError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(result.session, origin=result.origin)


def restart_meld(
    runtime: ClientRuntime,
    left_context: str,
    right_context: str,
    target_context: str,
    *,
    expected_version: str,
    mode: str = "directional",
    left_descendants: bool = False,
    right_descendants: bool = False,
) -> MeldSessionResult:
    """Replace one exact saved Meld review without deleting its target."""

    try:
        if mode not in {"directional", "symmetric"}:
            raise ValueError("mode must be directional or symmetric.")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (
                left_context,
                right_context,
                target_context,
                expected_version,
            )
        ):
            raise ValueError(
                "Meld restart names and expected_version must be nonblank text."
            )
        if not isinstance(left_descendants, bool) or not isinstance(
            right_descendants,
            bool,
        ):
            raise TypeError("Meld scope controls must be booleans.")
        current_name = _current_context_name(runtime)
        left = resolve_context_locator(left_context, current=current_name)
        right = resolve_context_locator(right_context, current=current_name)
        target = resolve_context_locator(target_context, current=current_name)
        if mode == "directional" and target != right:
            raise ValueError("Directional target must be the BASELINE.")
        request = MeldRestartRequest(
            mode=mode.upper(),  # type: ignore[arg-type]
            left_name=left,
            right_name=right,
            target_name=target,
            expected_version=expected_version,
            left_descendants=left_descendants,
            right_descendants=right_descendants,
        )
    except (TypeError, ValueError, CoreMeldError, MeldRestartError) as error:
        _raise(MeldInputError, error)
    try:
        result = execute_meld_restart(
            request,
            store=runtime.store,
            provider_factory=lambda: _safe_semantic_provider(runtime),
        )
    except MeldProviderFailure:
        raise
    except MeldProviderError as error:
        _raise(MeldProviderFailure, error)
    except FileNotFoundError as error:
        _raise(MeldContextError, error)
    except ProfileError as error:
        _raise(MeldAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        _raise(MeldConflictError, error)
    except OSError as error:
        _raise(MeldStorageError, error)
    except (
        CoreMeldError,
        MeldRestartError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(result.session, origin=result.origin)


def open_meld(runtime: ClientRuntime, target_context: str) -> MeldSessionResult:
    """Open one exact saved review without provider or mutation."""

    try:
        snapshot = _meld_snapshot(runtime, target_context)
    except FileNotFoundError as error:
        _raise(MeldContextError, error)
    except ProfileError as error:
        _raise(MeldAuthorityError, error)
    except OSError as error:
        _raise(MeldStorageError, error)
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(snapshot.session)


def resolve_meld(
    runtime: ClientRuntime,
    target_context: str,
    decisions: Sequence[MeldDecisionInput] = (),
    *,
    expected_version: str,
) -> MeldSessionResult:
    """Finalize one complete decision set, Update once, verify, and Apply."""

    try:
        snapshot = _expected_meld_snapshot(
            runtime,
            target_context,
            expected_version,
        )
        session = snapshot.session
        if session.schema_version != MELD_CANDIDATE_SCHEMA_VERSION:
            raise MeldResolutionError(
                "Legacy Compare-backed Meld sessions are read-only; restart Meld."
            )
        if any(not isinstance(item, MeldDecisionInput) for item in decisions):
            raise TypeError("Meld decisions must use MeldDecisionInput.")
        typed = tuple(
            ResolveDecision(
                issue_uid=item.issue_uid,
                kind=item.kind.upper(),  # type: ignore[arg-type]
                intent=item.intent,
            )
            for item in decisions
        )
        target = runtime.store.load_direct(session.target.context_name)
        proposal = plan_meld_candidate_update(
            session,
            typed,
            target=target,
            update_provider_factory=lambda: _safe_semantic_provider(runtime),
            audit_provider_factory=lambda: _safe_semantic_provider(runtime),
            direction_provider_factory=lambda: _safe_semantic_provider(runtime),
            coverage_provider_factory=lambda: _safe_semantic_provider(runtime),
        )
        saved, receipt = execute_meld_candidate_proposal(
            session,
            proposal,
            store=runtime.store,
            expected_session_digest=snapshot.version_token,
        )
        if receipt.missing_claim_aliases:
            raise MeldResolutionError(
                "The proposed post-image dropped Source claim(s): "
                + ", ".join(receipt.missing_claim_aliases)
                + ". Nothing was applied."
            )
    except MeldProviderFailure:
        raise
    except MeldSessionVersionInputError as error:
        _raise(MeldInputError, error)
    except MeldSessionVersionError as error:
        _raise(MeldConflictError, error)
    except FileNotFoundError as error:
        _raise(MeldContextError, error)
    except ProfileError as error:
        _raise(MeldAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        _raise(MeldConflictError, error)
    except OSError as error:
        _raise(MeldStorageError, error)
    except MeldResolutionError as error:
        _raise(MeldInputError, error)
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(saved, origin="AUDIT_RESOLVE_UPDATE")


__all__ = [
    "open_meld",
    "resolve_meld",
    "restart_meld",
    "start_meld",
]
