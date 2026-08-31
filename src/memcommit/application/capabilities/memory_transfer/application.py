"""Terminal-independent contracts for direct-Memory Copy and Move."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MemoryTransferKind = Literal["COPY", "MOVE"]
MoveLinkPolicy = Literal["BLOCK", "RETARGET", "BREAK"]


class MemoryTransferError(RuntimeError):
    """Raised when one exact Copy or Move cannot be completed atomically."""


class MemoryTransferStalePlanError(MemoryTransferError):
    """Raised when frozen Source, Target, or link evidence changed before Apply."""


class MemoryTransferAuthorityError(MemoryTransferError):
    """Raised when a readable Source does not authorize the requested effect."""


@dataclass(frozen=True, slots=True)
class MemoryTransferPlacement:
    """One exact gap in a frozen Target direct-item order."""

    position: int
    previous_uid: str | None
    next_uid: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("Copy/Move placement must be nonnegative.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first Copy/Move gap has no previous item.")


@dataclass(frozen=True, slots=True)
class CopyMemoriesRequest:
    """Copy exact local or READ-granted Memories into one local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None


@dataclass(frozen=True, slots=True)
class MoveMemoriesRequest:
    """Move directly owned local Memories into one existing local Context."""

    memory_locators: tuple[str, ...]
    into_locator: str | None = None
    source_locator: str | None = None
    before: str | None = None
    after: str | None = None
    # A live Embed names the Memory's current owner binding, so moving that
    # Memory retargets the local live link atomically unless breakage is an
    # explicit request. Immutable Reference snapshots never participate.
    link_policy: MoveLinkPolicy = "RETARGET"


@dataclass(frozen=True, slots=True)
class FrozenTransferAuthority:
    """Path-free Grant identity retained with one exported Source binding."""

    public_name: str
    grantee_profile_uid: str
    authority_profile_uid: str
    attachment_context_uid: str
    attachment_context_name: str
    grant_uid: str
    grant_revision: int
    grant_digest: str
    resource_uid: str
    resource_name: str
    authority_context_name: str
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        text_values = (
            self.public_name,
            self.grantee_profile_uid,
            self.authority_profile_uid,
            self.attachment_context_uid,
            self.attachment_context_name,
            self.grant_uid,
            self.grant_digest,
            self.resource_uid,
            self.resource_name,
            self.authority_context_name,
        )
        if any(not isinstance(value, str) or not value for value in text_values):
            raise ValueError("A frozen transfer authority binding is incomplete.")
        if (
            isinstance(self.grant_revision, bool)
            or not isinstance(self.grant_revision, int)
            or self.grant_revision < 1
        ):
            raise ValueError("A frozen transfer Grant revision is invalid.")
        if (
            not isinstance(self.permissions, tuple)
            or not self.permissions
            or len(set(self.permissions)) != len(self.permissions)
            or any(
                not isinstance(permission, str) or not permission
                for permission in self.permissions
            )
        ):
            raise ValueError("Frozen transfer Grant permissions are invalid.")

    def to_dict(self) -> dict[str, object]:
        """Project stable checkpoint and digest provenance without Store paths."""

        return {
            "kind": "GRANTED_CONTEXT",
            "public_name": self.public_name,
            "grantee_profile_uid": self.grantee_profile_uid,
            "authority_profile_uid": self.authority_profile_uid,
            "attachment": {
                "uid": self.attachment_context_uid,
                "name": self.attachment_context_name,
            },
            "grant": {
                "uid": self.grant_uid,
                "revision": self.grant_revision,
                "digest": self.grant_digest,
                "permissions": list(self.permissions),
            },
            "resource": {
                "uid": self.resource_uid,
                "name": self.resource_name,
            },
            "authority_context_name": self.authority_context_name,
        }


@dataclass(frozen=True, slots=True)
class FrozenTransferMemory:
    """One exact Source Memory and its direct owner binding."""

    source_context_name: str
    source_context_uid: str
    source_context_digest: str
    source_memory_uid: str
    content: str
    output_memory_uid: str
    source_authority: FrozenTransferAuthority | None = None


@dataclass(frozen=True, slots=True)
class FrozenInboundMemoryLink:
    """One direct live Embed that targets a Memory selected for Move."""

    owner_context_name: str
    owner_context_uid: str
    owner_context_digest: str
    reference_uid: str
    source_context_uid: str
    source_memory_uid: str


