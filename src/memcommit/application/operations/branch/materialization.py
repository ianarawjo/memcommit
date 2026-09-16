"""Fresh Branch identities and internal pointer remapping for frozen Sources."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.naming import validate_portable_context_name


def _branch_memory_uid_map(
    ctx: Context,
    supplied: Mapping[str, str] | None,
) -> dict[str, str]:
    """Freeze fresh occurrence identities for every current direct Memory."""

    source_uids = {item.uid for item in ctx.iter_items() if isinstance(item, Memory)}
    result = (
        {uid: str(uuid.uuid4()) for uid in source_uids}
        if supplied is None
        else dict(supplied)
    )
    if set(result) != source_uids:
        raise ValueError(
            "Branch Memory identity map must cover exactly the current Memories."
        )
    if any(
        not isinstance(source_uid, str)
        or not source_uid
        or not isinstance(target_uid, str)
        or not target_uid
        or source_uid == target_uid
        for source_uid, target_uid in result.items()
    ):
        raise ValueError("Branch Memory identity map is invalid.")
    target_uids = tuple(result.values())
    if len(target_uids) != len(set(target_uids)):
        raise ValueError("Branch Memory identity map contains duplicate targets.")
    direct_non_memory_uids = {
        item.uid for item in ctx.iter_items() if not isinstance(item, Memory)
    }
    if set(target_uids) & direct_non_memory_uids:
        raise ValueError("Branch Memory identity collides with a direct item.")
    return result


def _copy_context_for_branch(
    ctx: Context,
    new_name: str,
    *,
    memory_uid_map: Mapping[str, str] | None,
) -> Context:
    new_ctx = Context(
        uid=str(uuid.uuid4()),
        name=validate_portable_context_name(new_name),
    )
    from memcommit.application.capabilities.context_snapshot import (
        ContextSnapshotRef,
    )

    uid_map = _branch_memory_uid_map(
        ctx,
        memory_uid_map,
    )
    for info in ctx.iter_items():
        if isinstance(info, Memory):
            new_ctx.add(Memory(uid=uid_map[info.uid], content=info.content))
        elif isinstance(info, (MemoryRef, QueryContextRef)):
            new_ctx.add(info.copy())
        elif isinstance(info, ContextSnapshotRef):
            new_ctx.add(info.copy())
        else:
            new_ctx.add(info)
    return new_ctx


def branch(
    ctx: Context,
    new_name: str,
    *,
    memory_uid_map: Mapping[str, str] | None = None,
) -> Context:
    """
    Create a new Context that is a copy of ctx under new_name.

    Direct Memory items are copied as independent objects with fresh occurrence
    UIDs. The durable Branch checkpoint, rather than a shared writable address,
    records how those occurrences descend from the Source. Embedded Context
    references are carried over as-is (live-reference semantics are preserved;
    the sub-contexts themselves are not cloned).
    """

    return _copy_context_for_branch(
        ctx,
        new_name,
        memory_uid_map=memory_uid_map,
    )


def branch_subtree(
    contexts: Sequence[Context],
    source_root: str,
    new_root: str,
    *,
    memory_uid_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[Context, ...]:
    """Copy one frozen lexical Context subtree under a fresh root.

    Context and direct-Memory occurrence identities are regenerated because
    every branch is independently editable. The publishing checkpoint retains
    their lineage explicitly. Persisted pointers whose targets are inside the
    frozen subtree follow the new Context and Memory identities; outside
    pointers retain the ordinary shallow Branch live-reference behavior.
    """
    sources = tuple(contexts)
    if not sources:
        raise ValueError("A subtree branch requires at least one Context.")
    if not source_root or not new_root or source_root == new_root:
        raise ValueError("A subtree branch requires distinct named roots.")

    source_by_name = {context.name: context for context in sources}
    if len(source_by_name) != len(sources) or source_root not in source_by_name:
        raise ValueError("A subtree branch requires one distinct Source root.")
    if len({context.uid for context in sources}) != len(sources):
        raise ValueError("A subtree branch requires distinct Context identities.")

    prefix = source_root + "/"
    if any(
        context.name != source_root and not context.name.startswith(prefix)
        for context in sources
    ):
        raise ValueError("A subtree branch received a Context outside its Source root.")

    target_names = {
        source.name: new_root + source.name[len(source_root) :] for source in sources
    }
    for target_name in target_names.values():
        validate_portable_context_name(target_name)
    if len(set(target_names.values())) != len(sources):
        raise ValueError("A subtree branch produced duplicate target names.")

    targets = {
        source.name: Context(uid=str(uuid.uuid4()), name=target_names[source.name])
        for source in sources
    }
    supplied_maps = dict(memory_uid_maps or {})
    if set(supplied_maps) - {source.uid for source in sources}:
        raise ValueError("Subtree Branch Memory map names an unknown Context.")
    uid_maps = {
        source.uid: _branch_memory_uid_map(
            source,
            supplied_maps.get(source.uid),
        )
        for source in sources
    }
    from memcommit.application.capabilities.context_snapshot import (
        ContextSnapshotRef,
    )

    # Populate every target Memory first so an internal live reference can
    # bind to the independently owned target occurrence regardless of Context
    # traversal order.
    for source in sources:
        target = targets[source.name]
        for item in source.iter_items():
            if isinstance(item, Memory):
                target.add(
                    Memory(
                        uid=uid_maps[source.uid][item.uid],
                        content=item.content,
                    )
                )

    for source in sources:
        target = targets[source.name]
        for item in source.iter_items():
            if isinstance(item, Memory):
                continue
            elif isinstance(item, MemoryRef):
                if item.is_snapshot:
                    # A snapshot records the original Source identity. Branch
                    # copies the retained evidence but must not retarget its
                    # provenance to the new branch.
                    target.add(item.copy())
                    continue
                internal_owner = source_by_name.get(item.target_context_name)
                if internal_owner is None:
                    target.add(item.copy())
                    continue
                if internal_owner.uid != item.target_context_uid:
                    raise ValueError(
                        "A subtree Branch found a stale internal Memory reference."
                    )
                internal_memory = internal_owner.memories.get(item.target_memory_uid)
                if not isinstance(internal_memory, Memory):
                    raise ValueError(
                        "A subtree Branch found an unavailable internal Memory target."
                    )
                target_owner = targets[internal_owner.name]
                target_memory_uid = uid_maps[internal_owner.uid][item.target_memory_uid]
                target_memory = target_owner.memories.get(target_memory_uid)
                if not isinstance(target_memory, Memory):
                    raise ValueError(
                        "A subtree Branch lost an internal Memory occurrence."
                    )
                target.add(
                    MemoryRef(
                        uid=item.uid,
                        target_context_uid=target_owner.uid,
                        target_context_name=target_owner.name,
                        target_memory_uid=target_memory_uid,
                        target=target_memory,
                    )
                )
            elif isinstance(item, QueryContextRef):
                target.add(item.copy())
            elif isinstance(item, ContextSnapshotRef):
                # A Context Reference is already an immutable value. Branch
                # preserves its historical Source identity and scope.
                target.add(item.copy())
            else:
                internal_context = source_by_name.get(item.name)
                if internal_context is None:
                    # Context serialization stores only uid/name. Use a fresh
                    # stub so the branch cannot share a mutable object merely
                    # because an external live reference was retained.
                    target.add(Context(uid=item.uid, name=item.name))
                    continue
                if internal_context.uid != item.uid:
                    raise ValueError(
                        "A subtree Branch found a stale internal Context reference."
                    )
                target.add(targets[internal_context.name])
        target.order = [
            (
                uid_maps[source.uid][item.uid]
                if isinstance(item, Memory)
                else (
                    targets[item.name].uid
                    if isinstance(item, Context) and item.name in targets
                    else item.uid
                )
            )
            for item in source.iter_items()
        ]
        ordinary_names = {
            item.name for item in target.iter_items() if isinstance(item, Context)
        }
        query_names = {
            item.name
            for item in target.iter_items()
            if isinstance(item, QueryContextRef)
        }
        collisions = ordinary_names & query_names
        if collisions:
            raise ValueError(
                "A subtree Branch would give ordinary and query-only Context "
                "pointers the same name: "
                + ", ".join(repr(name) for name in sorted(collisions))
            )
    return tuple(targets[source.name] for source in sources)
