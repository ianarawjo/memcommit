"""Pure relative-path planning helpers for recursive structural Merge."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef


def relative_context_suffix(name: str, root: str) -> str:
    """Return one complete lexical suffix, rejecting names outside the root."""

    if name == root:
        return ""
    prefix = root + "/"
    if not name.startswith(prefix):
        raise ValueError(f"Context '{name}' is outside recursive root '{root}'.")
    return name[len(root) :]


def align_context_names(
    source_names: Sequence[str],
    *,
    source_root: str,
    target_root: str,
) -> tuple[tuple[str, str], ...]:
    """Map every frozen Source path to the same relative Target path."""

    names = tuple(source_names)
    if not names or names[0] != source_root or len(set(names)) != len(names):
        raise ValueError("Recursive Merge requires one ordered distinct Source tree.")
    return tuple(
        (
            name,
            target_root + relative_context_suffix(name, source_root),
        )
        for name in names
    )


def fresh_target_contexts(
    sources: Sequence[Context],
    *,
    target_names: Mapping[str, str],
    existing_targets: Mapping[str, Context],
) -> dict[str, Context]:
    """Assign existing or fresh Target identity to every Source Context UID."""

    result: dict[str, Context] = {}
    for source in sources:
        target_name = target_names[source.name]
        existing = existing_targets.get(target_name)
        result[source.uid] = existing or Context(
            uid=str(uuid.uuid4()),
            name=target_name,
        )
    if len(result) != len(sources):
        raise ValueError("Recursive Merge Source Context identities must be distinct.")
    return result


def project_context_for_tree_merge(
    source: Context,
    *,
    source_by_uid: Mapping[str, Context],
    target_by_source_uid: Mapping[str, Context],
    memory_only: bool,
) -> Context:
    """Copy direct Source items while retargeting internal subtree pointers."""

    projected = Context(uid=source.uid, name=source.name)
    for item in source.iter_items():
        if isinstance(item, Memory):
            projected.add(Memory(uid=item.uid, content=item.content))
            continue
        if memory_only:
            continue
        if isinstance(item, MemoryRef):
            if item.is_snapshot:
                projected.add(item.copy())
                continue
            internal_owner = source_by_uid.get(item.target_context_uid)
            if internal_owner is None:
                projected.add(item.copy())
                continue
            if internal_owner.name != item.target_context_name:
                raise ValueError(
                    "Recursive Merge found a stale internal Memory reference."
                )
            internal_memory = internal_owner.memories.get(item.target_memory_uid)
            if not isinstance(internal_memory, Memory):
                raise ValueError(
                    "Recursive Merge found an unavailable internal Memory target."
                )
            target_owner = target_by_source_uid[internal_owner.uid]
            projected.add(
                MemoryRef(
                    uid=item.uid,
                    target_context_uid=target_owner.uid,
                    target_context_name=target_owner.name,
                    target_memory_uid=item.target_memory_uid,
                    target=internal_memory,
                )
            )
            continue
        if isinstance(item, QueryContextRef):
            projected.add(item.copy())
            continue
        internal_context = source_by_uid.get(item.uid)
        if internal_context is None:
            projected.add(Context(uid=item.uid, name=item.name))
            continue
        if internal_context.name != item.name:
            raise ValueError(
                "Recursive Merge found a stale internal Context reference."
            )
        projected.add(target_by_source_uid[internal_context.uid])
    return projected
