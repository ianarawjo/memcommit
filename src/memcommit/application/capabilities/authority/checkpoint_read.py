"""Authorize bounded retained History independently of current Context READ."""

from __future__ import annotations

from dataclasses import dataclass, field

from memcommit.application.capabilities.authority.checkpoint_read_model import (
    CheckpointEmbed,
    CheckpointRead,
    CheckpointReference,
)
from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    CheckpointHistoryComparison,
    CheckpointHistoryRevision,
    CheckpointHistorySlice,
    build_checkpoint_history_slice,
)
from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    HistoryCheckpoint,
    HistoryError,
    MemoryTransition,
)


class CheckpointReadAuthorizationError(PermissionError):
    """Retained checkpoint evidence is outside the caller's frozen right."""


@dataclass(frozen=True, slots=True)
class AuthorizedCheckpointHistory:
    """A capability view that exposes only the requested authorized window."""

    request: CheckpointRead
    checkpoints: tuple[HistoryCheckpoint, ...]
    _history: CheckpointHistorySlice = field(repr=False, compare=False)
    _checkpoint_uids: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_checkpoint_uids",
            frozenset(checkpoint.uid for checkpoint in self.checkpoints),
        )

    @property
    def context_uid(self) -> str:
        return self.request.context_uid

    def _require_checkpoint(self, checkpoint_uid: str) -> None:
        if checkpoint_uid not in self._checkpoint_uids:
            raise CheckpointReadAuthorizationError(
                f"Checkpoint [{checkpoint_uid[:8]}] is outside this read window."
            )

    def record(self, checkpoint_uid: str):
        self._require_checkpoint(checkpoint_uid)
        return self._history.record(checkpoint_uid)

    def revision(self, checkpoint_uid: str) -> CheckpointHistoryRevision:
        self._require_checkpoint(checkpoint_uid)
        return self._history.revision(checkpoint_uid)

    def transitions(self, checkpoint_uid: str) -> tuple[MemoryTransition, ...]:
        self._require_checkpoint(checkpoint_uid)
        return self._history.transitions(checkpoint_uid)

    def comparison(
        self,
        from_checkpoint_uid: str,
        to_checkpoint_uid: str,
    ) -> CheckpointHistoryComparison:
        """Compare two complete result states inside this exact read window."""

        self._require_checkpoint(from_checkpoint_uid)
        self._require_checkpoint(to_checkpoint_uid)
        return self._history.comparison(from_checkpoint_uid, to_checkpoint_uid)


def _candidate_checkpoint_reads(
    access: ContextAccess,
    request: CheckpointRead,
) -> tuple[CheckpointRead, ...]:
    view = access.view
    if view is None:
        return ()
    grant = view.grant
    if "READ" not in grant.permissions:
        raise CheckpointReadAuthorizationError(
            "Checkpoint reads require current Context READ permission."
        )
    binding = next(
        (
            context
            for context in grant.contexts
            if context.uid == request.context_uid
            and context.name == access.context_name
        ),
        None,
    )
    if binding is None:
        raise CheckpointReadAuthorizationError(
            "Checkpoint read Context is outside the resolved Grant binding."
        )
    candidates = tuple(
        checkpoint_read
        for checkpoint_read in grant.checkpoint_reads
        if checkpoint_read.context_uid == request.context_uid
    )
    if not candidates:
        raise CheckpointReadAuthorizationError(
            "Current Context READ does not expose retained checkpoint History."
        )
    if isinstance(request.scope, CheckpointEmbed) and not any(
        isinstance(candidate.scope, CheckpointEmbed) for candidate in candidates
    ):
        raise CheckpointReadAuthorizationError(
            "An exact Checkpoint Reference cannot authorize a growing Embed window."
        )
    return candidates


def _authorized_by(
    granted: CheckpointRead,
    request: CheckpointRead,
    history: CheckpointHistorySlice,
) -> bool:
    if granted.context_uid != request.context_uid:
        return False
    requested_scope = request.scope
    granted_scope = granted.scope
    if isinstance(granted_scope, CheckpointReference):
        return isinstance(requested_scope, CheckpointReference) and set(
            requested_scope.checkpoint_uids
        ).issubset(granted_scope.checkpoint_uids)
    try:
        embedded_uids = {
            checkpoint.uid
            for checkpoint in history.after(granted_scope.checkpoint_uid)
        }
    except HistoryError:
        # Retention or Context replacement may invalidate an older Grant.
        return False
    if isinstance(requested_scope, CheckpointReference):
        return set(requested_scope.checkpoint_uids).issubset(embedded_uids)
    return requested_scope.checkpoint_uid in embedded_uids


def authorize_checkpoint_read(
    access: ContextAccess,
    request: CheckpointRead,
    history: CheckpointHistorySlice,
) -> AuthorizedCheckpointHistory:
    """Project only the requested exact or anchored window after authorization."""

    if request.context_uid != history.context_uid:
        raise CheckpointReadAuthorizationError(
            "Checkpoint read Context identity does not match retained History."
        )
    try:
        if isinstance(request.scope, CheckpointReference):
            checkpoints = history.reference(request.scope.checkpoint_uids)
        else:
            checkpoints = history.after(request.scope.checkpoint_uid)
    except HistoryError as error:
        raise CheckpointReadAuthorizationError(str(error)) from error

    candidates = _candidate_checkpoint_reads(access, request)
    if access.is_granted and not any(
        _authorized_by(candidate, request, history) for candidate in candidates
    ):
        raise CheckpointReadAuthorizationError(
            "Requested checkpoints are outside the granted CheckpointRead scope."
        )
    return AuthorizedCheckpointHistory(
        request=request,
        checkpoints=checkpoints,
        _history=history,
    )


def read_checkpoint_history(
    access: ContextAccess,
    request: CheckpointRead,
) -> AuthorizedCheckpointHistory:
    """Open and return one bounded retained-history capability view.

    A granted access with no candidate checkpoint right fails before the
    authority Store's checkpoint log is opened. Ordering-dependent Embed
    coverage is then decided only inside this authority boundary.
    """

    if access.is_granted:
        _candidate_checkpoint_reads(access, request)
    history = build_checkpoint_history_slice(access.store, access.context_name)
    return authorize_checkpoint_read(access, request, history)


__all__ = [
    "AuthorizedCheckpointHistory",
    "CheckpointReadAuthorizationError",
    "authorize_checkpoint_read",
    "read_checkpoint_history",
]
