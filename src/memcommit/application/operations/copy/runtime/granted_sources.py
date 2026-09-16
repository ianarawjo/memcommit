"""Copy's retained READ-granted Source preparation and publication locks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass

from memcommit.application.authorization.context_operation import (
    authorized_context_operation,
)
from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferFrame,
    StoreTransferToken,
    source_access_snapshot,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferAuthority,
    FrozenTransferMemory,
    MemoryTransferError,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    freeze_granted_context_binding,
)
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class CopyStoreToken:
    bindings: StoreTransferToken
    authority_checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...]


def load_granted_source_frames(
    store: MemoryStore,
    frames: tuple[StoreTransferFrame, ...],
    *,
    owner_locators: tuple[str, ...],
    current_name: str | None,
    allow_granted_sources: bool,
) -> tuple[StoreTransferFrame, ...]:
    additions: list[StoreTransferFrame] = []
    with source_access_snapshot(
        store,
        owner_locators,
        current_name=current_name,
        inspect_grants=allow_granted_sources,
    ) as accesses:
        seen: set[tuple[str, str]] = set()
        for access in accesses:
            if not access.is_granted:
                continue
            context = access.store.load_direct(access.context_name)
            identity = (access.access_name, context.uid)
            if identity in seen:
                continue
            seen.add(identity)
            additions.append(
                StoreTransferFrame(
                    context=context,
                    expected_digest=context_record_digest(context),
                    display_name=access.access_name,
                    access=access,
                )
            )
    return (*frames, *additions)


def frozen_transfer_authority(access: ContextAccess) -> FrozenTransferAuthority | None:
    if not access.is_granted:
        return None
    binding = freeze_granted_context_binding(access)
    return FrozenTransferAuthority(
        access_name=binding.access_name,
        grantee_profile_uid=binding.grantee_profile_uid,
        authority_profile_uid=binding.authority_profile_uid,
        grant_uid=binding.grant_uid,
        grant_revision=binding.grant_revision,
        grant_digest=binding.grant_digest,
        resource_uid=binding.resource_uid,
        resource_name=binding.resource_name,
        authority_context_name=binding.authority_context_name,
        permissions=binding.permissions,
    )


def unique_source_accesses(
    memories: tuple[FrozenTransferMemory, ...],
    frames_by_name: dict[str, StoreTransferFrame],
) -> tuple[ContextAccess, ...]:
    accesses: list[ContextAccess] = []
    seen: set[tuple[str, str, str]] = set()
    for item in memories:
        access = frames_by_name[item.source_context_name].access
        key = (
            str(access.store.store_dir),
            access.context_name,
            access.view.grant.uid if access.view is not None else "",
        )
        if key not in seen:
            seen.add(key)
            accesses.append(access)
    return tuple(accesses)


def copy_authority_checks(
    accesses: tuple[ContextAccess, ...],
) -> tuple[tuple[ContextAccess, tuple[str, ...]], ...]:
    checks: list[tuple[ContextAccess, tuple[str, ...]]] = []
    for access in accesses:
        if not access.is_granted:
            continue
        checks.append((access, ("READ",)))
    return tuple(checks)


@contextmanager
def locked_granted_sources(
    memories: tuple[FrozenTransferMemory, ...],
    frames: dict[str, StoreTransferFrame],
    *,
    authority_checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...],
) -> Iterator[None]:
    """Keep grant and external Source validation held until the Target commit returns."""
    external_frames: dict[tuple[str, str], StoreTransferFrame] = {}
    for item in memories:
        frame = frames[item.source_context_name]
        if not frame.access.is_granted:
            continue
        key = (str(frame.access.store.store_dir), frame.access.context_name)
        existing = external_frames.get(key)
        if existing is not None and (
            existing.context.uid != frame.context.uid
            or existing.expected_digest != frame.expected_digest
        ):
            raise MemoryTransferError(
                "Granted Copy has inconsistent aliases for one authority Source."
            )
        external_frames[key] = frame
    with authorized_context_operation(authority_checks):
        with ExitStack() as stack:
            # Hold every external Source record through the local Target
            # commit. Grant revalidation alone cannot close a concurrent
            # authority-content change after the reviewed Copy plan.
            grouped: dict[str, list[StoreTransferFrame]] = {}
            for (store_dir, _context_name), frame in external_frames.items():
                grouped.setdefault(store_dir, []).append(frame)
            for store_dir in sorted(grouped):
                group = sorted(
                    grouped[store_dir],
                    key=lambda value: value.access.context_name,
                )
                first, *remaining = group
                # One locked snapshot holds that authority Store's global
                # command lock. Validate the remaining Contexts while the
                # same lock prevents every cooperative Store write; taking
                # locked_context_snapshot twice on one Store would attempt
                # to reacquire its non-reentrant command lock.
                stack.enter_context(
                    first.access.store.locked_context_snapshot(
                        first.access.context_name,
                        expected_uid=first.context.uid,
                        expected_digest=first.expected_digest,
                    )
                )
                for frame in remaining:
                    current = frame.access.store.load_direct(frame.access.context_name)
                    if (
                        current.uid != frame.context.uid
                        or context_record_digest(current) != frame.expected_digest
                    ):
                        raise ConcurrentContextUpdateError(
                            f"Context {frame.access.context_name!r} changed "
                            "before it could be published."
                        )
            yield
