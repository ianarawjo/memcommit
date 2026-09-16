"""Captured Context frames, explicit access snapshots, and runtime ownership checks."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferError,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandCandidate,
    resolve_existing_context_operand,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.application.operations.profile.config import profile_store_dir
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore, context_record_digest


@dataclass(frozen=True, slots=True)
class StoreTransferFrame:
    context: Context
    expected_digest: str
    display_name: str
    access: ContextAccess


@dataclass(frozen=True, slots=True)
class StoreTransferToken:
    owner: object
    operation_uid: str
    plan_digest: str
    frames: tuple[StoreTransferFrame, ...]
    context_catalog: tuple[str, ...]


def capture_context_frames(store: MemoryStore) -> tuple[StoreTransferFrame, ...]:
    contexts = store.load_direct_context_graph_strict()
    return tuple(
        StoreTransferFrame(
            context=context,
            expected_digest=(context._store_digest or context_record_digest(context)),
            display_name=context.name,
            access=ContextAccess(
                store=store,
                context_name=context.name,
                access_name=context.name,
                permission="READ",
            ),
        )
        for context in contexts
    )


@contextmanager
def source_access_snapshot(
    store: MemoryStore,
    owner_locators: tuple[str, ...],
    *,
    current_name: str | None,
    inspect_grants: bool,
) -> Iterator[Iterator[ContextAccess]]:
    """Resolve explicit public owners while the registry snapshot stays held.

    Callers decide whether to load or reject an access. Grant identity validation
    retains the access resolver's record checks; UID discovery does not load
    authority Memories through GrantedReadStore merely to select a Source.
    """
    if not owner_locators or not inspect_grants:
        yield iter(())
        return
    with authority_grant_snapshot_lock() as registry:
        # Explicitly rooted stores must not inherit the host Profile's Grants.
        if store.store_dir.resolve() != profile_store_dir(registry.active).resolve():
            yield iter(())
            return
        candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None

        def resolve_access(locator: str) -> ContextAccess:
            nonlocal candidates
            try:
                return resolve_context_access(
                    store,
                    locator,
                    current_name=current_name,
                    required_permission="READ",
                    registry=registry,
                )
            except FileNotFoundError:
                pass
            if candidates is None:
                names = tuple(store.list_context_names())
                if names:
                    root = ContextAccess(
                        store=store,
                        context_name=names[0],
                        access_name=names[0],
                        permission="READ",
                    )
                    catalog = freeze_profile_readable_context_catalog(
                        store,
                        root,
                        registry=registry,
                        include_query_routes=False,
                    )
                    rows = []
                    for name in catalog.list_context_names():
                        access = catalog.access_for(name)
                        if access.view is None:
                            uid = access.store.load_direct(access.context_name).uid
                        else:
                            # The access resolver already validated this binding.
                            # Loading its Memory frame here would make Move read
                            # a granted Source before it can reject the operation.
                            uid = next(
                                binding.uid
                                for binding in access.view.grant.contexts
                                if binding.name == access.context_name
                            )
                        rows.append(
                            ContextOperandCandidate(uid=uid, name=name, value=access)
                        )
                    candidates = tuple(rows)
                else:
                    candidates = ()
            resolved = resolve_existing_context_operand(
                candidates,
                locator,
                current=current_name,
            )
            return resolve_context_access(
                store,
                resolved.name,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )

        # Resolve in operand order: an operation may reject the first Grant
        # before a later invalid locator, and Copy loads under this same lock.
        accesses = (resolve_access(locator) for locator in owner_locators)
        yield accesses


def validate_context_bindings(
    token: object,
    *,
    owner: object,
    plan_digest: str,
    expected_plan_digest: str,
    memories: tuple[FrozenTransferMemory, ...],
    into_name: str,
    into_uid: str,
    into_digest: str,
) -> StoreTransferToken:
    """Keep runtime identity and exact frozen data bound independently of effect policy."""
    if not isinstance(token, StoreTransferToken) or token.owner is not owner:
        raise MemoryTransferError("Copy/Move plan belongs to a different runtime.")
    if plan_digest != token.plan_digest or expected_plan_digest != plan_digest:
        raise MemoryTransferError("Copy/Move frozen plan was modified.")
    frames = {frame.display_name: frame for frame in token.frames}
    try:
        into = frames[into_name]
    except KeyError as error:
        raise MemoryTransferError("Copy/Move lost its Target binding.") from error
    if into.context.uid != into_uid or into.expected_digest != into_digest:
        raise MemoryTransferError("Copy/Move Target binding changed.")
    for item in memories:
        frame = frames.get(item.source_context_name)
        if (
            frame is None
            or frame.context.uid != item.source_context_uid
            or frame.expected_digest != item.source_context_digest
        ):
            raise MemoryTransferError("Copy/Move Source binding changed.")
        memory = frame.context.memories.get(item.source_memory_uid)
        if not isinstance(memory, Memory) or memory.content != item.content:
            raise MemoryTransferError("Copy/Move opaque Source changed.")
    return token
