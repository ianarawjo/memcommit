"""Update adapter for the operation-neutral execution phase flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from memcommit.update import UpdateSession


UpdateIncorporate = Callable[[UpdateSession, str], UpdateSession]
UpdateDecisionResolver = Callable[
    [UpdateSession, UpdateIncorporate, str | None],
    UpdateSession | None,
]
UpdateApplier = Callable[[UpdateSession], UpdateSession]


class UpdateApplicationFlowError(RuntimeError):
    """The Update adapter crossed an invalid decision or Apply boundary."""


@dataclass(frozen=True)
class UpdateApplicationFlowPort:
    """Adapt one staged Update to shared decision/application phase order."""

    interactive: bool
    decision_resolver: UpdateDecisionResolver
    incorporate: UpdateIncorporate
    local_applier: UpdateApplier
    granted_source_applier: UpdateApplier
    granted_target_applier: UpdateApplier
    analysis_origin: str | None = None

    def __post_init__(self) -> None:
        if type(self.interactive) is not bool:
            raise TypeError("Update interactive state must be boolean.")

    def decide(self, prepared: UpdateSession) -> UpdateSession | None:
        """Resolve only execution-time Update choices and approval."""

        if not isinstance(prepared, UpdateSession) or prepared.status != "staged":
            raise UpdateApplicationFlowError(
                "Update application flow requires a staged session."
            )
        if not self.interactive:
            return prepared
        decided = self.decision_resolver(
            prepared,
            self.incorporate,
            self.analysis_origin,
        )
        if decided is None:
            return None
        if not isinstance(decided, UpdateSession) or decided.status != "staged":
            raise UpdateApplicationFlowError(
                "Update decision resolver returned an invalid staged session."
            )
        return decided

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
