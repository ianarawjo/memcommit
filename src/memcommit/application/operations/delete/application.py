"""Terminal-independent contracts for the unified Delete operation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Protocol


DeletedItemKind = Literal[
    "MEMORY",
    "MEMORY_REF",
    "QUERY_CONTEXT_REF",
    "CONTEXT",
]
ContextDeletionStatus = Literal["APPLIED", "APPLIED_WITH_CLEANUP_WARNING"]


class DeleteError(RuntimeError):
    """Base failure for one unified Delete operation request."""


class DeleteInputError(DeleteError, ValueError):
    """A Delete selector or reviewed plan is invalid."""


class DeleteStalePlanError(DeleteError):
    """The exact deletion target changed after it was reviewed."""


@dataclass(frozen=True, slots=True)
class DirectItemDeleteRequest:
    """One immediate, checkpointed direct-item removal request."""

    selector: str
    context_locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, str) or not self.selector:
            raise DeleteInputError("Delete item selector must be nonblank text.")
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str) or not self.context_locator
        ):
            raise DeleteInputError("Delete item Context locator must be nonblank text.")


@dataclass(frozen=True, slots=True)
class DeletedDirectItem:
    """Stable projection of the direct item removed from its owner."""

    kind: DeletedItemKind
    uid: str
    content: str | None = None
    name: str | None = None
    target_context_name: str | None = None
    target_memory_uid: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {
            "MEMORY",
            "MEMORY_REF",
            "QUERY_CONTEXT_REF",
            "CONTEXT",
        }:
            raise DeleteError("Deleted direct-item kind is invalid.")
        if not isinstance(self.uid, str) or not self.uid:
            raise DeleteError("Deleted direct-item UID must be nonblank text.")
        if self.kind == "MEMORY" and not isinstance(self.content, str):
            raise DeleteError("Deleted Memory content must be text.")
        if self.kind in {"QUERY_CONTEXT_REF", "CONTEXT"} and (
            not isinstance(self.name, str) or not self.name
        ):
            raise DeleteError("Deleted Context-like item name is incomplete.")
        if self.kind == "MEMORY_REF" and (
            not isinstance(self.target_context_name, str)
            or not self.target_context_name
            or not isinstance(self.target_memory_uid, str)
            or not self.target_memory_uid
        ):
            raise DeleteError("Deleted Memory Reference target is incomplete.")


@dataclass(frozen=True, slots=True)
class FrozenDirectItemDeleteTarget:
    """Exact authorized owner and full item identity frozen before mutation."""

    context_name: str
    context_uid: str
    item: DeletedDirectItem
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise DeleteError("Delete item target Context name is incomplete.")
        if not isinstance(self.context_uid, str) or not self.context_uid:
            raise DeleteError("Delete item target Context UID is incomplete.")
        if not isinstance(self.item, DeletedDirectItem):
            raise DeleteError("Delete item target is invalid.")


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
            raise DeleteError("Delete item receipt identity is incomplete.")
        if not isinstance(self.item, DeletedDirectItem):
            raise DeleteError("Delete item receipt has an invalid item.")


@dataclass(frozen=True, slots=True)
class ContextDeleteRequest:
    """One local ordinary Context locator to freeze for permanent deletion."""

    context_locator: str

    def __post_init__(self) -> None:
        if not isinstance(self.context_locator, str) or not self.context_locator:
            raise DeleteInputError("Delete Context locator must be nonblank text.")


@dataclass(frozen=True, slots=True)
class FrozenContextDeletePlan:
    """Exact Context identity reviewed before permanent deletion."""

    context_name: str
    context_uid: str
    context_digest: str
    plan_digest: str
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.context_name, self.context_uid)
        ):
            raise DeleteError("Delete Context plan identity is incomplete.")
        for value, label in (
            (self.context_digest, "Context"),
            (self.plan_digest, "plan"),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise DeleteError(f"Delete {label} digest is invalid.")

    @property
    def descendants_preserved(self) -> bool:
        return True

    @property
    def checkpoint_history_deleted(self) -> bool:
        return True

    @property
    def restorable_snapshot_retained(self) -> bool:
        return False

    @property
    def lifecycle_metadata_retained(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class ContextDeleteResult:
    """Committed lifecycle receipt, including post-commit cleanup state."""

    status: ContextDeletionStatus
    context_name: str
    context_uid: str
    context_digest: str
    plan_digest: str
    event_uid: str
    operation_id: str
    previous_checkpoint_status: str
    descendants_preserved: bool
    cleanup_warning: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"APPLIED", "APPLIED_WITH_CLEANUP_WARNING"}:
            raise DeleteError("Delete Context result status is invalid.")
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.context_name,
                self.context_uid,
                self.event_uid,
                self.operation_id,
                self.previous_checkpoint_status,
            )
        ):
            raise DeleteError("Delete Context receipt identity is incomplete.")
        if self.descendants_preserved is not True:
            raise DeleteError("Delete Context must preserve lexical descendants.")
        if self.status == "APPLIED" and self.cleanup_warning is not None:
            raise DeleteError("Successful Delete receipt cannot contain a warning.")
        if self.status == "APPLIED_WITH_CLEANUP_WARNING" and (
            not isinstance(self.cleanup_warning, str) or not self.cleanup_warning
        ):
            raise DeleteError("Incomplete cleanup requires a bounded warning.")


class DeletePort(Protocol):
    def freeze_item(
        self,
        request: DirectItemDeleteRequest,
    ) -> FrozenDirectItemDeleteTarget: ...

    def remove_item(
        self,
        target: FrozenDirectItemDeleteTarget,
    ) -> DirectItemDeleteResult: ...

    def freeze_context(
        self,
        request: ContextDeleteRequest,
    ) -> FrozenContextDeletePlan: ...

    def delete_context(
        self,
        plan: FrozenContextDeletePlan,
    ) -> ContextDeleteResult: ...


def context_delete_plan_digest(
    *,
    context_name: str,
    context_uid: str,
    context_digest: str,
) -> str:
    """Bind approval to one identity, record revision, and effect contract."""

    payload = {
        "version": 1,
        "operation": "delete-context",
        "context_name": context_name,
        "context_uid": context_uid,
        "context_digest": context_digest,
        "checkpoint_history_deleted": True,
        "descendants_preserved": True,
        "lifecycle_metadata_retained": True,
        "restorable_snapshot_retained": False,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
        raise DeleteError("Delete port returned an invalid item target.")
    result = port.remove_item(target)
    if not isinstance(result, DirectItemDeleteResult):
        raise DeleteError("Delete port returned an invalid item receipt.")
    if (
        result.context_name != target.context_name
        or result.context_uid != target.context_uid
        or result.item != target.item
    ):
        raise DeleteError("Delete item receipt does not match its frozen target.")
    return result


def prepare_context_delete(
    request: ContextDeleteRequest,
    *,
    port: DeletePort,
) -> FrozenContextDeletePlan:
    """Freeze a permanent deletion target without changing durable state."""

    if not isinstance(request, ContextDeleteRequest):
        raise DeleteInputError("Delete Context requires a ContextDeleteRequest.")
    plan = port.freeze_context(request)
    if not isinstance(plan, FrozenContextDeletePlan):
        raise DeleteError("Delete port returned an invalid Context plan.")
    expected = context_delete_plan_digest(
        context_name=plan.context_name,
        context_uid=plan.context_uid,
        context_digest=plan.context_digest,
    )
    if plan.plan_digest != expected:
        raise DeleteError("Delete Context plan does not match its exact target.")
    return plan


def apply_context_delete(
    plan: FrozenContextDeletePlan,
    *,
    port: DeletePort,
) -> ContextDeleteResult:
    """Apply one exact reviewed plan; approval remains an adapter concern."""

    if not isinstance(plan, FrozenContextDeletePlan):
        raise DeleteInputError("Delete Apply requires a frozen Context plan.")
    expected = context_delete_plan_digest(
        context_name=plan.context_name,
        context_uid=plan.context_uid,
        context_digest=plan.context_digest,
    )
    if plan.plan_digest != expected:
        raise DeleteInputError("Delete Context plan digest was modified after review.")
    result = port.delete_context(plan)
    if not isinstance(result, ContextDeleteResult):
        raise DeleteError("Delete port returned an invalid Context receipt.")
    if (
        result.context_name != plan.context_name
        or result.context_uid != plan.context_uid
        or result.context_digest != plan.context_digest
        or result.plan_digest != plan.plan_digest
    ):
        raise DeleteError("Delete Context receipt does not match its reviewed plan.")
    return result


__all__ = [
    "ContextDeleteRequest",
    "ContextDeleteResult",
    "ContextDeletionStatus",
    "DeleteError",
    "DeleteInputError",
    "DeletePort",
    "DeleteStalePlanError",
    "DeletedDirectItem",
    "DeletedItemKind",
    "DirectItemDeleteRequest",
    "DirectItemDeleteResult",
    "FrozenContextDeletePlan",
    "FrozenDirectItemDeleteTarget",
    "apply_context_delete",
    "context_delete_plan_digest",
    "prepare_context_delete",
    "run_direct_item_delete",
]
