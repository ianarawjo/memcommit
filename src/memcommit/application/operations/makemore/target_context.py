"""Freeze an exact Makemore destination as bounded ambient context."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    authorized_context_operation,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.core.context import Context, GrantedContextLink, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreTargetContext,
    MakemoreTargetContextItem,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    FrozenMemorizationTarget,
)
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.application.operations.update.model import GrantedUpdateTarget


GRANTED_MAKEMORE_AMBIENT_PERMISSIONS = (
    "READ",
    "EMBED",
    "DERIVE",
    "COMBINE",
)
GRANTED_MAKEMORE_ADD_PERMISSIONS = (
    *GRANTED_MAKEMORE_AMBIENT_PERMISSIONS,
    "EXPORT",
    "SAVE_ANALYSIS",
)


@dataclass(frozen=True)
class FrozenMakemoreLocalContext:
    """One local Context whose exact contents contributed to the ambient frame."""

    context_name: str
    context_uid: str
    context_digest: str


@dataclass(frozen=True)
class FrozenMakemoreGrantedContext:
    """One reauthorizable granted Context contributing ambient content."""

    binding: GrantedUpdateTarget
    context_uid: str
    context_digest: str


@dataclass(frozen=True)
class FrozenMakemoreTargetContext:
    """Target ambient frame plus every local and granted pre-image it consumed."""

    target: FrozenMemorizationTarget
    semantic: MakemoreTargetContext
    local_contexts: tuple[FrozenMakemoreLocalContext, ...]
    granted_contexts: tuple[FrozenMakemoreGrantedContext, ...]
    excluded_root_memory_uids: tuple[str, ...] = ()
    required_granted_permissions: tuple[str, ...] = (
        GRANTED_MAKEMORE_AMBIENT_PERMISSIONS
    )


@dataclass(frozen=True)
class _AmbientRecord:
    kind: str
    context_name: str
    memory_uid: str | None
    content: str | None


def _assert_granted_ambient_permissions(
    access: ContextAccess,
    required_permissions: tuple[str, ...],
) -> None:
    view = access.view
    if view is None:
        raise MakemoreError("Makemore expected a granted Target Context.")
    missing = sorted(
        set(required_permissions) - set(view.grant.permissions)
    )
    if missing:
        raise MakemoreError(
            f"Grant {view.grant.uid[:8]} does not allow "
            + " + ".join(missing)
            + f" ambient Makemore access to {access.display_name!r}."
        )


def _assert_link_matches_access(
    link: GrantedContextLink,
    access: ContextAccess,
) -> None:
    binding = freeze_granted_context_binding(access)
    if (
        binding.public_name != link.public_name
        or binding.grantee_profile_uid != link.grantee_profile_uid
        or binding.authority_profile_uid != link.authority_profile_uid
        or binding.attachment_context_uid != link.attachment_context_uid
        or binding.attachment_context_name != link.attachment_context_name
        or binding.grant_uid != link.grant_uid
        or binding.grant_revision < link.grant_revision_at_creation
        or binding.resource_uid != link.resource_uid
        or binding.resource_name != link.resource_name
        or binding.authority_context_name != link.authority_context_name
    ):
        raise MakemoreError(
            "The authority Grant binding behind an embedded Target Context changed."
        )


def freeze_makemore_target_context(
    store: MemoryStore,
    *,
    target: FrozenMemorizationTarget,
    excluded_root_memory_uids: tuple[str, ...] = (),
    required_granted_permissions: tuple[str, ...] = (
        GRANTED_MAKEMORE_AMBIENT_PERMISSIONS
    ),
) -> FrozenMakemoreTargetContext:
    """Follow the exact Target's safe ambient graph without broad Profile expansion."""

    if not isinstance(store, MemoryStore):
        raise TypeError("Makemore Target freezing requires a MemoryStore.")
    if not isinstance(target, FrozenMemorizationTarget):
        raise TypeError("Makemore Target freezing requires a frozen Target.")
    if len(set(excluded_root_memory_uids)) != len(excluded_root_memory_uids):
        raise MakemoreError("Makemore Source exclusions must be distinct.")
    if (
        not isinstance(required_granted_permissions, tuple)
        or not set(GRANTED_MAKEMORE_AMBIENT_PERMISSIONS).issubset(
            required_granted_permissions
        )
        or len(set(required_granted_permissions)) != len(required_granted_permissions)
    ):
        raise MakemoreError("Makemore granted Target permissions are invalid.")

    records: list[_AmbientRecord] = []
    seen_records: set[tuple[str, str, str]] = set()
    seen_context_uids: set[str] = set()
    seen_query_names: set[str] = set()
    local_bindings: dict[str, FrozenMakemoreLocalContext] = {}
    granted_bindings: dict[str, FrozenMakemoreGrantedContext] = {}

    def add_memory(*, context_name: str, context_uid: str, memory: Memory) -> None:
        key = ("MEMORY", context_uid, memory.uid)
        if key in seen_records:
            return
        seen_records.add(key)
        records.append(
            _AmbientRecord("MEMORY", context_name, memory.uid, memory.content)
        )

    def add_query(query: QueryContextRef) -> None:
        if query.name in seen_query_names:
            return
        seen_query_names.add(query.name)
        records.append(_AmbientRecord("QUERY_ONLY_CONTEXT", query.name, None, None))

    def remember_local(context: Context) -> None:
        binding = FrozenMakemoreLocalContext(
            context_name=context.name,
            context_uid=context.uid,
            context_digest=context_record_digest(context),
        )
        previous = local_bindings.get(context.name)
        if previous is not None and previous != binding:
            raise MakemoreError(
                f"Makemore Target Context {context.name!r} changed while freezing."
            )
        local_bindings[context.name] = binding

    def load_granted(public_name: str, attachment_name: str) -> tuple[ContextAccess, Context]:
        access = resolve_context_access(
            store,
            public_name,
            current_name=attachment_name,
            required_permission="READ",
        )
        _assert_granted_ambient_permissions(access, required_granted_permissions)
        with authorized_context_operation(((access, required_granted_permissions),)):
            context = GrantedReadStore(access).load_direct(public_name)
        binding = FrozenMakemoreGrantedContext(
            binding=freeze_granted_context_binding(access),
            context_uid=context.uid,
            context_digest=context_record_digest(context),
        )
        previous = granted_bindings.get(public_name)
        if previous is not None and previous != binding:
            raise MakemoreError(
                f"Granted Target Context {public_name!r} changed while freezing."
            )
        granted_bindings[public_name] = binding
        return access, context

    def visit_memory_ref_local(item: MemoryRef) -> None:
        if item.target is not None:
            add_memory(
                context_name=item.target_context_name,
                context_uid=item.target_context_uid,
                memory=item.target,
            )
            return
        if not store.context_exists(item.target_context_name):
            raise MakemoreError(
                f"Target ambient Memory reference Context "
                f"{item.target_context_name!r} is unavailable."
            )
        source = store.load_direct(item.target_context_name)
        if source.uid != item.target_context_uid:
            raise MakemoreError(
                "A Target ambient Memory reference Context identity changed."
            )
        remember_local(source)
        target_memory = source.memories.get(item.target_memory_uid)
        if isinstance(target_memory, Memory):
            add_memory(
                context_name=source.name,
                context_uid=source.uid,
                memory=target_memory,
            )
        else:
            raise MakemoreError(
                "A Target ambient Memory reference is unavailable."
            )

    def visit_local(context: Context, *, root: bool = False) -> None:
        if context.uid in seen_context_uids:
            return
        seen_context_uids.add(context.uid)
        remember_local(context)
        for item in context.iter_items():
            if isinstance(item, Memory):
                if root and item.uid in excluded_root_memory_uids:
                    continue
                add_memory(
                    context_name=context.name,
                    context_uid=context.uid,
                    memory=item,
                )
            elif isinstance(item, MemoryRef):
                visit_memory_ref_local(item)
            elif isinstance(item, QueryContextRef):
                add_query(item)
            elif item._granted_link is not None:
                link = item._granted_link
                access, granted = load_granted(
                    link.public_name,
                    link.attachment_context_name,
                )
                _assert_link_matches_access(link, access)
                if granted.uid != link.context_uid:
                    raise MakemoreError(
                        "The granted Target Context identity changed."
                    )
                visit_granted(
                    granted,
                    attachment_name=link.attachment_context_name,
                )
            elif store.context_exists(item.name):
                child = store.load_direct(item.name)
                if child.uid != item.uid:
                    raise MakemoreError(
                        "A Target ambient embedded Context identity changed."
                    )
                visit_local(child)
            else:
                raise MakemoreError(
                    f"Target ambient embedded Context {item.name!r} is unavailable."
                )

    def visit_granted(context: Context, *, attachment_name: str) -> None:
        if context.uid in seen_context_uids:
            return
        seen_context_uids.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Memory):
                add_memory(
                    context_name=context.name,
                    context_uid=context.uid,
                    memory=item,
                )
            elif isinstance(item, MemoryRef):
                access, owner = load_granted(item.target_context_name, attachment_name)
                _assert_granted_ambient_permissions(
                    access,
                    required_granted_permissions,
                )
                if owner.uid != item.target_context_uid:
                    continue
                memory = owner.memories.get(item.target_memory_uid)
                if isinstance(memory, Memory):
                    add_memory(
                        context_name=owner.name,
                        context_uid=owner.uid,
                        memory=memory,
                    )
            elif isinstance(item, QueryContextRef):
                add_query(item)
            else:
                _access, child = load_granted(item.name, attachment_name)
                if child.uid == item.uid:
                    visit_granted(child, attachment_name=attachment_name)

    root = store.load_direct(target.context_name)
    if (
        root.uid != target.context_uid
        or context_record_digest(root) != target.context_digest
    ):
        raise MakemoreError(
            f"Target Context {target.context_name!r} changed before Makemore began."
        )
    visit_local(root, root=True)
    semantic_items = tuple(
        MakemoreTargetContextItem(
            alias=f"t{index}",
            kind=record.kind,
            context_name=record.context_name,
            memory_uid=record.memory_uid,
            content=record.content,
        )
        for index, record in enumerate(records, 1)
    )
    return FrozenMakemoreTargetContext(
        target=target,
        semantic=MakemoreTargetContext(
            context_name=target.context_name,
            items=semantic_items,
        ),
        local_contexts=tuple(local_bindings.values()),
        granted_contexts=tuple(granted_bindings.values()),
        excluded_root_memory_uids=excluded_root_memory_uids,
        required_granted_permissions=required_granted_permissions,
    )


