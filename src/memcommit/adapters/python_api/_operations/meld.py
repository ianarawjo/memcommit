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
    MeldApplyResult as PublicMeldApplyResult,
    MeldIssueResult,
    MeldOptionResult,
    MeldProposalResult,
    MeldSessionResult,
)
from memcommit.application.authority.access import resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.application.operations.meld.model import (
    MELD_SCHEMA_VERSION,
    MeldError as CoreMeldError,
    meld_canonical_digest,
)
from memcommit.application.operations.meld.application import MeldApplyRequest
from memcommit.application.operations.meld.provider import MeldProviderError
from memcommit.application.operations.meld.resolution_application import (
    MeldResolutionError,
    MeldResolutionTurnRequest,
    prepare_meld_resolution_turn,
)
from memcommit.application.operations.meld.restart_application import (
    MeldRestartError,
    MeldRestartRequest,
)
from memcommit.application.operations.meld.runtime import (
    execute_meld_apply,
    execute_meld_preservation,
    execute_prepared_meld_turn,
    execute_meld_restart,
    execute_meld_session_defer,
    execute_meld_session_open,
    execute_meld_start,
    load_meld_source,
    prepare_pending_meld_turn,
)
from memcommit.application.operations.meld.session_application import (
    MeldSessionVersionError,
    MeldSessionVersionInputError,
    prepare_meld_preservation_turn,
    require_meld_session_version,
)
from memcommit.application.operations.meld.start_application import MeldStartError, MeldStartRequest
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
    return MeldSessionResult(
        session_uid=session.uid,
        version=meld_canonical_digest(session.to_dict()),
        mode=session.mode,
        state=session.state,
        left_context=session.frames[0].context_name,
        right_context=session.frames[1].context_name,
        target_context=session.target.context_name,
        turn_count=len(session.turns),
        overview=assessment.overview if assessment is not None else None,
        ready_to_apply=(assessment.ready_to_apply if assessment is not None else False),
        issues=(
            tuple(
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
    return execute_meld_session_open(target.uid, store=runtime.store)


def _expected_meld_snapshot(
    runtime: ClientRuntime,
    target_name: str,
    expected_version: str,
    *,
    allow_applied_predecessor: bool = False,
):
    """Load once and bind a public mutation to the caller's reviewed version."""

    snapshot = _meld_snapshot(runtime, target_name)
    return require_meld_session_version(
        snapshot,
        expected_version,
        allow_applied_predecessor=allow_applied_predecessor,
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


def comment_meld(
    runtime: ClientRuntime,
    target_context: str,
    comment: str = "",
    *,
    expected_version: str,
    issue_uid: str | None = None,
    option_uid: str | None = None,
    revision: str = "EXTEND",
    revises_turn_uids: Sequence[str] = (),
) -> MeldSessionResult:
    """Submit one complete semantic follow-up against a saved version."""

    try:
        if not isinstance(comment, str):
            raise MeldResolutionError("comment must be text.")
        if not isinstance(revision, str):
            raise MeldResolutionError("revision must be text.")
        snapshot = _expected_meld_snapshot(
            runtime,
            target_context,
            expected_version,
        )
        pending = prepare_meld_resolution_turn(
            MeldResolutionTurnRequest(
                snapshot=snapshot,
                comment=comment,
                issue_uid=issue_uid,
                option_uid=option_uid,
                revision=revision.upper(),  # type: ignore[arg-type]
                revises_turn_uids=tuple(revises_turn_uids),
            )
        )
        result = execute_prepared_meld_turn(
            prepare_pending_meld_turn(pending, store=runtime.store),
            provider_factory=lambda: _safe_semantic_provider(runtime),
        )
    except MeldProviderFailure:
        raise
    except MeldSessionVersionInputError as error:
        _raise(MeldInputError, error)
    except MeldSessionVersionError as error:
        _raise(MeldConflictError, error)
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
    except MeldResolutionError as error:
        _raise(MeldInputError, error)
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(result.session, origin=result.origin)


def preserve_meld(
    runtime: ClientRuntime,
    target_context: str,
    *,
    expected_version: str,
) -> MeldSessionResult:
    """Preserve every remaining distinction under the saved-session CAS."""

    try:
        snapshot = _expected_meld_snapshot(
            runtime,
            target_context,
            expected_version,
        )
        pending = prepare_meld_preservation_turn(
            snapshot,
            guidance=(
                "Preserve every remaining supported source distinction "
                "without inventing unsupported content."
            ),
        )
        session = pending.session
        if (
            session.mode == "SYMMETRIC"
            and session.schema_version >= MELD_SCHEMA_VERSION
        ):
            saved = execute_meld_preservation(pending, store=runtime.store)
            return _project_meld(saved.session, origin="LOCAL")
        prepared = prepare_pending_meld_turn(
            pending,
            store=runtime.store,
        )
        result = execute_prepared_meld_turn(
            prepared,
            provider_factory=lambda: _safe_semantic_provider(runtime),
        )
    except MeldProviderFailure:
        raise
    except MeldSessionVersionInputError as error:
        _raise(MeldInputError, error)
    except MeldSessionVersionError as error:
        _raise(MeldConflictError, error)
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
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(result.session, origin=result.origin)


def defer_meld(
    runtime: ClientRuntime,
    target_context: str,
    *,
    expected_version: str,
) -> MeldSessionResult:
    """Close one saved review without changing its target."""

    try:
        snapshot = _expected_meld_snapshot(
            runtime,
            target_context,
            expected_version,
        )
        saved = execute_meld_session_defer(snapshot, store=runtime.store)
    except MeldSessionVersionInputError as error:
        _raise(MeldInputError, error)
    except MeldSessionVersionError as error:
        _raise(MeldConflictError, error)
    except FileNotFoundError as error:
        _raise(MeldContextError, error)
    except ConcurrentContextUpdateError as error:
        _raise(MeldConflictError, error)
    except OSError as error:
        _raise(MeldStorageError, error)
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return _project_meld(saved.session, origin="LOCAL")


def apply_meld(
    runtime: ClientRuntime,
    target_context: str,
    *,
    expected_version: str,
) -> PublicMeldApplyResult:
    """Apply exactly one ready saved proposal without another provider turn."""

    try:
        snapshot = _expected_meld_snapshot(
            runtime,
            target_context,
            expected_version,
            allow_applied_predecessor=True,
        )
        applied = execute_meld_apply(
            MeldApplyRequest(
                session=snapshot.session,
                expected_session_digest=snapshot.version_token,
            ),
            store=runtime.store,
        )
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
    except (CoreMeldError, RuntimeError, TypeError, ValueError) as error:
        _raise(MeldExecutionError, error)
    return PublicMeldApplyResult(
        session=_project_meld(applied.session, origin="LOCAL"),
        recovered=applied.receipt.recovered,
        checkpoint_uid=applied.receipt.checkpoint_uid,
        result_count=applied.receipt.result_count,
    )


__all__ = [
    "apply_meld",
    "comment_meld",
    "defer_meld",
    "open_meld",
    "preserve_meld",
    "restart_meld",
    "start_meld",
]
