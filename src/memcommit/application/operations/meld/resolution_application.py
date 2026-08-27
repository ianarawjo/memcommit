"""Operation-owned projection from exact Meld choices to semantic turns."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.meld.model import MeldError, MeldRevision
from memcommit.application.operations.meld.session_application import (
    MeldSessionSnapshot,
    MeldTurnRequest,
    PendingMeldTurn,
    prepare_meld_turn,
)
from memcommit.resolution import (
    ResolutionAttempt,
    ResolutionBinding,
    ResolutionCase,
    ResolutionRequirement,
    ResolutionSubmission,
    ResolutionValidationError,
    evaluate_resolution,
)


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
    "MeldResolutionError",
    "MeldResolutionTurnRequest",
    "meld_resolution_case",
    "prepare_meld_resolution_turn",
]
