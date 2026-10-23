"""Pure Context remapping and destination identity checks shared by Import inputs."""

from __future__ import annotations

import copy

from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.models.context import Context
from memcommit.core.context_name_validation import validate_context_name
from memcommit.persistence.store import MemoryStore


def _context_name_mapping(
    source_names: tuple[str, ...],
    *,
    source_root: str,
    target_root: str,
) -> dict[str, str]:
    validate_context_name(target_root)
    mapping: dict[str, str] = {}
    for source_name in source_names:
        suffix = source_name[len(source_root) :]
        target_name = validate_context_name(target_root + suffix)
        mapping[source_name] = target_name
    if len(set(mapping.values())) != len(mapping):
        raise ProfileError("Context import produced duplicate destination names.")
    return mapping


def remap_imported_context_names(
    source_contexts: tuple[Context, ...],
    mapping: dict[str, str],
) -> tuple[Context, ...]:
    """Copy local Context frames and remap their destination names."""

    imported: list[Context] = []
    for source in source_contexts:
        target = copy.deepcopy(source)
        target.name = mapping[source.name]
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
