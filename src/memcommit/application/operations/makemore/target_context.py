"""Freeze an exact Makemore destination as bounded ambient context."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreTargetContext,
    MakemoreTargetContextItem,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    FrozenMemorizationTarget,
)
from memcommit.persistence.store import ProfileStore, context_record_digest


@dataclass(frozen=True)
class FrozenMakemoreLocalContext:
    """One local Context whose exact contents contributed to the ambient frame."""

    context_name: str
    context_uid: str
    context_digest: str


@dataclass(frozen=True)
class FrozenMakemoreTargetContext:
    """Target ambient frame and the local pre-images used to build it."""

    target: FrozenMemorizationTarget
    semantic: MakemoreTargetContext
    local_contexts: tuple[FrozenMakemoreLocalContext, ...]
    excluded_root_memory_uids: tuple[str, ...] = ()


def freeze_makemore_target_context(
    store: ProfileStore,
    *,
    target: FrozenMemorizationTarget,
    excluded_root_memory_uids: tuple[str, ...] = (),
) -> FrozenMakemoreTargetContext:
    root = store.load_direct(target.context_name)
    digest = context_record_digest(root)
    if root.uid != target.context_uid:
        raise MakemoreError(
            f"Target Context {target.context_name!r} changed before Makemore began."
        )
    if len(set(excluded_root_memory_uids)) != len(excluded_root_memory_uids):
        raise MakemoreError("Makemore Source exclusions must be distinct.")
    items = tuple(
        MakemoreTargetContextItem(
            alias=f"t{index}",
            kind="MEMORY",
            context_name=root.name,
            memory_uid=memory.uid,
            content=memory.content,
        )
        for index, memory in enumerate(
            (
                item
                for item in root.iter_memories()
                if item.uid not in excluded_root_memory_uids
            ),
            1,
        )
    )
    return FrozenMakemoreTargetContext(
        target=target,
        semantic=MakemoreTargetContext(context_name=root.name, items=items),
        local_contexts=(FrozenMakemoreLocalContext(root.name, root.uid, digest),),
        excluded_root_memory_uids=excluded_root_memory_uids,
    )


def _assert_local_contexts_unchanged(
    store: ProfileStore,
    frozen: FrozenMakemoreTargetContext,
) -> None:
    for binding in frozen.local_contexts:
        current = store.load_direct(binding.context_name)
        if (
            current.uid != binding.context_uid
            or context_record_digest(current) != binding.context_digest
        ):
            raise MakemoreError(
                f"Target ambient Context {binding.context_name!r} changed while "
                "Makemore was running; no generated Memories were added."
            )


@contextmanager
def revalidated_makemore_target(
    store: ProfileStore,
    frozen: FrozenMakemoreTargetContext,
    *,
    revalidate_after: bool = True,
) -> Iterator[None]:
    """Reject changes to the exact ambient frame before and after semantic work."""
    _assert_local_contexts_unchanged(store, frozen)
    yield
    if revalidate_after:
        _assert_local_contexts_unchanged(store, frozen)
