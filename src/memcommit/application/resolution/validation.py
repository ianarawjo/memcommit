"""Exact validation for one frozen operation-owned resolution surface."""

from __future__ import annotations

from typing import Literal

from memcommit.application.resolution.model import (
    ResolutionAttempt,
    ResolutionCase,
    ResolutionProgress,
    ResolutionSubmission,
)


ResolutionValidationCode = Literal[
    "BULK_WITH_SUBMISSIONS",
    "COMMENT_NOT_ALLOWED",
    "DUPLICATE_ITEM",
    "STALE_BINDING",
    "UNAVAILABLE_CHOICE",
    "UNKNOWN_ITEM",
    "UNRESOLVED_REQUIRED",
]


class ResolutionValidationError(ValueError):
    """A structured operation-neutral resolution contract violation."""

    def __init__(
        self,
        code: ResolutionValidationCode,
        message: str,
        *,
        item_uids: tuple[str, ...] = (),
        choice_uid: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.item_uids = item_uids
        self.choice_uid = choice_uid


def evaluate_resolution(
    case: ResolutionCase,
    attempt: ResolutionAttempt,
) -> ResolutionProgress:
    """Validate and canonically order staged answers without applying them."""

    if not isinstance(case, ResolutionCase):
        raise TypeError("Resolution evaluation requires a ResolutionCase.")
    if not isinstance(attempt, ResolutionAttempt):
        raise TypeError("Resolution evaluation requires a ResolutionAttempt.")
    if attempt.binding != case.binding:
        raise ResolutionValidationError(
            "STALE_BINDING",
            "Resolution attempt does not match the frozen artifact revision.",
        )
    submissions = attempt.submissions
    bulk_choice_uid = attempt.bulk_choice_uid
    if bulk_choice_uid is not None and submissions:
        raise ResolutionValidationError(
            "BULK_WITH_SUBMISSIONS",
            "Use either a bulk resolution or per-item submissions.",
        )

    requirements = {
        requirement.item_uid: requirement for requirement in case.requirements
    }
    if bulk_choice_uid is not None:
        unavailable = tuple(
            requirement.item_uid
            for requirement in case.requirements
            if bulk_choice_uid not in requirement.choice_uids
        )
        if unavailable:
            raise ResolutionValidationError(
                "UNAVAILABLE_CHOICE",
                "The bulk choice is unavailable for one or more items.",
                item_uids=unavailable,
                choice_uid=bulk_choice_uid,
            )
        supplied = {
            requirement.item_uid: ResolutionSubmission(
                item_uid=requirement.item_uid,
                choice_uid=bulk_choice_uid,
            )
            for requirement in case.requirements
        }
    else:
        supplied: dict[str, ResolutionSubmission] = {}
        for submission in submissions:
            requirement = requirements.get(submission.item_uid)
            if requirement is None:
                raise ResolutionValidationError(
                    "UNKNOWN_ITEM",
                    "Resolution submission names an unknown item.",
                    item_uids=(submission.item_uid,),
                    choice_uid=submission.choice_uid,
                )
            if submission.item_uid in supplied:
                raise ResolutionValidationError(
                    "DUPLICATE_ITEM",
                    "Resolution submission repeats an item.",
                    item_uids=(submission.item_uid,),
                    choice_uid=submission.choice_uid,
                )
            if (
                submission.choice_uid is not None
                and submission.choice_uid not in requirement.choice_uids
            ):
                raise ResolutionValidationError(
                    "UNAVAILABLE_CHOICE",
                    "Resolution choice is unavailable for this item.",
                    item_uids=(submission.item_uid,),
                    choice_uid=submission.choice_uid,
                )
            if submission.comment.strip() and not requirement.comment_allowed:
                raise ResolutionValidationError(
                    "COMMENT_NOT_ALLOWED",
                    "This resolution item does not accept a free response.",
                    item_uids=(submission.item_uid,),
                    choice_uid=submission.choice_uid,
                )
            supplied[submission.item_uid] = submission

    unresolved = tuple(
        requirement.item_uid
        for requirement in case.requirements
        if requirement.obligation == "REQUIRED" and requirement.item_uid not in supplied
    )
    ordered = tuple(
        supplied[requirement.item_uid]
        for requirement in case.requirements
        if requirement.item_uid in supplied
    )
    return ResolutionProgress(
        binding=case.binding,
        submissions=ordered,
        unresolved_required_uids=unresolved,
    )


def require_resolution_ready(
    case: ResolutionCase,
    attempt: ResolutionAttempt,
) -> ResolutionProgress:
    """Return complete progress or fail with exact unresolved identities."""

    progress = evaluate_resolution(case, attempt)
    if progress.unresolved_required_uids:
        raise ResolutionValidationError(
            "UNRESOLVED_REQUIRED",
            "Resolution has unresolved required items.",
            item_uids=progress.unresolved_required_uids,
        )
    return progress