def _assert_local_contexts_unchanged(
    store: MemoryStore,
    frozen: FrozenMakemoreTargetContext,
) -> None:
    for binding in frozen.local_contexts:
        current = store.load_direct(binding.context_name)
        if (
            current.uid != binding.context_uid
            or context_record_digest(current) != binding.context_digest
        ):
            raise MakemoreError(
                f"Target ambient Context {binding.context_name!r} changed while "
                "Makemore was running; no generated Memories were added."
            )


def _assert_granted_contexts_unchanged(
    accesses: tuple[ContextAccess, ...],
    frozen: FrozenMakemoreTargetContext,
) -> None:
    by_name = {access.display_name: access for access in accesses}
    for item in frozen.granted_contexts:
        access = by_name[item.binding.public_name]
        context = GrantedReadStore(access).load_direct(item.binding.public_name)
        if (
            context.uid != item.context_uid
            or context_record_digest(context) != item.context_digest
        ):
            raise MakemoreError(
                f"Granted Target ambient Context {item.binding.public_name!r} "
                "changed while Makemore was running; no proposal was published."
            )


@contextmanager
def authorized_frozen_makemore_target(
    store: MemoryStore,
    frozen: FrozenMakemoreTargetContext,
    *,
    revalidate_after: bool = True,
    required_granted_permissions: tuple[str, ...] | None = None,
) -> Iterator[None]:
    """Hold every Grant stable and revalidate every ambient pre-image."""

    accesses = tuple(
        revalidate_granted_context_binding(
            item.binding,
            required_permission="READ",
            active_store=store,
        )
        for item in frozen.granted_contexts
    )
    permissions = (
        frozen.required_granted_permissions
        if required_granted_permissions is None
        else required_granted_permissions
    )
    if not set(frozen.required_granted_permissions).issubset(permissions):
        raise MakemoreError(
            "Makemore cannot weaken its frozen granted Target permissions."
        )
    for access in accesses:
        _assert_granted_ambient_permissions(access, permissions)
    checks = tuple((access, permissions) for access in accesses)
    with authorized_context_operation(checks):
        _assert_local_contexts_unchanged(store, frozen)
        _assert_granted_contexts_unchanged(accesses, frozen)
        yield
        if revalidate_after:
            _assert_local_contexts_unchanged(store, frozen)
            _assert_granted_contexts_unchanged(accesses, frozen)


__all__ = [
    "FrozenMakemoreGrantedContext",
    "FrozenMakemoreLocalContext",
    "FrozenMakemoreTargetContext",
    "GRANTED_MAKEMORE_ADD_PERMISSIONS",
    "GRANTED_MAKEMORE_AMBIENT_PERMISSIONS",
    "authorized_frozen_makemore_target",
    "freeze_makemore_target_context",
]
