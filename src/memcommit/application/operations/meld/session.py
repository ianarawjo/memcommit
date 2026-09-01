"""Version binding for the current Audit-backed Meld session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.meld.model import MeldError, MeldSession


class MeldSessionVersionError(MeldError):
    """A saved Meld changed after the caller reviewed it."""


class MeldSessionVersionInputError(ValueError):
    """A caller omitted or malformed the opaque Meld version token."""


@dataclass(frozen=True, slots=True)
class MeldSessionSnapshot:
    """One exact saved Meld revision and its opaque optimistic-CAS token."""

    session: MeldSession
    version_token: str

    def __post_init__(self) -> None:
        if not isinstance(self.session, MeldSession):
            raise TypeError("A Meld snapshot requires a Meld session.")
        if not isinstance(self.version_token, str) or not self.version_token:
            raise ValueError("A saved Meld session requires a version token.")


def require_meld_session_version(
    snapshot: MeldSessionSnapshot,
    expected_version: str,
) -> MeldSessionSnapshot:
    """Bind one current Meld action to the exact revision a caller reviewed."""

    if not isinstance(snapshot, MeldSessionSnapshot):
        raise TypeError("Meld version validation requires a saved snapshot.")
    if not isinstance(expected_version, str) or not expected_version:
        raise MeldSessionVersionInputError(
            "A saved Meld action requires an opaque expected version."
        )
    if snapshot.version_token != expected_version:
        raise MeldSessionVersionError(
            "The saved Meld changed after this action was reviewed."
        )
    return snapshot


__all__ = [
    "MeldSessionSnapshot",
    "MeldSessionVersionError",
    "MeldSessionVersionInputError",
    "require_meld_session_version",
]
