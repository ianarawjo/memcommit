"""In-memory live and snapshot link placement shared by operation runtimes.

Callers freeze authority and own persistence; these helpers only validate and
construct the relationship in an already supplied Target Context.
"""

from __future__ import annotations

import hashlib
import uuid

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef


def _direct_source_memory(
    memory: Memory,
    source: Context,
) -> Memory:
    """Return the exact directly owned Source object behind one request."""

    source_item = source.memories.get(memory.uid)
    if not isinstance(source_item, Memory):
        raise ValueError(
            f"Memory [{memory.uid[:8]}] is not directly owned by '{source.name}'."
        )
    return source_item


def embed_memory(
    memory: Memory,
    source: Context,
    target: Context,
    *,
    position: int | None = None,
) -> MemoryRef:
    """Add a read-only live Memory link whose content resolves from Source."""

    if source.uid == target.uid:
        raise ValueError("Cannot embed a Memory into its owning Context.")
    memory = _direct_source_memory(memory, source)
    if position is not None and not 0 <= position <= len(target.ordered_uids()):
        raise ValueError(
            f"Memory Embed position must be between 0 and {len(target.ordered_uids())}."
        )

    for info in target.iter_items():
        if (
            isinstance(info, MemoryRef)
            and info.is_live
            and info.target_context_uid == source.uid
            and info.target_memory_uid == memory.uid
        ):
            raise ValueError(
                f"Memory [{memory.uid[:8]}] from '{source.name}' is already "
                f"embedded in '{target.name}'."
            )

    ref = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=memory.uid,
        target=memory,
    )
    target.add(ref, position=position)
    return ref


def reference_memory(
    memory: Memory,
    source: Context,
    target: Context,
) -> MemoryRef:
    """Add an immutable read-only snapshot of one directly owned Memory."""

    memory = _direct_source_memory(memory, source)
    digest = hashlib.sha256(memory.content.encode("utf-8")).hexdigest()
    for info in target.iter_items():
        if (
            isinstance(info, MemoryRef)
            and info.is_snapshot
            and info.target_context_uid == source.uid
            and info.target_memory_uid == memory.uid
            and info.snapshot_content_sha256 == digest
        ):
            raise ValueError(
                f"Memory [{memory.uid[:8]}] from '{source.name}' already has "
                f"this exact snapshot in '{target.name}'."
            )
    ref = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=memory.uid,
        target=memory,
        snapshot_content_sha256=digest,
    )
    target.add(ref)
    return ref


def reference_context(
    snapshot,
    target: Context,
):
    """Add one immutable Context snapshot as a read-only direct item.

    The snapshot is constructed by the operation runtime because its package
    binds a complete reviewed read scope. This domain boundary owns duplicate
    and self-reference checks without importing Store or CLI concerns.
    """

    from memcommit.application.capabilities.context_snapshot import (
        ContextSnapshotRef,
    )

    if not isinstance(snapshot, ContextSnapshotRef):
        raise TypeError("Context Reference requires a ContextSnapshotRef.")
    if snapshot.target_context_uid == target.uid:
        raise ValueError("Cannot reference a Context into itself.")
    for item in target.iter_items():
        if (
            isinstance(item, ContextSnapshotRef)
            and item.target_context_uid == snapshot.target_context_uid
            and item.snapshot_content_sha256 == snapshot.snapshot_content_sha256
        ):
            raise ValueError(
                f"Context '{snapshot.target_context_name}' already has this "
                f"exact snapshot in '{target.name}'."
            )
    target.add(snapshot)
    return snapshot


def reference_query_context(
    name: str,
    target_source_uid: str,
    target: Context,
    provider: str = "codex_chatgpt",
) -> QueryContextRef:
    """Attach an opaque query-only source to a Context."""
    for info in target.iter_items():
        if (
            isinstance(info, QueryContextRef)
            and info.target_source_uid == target_source_uid
        ):
            raise ValueError(
                f"Query source '{name}' is already referenced in '{target.name}'."
            )
        if isinstance(info, (Context, QueryContextRef)) and info.name == name:
            raise ValueError(
                f"A context-like item named '{name}' already exists in '{target.name}'."
            )

    ref = QueryContextRef(
        uid=str(uuid.uuid4()),
        name=name,
        target_source_uid=target_source_uid,
        provider=provider,
    )
    target.add(ref)
    return ref


def validate_embed(
    child: Context,
    parent: Context,
    *,
    position: int | None = None,
) -> None:
    """Validate one live Context insertion without mutating either Context."""

    if position is not None and (
        isinstance(position, bool)
        or not isinstance(position, int)
        or not 0 <= position <= len(parent.ordered_uids())
    ):
        raise ValueError(
            f"Embed position must be between 0 and {len(parent.ordered_uids())}."
        )
    if child.uid == parent.uid:
        raise ValueError("Cannot embed a context into itself.")
    for info in parent.iter_items():
        # Context.add() deliberately replaces an existing direct item with the
        # same UID.  Embed must reject that generic update behavior because two
        # public Grant aliases can identify one authority Context: accepting the
        # second alias would silently replace the first durable relationship.
        if info.uid == child.uid:
            if isinstance(info, Context):
                raise ValueError(
                    f"'{child.name}' has the same Context identity as already "
                    f"embedded '{info.name}' in '{parent.name}'."
                )
            raise ValueError(
                f"Cannot embed '{child.name}' in '{parent.name}': its Context "
                f"identity [{child.uid[:8]}] is already used by a direct item."
            )
        if isinstance(info, (Context, QueryContextRef)) and info.name == child.name:
            raise ValueError(f"'{child.name}' is already embedded in '{parent.name}'.")


def embed(
    child: Context,
    parent: Context,
    *,
    position: int | None = None,
) -> None:
    """
    Embed child inside parent (as a live reference).
    New embeds append unless an exact direct-item insertion position is supplied.
    Raises ValueError if already embedded, self-referential, or out of range.
    """
    validate_embed(child, parent, position=position)
    # Context.add historically clamps positions for generic callers. Embed's
    # reviewed gap is an exact safety boundary, so validate it before mutation.
    parent.add(child, position=position)
