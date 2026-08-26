"""Meld adapter for the operation-neutral application phase flow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from memcommit.operations.meld.model import MeldSession


MeldApplicationReceipt = tuple[bool, str, int]
MeldApplier = Callable[[MeldSession, str], MeldApplicationReceipt]


class MeldApplicationFlowError(RuntimeError):
    """The Meld adapter crossed an invalid final Apply boundary."""


@dataclass(frozen=True)
class MeldApplicationFlowPort:
    """Adapt one accepted Meld session to the shared application phases.

    The interactive workbench has already persisted every decision turn before
    this port is entered. The decision phase therefore preserves the exact
    mutable session object expected by Meld's existing Apply and recovery
    implementation; cloning it here would change caller-visible lifecycle
    behavior and its saved-session CAS contract.
    """

    expected_session_digest: str
    applier: MeldApplier

    def decide(self, prepared: MeldSession) -> MeldSession:
        """Hand off the exact decision-complete session from the operation."""

        return prepared

    def apply(self, decided: MeldSession) -> MeldApplicationReceipt:
        """Apply through the operation-owned dispatcher and verify its receipt."""

        receipt = self.applier(decided, self.expected_session_digest)
        if (
            not isinstance(receipt, tuple)
            or len(receipt) != 3
            or type(receipt[0]) is not bool
            or not isinstance(receipt[1], str)
            or not receipt[1]
            or type(receipt[2]) is not int
            or receipt[2] < 0
        ):
            raise MeldApplicationFlowError(
                "Meld Apply returned an invalid application receipt."
            )
        application = decided.application
        if (
            decided.state != "APPLIED"
            or application is None
            or application.checkpoint_uid != receipt[1]
            or len(application.result_memory_uids) != receipt[2]
        ):
            raise MeldApplicationFlowError(
                "Meld Apply returned a receipt outside the decided session."
            )
        return receipt
