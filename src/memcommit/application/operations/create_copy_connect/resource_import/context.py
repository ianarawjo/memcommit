"""Closed Context-tree imports for ``mem import context``."""

from __future__ import annotations

import copy

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.profiles.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    profile_store_dir,
)
from memcommit.application.operations.profiles.profile.model._storage import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.core.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore

from ._shared import (
    require_active_profile_snapshot,
    require_cross_profile_source,
    source_profile,
)
from .contracts import ContextImportPlan, ContextImportResult


def _source_context_names(
    store: MemoryStore,
    source_name: str,
    *,
    recursive: bool,
) -> tuple[str, ...]:
    names = tuple(store.list_context_names())
    if source_name not in names:
        raise FileNotFoundError(f"Context {source_name!r} not found in source Profile.")
    if not recursive:
        return (source_name,)
    return tuple(
        name
        for name in names
        if name == source_name or name.startswith(source_name + "/")
    )


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


def _prepare_context_import(
    registry: ProfileRegistry,
    destination: MemoryStore,
    source_profile_entry: ProfileEntry,
    source_name: str,
    snapshots: tuple[Context, ...],
    *,
    target_root: str,
    recursive: bool,
) -> tuple[ContextImportPlan, tuple[Context, ...]]:
    source_names = tuple(context.name for context in snapshots)
    mapping = _context_name_mapping(
        source_names,
        source_root=source_name,
        target_root=target_root,
    )
    imported = _closed_import_contexts(snapshots, mapping)
    _reject_context_identity_collisions(destination, imported)
    return (
        ContextImportPlan(
            source_profile=source_profile_entry.name,
            source_profile_uid=source_profile_entry.uid,
            target_profile=registry.active.name,
            target_profile_uid=registry.active.uid,
            source_context=source_name,
            target_contexts=tuple(context.name for context in imported),
            source_context_versions=tuple(
                (context.name, context.uid, str(context._store_digest or ""))
                for context in snapshots
            ),
            context_count=len(imported),
            memory_count=sum(
                1
                for context in imported
                for item in context.iter_items()
                if isinstance(item, Memory)
            ),
            recursive=recursive,
        ),
        imported,
    )


def plan_context_import(
    source_profile_name: str,
    source_context_locator: str,
    *,
    target_name: str | None = None,
    recursive: bool = False,
) -> ContextImportPlan:
    """Validate and freeze one read-only Context import preview."""

    destination = MemoryStore()
    with authority_grant_snapshot_lock() as registry:
        require_active_profile_snapshot(registry, destination)
        source = source_profile(registry, source_profile_name)
        require_cross_profile_source(registry, source)
        source_store = MemoryStore(
            root=profile_store_dir(source),
            create=False,
        )
        source_name = resolve_context_locator(
            source_context_locator,
            current=source_store.current_context_name(),
        )
        target_root = target_name or source_name
        with source_store._context_graph_lock(exclusive=True):
            source_names = _source_context_names(
                source_store,
                source_name,
                recursive=recursive,
            )
            with source_store._context_write_locks(source_names):
                snapshots = tuple(
                    source_store.load_direct(name) for name in source_names
                )
                plan, _imported = _prepare_context_import(
                    registry,
                    destination,
                    source,
                    source_name,
                    snapshots,
                    target_root=target_root,
                    recursive=recursive,
                )
                return plan


def import_context_from_profile(
    source_profile_name: str,
    source_context_locator: str,
    *,
    target_name: str | None = None,
    recursive: bool = False,
    expected_plan: ContextImportPlan | None = None,
) -> ContextImportResult:
    """Import one closed Context set into the active Profile with stable UIDs."""

    destination = MemoryStore()
    with authority_grant_snapshot_lock() as registry:
        require_active_profile_snapshot(registry, destination)
        source = source_profile(registry, source_profile_name)
        require_cross_profile_source(registry, source)
        source_store = MemoryStore(
            root=profile_store_dir(source),
            create=False,
        )
        source_name = resolve_context_locator(
            source_context_locator,
            current=source_store.current_context_name(),
        )
        target_root = target_name or source_name

        # The exclusive source graph lock freezes recursive membership and
        # every record identity until the destination transaction commits.
        with source_store._context_graph_lock(exclusive=True):
            source_names = _source_context_names(
                source_store,
                source_name,
                recursive=recursive,
            )
            with source_store._context_write_locks(source_names):
                snapshots = tuple(
                    source_store.load_direct(name) for name in source_names
                )
                actual_plan, imported = _prepare_context_import(
                    registry,
                    destination,
                    source,
                    source_name,
                    snapshots,
                    target_root=target_root,
                    recursive=recursive,
                )
                if expected_plan is not None and actual_plan != expected_plan:
                    raise ProfileError(
                        "Context import inputs changed after review; reopen mem import."
                    )
                entries = tuple(
                    (
                        context,
                        AutoCheckpoint(
                            command="import",
                            args={
                                "resource_kind": "context",
                                "source_profile_uid": source.uid,
                                "source_profile_name": source.name,
                                "source_context": source_context.name,
                                "source_context_uid": source_context.uid,
                                "source_context_digest": source_context._store_digest,
                                "target_context": context.name,
                                "recursive": recursive,
                            },
                            description=(
                                f"Imported Context '{source_context.name}' from "
                                f"Profile '{source.name}' as '{context.name}'."
                            ),
                        ),
                    )
                    for source_context, context in zip(
                        snapshots,
                        imported,
                        strict=True,
                    )
                )
                created = destination.create_missing_contexts(
                    entries,
                    require_all_new=True,
                )

    return ContextImportResult(
        source_profile=source.name,
        source_context=source_name,
        target_contexts=tuple(context.name for context in created),
        context_count=len(created),
        memory_count=sum(
            1
            for context in created
            for item in context.iter_items()
            if isinstance(item, Memory)
        ),
        recursive=recursive,
    )
