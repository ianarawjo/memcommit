"""Fresh Context and Memory identities for frozen Branch Sources."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name


def _branch_memory_uid_map(
    ctx: Context,
    supplied: Mapping[str, str] | None,
) -> dict[str, str]:
    """Freeze fresh occurrence identities for every current direct Memory."""

    source_uids = {item.uid for item in ctx.iter_memories() if isinstance(item, Memory)}
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
    return result


def _copy_context_for_branch(
    ctx: Context,
    new_name: str,
    *,
    memory_uid_map: Mapping[str, str] | None,
) -> Context:
    new_ctx = Context(
        uid=str(uuid.uuid4()),
        name=validate_context_name(new_name),
    )

    uid_map = _branch_memory_uid_map(
        ctx,
        memory_uid_map,
    )
    for info in ctx.iter_memories():
        if isinstance(info, Memory):
            new_ctx.add(Memory(uid=uid_map[info.uid], content=info.content))
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
    records how those occurrences descend from the Source.
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
    their lineage explicitly. Each lexical Context remains an independent
    owner of its copied Memories.
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
        validate_context_name(target_name)
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

    for source in sources:
        target = targets[source.name]
        for item in source.iter_memories():
            if isinstance(item, Memory):
                target.add(
                    Memory(
                        uid=uid_maps[source.uid][item.uid],
                        content=item.content,
                    )
                )

    return tuple(targets[source.name] for source in sources)
