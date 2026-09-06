"""Pure Context remapping and destination identity checks shared by Import inputs."""

from __future__ import annotations

import copy

from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore


def _context_name_mapping(
    source_names: tuple[str, ...],
    *,
    source_root: str,
    target_root: str,
) -> dict[str, str]:
    validate_portable_context_name(target_root)
    mapping: dict[str, str] = {}
    for source_name in source_names:
        suffix = source_name[len(source_root) :]
        target_name = validate_portable_context_name(target_root + suffix)
        mapping[source_name] = target_name
    if len(set(mapping.values())) != len(mapping):
        raise ProfileError("Context import produced duplicate destination names.")
    return mapping


def _closed_import_contexts(
    source_contexts: tuple[Context, ...],
    mapping: dict[str, str],
) -> tuple[Context, ...]:
    """Rewrite internal locators and reject pointers outside the import set.

    A copied pointer must not continue resolving against a different Profile.
    Requiring a closed set keeps import by value distinct from a live grant or
    reference and avoids silently transferring query-only authority.
    """

    from memcommit.application.capabilities.context_snapshot import (
        ContextSnapshotRef,
    )

    source_by_name = {context.name: context for context in source_contexts}
    imported: list[Context] = []
    for source in source_contexts:
        target = copy.deepcopy(source)
        target.name = mapping[source.name]
        for item in target.iter_items():
            if isinstance(item, QueryContextRef):
                raise ProfileError(
                    f"Context {source.name!r} contains query-only view "
                    f"{item.name!r}; import its Profile or use an authority grant."
                )
            if isinstance(item, ContextSnapshotRef):
                # Snapshot content and provenance are self-contained. Keep the
                # historical source name rather than creating a live locator.
                continue
            if isinstance(item, Context):
                referenced = source_by_name.get(item.name)
                if referenced is None or item.name not in mapping:
                    raise ProfileError(
                        f"Context {source.name!r} references Context {item.name!r} "
                        "outside the import set; include it with --recursive."
                    )
                if referenced.uid != item.uid:
                    raise ProfileError("Imported Context reference identity is stale.")
                item.name = mapping[item.name]
            elif isinstance(item, MemoryRef):
                if item.is_snapshot:
                    continue
                referenced = source_by_name.get(item.target_context_name)
                if referenced is None or item.target_context_name not in mapping:
                    raise ProfileError(
                        f"Context {source.name!r} references Memory in Context "
                        f"{item.target_context_name!r} outside the import set."
                    )
                if referenced.uid != item.target_context_uid:
                    raise ProfileError("Imported Memory reference identity is stale.")
                referenced_memory = referenced.memories.get(item.target_memory_uid)
                if not isinstance(referenced_memory, Memory):
                    raise ProfileError(
                        "Imported Memory reference target is unavailable."
                    )
                item.target_context_name = mapping[item.target_context_name]
        imported.append(target)
    return tuple(imported)


def _reject_context_identity_collisions(
    destination: MemoryStore,
    imported: tuple[Context, ...],
) -> None:
    imported_uids = {context.uid for context in imported}
    for name in destination.list_context_names():
        existing = destination.load_direct(name)
        if existing.uid in imported_uids:
            raise ProfileError(
                f"Context identity [{existing.uid[:8]}] already exists as "
                f"{existing.name!r} in the active Profile."
            )
