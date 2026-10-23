"""MemoryStore implementation for saving selected Memories as a Context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from memcommit.application.context_access.access import ContextAccess
from memcommit.application.capabilities.save_context_from_selection.application import (
    FrozenContextSelectionSave,
    SaveContextFromSelectionError,
    SaveContextFromSelectionPort,
    SaveContextFromSelectionRequest,
    SaveContextFromSelectionResult,
    SelectedMemory,
    save_context_from_selection,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.core.context_name_validation import validate_context_name
from memcommit.persistence.store import MemoryStore


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
    checkpoint: AutoCheckpointRequest
    sources: tuple[_ResolvedSource, ...]
    local_bindings: tuple[tuple[str, str], ...]


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


class MemoryStoreSaveContextFromSelectionPort(SaveContextFromSelectionPort):
    """Prepare and publish a new local Context under Source freshness checks and Store locks."""

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
        validate_context_name(request.destination_name)
        self._store.assert_context_creatable(request.destination_name)
        sources = _resolve_sources(self._catalog, request.selection)
        output = Context(uid=str(uuid.uuid4()), name=request.destination_name)
        output_uids: list[str] = []
        source_rows: list[dict[str, object]] = []
        for source in sources:
            output_item = Memory(uid=str(uuid.uuid4()), content=source.memory.content)
            output.add(output_item)
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

        checkpoint = AutoCheckpointRequest(
            command=request.origin.operation,
            command_details={
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
        )

        local_bindings = tuple(
            dict.fromkeys(
                (
                    source.access.context_name,
                    source.context.uid,
                )
                for source in sources
            )
        )
        return FrozenContextSelectionSave(
            mode=request.mode,
            destination_name=request.destination_name,
            source_count=len(sources),
            token=_StoreSelectionSaveToken(
                output=output,
                output_uids=tuple(output_uids),
                checkpoint=checkpoint,
                sources=sources,
                local_bindings=local_bindings,
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
        created_checkpoint = self._store.create_context_with_sources(
            token.output,
            token.checkpoint,
            source_bindings=token.local_bindings,
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
