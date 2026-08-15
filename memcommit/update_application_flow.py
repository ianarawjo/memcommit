"""Update adapter for the operation-neutral application phase flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from memcommit.update import UpdateSession


UpdateIncorporate = Callable[[UpdateSession, str], UpdateSession]
UpdateReviewer = Callable[
    [UpdateSession, UpdateIncorporate, str | None],
    UpdateSession | None,
]
UpdateApplier = Callable[[UpdateSession], UpdateSession]


class UpdateApplicationFlowError(RuntimeError):
    """The Update adapter crossed an invalid review or Apply boundary."""


@dataclass(frozen=True)
class UpdateApplicationFlowPort:
    """Adapt one staged Update to shared review/application phase order."""

    interactive: bool
    reviewer: UpdateReviewer
    incorporate: UpdateIncorporate
    local_applier: UpdateApplier
    granted_source_applier: UpdateApplier
    granted_target_applier: UpdateApplier
    analysis_origin: str | None = None

    def __post_init__(self) -> None:
        if type(self.interactive) is not bool:
            raise TypeError("Update interactive state must be boolean.")

    def review(self, prepared: UpdateSession) -> UpdateSession | None:
        """Retain noninteractive parity or enter the existing Update review."""

        if not isinstance(prepared, UpdateSession) or prepared.status != "staged":
            raise UpdateApplicationFlowError(
                "Update application flow requires a staged session."
            )
        if not self.interactive:
            return prepared
        reviewed = self.reviewer(
            prepared,
            self.incorporate,
            self.analysis_origin,
        )
        if reviewed is None:
            return None
        if not isinstance(reviewed, UpdateSession) or reviewed.status != "staged":
            raise UpdateApplicationFlowError(
                "Update review returned an invalid staged session."
            )
        return reviewed

    def apply(self, reviewed: UpdateSession) -> UpdateSession:
        """Dispatch by the mutation owner, then verify the durable receipt."""

        if not isinstance(reviewed, UpdateSession) or reviewed.status != "staged":
            raise UpdateApplicationFlowError(
                "Update Apply requires the exact staged review."
            )
        if reviewed.granted_target is not None:
            applied = self.granted_target_applier(reviewed)
        elif reviewed.granted_source is not None:
            applied = self.granted_source_applier(reviewed)
        else:
            applied = self.local_applier(reviewed)
        if (
            not isinstance(applied, UpdateSession)
            or applied.status != "applied"
            or applied.application is None
            or replace(applied, status="staged", application=None) != reviewed
        ):
            raise UpdateApplicationFlowError(
                "Update Apply returned a receipt outside the reviewed session."
            )
        return applied
