"""Update adapter for the operation-neutral execution phase flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from memcommit.application.operations.update.model import UpdateSession


UpdateApplier = Callable[[UpdateSession], UpdateSession]
UpdateAuthorityReviewer = Callable[[UpdateSession], UpdateSession | None]


class UpdateApplicationFlowError(RuntimeError):
    """The Update adapter crossed an invalid decision or Apply boundary."""


@dataclass(frozen=True)
class UpdateApplicationFlowPort:
    """Apply one complete plan, retaining only external-owner approval."""

    local_applier: UpdateApplier
    granted_source_applier: UpdateApplier
    granted_target_applier: UpdateApplier
    authority_reviewer: UpdateAuthorityReviewer | None = None

    def decide(self, prepared: UpdateSession) -> UpdateSession | None:
        """Skip semantic review while preserving a granted-target write gate."""

        if not isinstance(prepared, UpdateSession) or prepared.status != "staged":
            raise UpdateApplicationFlowError(
                "Update application flow requires a staged session."
            )
        if prepared.granted_target is None or not prepared.operations:
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
