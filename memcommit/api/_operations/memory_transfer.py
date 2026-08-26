"""Public application assembly for direct-Memory Copy and Move."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.readable import active_client_registry
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    MemoryTransferAuthorityError,
    MemoryTransferConflictError,
    MemoryTransferContextError,
    MemoryTransferExecutionError,
    MemoryTransferError as PublicMemoryTransferError,
    MemoryTransferInputError,
    MemoryTransferStorageError,
)
from memcommit.api.memory_transfer import (
    CopyMemoriesReceipt,
    MemoryTransferCheckpointResult,
    MemoryTransferItemResult,
    MemoryTransferPlacementResult,
    MoveMemoriesReceipt,
)
from memcommit.operations.memory_transfer.application import (
    CopyMemoriesRequest,
    MemoryTransferAuthorityError as InternalMemoryTransferAuthorityError,
    MemoryTransferError as InternalMemoryTransferError,
    MemoryTransferStalePlanError,
    MoveMemoriesRequest,
    run_copy,
    run_move,
)
from memcommit.operations.memory_transfer.runtime import MemoryStoreMemoryTransferPort
from memcommit.operations.profile.config import ProfileConfigError
from memcommit.operations.profile.model import ProfileError
from memcommit.store import ConcurrentContextUpdateError
from memcommit.authority.write_protection import WriteProtectionError


def _locators(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise MemoryTransferInputError(
            "Memory locators must be a sequence of locator strings, not one string."
        )
    try:
        result = tuple(values)
    except TypeError as error:
        raise_public(MemoryTransferInputError, error)
    if not result or any(not isinstance(value, str) or not value for value in result):
        raise MemoryTransferInputError(
            "Memory locators must contain one or more nonempty strings."
        )
    return result


def _placement(value) -> MemoryTransferPlacementResult:
    return MemoryTransferPlacementResult(
        position=value.position,
        previous_uid=value.previous_uid,
        next_uid=value.next_uid,
    )


def _items(values) -> tuple[MemoryTransferItemResult, ...]:
    return tuple(
        MemoryTransferItemResult(
            source_context_name=value.source_context_name,
            source_context_uid=value.source_context_uid,
            source_memory_uid=value.source_memory_uid,
            into_memory_uid=value.into_memory_uid,
        )
        for value in values
    )


def _checkpoints(values) -> tuple[MemoryTransferCheckpointResult, ...]:
    return tuple(
        MemoryTransferCheckpointResult(
            context_name=value.context_name,
            context_uid=value.context_uid,
            checkpoint_uid=value.checkpoint_uid,
        )
        for value in values
    )


def _raise(error: Exception) -> None:
    if isinstance(error, PublicMemoryTransferError):
        raise error
    if isinstance(error, MemoryTransferStalePlanError):
        raise_public(MemoryTransferConflictError, error)
    if isinstance(error, InternalMemoryTransferAuthorityError):
        raise_public(MemoryTransferAuthorityError, error)
    if isinstance(error, FileNotFoundError):
        raise_public(MemoryTransferContextError, error)
    if isinstance(error, (ProfileConfigError, ProfileError, WriteProtectionError)):
        raise_public(MemoryTransferAuthorityError, error)
    if isinstance(error, ConcurrentContextUpdateError):
        raise_public(MemoryTransferConflictError, error)
    if isinstance(error, OSError):
        raise_public(MemoryTransferStorageError, error)
    if isinstance(error, (KeyError, TypeError, ValueError)):
        raise_public(MemoryTransferInputError, error)
    if isinstance(error, InternalMemoryTransferError):
        # Resolution, collision, policy, and link-boundary failures are
        # actionable request errors unless separately classified as stale.
        raise_public(MemoryTransferInputError, error)
    raise_public(MemoryTransferExecutionError, error)


def copy_memories(
    runtime: ClientRuntime,
    memory_locators: Sequence[str],
    *,
    into_context: str | None = None,
    source_context: str | None = None,
    before: str | None = None,
    after: str | None = None,
) -> CopyMemoriesReceipt:
    """Copy one exact ordered batch into an existing local Context."""

    try:
        result = run_copy(
            CopyMemoriesRequest(
                memory_locators=_locators(memory_locators),
                into_locator=into_context,
                source_locator=source_context,
                before=before,
                after=after,
            ),
            port=MemoryStoreMemoryTransferPort.capture(
                runtime.store,
                allow_granted_sources=active_client_registry(runtime) is not None,
            ),
        )
    except Exception as error:
        _raise(error)
        raise AssertionError("unreachable")
    return CopyMemoriesReceipt(
        into_context_name=result.into_name,
        into_context_uid=result.into_uid,
        placement=_placement(result.placement),
        items=_items(result.items),
        plan_digest=result.plan_digest,
        checkpoints=_checkpoints(result.checkpoints),
    )


def move_memories(
    runtime: ClientRuntime,
    memory_locators: Sequence[str],
    *,
    into_context: str | None = None,
    source_context: str | None = None,
    before: str | None = None,
    after: str | None = None,
    retarget_links: bool = False,
    break_links: bool = False,
) -> MoveMemoriesReceipt:
    """Move one exact ordered batch and every selected link effect atomically."""

    if not isinstance(retarget_links, bool) or not isinstance(break_links, bool):
        raise MemoryTransferInputError(
            "retarget_links and break_links must be booleans."
        )
    if retarget_links and break_links:
        raise MemoryTransferInputError(
            "Choose only one of retarget_links or break_links."
        )
    # Retargeting is the normal meaning of moving a live Memory identity.
    # Keep retarget_links as a compatibility spelling while breakage remains
    # the only behavior that needs an explicit opt-in.
    policy = "BREAK" if break_links else "RETARGET"
    try:
        result = run_move(
            MoveMemoriesRequest(
                memory_locators=_locators(memory_locators),
                into_locator=into_context,
                source_locator=source_context,
                before=before,
                after=after,
                link_policy=policy,
            ),
            port=MemoryStoreMemoryTransferPort.capture(
                runtime.store,
                allow_granted_sources=active_client_registry(runtime) is not None,
            ),
        )
    except Exception as error:
        _raise(error)
        raise AssertionError("unreachable")
    return MoveMemoriesReceipt(
        into_context_name=result.into_name,
        into_context_uid=result.into_uid,
        link_policy=result.link_policy,
        placement=_placement(result.placement),
        items=_items(result.items),
        inbound_link_count=result.inbound_link_count,
        retargeted_link_count=result.retargeted_link_count,
        dangling_link_count=result.dangling_link_count,
        plan_digest=result.plan_digest,
        checkpoints=_checkpoints(result.checkpoints),
    )


__all__ = ["copy_memories", "move_memories"]
