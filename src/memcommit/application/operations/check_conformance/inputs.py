"""Freeze complete Conformance evidence and recheck its live owners."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import uuid

from memcommit.application.authorization.context_operation import (
    _require_granted_permissions,
    authorized_context_operation,
)
from memcommit.application.capabilities.context_snapshot import ContextSnapshotRef
from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
    _resolve_granted_context_identity,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.application.context_access.model import GrantedContextBinding
from memcommit.application.context_access.readable_contexts import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
)
from memcommit.application.operations.check_conformance.model import ConformanceError
from memcommit.application.operations.profile.config import (
    ProfileRegistry,
    load_profile_registry,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.core.context import (
    Context,
    GrantedContextLink,
    GrantedMemorySource,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


class ConformanceInputError(ConformanceError):
    """Conformance evidence is unavailable or no longer matches its frozen value."""


@dataclass(frozen=True)
class ConformanceReadDependency:
    store: MemoryStore | GrantedReadStore
    name: str
    uid: str
    digest: str | None
    memory_digest: tuple[str, str] | None = None
    access: ContextAccess | None = None
    granted_binding: GrantedContextBinding | None = None


@dataclass(frozen=True)
class ConformanceInputs:
    root: Context
    memories: tuple[Memory, ...]
    dependencies: tuple[ConformanceReadDependency, ...]


def _memory_digest(memory: Memory) -> str:
    return hashlib.sha256(memory.content.encode("utf-8")).hexdigest()


def capture_conformance_dependency(
    store: MemoryStore | GrantedReadStore,
    context: Context,
    *,
    access: ContextAccess | None = None,
    memory: Memory | None = None,
) -> ConformanceReadDependency:
    # A selected Rule Memory must not depend on unrelated owner content.
    return ConformanceReadDependency(
        store=store,
        name=context.name,
        uid=context.uid,
        digest=context_record_digest(context) if memory is None else None,
        memory_digest=(memory.uid, _memory_digest(memory))
        if memory is not None
        else None,
        access=access,
        granted_binding=(
            freeze_granted_context_binding(access)
            if access is not None and access.is_granted
            else None
        ),
    )


def _resolve_embed_access(
    source: GrantedContextLink | GrantedMemorySource, store: MemoryStore
) -> ContextAccess:
    registry = load_profile_registry()
    if registry.active.uid != source.grantee_profile_uid:
        raise ProfileError(
            "The active Profile no longer matches the granted Context source."
        )
    access = _resolve_granted_context_identity(
        store,
        grant_uid=source.grant_uid,
        authority_context_name=source.authority_context_name,
        required_permission="READ",
        registry=registry,
    )
    _require_granted_permissions(access, ("READ",))
    view = access.view
    assert view is not None
    grant = view.grant
    if (
        grant.uid != source.grant_uid
        or grant.revision < source.grant_revision_at_creation
        or view.authority.uid != source.authority_profile_uid
        or view.grantee.uid != source.grantee_profile_uid
        or grant.resource_uid != source.resource_uid
        or grant.resource_name != source.resource_name
        or access.context_name != source.authority_context_name
    ):
        kind = "Context" if isinstance(source, GrantedContextLink) else "Memory"
        raise ProfileError(
            f"The authority Grant binding behind an embedded {kind} changed."
        )
    return access


class _ConformanceReader:
    def __init__(self, catalog: ReadableContextCatalog, store: MemoryStore):
        self.catalog = catalog
        self.store = store
        self.frames: dict[str, Context] = {}
        self.dependencies: dict[str, ConformanceReadDependency] = {}

    def load(self, name: str, access: ContextAccess | None = None) -> Context:
        if name in self.frames:
            previous = self.dependencies[name]
            if access is not None and (
                access.store.store_dir != previous.access.store.store_dir
                or access.context_name != previous.access.context_name
                or (
                    freeze_granted_context_binding(access)
                    if access.is_granted
                    else None
                )
                != previous.granted_binding
            ):
                raise ConformanceInputError(
                    f"Context input {name!r} has conflicting authority bindings."
                )
            return self.frames[name]
        access = access or self.catalog.access_for(name)
        source = GrantedReadStore(access) if access.is_granted else access.store
        # Direct records preserve broken pointers which the ordinary loader skips.
        with authorized_context_operation(((access, ("READ",)),)):
            context = source.load_direct(name)
        self.frames[name] = context
        self.dependencies[name] = capture_conformance_dependency(
            source, context, access=access
        )
        return context

    def resolve_context(self, item: Context) -> Context | None:
        access = (
            _resolve_embed_access(item._granted_link, self.store)
            if item._granted_link is not None
            else None
        )
        name = access.access_name if access is not None else item.name
        try:
            child = self.load(name, access)
        except FileNotFoundError:
            return None
        if child.uid != item.uid:
            raise ConformanceInputError(
                f"Embedded Context {item.name!r} changed identity."
            )
        return child

    def resolve_memory(self, item: MemoryRef) -> Memory | None:
        if item.is_snapshot:
            return item.target
        access = (
            _resolve_embed_access(item.granted_source, self.store)
            if item.granted_source is not None
            else None
        )
        name = access.access_name if access is not None else item.target_context_name
        try:
            owner = self.load(name, access)
        except FileNotFoundError:
            return None
        if owner.uid != item.target_context_uid:
            raise ConformanceInputError(
                f"Memory Embed owner {name!r} changed identity."
            )
        memory = owner.memories.get(item.target_memory_uid)
        return memory if isinstance(memory, Memory) else None


def prepare_conformance_inputs(store: MemoryStore, name: str) -> ConformanceInputs:
    access = resolve_context_access(
        store, name, current_name=None, required_permission="READ"
    )
    catalog = freeze_readable_context_catalog(store, access, include_query_routes=False)
    reader = _ConformanceReader(catalog, store)
    root = reader.load(access.access_name)
    memories: list[Memory] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()

    def unavailable(context: Context, item: Context | MemoryRef) -> None:
        raise ConformanceInputError(
            f"Context input [{item.uid[:8]}] in {context.name!r} is unavailable."
        )

    def visit(
        context: Context,
        path: tuple[str, ...],
        snapshots: tuple[str, ...],
        retained: set[tuple[str, str]] | None = None,
    ) -> None:
        if isinstance(context, ContextSnapshotRef):
            snapshots = (*snapshots, context.snapshot_content_sha256)
            retained = {
                (record["name"], record["uid"])
                for record in context.snapshot_package["contexts"]
            }
        # A retained and a live copy of the same Context are distinct evidence.
        identity = (context.uid, snapshots)
        if identity in seen:
            return
        seen.add(identity)
        path = (*path, context.uid)
        for item in context.iter_items():
            if isinstance(item, (Memory, MemoryRef)):
                value = item
                if isinstance(item, MemoryRef):
                    # Snapshot packages never refresh from present-day storage.
                    value = item.target if snapshots else reader.resolve_memory(item)
                    if value is None:
                        unavailable(context, item)
                # Preserve direct item UIDs and the existing nested occurrence keys.
                uid = (
                    item.uid
                    if len(path) == 1
                    else str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            "memcommit:conformance-input:"
                            + repr((path, item.uid, snapshots, value.content)),
                        )
                    )
                )
                memories.append(Memory(uid, value.content))
            elif isinstance(item, QueryContextRef):
                raise ConformanceInputError(
                    f"Query-only Context {item.name!r} cannot supply readable input."
                )
            elif isinstance(item, Context):
                child = item
                if (
                    retained is not None
                    and not isinstance(item, ContextSnapshotRef)
                    and (item.name, item.uid) not in retained
                ):
                    # An opaque retained pointer is not captured evidence.
                    unavailable(context, item)
                if not snapshots and not isinstance(item, ContextSnapshotRef):
                    child = reader.resolve_context(item)
                if child is None:
                    unavailable(context, item)
                visit(child, path, snapshots, retained)

    visit(root, (), ())
    return ConformanceInputs(root, tuple(memories), tuple(reader.dependencies.values()))


def revalidate_conformance_inputs(
    dependencies: tuple[ConformanceReadDependency, ...],
    *,
    active_store: MemoryStore,
    registry: ProfileRegistry | None = None,
) -> None:
    for dependency in dependencies:
        reader = dependency.store
        if dependency.granted_binding is not None:
            access = revalidate_granted_context_binding(
                dependency.granted_binding, registry=registry, active_store=active_store
            )
            reader = GrantedReadStore(access, registry=registry)
        try:
            current = reader.load_direct(dependency.name)
        except FileNotFoundError as error:
            raise ConformanceInputError(
                f"Context input {dependency.name!r} disappeared."
            ) from error
        if current.uid != dependency.uid:
            raise ConformanceInputError(
                f"Context input {dependency.name!r} changed identity."
            )
        if (
            dependency.digest is not None
            and context_record_digest(current) != dependency.digest
        ):
            raise ConformanceInputError(
                f"Context input {dependency.name!r} changed content."
            )
        if dependency.memory_digest is not None:
            uid, digest = dependency.memory_digest
            memory = current.memories.get(uid)
            if not isinstance(memory, Memory) or _memory_digest(memory) != digest:
                raise ConformanceInputError(
                    f"Memory input [{uid[:8]}] in {dependency.name!r} changed."
                )
