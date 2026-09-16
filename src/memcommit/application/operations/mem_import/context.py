"""Closed Context-tree imports for ``mem import context``."""

from __future__ import annotations

from memcommit.application.capabilities.operand_resolution import (
    resolve_existing_local_context_operand,
)
from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    profile_store_dir,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    authority_grant_snapshot_lock,
)
from memcommit.core.context import (
    AutoCheckpoint,
    Context,
    Memory,
)
from memcommit.persistence.store import MemoryStore

from ._shared import (
    require_active_profile_snapshot,
    require_cross_profile_source,
    source_profile,
)
from .contracts import ContextImportPlan, ContextImportResult
from .context_data import (
    _closed_import_contexts,
    _context_name_mapping,
    _reject_context_identity_collisions,
)


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
        source_current = source_store.current_context_name()
        resolved_source = resolve_existing_local_context_operand(
            source_store,
            source_context_locator,
            current=source_current,
        )
        source_name = resolved_source.name
        target_root = target_name or source_name
        with source_store._context_graph_lock(exclusive=True):
            if source_store.load_direct(source_name).uid != resolved_source.uid:
                raise ProfileError(
                    "Context import Source changed identity during resolution."
                )
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
        source_current = source_store.current_context_name()
        resolved_source = resolve_existing_local_context_operand(
            source_store,
            source_context_locator,
            current=source_current,
        )
        source_name = resolved_source.name
        target_root = target_name or source_name

        # The exclusive source graph lock freezes recursive membership and
        # every record identity until the destination transaction commits.
        with source_store._context_graph_lock(exclusive=True):
            if source_store.load_direct(source_name).uid != resolved_source.uid:
                raise ProfileError(
                    "Context import Source changed identity during resolution."
                )
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
