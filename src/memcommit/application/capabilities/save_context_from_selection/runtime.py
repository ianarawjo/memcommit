"""MemoryStore implementation for saving selected Memories as a Context."""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Protocol

import memcommit.application.capabilities.ops as ops
from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    authorized_context_operation,
    granted_memory_source,
)
from memcommit.application.capabilities.save_context_from_selection.application import (
    FrozenContextSelectionSave,
    SaveContextFromSelectionError,
    SaveContextFromSelectionPort,
    SaveContextFromSelectionRequest,
    SaveContextFromSelectionResult,
    SelectedMemory,
    save_context_from_selection,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore, context_record_digest


class SaveContextSelectionCatalog(Protocol):
    """Exact readable bindings frozen by the selecting operation."""

    def access_for(self, name: str) -> ContextAccess: ...


@dataclass(frozen=True, slots=True)
class _ResolvedSource:
    selected: SelectedMemory
    access: ContextAccess
    context: Context
    memory: Memory


@dataclass(frozen=True, slots=True)
class _StoreSelectionSaveToken:
    output: Context
    output_uids: tuple[str, ...]
    checkpoint: AutoCheckpoint
    sources: tuple[_ResolvedSource, ...]
    checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...]
    local_bindings: tuple[tuple[str, str, str], ...]
    external_sources: tuple[tuple[str, str, str, str], ...]
    external_accesses: dict[tuple[str, str], ContextAccess]


def _resolve_sources(
    catalog: SaveContextSelectionCatalog,
    selection: tuple[SelectedMemory, ...],
) -> tuple[_ResolvedSource, ...]:
    resolved: list[_ResolvedSource] = []
    for selected in selection:
        access = catalog.access_for(selected.source_context_name)
        # READ is the enforceable Source boundary for copying, retaining a
        # snapshot, and creating a live relationship. Derived-use permissions
        # were retired because content already disclosed under READ cannot be
        # meaningfully constrained by those downstream labels.
        authorize_context_use(access, ContextUse.READ)
        context = access.store.load_direct(access.context_name)
        if context.uid != selected.source_context_uid:
            raise SaveContextFromSelectionError(
                f"Source Context '{selected.source_context_name}' changed identity "
                "after selection."
            )
        item = context.memories.get(selected.source_memory_uid)
        if not isinstance(item, Memory) or item.content != selected.content:
            raise SaveContextFromSelectionError(
                f"Source Memory [{selected.source_memory_uid[:8]}] changed after "
                "selection."
            )
        resolved.append(
            _ResolvedSource(
                selected=selected,
                access=access,
                context=context,
                memory=item,
            )
        )
    return tuple(resolved)


def _unique_accesses(sources: tuple[_ResolvedSource, ...]) -> tuple[ContextAccess, ...]:
    values: list[ContextAccess] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        access = source.access
        key = (
            str(access.store.store_dir),
            access.context_name,
            access.view.grant.uid if access.view is not None else "",
        )
        if key not in seen:
            seen.add(key)
            values.append(access)
    return tuple(values)


def _linked_memory(
    source: _ResolvedSource,
    output: Context,
    *,
    snapshot: bool,
) -> MemoryRef:
    """Create a public-name relationship without leaking authority locators."""

    public_source = Context(
        uid=source.context.uid,
        name=source.selected.source_context_name,
    )
    public_memory = Memory(uid=source.memory.uid, content=source.memory.content)
    public_source.add(public_memory)
    link = (
        ops.reference_memory(public_memory, public_source, output)
        if snapshot
        else ops.embed_memory(public_memory, public_source, output)
    )
    if not source.access.is_granted:
        return link

    bound = MemoryRef(
        uid=link.uid,
        target_context_uid=link.target_context_uid,
        target_context_name=link.target_context_name,
        target_memory_uid=link.target_memory_uid,
        target=public_memory,
        snapshot_content_sha256=link.snapshot_content_sha256,
        granted_source=granted_memory_source(
            source.access,
            context_uid=source.context.uid,
            memory_uid=source.memory.uid,
        ),
    )
    output.memories[link.uid] = bound
    return bound


