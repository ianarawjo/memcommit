"""Operation-owned application contracts for reviewed Meld execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.operations.meld.model import MELD_OWNER_AWARE_SCHEMA_VERSION, MeldSession


MeldApplyRoute = Literal[
    "STANDARD_TARGET",
    "LOCAL_OWNER_SUBTREE",
    "GRANTED_TARGET",
    "GRANTED_OWNER_SUBTREE",
]


class MeldApplicationError(RuntimeError):
    """A reviewed Meld could not cross its application boundary safely."""


@dataclass(frozen=True)
class MeldApplyRequest:
    """One exact accepted session revision and its optimistic-CAS digest."""

    session: MeldSession
    expected_session_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.expected_session_digest, str) or not (
            self.expected_session_digest
        ):
            raise ValueError("Meld Apply requires a nonempty session digest.")


@dataclass(frozen=True)
class MeldApplyReceipt:
    """Complete operation-owned evidence returned after Meld application."""

    recovered: bool
    checkpoint_uid: str
    result_count: int

    def __post_init__(self) -> None:
        if type(self.recovered) is not bool:
            raise TypeError("Meld recovered state must be boolean.")
        if not isinstance(self.checkpoint_uid, str) or not self.checkpoint_uid:
            raise ValueError("Meld Apply requires a checkpoint UID.")
        if type(self.result_count) is not int or self.result_count < 0:
            raise ValueError("Meld result count must be a nonnegative integer.")


@dataclass(frozen=True)
class MeldApplyResult:
    """The same reviewed session advanced to APPLIED with one exact receipt."""

    session: MeldSession
    route: MeldApplyRoute
    receipt: MeldApplyReceipt


class MeldApplyPort(Protocol):
    """Execute each authority/storage shape without importing a terminal host."""

    def apply_standard_target(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        """Apply a symmetric or legacy single-Target Meld."""

    def apply_local_owner_subtree(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        """Apply one owner-aware directional Meld to local Contexts."""

    def apply_granted_target(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        """Apply one legacy directional Meld to an authority-owned Target."""

    def apply_granted_owner_subtree(
        self,
        session: MeldSession,
        *,
        expected_session_digest: str,
    ) -> MeldApplyReceipt:
        """Apply one owner-aware Meld to an authority-owned subtree."""


def meld_apply_route(session: MeldSession) -> MeldApplyRoute:
    """Classify one reviewed session without touching Store or provider state."""

    owner_aware = (
        session.mode == "DIRECTIONAL"
        and session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
    )
    if session.mode == "DIRECTIONAL" and session.granted_target is not None:
        return "GRANTED_OWNER_SUBTREE" if owner_aware else "GRANTED_TARGET"
    if owner_aware:
        return "LOCAL_OWNER_SUBTREE"
    return "STANDARD_TARGET"


def run_meld_apply(
    request: MeldApplyRequest,
    *,
    port: MeldApplyPort,
) -> MeldApplyResult:
    """Route one exact accepted review and validate its durable receipt."""

    route = meld_apply_route(request.session)
    if route == "GRANTED_OWNER_SUBTREE":
        receipt = port.apply_granted_owner_subtree(
            request.session,
            expected_session_digest=request.expected_session_digest,
        )
    elif route == "GRANTED_TARGET":
        receipt = port.apply_granted_target(
            request.session,
            expected_session_digest=request.expected_session_digest,
        )
    elif route == "LOCAL_OWNER_SUBTREE":
        receipt = port.apply_local_owner_subtree(
            request.session,
            expected_session_digest=request.expected_session_digest,
        )
    else:
        receipt = port.apply_standard_target(
            request.session,
            expected_session_digest=request.expected_session_digest,
        )
    if not isinstance(receipt, MeldApplyReceipt):
        raise TypeError("Meld Apply port returned an invalid receipt.")
    application = request.session.application
    if (
        request.session.state != "APPLIED"
        or application is None
        or application.checkpoint_uid != receipt.checkpoint_uid
        or len(application.result_memory_uids) != receipt.result_count
    ):
        raise MeldApplicationError(
            "Meld Apply returned a receipt outside the reviewed session."
        )
    return MeldApplyResult(
        session=request.session,
        route=route,
        receipt=receipt,
    )


__all__ = [
    "MeldApplicationError",
    "MeldApplyPort",
    "MeldApplyReceipt",
    "MeldApplyRequest",
    "MeldApplyResult",
    "MeldApplyRoute",
    "meld_apply_route",
    "run_meld_apply",
]
