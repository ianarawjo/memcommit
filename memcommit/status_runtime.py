"""MemoryStore composition for the read-only Status application."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from memcommit.authority.access import (
    ContextAccess,
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.context_snapshot import ContextSnapshotRef
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.readable_catalog import ReadableContextCatalog
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.profile_config import ProfileRegistry, profile_store_dir
from memcommit.profiles import (
    authority_grant_snapshot_lock,
    grants_for_attachment,
)
from memcommit.source_projection.model import SourceState
from memcommit.status_application import (
    FrozenStatusContext,
    FrozenStatusFrame,
    NoCurrentStatusContextError,
    StatusCheckpoint,
    StatusEmbeddedContext,
    StatusGrant,
    StatusMemory,
    StatusMemoryReference,
    StatusQueryView,
    StatusRequest,
    StatusResult,
    inspect_status,
)
from memcommit.store import MemoryStore


def _required_text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Status checkpoint {key} is invalid.")
    return value


def _checkpoint(record: Mapping[str, Any]) -> StatusCheckpoint:
    uid = _required_text(record, "uid")
    timestamp = _required_text(record, "timestamp")
    automatic = record.get("auto", False)
    if not isinstance(automatic, bool):
        raise ValueError("Status checkpoint auto flag is invalid.")
    command_value = record.get("command")
    command = (
        command_value.strip()
        if isinstance(command_value, str) and command_value.strip()
        else "checkpoint"
    )
    description_value = record.get("description") or record.get("message")
    description = (
        description_value.strip()
        if isinstance(description_value, str) and description_value.strip()
        else "(no message)"
    )
    return StatusCheckpoint(
        uid=uid,
        timestamp=timestamp,
        command=command,
        description=description,
        automatic=automatic,
    )


class MemoryStoreStatusSource:
    """Freeze Status facts under one Profile/Grant registry generation."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def _profile_name(self, registry: ProfileRegistry) -> str:
        if (
            profile_store_dir(registry.active).resolve()
            == self._store.store_dir.resolve()
        ):
            return registry.active.name
        return "standalone"

    def _attached_grants(
        self,
        context_name: str,
        *,
        access: ContextAccess,
        registry: ProfileRegistry,
    ) -> tuple[StatusGrant, ...]:
        if access.is_granted or self._profile_name(registry) == "standalone":
            return ()
        return tuple(
            StatusGrant(
                uid=grant.uid,
                revision=grant.revision,
                public_name=grant.public_name,
                permissions=grant.permissions,
            )
            for grant in grants_for_attachment(
                attachment_name=context_name,
                registry=registry,
            )
        )

    def _snapshot_context(
        self,
        context: Context,
        *,
        access: ContextAccess,
        registry: ProfileRegistry,
    ) -> FrozenStatusContext:
        memories: list[StatusMemory] = []
        references: list[StatusMemoryReference] = []
        query_views: list[StatusQueryView] = []
        embedded: list[StatusEmbeddedContext] = []
        for item in context.iter_items():
            if isinstance(item, Memory):
                memories.append(StatusMemory(uid=item.uid, content=item.content))
            elif isinstance(item, MemoryRef):
                # Status reports the relationship but deliberately does not
                # open the pointed-to Context merely to decide its availability.
                references.append(
                    StatusMemoryReference(
                        uid=item.uid,
                        target_context_name=item.target_context_name,
                        target_memory_uid=item.target_memory_uid,
                    )
                )
            elif isinstance(item, QueryContextRef):
                query_views.append(StatusQueryView(uid=item.uid, name=item.name))
            elif isinstance(item, Context):
                embedded.append(
                    StatusEmbeddedContext(
                        uid=item.uid,
                        name=item.name,
                        snapshot=isinstance(item, ContextSnapshotRef),
                    )
                )

        view = access.view
        checkpoints = (
            ()
            if access.is_granted
            else tuple(
                _checkpoint(record)
                for record in self._store.list_checkpoints(access.context_name)
            )
        )
        return FrozenStatusContext(
            uid=context.uid,
            name=context.name,
            source=context_access_display_facts(
                access,
                states=(SourceState.READ_ONLY,) if access.is_granted else (),
            ),
            access_grant_uid=view.grant.uid if view is not None else None,
            access_grant_revision=view.grant.revision if view is not None else None,
            memories=tuple(memories),
            memory_references=tuple(references),
            query_views=tuple(query_views),
            embedded_contexts=tuple(embedded),
            grants=self._attached_grants(
                access.context_name,
                access=access,
                registry=registry,
            ),
            checkpoints=checkpoints,
        )

    def freeze(self, request: StatusRequest) -> FrozenStatusFrame:
        with authority_grant_snapshot_lock() as registry:
            current_name = self._store.current_context_name()
            if not current_name:
                raise NoCurrentStatusContextError(
                    "No current Context. Run 'mem init <name>' to get started."
                )
            access = resolve_context_access(
                self._store,
                None,
                current_name=current_name,
                required_permission="READ",
                registry=registry,
            )
            catalog = ReadableContextCatalog(
                self._store,
                access,
                registry=registry,
            )
            scope = ContextScope.create(
                (access.display_name,),
                include_descendants=request.include_descendants,
            )
            expanded = expand_lexical_context_names(
                scope,
                sorted(catalog.list_context_names(), key=str.casefold),
            )
            names = (
                access.display_name,
                *(name for name in expanded if name != access.display_name),
            )
            contexts: list[FrozenStatusContext] = []
            seen_uids: set[str] = set()

            def visit(public_name: str, *, expected_uid: str | None = None) -> None:
                context_access = catalog.access_for(public_name)
                context = catalog.load_direct(public_name)
                if expected_uid is not None and context.uid != expected_uid:
                    raise RuntimeError(
                        "An embedded Context identity changed during Status."
                    )
                if context.uid in seen_uids:
                    return
                seen_uids.add(context.uid)
                contexts.append(
                    self._snapshot_context(
                        context,
                        access=context_access,
                        registry=registry,
                    )
                )
                if not request.follow_embeds:
                    return
                for item in context.iter_items():
                    if not isinstance(item, Context):
                        continue
                    if not catalog.context_exists(item.name):
                        # The direct relationship remains visible even when
                        # its body is unavailable under current READ authority.
                        continue
                    visit(item.name, expected_uid=item.uid)

            for name in names:
                visit(name)
            return FrozenStatusFrame(
                current_context_name=access.display_name,
                profile_name=self._profile_name(registry),
                contexts=tuple(contexts),
            )


def execute_status(
    request: StatusRequest,
    *,
    store: MemoryStore,
) -> StatusResult:
    """Execute Status against one explicit Store without terminal effects."""

    return inspect_status(request, source=MemoryStoreStatusSource(store))


__all__ = ["MemoryStoreStatusSource", "execute_status"]
