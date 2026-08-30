"""Update adapter for the operation-neutral execution phase flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from memcommit.application.operations.update.model import UpdateSession


UpdateApplier = Callable[[UpdateSession], UpdateSession]
UpdateDecisionReviewer = Callable[[UpdateSession], UpdateSession | None]


class UpdateApplicationFlowError(RuntimeError):
    """The Update adapter crossed an invalid decision or Apply boundary."""


@dataclass(frozen=True)
class UpdateApplicationFlowPort:
    """Apply one complete plan under caller-selected review policy.

    A direct console invocation supplies ``application_reviewer``. Composing
    operations omit it because their own session already owns the decision.
    ``authority_reviewer`` remains the compatibility gate for callers that
    expose only granted-Target approval.
    """

    local_applier: UpdateApplier
    granted_source_applier: UpdateApplier
    granted_target_applier: UpdateApplier
    application_reviewer: UpdateDecisionReviewer | None = None
    authority_reviewer: UpdateDecisionReviewer | None = None

    @staticmethod
    def _same_review_boundary(
        prepared: UpdateSession,
        reviewed: UpdateSession,
    ) -> bool:
        """Allow semantic revision without changing the frozen invocation."""

        return replace(
            reviewed,
            uid=prepared.uid,
            created_at=prepared.created_at,
            operations=prepared.operations,
        ) == prepared

    def decide(self, prepared: UpdateSession) -> UpdateSession | None:
        """Resolve the direct-command review or a granted-target write gate."""

        if not isinstance(prepared, UpdateSession) or prepared.status != "staged":
            raise UpdateApplicationFlowError(
                "Update application flow requires a staged session."
            )
        if not prepared.operations:
            return prepared
        if self.application_reviewer is not None:
            reviewed = self.application_reviewer(prepared)
            if reviewed is None:
                return None
            if (
                not isinstance(reviewed, UpdateSession)
                or reviewed.status != "staged"
                or not self._same_review_boundary(prepared, reviewed)
            ):
                raise UpdateApplicationFlowError(
                    "Update review changed the frozen invocation boundary."
                )
            return reviewed
        if prepared.granted_target is None:
            # Composing operations do not enter the direct-command review
            # adapter; their own session already owns the human decision.
            return prepared
        if self.authority_reviewer is None:
            raise UpdateApplicationFlowError(
                "A granted Target mutation requires an authority reviewer."
            )
        reviewed = self.authority_reviewer(prepared)
        if reviewed is None:
            return None
        if not isinstance(reviewed, UpdateSession) or reviewed != prepared:
            # Authority review may approve or close the exact frozen plan; it
            # cannot disguise another provider turn as an approval decision.
            raise UpdateApplicationFlowError(
                "Update authority review returned a different staged plan."
            )
        return reviewed

    def apply(self, decided: UpdateSession) -> UpdateSession:
        """Dispatch by the mutation owner, then verify the durable receipt."""

        if not isinstance(decided, UpdateSession) or decided.status != "staged":
            raise UpdateApplicationFlowError(
                "Update Apply requires the exact staged decisions."
            )
        if decided.granted_target is not None:
            applied = self.granted_target_applier(decided)
        elif decided.granted_source is not None:
            applied = self.granted_source_applier(decided)
        else:
            applied = self.local_applier(decided)
        if (
            not isinstance(applied, UpdateSession)
            or applied.status != "applied"
            or applied.application is None
            or replace(applied, status="staged", application=None) != decided
        ):
            raise UpdateApplicationFlowError(
                "Update Apply returned a receipt outside the decided session."
            )
        return applied
