"""Terminal-independent contracts for deleting one current-Context Memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


DeletedItemKind = Literal["MEMORY",]


class MemDeleteError(RuntimeError):
    """Base failure for one unified Delete operation request."""


@dataclass(frozen=True, slots=True)
class ContextDeletePlan:
    """The current Context and exact subtree identities shown before deletion."""

    context_name: str
    context_identities: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ContextDeleteResult:
    context_name: str
    deleted_context_count: int
    cleanup_warning: str | None = None


class DeleteInputError(MemDeleteError, ValueError):
    """A Delete selector or reviewed plan is invalid."""


@dataclass(frozen=True, slots=True)
class DirectItemDeleteRequest:
    """One immediate, checkpointed direct-item removal request."""

    selector: str
    context_locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, str) or not self.selector:
            raise DeleteInputError("Delete item selector must be nonblank text.")
        if ":" in self.selector:
            raise DeleteInputError(
                "Delete accepts only a Memory UID in the current Context."
            )
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator
        ):
            raise DeleteInputError("Delete item Context locator must be nonblank text.")


@dataclass(frozen=True, slots=True)
class DeletedDirectItem:
    """Stable projection of one directly owned Memory removed by Delete."""

    kind: DeletedItemKind
    uid: str
    content: str

    def __post_init__(self) -> None:
        if self.kind != "MEMORY":
            raise MemDeleteError("Deleted direct-item kind is invalid.")
        if not isinstance(self.uid, str) or not self.uid:
            raise MemDeleteError("Deleted Memory UID must be nonblank text.")
        if not isinstance(self.content, str):
            raise MemDeleteError("Deleted Memory content must be text.")


@dataclass(frozen=True, slots=True)
class FrozenDirectItemDeleteTarget:
    """Exact authorized owner and full item identity frozen before mutation."""

    context_name: str
    context_uid: str
    item: DeletedDirectItem
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise MemDeleteError("Delete item target Context name is incomplete.")
        if not isinstance(self.context_uid, str) or not self.context_uid:
            raise MemDeleteError("Delete item target Context UID is incomplete.")
        if not isinstance(self.item, DeletedDirectItem):
            raise MemDeleteError("Delete item target is invalid.")


@dataclass(frozen=True, slots=True)
class DirectItemDeleteResult:
    """Complete checkpointed receipt for one direct-item removal."""

    context_name: str
    context_uid: str
    item: DeletedDirectItem
    checkpoint_uid: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_name, self.context_uid, self.checkpoint_uid)
        ):
            raise MemDeleteError("Delete item receipt identity is incomplete.")
        if not isinstance(self.item, DeletedDirectItem):
            raise MemDeleteError("Delete item receipt has an invalid item.")


class DeletePort(Protocol):
    def freeze_item(
        self, request: DirectItemDeleteRequest
    ) -> FrozenDirectItemDeleteTarget: ...

    def remove_item(
        self, target: FrozenDirectItemDeleteTarget
    ) -> DirectItemDeleteResult: ...


def run_direct_item_delete(
    request: DirectItemDeleteRequest,
    *,
    port: DeletePort,
    frozen_target: FrozenDirectItemDeleteTarget | None = None,
) -> DirectItemDeleteResult:
    """Remove one exact item and require one complete checkpoint receipt."""

    if not isinstance(request, DirectItemDeleteRequest):
        raise DeleteInputError("Delete item requires a DirectItemDeleteRequest.")
    target = frozen_target or port.freeze_item(request)
    if not isinstance(target, FrozenDirectItemDeleteTarget):
        raise MemDeleteError("Delete port returned an invalid item target.")
    result = port.remove_item(target)
    if not isinstance(result, DirectItemDeleteResult):
        raise MemDeleteError("Delete port returned an invalid item receipt.")
    if (
        result.context_name != target.context_name
        or result.context_uid != target.context_uid
        or result.item != target.item
    ):
        raise MemDeleteError("Delete item receipt does not match its frozen target.")
    return result


__all__ = [
    "ContextDeletePlan",
    "ContextDeleteResult",
    "MemDeleteError",
    "DeleteInputError",
    "DeletePort",
    "DeletedDirectItem",
    "DeletedItemKind",
    "DirectItemDeleteRequest",
    "DirectItemDeleteResult",
    "FrozenDirectItemDeleteTarget",
    "run_direct_item_delete",
]
