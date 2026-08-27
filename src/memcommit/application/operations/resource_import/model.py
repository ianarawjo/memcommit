"""Identity-preserving imports across registered Profile boundaries."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass

from memcommit.context import (
    AutoCheckpoint,
    Context,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.application.operations.profile.config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    StoreInspection,
    authority_grant_snapshot_lock,
    import_baseline_profile,
    inspect_store,
)
from memcommit.persistence.store import MemoryStore
from memcommit.context_targeting.naming import validate_portable_context_name


@dataclass(frozen=True)
class ContextImportResult:
    """Receipt for one Context or lexical Context-tree import."""

    source_profile: str
    source_context: str
    target_contexts: tuple[str, ...]
    context_count: int
    memory_count: int
    recursive: bool


@dataclass(frozen=True)
class MemoryImportResult:
    """Receipt for one directly owned Memory import."""

    source_profile: str
    source_context: str
    target_context: str
    memory: Memory


@dataclass(frozen=True)
class ContextImportPlan:
    """Frozen identities and counts shown before one Context import."""

    source_profile: str
    source_profile_uid: str
    target_profile: str
    target_profile_uid: str
    source_context: str
    target_contexts: tuple[str, ...]
    source_context_versions: tuple[tuple[str, str, str], ...]
    context_count: int
    memory_count: int
    recursive: bool


@dataclass(frozen=True)
class MemoryImportPlan:
    """Frozen identities shown before one direct Memory import."""

    source_profile: str
    source_profile_uid: str
    target_profile: str
    target_profile_uid: str
    source_context: str
    source_context_uid: str
    source_context_digest: str
    source_memory_uid: str
    source_memory_content_sha256: str
    target_context: str
    target_context_uid: str
    target_context_digest: str


def _source_profile(
    registry: ProfileRegistry,
    name: str,
) -> ProfileEntry:
    canonical = validate_profile_name(name)
    profile = registry.by_name(canonical)
    if profile is None:
        raise ProfileError(f"Profile {canonical!r} does not exist.")
    if registry.is_removed(profile):
        raise ProfileError(f"Profile {canonical!r} was removed from direct selection.")
    inspect_store(profile_store_dir(profile))
    return profile


def _require_cross_profile_source(
    registry: ProfileRegistry,
    source: ProfileEntry,
) -> None:
    if source.uid == registry.active_uid:
        raise ProfileError(
            "Context and Memory import require a different source Profile. "
            "Use branch or ordinary Context commands inside the active Profile."
        )


def _require_active_profile_snapshot(
    registry: ProfileRegistry,
    destination: MemoryStore,
) -> None:
    expected = profile_store_dir(registry.active).absolute()
    if destination.store_dir.absolute() != expected:
        raise ProfileError(
            "Active Profile changed while import was starting; rerun the command."
        )


def import_profile_from_profile(
    name: str,
    source_profile_name: str,
    *,
    expected_source_profile_uid: str | None = None,
) -> tuple[ProfileEntry, StoreInspection]:
    """Create one clean Profile from another registered Profile."""

    registry = load_profile_registry()
    source = _source_profile(registry, source_profile_name)
    if (
        expected_source_profile_uid is not None
        and source.uid != expected_source_profile_uid
    ):
        raise ProfileError("Source Profile identity changed after import review.")
    return import_baseline_profile(
        name,
        profile_store_dir(source),
        source_profile=source,
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

    from memcommit.application.retained_history.context_snapshot import ContextSnapshotRef

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
                # A Context snapshot is already a closed retained value. Its
                # historical Source name is provenance, not a live locator.
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
                    # Snapshot content and provenance are self-contained. An
                    # Import must not turn it back into a live cross-Profile
                    # dependency merely because its original Source is absent.
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
    source_profile: ProfileEntry,
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
            source_profile=source_profile.name,
            source_profile_uid=source_profile.uid,
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
        _require_active_profile_snapshot(registry, destination)
        source_profile = _source_profile(registry, source_profile_name)
        _require_cross_profile_source(registry, source_profile)
        source_store = MemoryStore(
            root=profile_store_dir(source_profile),
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
                    source_profile,
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
        _require_active_profile_snapshot(registry, destination)
        source_profile = _source_profile(registry, source_profile_name)
        _require_cross_profile_source(registry, source_profile)
        source_store = MemoryStore(
            root=profile_store_dir(source_profile),
            create=False,
        )
        source_current = source_store.current_context_name()
        source_name = resolve_context_locator(
            source_context_locator,
            current=source_current,
        )
        target_root = target_name or source_name

        # The exclusive source graph lock freezes recursive membership as well
        # as every record identity until the destination transaction commits.
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
                    source_profile,
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
                                "source_profile_uid": source_profile.uid,
                                "source_profile_name": source_profile.name,
                                "source_context": source.name,
                                "source_context_uid": source.uid,
                                "source_context_digest": source._store_digest,
                                "target_context": context.name,
                                "recursive": recursive,
                            },
                            description=(
                                f"Imported Context '{source.name}' from Profile "
                                f"'{source_profile.name}' as '{context.name}'."
                            ),
                        ),
                    )
                    for source, context in zip(snapshots, imported, strict=True)
                )
                created = destination.create_missing_contexts(
                    entries,
                    require_all_new=True,
                )

    return ContextImportResult(
        source_profile=source_profile.name,
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
    source_profile: ProfileEntry,
    source_context: Context,
    source_memory: Memory,
    target: Context,
) -> MemoryImportPlan:
    return MemoryImportPlan(
        source_profile=source_profile.name,
        source_profile_uid=source_profile.uid,
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
        _require_active_profile_snapshot(registry, destination)
        source_profile = _source_profile(registry, source_profile_name)
        _require_cross_profile_source(registry, source_profile)
        source_store = MemoryStore(
            root=profile_store_dir(source_profile),
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
                    source_profile,
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
        _require_active_profile_snapshot(registry, destination)
        source_profile = _source_profile(registry, source_profile_name)
        _require_cross_profile_source(registry, source_profile)
        source_store = MemoryStore(
            root=profile_store_dir(source_profile),
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
                    source_profile,
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
                            "source_profile_uid": source_profile.uid,
                            "source_profile_name": source_profile.name,
                            "source_context": source_context.name,
                            "source_context_uid": source_context.uid,
                            "source_context_digest": source_context._store_digest,
                            "source_memory_uid": source_memory.uid,
                            "target_context": target.name,
                        },
                        description=(
                            f"Imported Memory [{source_memory.uid[:8]}] from "
                            f"Profile '{source_profile.name}' Context "
                            f"'{source_context.name}'."
                        ),
                    ),
                )

    return MemoryImportResult(
        source_profile=source_profile.name,
        source_context=source_name,
        target_context=target_name,
        memory=imported,
    )
