"""Terminal-independent proposal iteration for durable Meld sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memcommit.application.capabilities.resolution import (
    ResolutionAttempt,
    ResolutionBinding,
    ResolutionCase,
    ResolutionRequirement,
    ResolutionSubmission,
    ResolutionValidationError,
    evaluate_resolution,
)

from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import (
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


def run_meld_initial_preservation(
    snapshot: MeldSessionSnapshot,
    *,
    repository: MeldSessionRepository,
) -> MeldSessionSnapshot:
    """Publish one conservative initial symmetric result under session CAS."""

    candidate = _clone(snapshot.session)
    candidate.complete_initial_preservation()
    saved = repository.replace(
        candidate,
        expected_version=snapshot.version_token,
    )
    if saved.session.state != "READY_TO_APPLY":
        raise MeldError("Initial Meld preservation returned an invalid state.")
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


class MeldResolutionError(MeldError):
    """One submitted Meld response is invalid for the frozen assessment."""


@dataclass(frozen=True)
class MeldResolutionTurnRequest:
    """One whole-set comment or exact issue response against a saved revision."""

    snapshot: MeldSessionSnapshot
    comment: str = ""
    issue_uid: str | None = None
    option_uid: str | None = None
    revision: MeldRevision = "EXTEND"
    revises_turn_uids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, MeldSessionSnapshot):
            raise TypeError("Meld resolution requires a saved session snapshot.")
        if not isinstance(self.comment, str):
            raise MeldResolutionError("Meld response comment must be text.")
        for value, label in (
            (self.issue_uid, "issue UID"),
            (self.option_uid, "option UID"),
        ):
            if value is not None and (
                not isinstance(value, str)
                or not value
                or any(character in value for character in "\r\n")
            ):
                raise MeldResolutionError(
                    f"Meld response {label} must be nonempty one-line text."
                )
        if self.revision not in {"CONFIRM", "EXTEND", "CORRECT", "RETRACT"}:
            raise MeldResolutionError("Meld response revision is invalid.")
        if not isinstance(self.revises_turn_uids, tuple) or any(
            not isinstance(turn_uid, str) or not turn_uid
            for turn_uid in self.revises_turn_uids
        ):
            raise MeldResolutionError("Meld revised turn UIDs are invalid.")
        if self.revises_turn_uids and self.revision not in {"CORRECT", "RETRACT"}:
            raise MeldResolutionError(
                "Meld revised turn UIDs require CORRECT or RETRACT."
            )


def meld_resolution_case(snapshot: MeldSessionSnapshot) -> ResolutionCase:
    """Project the current Meld assessment without copying its semantics."""

    if not isinstance(snapshot, MeldSessionSnapshot):
        raise TypeError("Meld resolution requires a saved session snapshot.")
    assessment = snapshot.session.current_assessment
    return ResolutionCase(
        binding=ResolutionBinding(
            operation="meld",
            artifact_uid=snapshot.session.uid,
            revision=snapshot.version_token,
        ),
        requirements=(
            tuple(
                ResolutionRequirement(
                    item_uid=issue.uid,
                    choice_uids=tuple(option.uid for option in issue.options),
                    obligation=(
                        "REQUIRED" if issue.priority == "REQUIRED" else "OPTIONAL"
                    ),
                    comment_allowed=True,
                )
                for issue in assessment.issues
            )
            if assessment is not None
            else ()
        ),
    )


def _resolution_error(error: ResolutionValidationError) -> MeldResolutionError:
    if error.code == "UNKNOWN_ITEM":
        return MeldResolutionError("Meld response names an unknown current issue.")
    if error.code == "UNAVAILABLE_CHOICE":
        return MeldResolutionError("Meld response names an unavailable issue option.")
    if error.code == "STALE_BINDING":
        return MeldResolutionError(
            "Meld response does not match the saved session revision."
        )
    return MeldResolutionError(str(error))


def prepare_meld_resolution_turn(
    request: MeldResolutionTurnRequest,
) -> PendingMeldTurn:
    """Validate one exact response, then compose the operation-owned provider turn."""

    if not isinstance(request, MeldResolutionTurnRequest):
        raise TypeError("Meld resolution requires a typed turn request.")
    if request.issue_uid is None:
        if request.option_uid is not None:
            raise MeldResolutionError("A Meld option requires one exact issue.")
        if not isinstance(request.comment, str) or not request.comment.strip():
            raise MeldResolutionError("A whole-set Meld response requires a comment.")
        return prepare_meld_turn(
            MeldTurnRequest(
                snapshot=request.snapshot,
                comment=request.comment,
                scope="ALL",
                revision=request.revision,
                revises_turn_uids=request.revises_turn_uids,
            )
        )

    case = meld_resolution_case(request.snapshot)
    try:
        progress = evaluate_resolution(
            case,
            ResolutionAttempt(
                binding=case.binding,
                submissions=(
                    ResolutionSubmission(
                        item_uid=request.issue_uid,
                        choice_uid=request.option_uid,
                        comment=request.comment,
                    ),
                ),
            ),
        )
    except ResolutionValidationError as error:
        raise _resolution_error(error) from error
    except (TypeError, ValueError) as error:
        raise MeldResolutionError(str(error)) from error

    submission = progress.submissions[0]
    issue = next(
        issue
        for issue in request.snapshot.session.current_assessment.issues
        if issue.uid == submission.item_uid
    )
    parts: list[str] = []
    if submission.choice_uid is not None:
        option = next(
            option for option in issue.options if option.uid == submission.choice_uid
        )
        # Choice text is operation evidence. Interfaces carry only its stable UID
        # so a reordered or rerendered option cannot silently change the answer.
        parts.append(f"Choose this reading: {option.text}")
    if submission.comment.strip():
        parts.append(submission.comment)
    return prepare_meld_turn(
        MeldTurnRequest(
            snapshot=request.snapshot,
            comment="\n\n".join(parts),
            scope="ISSUE",
            issue_uids=(submission.item_uid,),
            revision=request.revision,
            revises_turn_uids=request.revises_turn_uids,
        )
    )


__all__ = [
    "MeldDestinationPort",
    "MeldDestinationRequest",
    "MeldPreservationPort",
    "MeldResolutionError",
    "MeldResolutionTurnRequest",
    "MeldSessionRepository",
    "MeldSessionSnapshot",
    "MeldSessionVersionError",
    "MeldSessionVersionInputError",
    "MeldTurnRequest",
    "PendingMeldTurn",
    "meld_resolution_case",
    "prepare_meld_preservation_turn",
    "prepare_meld_resolution_turn",
    "prepare_meld_turn",
    "require_meld_session_version",
    "run_meld_destination_change",
    "run_meld_initial_preservation",
    "run_meld_preservation",
    "run_meld_session_defer",
    "run_meld_session_open",
]