@dataclass(frozen=True, slots=True)
class FrozenCopyMemoriesPlan:
    request: CopyMemoriesRequest
    memories: tuple[FrozenTransferMemory, ...]
    into_name: str
    into_uid: str
    into_digest: str
    placement: MemoryTransferPlacement
    plan_digest: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class FrozenMoveMemoriesPlan:
    request: MoveMemoriesRequest
    memories: tuple[FrozenTransferMemory, ...]
    into_name: str
    into_uid: str
    into_digest: str
    placement: MemoryTransferPlacement
    inbound_links: tuple[FrozenInboundMemoryLink, ...]
    plan_digest: str
    token: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class MemoryTransferItemResult:
    source_context_name: str
    source_context_uid: str
    source_memory_uid: str
    into_memory_uid: str


@dataclass(frozen=True, slots=True)
class MemoryTransferCheckpoint:
    context_name: str
    context_uid: str
    checkpoint_uid: str


@dataclass(frozen=True, slots=True)
class CopyMemoriesResult:
    into_name: str
    into_uid: str
    placement: MemoryTransferPlacement
    items: tuple[MemoryTransferItemResult, ...]
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpoint, ...]

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass(frozen=True, slots=True)
class MoveMemoriesResult:
    into_name: str
    into_uid: str
    link_policy: MoveLinkPolicy
    placement: MemoryTransferPlacement
    items: tuple[MemoryTransferItemResult, ...]
    inbound_link_count: int
    retargeted_link_count: int
    dangling_link_count: int
    plan_digest: str
    checkpoints: tuple[MemoryTransferCheckpoint, ...]

    @property
    def count(self) -> int:
        return len(self.items)


def _validate_common_request(
    memory_locators: tuple[str, ...],
    *,
    into_locator: str | None,
    source_locator: str | None,
    before: str | None,
    after: str | None,
) -> None:
    if (
        not isinstance(memory_locators, tuple)
        or not memory_locators
        or any(not isinstance(value, str) or not value for value in memory_locators)
    ):
        raise MemoryTransferError(
            "Copy/Move requires one or more nonempty Memory locators."
        )
    for value, label in (
        (into_locator, "Target Context"),
        (source_locator, "Source Context"),
        (before, "before selector"),
        (after, "after selector"),
    ):
        if value is not None and (not isinstance(value, str) or not value):
            raise MemoryTransferError(f"Copy/Move {label} must be nonempty text.")
    if before is not None and after is not None:
        raise MemoryTransferError("Pass only one of --before or --after.")


def validate_copy_request(request: CopyMemoriesRequest) -> CopyMemoriesRequest:
    if not isinstance(request, CopyMemoriesRequest):
        raise TypeError("Copy requires a CopyMemoriesRequest.")
    _validate_common_request(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    return request


def validate_move_request(request: MoveMemoriesRequest) -> MoveMemoriesRequest:
    if not isinstance(request, MoveMemoriesRequest):
        raise TypeError("Move requires a MoveMemoriesRequest.")
    _validate_common_request(
        request.memory_locators,
        into_locator=request.into_locator,
        source_locator=request.source_locator,
        before=request.before,
        after=request.after,
    )
    if request.link_policy not in {"BLOCK", "RETARGET", "BREAK"}:
        raise MemoryTransferError(
            "Move link_policy must be BLOCK, RETARGET, or BREAK."
        )
    return request


def _validate_plan_common(
    memories: tuple[FrozenTransferMemory, ...],
    *,
    into_name: str,
    into_uid: str,
    into_digest: str,
    placement: MemoryTransferPlacement,
    plan_digest: str,
) -> None:
    if not memories or len({
        (item.source_context_uid, item.source_memory_uid) for item in memories
    }) != len(memories):
        raise MemoryTransferError("Copy/Move plan has duplicate Sources.")
    if any(
        item.source_authority is not None
        and item.source_authority.public_name != item.source_context_name
        for item in memories
    ):
        raise MemoryTransferError(
            "Copy/Move plan has a mismatched Grant Source binding."
        )
    if not all((into_name, into_uid, into_digest, plan_digest)):
        raise MemoryTransferError("Copy/Move plan has an incomplete binding.")
    if not isinstance(placement, MemoryTransferPlacement):
        raise TypeError("Copy/Move plan has an invalid placement.")


__all__ = [
    "CopyMemoriesRequest",
    "CopyMemoriesResult",
    "FrozenCopyMemoriesPlan",
    "FrozenInboundMemoryLink",
    "FrozenMoveMemoriesPlan",
    "FrozenTransferAuthority",
    "FrozenTransferMemory",
    "MemoryTransferCheckpoint",
    "MemoryTransferAuthorityError",
    "MemoryTransferError",
    "MemoryTransferItemResult",
    "MemoryTransferKind",
    "MemoryTransferPlacement",
    "MemoryTransferStalePlanError",
    "MoveLinkPolicy",
    "MoveMemoriesRequest",
    "MoveMemoriesResult",
    "validate_copy_request",
    "validate_move_request",
]
