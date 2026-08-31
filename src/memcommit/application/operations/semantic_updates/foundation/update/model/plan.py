"""Session-independent exact Update plans."""

from __future__ import annotations

from dataclasses import dataclass

from .changes import UpdateOperation, operation_digest


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    """One exact ordered Update against a named working Target root.

    A plan deliberately carries no Impact, review, persistence, or Undo state.
    A direct ``mem update`` invocation may wrap it in an ``UpdateSession`` for
    compatibility, while Meld, Sever, Resolve, and other application
    operations can apply it directly to their own working Target.
    """

    uid: str
    target_uid: str
    target_name: str
    operations: tuple[UpdateOperation, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Update plan uid must be nonblank text.")
        if not isinstance(self.target_uid, str) or not self.target_uid.strip():
            raise ValueError("Update plan Target uid must be nonblank text.")
        if not isinstance(self.target_name, str) or not self.target_name.strip():
            raise ValueError("Update plan Target name must be nonblank text.")
        if not isinstance(self.operations, tuple):
            raise TypeError("Update plan operations must be a tuple.")

    @property
    def digest(self) -> str:
        """Return the digest of the exact ordered effects."""

        return operation_digest(self.operations)


__all__ = ["UpdatePlan"]
