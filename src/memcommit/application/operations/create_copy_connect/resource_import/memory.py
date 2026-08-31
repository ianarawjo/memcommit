"""Direct Memory imports for ``mem import memory``."""

from __future__ import annotations

import hashlib

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
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.persistence.store import MemoryStore

from ._shared import (
    require_active_profile_snapshot,
    require_cross_profile_source,
    source_profile,
)
from .contracts import MemoryImportPlan, MemoryImportResult


def _direct_memory(context: Context, selector: str) -> Memory:
    if not isinstance(selector, str) or not selector:
        raise ValueError("Memory selector must be non-empty.")
    matches = [
        item
        for item in context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    ]
    if not matches:
        raise KeyError(f"No directly owned Memory with uid starting with {selector!r}.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous Memory prefix {selector!r} matches "
            + ", ".join(memory.uid[:8] for memory in matches)
            + "."
        )
    return matches[0]


def _memory_content_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def _memory_import_plan(
    registry: ProfileRegistry,
    source_profile_entry: ProfileEntry,
    source_context: Context,
    source_memory: Memory,
    target: Context,
) -> MemoryImportPlan:
    return MemoryImportPlan(
        source_profile=source_profile_entry.name,
        source_profile_uid=source_profile_entry.uid,
        target_profile=registry.active.name,
        target_profile_uid=registry.active.uid,
        source_context=source_context.name,
        source_context_uid=source_context.uid,
        source_context_digest=str(source_context._store_digest or ""),
        source_memory_uid=source_memory.uid,
        source_memory_content_sha256=_memory_content_digest(source_memory),
        target_context=target.name,
        target_context_uid=target.uid,
        target_context_digest=str(target._store_digest or ""),
    )


def _memory_target_name(
    destination: MemoryStore,
    target_context_locator: str | None,
) -> str:
    destination_current = destination.current_context_name()
    if target_context_locator is None:
        if not destination_current:
            raise RuntimeError("No current Context; pass --into TARGET.")
        return destination_current
    return resolve_context_locator(
        target_context_locator,
        current=destination_current,
    )


def plan_memory_import(
    source_profile_name: str,
    source_context_locator: str,
    memory_selector: str,
    *,
    target_context_locator: str | None = None,
) -> MemoryImportPlan:
    """Validate and freeze one read-only direct Memory import preview."""

    destination = MemoryStore()
    target_name = _memory_target_name(destination, target_context_locator)
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
        with source_store._context_graph_lock(exclusive=False):
            with source_store._context_write_lock(source_name):
                source_context = source_store.load_direct(source_name)
                source_memory = _direct_memory(source_context, memory_selector)
                target = destination.load_for_update(target_name)
                if source_memory.uid in target.memories:
                    raise ProfileError(
                        f"Memory identity [{source_memory.uid[:8]}] already exists "
                        f"in Context {target.name!r}."
                    )
                return _memory_import_plan(
                    registry,
                    source,
                    source_context,
                    source_memory,
                    target,
                )


def import_memory_from_profile(
    source_profile_name: str,
    source_context_locator: str,
    memory_selector: str,
    *,
    target_context_locator: str | None = None,
    expected_plan: MemoryImportPlan | None = None,
) -> MemoryImportResult:
    """Import one directly owned Memory into an existing active Context."""

    destination = MemoryStore()
    target_name = _memory_target_name(destination, target_context_locator)

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
        with source_store._context_graph_lock(exclusive=False):
            with source_store._context_write_lock(source_name):
                source_context = source_store.load_direct(source_name)
                source_memory = _direct_memory(source_context, memory_selector)
                target = destination.load_for_update(target_name)
                if source_memory.uid in target.memories:
                    raise ProfileError(
                        f"Memory identity [{source_memory.uid[:8]}] already exists "
                        f"in Context {target.name!r}."
                    )
                actual_plan = _memory_import_plan(
                    registry,
                    source,
                    source_context,
                    source_memory,
                    target,
                )
                if expected_plan is not None and actual_plan != expected_plan:
                    raise ProfileError(
                        "Memory import inputs changed after review; reopen mem import."
                    )
                imported = Memory(
                    uid=source_memory.uid,
                    content=source_memory.content,
                )
                target.add(imported)
                destination.save(
                    target,
                    AutoCheckpoint(
                        command="import",
                        args={
                            "resource_kind": "memory",
                            "source_profile_uid": source.uid,
                            "source_profile_name": source.name,
                            "source_context": source_context.name,
                            "source_context_uid": source_context.uid,
                            "source_context_digest": source_context._store_digest,
                            "source_memory_uid": source_memory.uid,
                            "target_context": target.name,
                        },
                        description=(
                            f"Imported Memory [{source_memory.uid[:8]}] from "
                            f"Profile '{source.name}' Context "
                            f"'{source_context.name}'."
                        ),
                    ),
                )

    return MemoryImportResult(
        source_profile=source.name,
        source_context=source_name,
        target_context=target_name,
        memory=imported,
    )
