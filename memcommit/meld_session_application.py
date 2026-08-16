"""Terminal-independent saved-session lifecycle contracts for Meld."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.meld import (
    MeldError,
    MeldRevision,
    MeldSession,
    MeldTurnScope,
    meld_canonical_digest,
)


class MeldSessionVersionError(MeldError):
    """A saved-session action no longer matches the reviewed Meld revision."""


class MeldSessionVersionInputError(ValueError):
    """A caller did not supply a valid opaque Meld version token."""


@dataclass(frozen=True)
class MeldSessionSnapshot:
    """One exact saved Meld revision and its opaque optimistic-CAS token."""

    session: MeldSession
    version_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.version_token, str) or not self.version_token:
            raise ValueError("A saved Meld session requires a version token.")


@dataclass(frozen=True)
class MeldTurnRequest:
    """One provider-bound dialogue revision against an exact saved snapshot."""

    snapshot: MeldSessionSnapshot
    comment: str
    scope: MeldTurnScope
    issue_uids: tuple[str, ...] = ()
    revision: MeldRevision = "EXTEND"
    revises_turn_uids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PendingMeldTurn:
    """A process-local pending turn plus the saved version it must replace."""

    session: MeldSession
    expected_version: str


@dataclass(frozen=True)
class MeldDestinationRequest:
    """Move one unapplied symmetric Result and its saved session together."""

    snapshot: MeldSessionSnapshot
    destination_name: str


class MeldSessionRepository(Protocol):
    def load(self, target_context_uid: str) -> MeldSessionSnapshot:
        """Load one exact target-scoped session."""

    def replace(
        self,
        session: MeldSession,
        *,
        expected_version: str,
    ) -> MeldSessionSnapshot:
        """Save one complete revision only if its prior digest still matches."""


class MeldPreservationPort(Protocol):
    def materialize(
        self,
        snapshot: MeldSessionSnapshot,
        session: MeldSession,
    ) -> MeldSessionSnapshot:
        """Revalidate inputs and save one provider-free preserve-all result."""


class MeldDestinationPort(Protocol):
    def relocate(self, request: MeldDestinationRequest) -> MeldSessionSnapshot:
        """Rename the target and return the relocated exact session snapshot."""


def _clone(session: MeldSession) -> MeldSession:
    return MeldSession.from_dict(session.to_dict())


def require_meld_session_version(
    snapshot: MeldSessionSnapshot,
    expected_version: str,
    *,
    allow_applied_predecessor: bool = False,
) -> MeldSessionSnapshot:
    """Bind an external mutation to its reviewed version.

    Apply alone may replay the version immediately before a completed Apply.
    The applied session retains enough typed receipt state to reconstruct that
    exact predecessor, while ordinary dialogue and defer actions must match the
    current version literally.
    """

    if not isinstance(snapshot, MeldSessionSnapshot):
        raise TypeError("Meld version validation requires a saved snapshot.")
    if not isinstance(expected_version, str) or not expected_version:
        raise MeldSessionVersionInputError(
            "A saved Meld action requires an opaque expected version."
        )
    if snapshot.version_token == expected_version:
        return snapshot
    session = snapshot.session
    if allow_applied_predecessor and session.state == "APPLIED":
        application = session.application
        assert application is not None
        reviewed = _clone(session)
        reviewed.clear_application(
            change_set_digest=application.change_set_digest,
            checkpoint_uid=application.checkpoint_uid,
            checkpoints=application.checkpoints,
        )
        if meld_canonical_digest(reviewed.to_dict()) == expected_version:
            return snapshot
    raise MeldSessionVersionError(
        "The saved Meld changed after this action was reviewed."
    )


def run_meld_session_open(
    target_context_uid: str,
    *,
    repository: MeldSessionRepository,
) -> MeldSessionSnapshot:
    if not isinstance(target_context_uid, str) or not target_context_uid:
        raise ValueError("Meld session target UID must be nonempty text.")
    snapshot = repository.load(target_context_uid)
    if snapshot.session.target.context_uid != target_context_uid:
        raise MeldError("Meld session repository returned another target identity.")
    return snapshot


def prepare_meld_turn(request: MeldTurnRequest) -> PendingMeldTurn:
    """Build one pending provider turn without publishing partial session state."""

    if not isinstance(request, MeldTurnRequest):
        raise TypeError("Meld turn preparation requires a MeldTurnRequest.")
    candidate = _clone(request.snapshot.session)
    candidate.start_turn(
        request.comment,
        scope=request.scope,
        issue_uids=request.issue_uids,
        revision=request.revision,
        revises_turn_uids=request.revises_turn_uids,
    )
    return PendingMeldTurn(
        session=candidate,
        expected_version=request.snapshot.version_token,
    )


def run_meld_session_defer(
    snapshot: MeldSessionSnapshot,
    *,
    repository: MeldSessionRepository,
) -> MeldSessionSnapshot:
    candidate = _clone(snapshot.session)
    candidate.keep_review_only()
    saved = repository.replace(
        candidate,
        expected_version=snapshot.version_token,
    )
    if saved.session.state != "KEPT_REVIEW_ONLY":
        raise MeldError("Meld defer persistence returned an invalid session.")
    return saved


def prepare_meld_preservation_turn(
    snapshot: MeldSessionSnapshot,
    *,
    guidance: str,
) -> PendingMeldTurn:
    if not isinstance(guidance, str) or not guidance.strip():
        raise ValueError("Meld preservation guidance must be nonempty text.")
    candidate = _clone(snapshot.session)
    candidate.start_turn(guidance, scope="REMAINING")
    return PendingMeldTurn(
        session=candidate,
        expected_version=snapshot.version_token,
    )


def run_meld_preservation(
    pending: PendingMeldTurn,
    *,
    port: MeldPreservationPort,
) -> MeldSessionSnapshot:
    snapshot = MeldSessionSnapshot(
        session=pending.session,
        version_token=pending.expected_version,
    )
    saved = port.materialize(snapshot, pending.session)
    if saved.session.state not in {"READY_TO_APPLY", "AWAITING_REPLY"}:
        raise MeldError("Meld preservation returned an invalid reviewed state.")
    return saved


def run_meld_destination_change(
    request: MeldDestinationRequest,
    *,
    port: MeldDestinationPort,
) -> MeldSessionSnapshot:
    if not isinstance(request, MeldDestinationRequest):
        raise TypeError("Meld destination change requires a typed request.")
    if not isinstance(request.destination_name, str) or not request.destination_name:
        raise ValueError("Meld destination name must be nonempty text.")
    if request.snapshot.session.mode != "SYMMETRIC":
        raise MeldError("Only a symmetric Meld result can move destinations.")
    if request.destination_name == request.snapshot.session.target.context_name:
        return request.snapshot
    relocated = port.relocate(request)
    if relocated.session.target.context_name != request.destination_name:
        raise MeldError("Meld destination port returned another target name.")
    return relocated


__all__ = [
    "MeldDestinationPort",
    "MeldDestinationRequest",
    "MeldPreservationPort",
    "MeldSessionRepository",
    "MeldSessionSnapshot",
    "MeldSessionVersionError",
    "MeldSessionVersionInputError",
    "MeldTurnRequest",
    "PendingMeldTurn",
    "prepare_meld_preservation_turn",
    "prepare_meld_turn",
    "require_meld_session_version",
    "run_meld_destination_change",
    "run_meld_preservation",
    "run_meld_session_defer",
    "run_meld_session_open",
]