class MemoryStoreSaveContextFromSelectionPort(SaveContextFromSelectionPort):
    """Prepare and publish one new Context under Source and Grant locks."""

    def __init__(
        self,
        store: MemoryStore,
        catalog: SaveContextSelectionCatalog,
    ) -> None:
        self._store = store
        self._catalog = catalog

    def prepare(
        self,
        request: SaveContextFromSelectionRequest,
    ) -> FrozenContextSelectionSave:
        validate_portable_context_name(request.destination_name)
        self._store.assert_context_creatable(request.destination_name)
        sources = _resolve_sources(self._catalog, request.selection)
        accesses = _unique_accesses(sources)
        checks: list[tuple[ContextAccess, tuple[str, ...]]] = []
        for access in accesses:
            authorize_context_use(access, ContextUse.READ)
            if access.is_granted:
                # The lower-level lock primitive revalidates the same use while
                # preventing Grant revision changes through local publication.
                checks.append((access, (ContextUse.READ.value,)))

        output = Context(uid=str(uuid.uuid4()), name=request.destination_name)
        output_uids: list[str] = []
        source_rows: list[dict[str, object]] = []
        for source in sources:
            output_item: Memory | MemoryRef
            if request.mode == "COPY":
                output_item = Memory(
                    uid=str(uuid.uuid4()),
                    content=source.memory.content,
                )
                output.add(output_item)
            elif request.mode == "REFERENCE":
                output_item = _linked_memory(source, output, snapshot=True)
            else:
                output_item = _linked_memory(source, output, snapshot=False)
            output_uids.append(output_item.uid)
            row: dict[str, object] = {
                "selection_position": source.selected.position,
                "source_kind": source.selected.source_kind,
                "source_context": source.selected.source_context_name,
                "source_context_uid": source.context.uid,
                "source_memory_uid": source.memory.uid,
                "output_uid": output_item.uid,
            }
            if source.selected.relevance is not None:
                row["relevance"] = source.selected.relevance
            source_rows.append(row)

        checkpoint = AutoCheckpoint(
            command=request.origin.operation,
            args={
                "context_creation": {
                    "version": 1,
                    "context_uid": output.uid,
                    "context_name": output.name,
                },
                "save_context_from_selection": {
                    "version": 1,
                    "source_operation": request.origin.operation,
                    "source_arguments": dict(request.origin.arguments),
                    "mode": request.mode,
                    "output": output.name,
                    "items": source_rows,
                },
            },
            description=(
                f"Saved {len(sources)} selected Memory/ies as {request.mode} in "
                f"new Context '{request.destination_name}'; Sources unchanged"
            ),
        )

        local_bindings = tuple(
            dict.fromkeys(
                (
                    source.access.context_name,
                    source.context.uid,
                    context_record_digest(source.context),
                )
                for source in sources
                if not source.access.is_granted
            )
        )
        external_sources = tuple(
            dict.fromkeys(
                (
                    str(source.access.store.store_dir),
                    source.access.context_name,
                    source.context.uid,
                    context_record_digest(source.context),
                )
                for source in sources
                if source.access.is_granted
            )
        )
        external_accesses = {
            (str(source.access.store.store_dir), source.access.context_name): (
                source.access
            )
            for source in sources
            if source.access.is_granted
        }
        return FrozenContextSelectionSave(
            mode=request.mode,
            destination_name=request.destination_name,
            source_count=len(sources),
            token=_StoreSelectionSaveToken(
                output=output,
                output_uids=tuple(output_uids),
                checkpoint=checkpoint,
                sources=sources,
                checks=tuple(checks),
                local_bindings=local_bindings,
                external_sources=external_sources,
                external_accesses=external_accesses,
            ),
        )

    def save(
        self,
        prepared: FrozenContextSelectionSave,
    ) -> SaveContextFromSelectionResult:
        token = prepared.token
        if not isinstance(token, _StoreSelectionSaveToken):
            raise SaveContextFromSelectionError(
                "The prepared selected-Context save token is invalid."
            )
        if (
            token.output.name != prepared.destination_name
            or len(token.sources) != prepared.source_count
            or len(token.output_uids) != prepared.source_count
        ):
            raise SaveContextFromSelectionError(
                "The prepared selected-Context save changed before publication."
            )

        self._store.assert_context_creatable(prepared.destination_name)
        with authorized_context_operation(token.checks):
            with ExitStack() as stack:
                # Authority stores cannot join the active Profile's Store lock.
                # Hold every exact external Source until local publication ends.
                for store_dir, name, uid, digest in token.external_sources:
                    access = token.external_accesses[(store_dir, name)]
                    stack.enter_context(
                        access.store.locked_context_snapshot(
                            name,
                            expected_uid=uid,
                            expected_digest=digest,
                        )
                    )
                if token.local_bindings:
                    created_checkpoint = self._store.create_context_with_sources(
                        token.output,
                        token.checkpoint,
                        source_bindings=token.local_bindings,
                    )
                else:
                    created_checkpoint = self._store.create_context(
                        token.output,
                        token.checkpoint,
                    )

        if created_checkpoint is None:
            raise SaveContextFromSelectionError(
                "Saving the selected Context produced no checkpoint."
            )
        return SaveContextFromSelectionResult(
            mode=prepared.mode,
            context_name=token.output.name,
            context_uid=token.output.uid,
            checkpoint_uid=created_checkpoint.uid,
            item_uids=token.output_uids,
        )


def execute_save_context_from_selection(
    request: SaveContextFromSelectionRequest,
    *,
    store: MemoryStore,
    catalog: SaveContextSelectionCatalog,
) -> SaveContextFromSelectionResult:
    """Execute the reviewed save without CLI, TUI, or provider bootstrap."""

    return save_context_from_selection(
        request,
        port=MemoryStoreSaveContextFromSelectionPort(store, catalog),
    )


__all__ = [
    "MemoryStoreSaveContextFromSelectionPort",
    "SaveContextSelectionCatalog",
    "execute_save_context_from_selection",
]
