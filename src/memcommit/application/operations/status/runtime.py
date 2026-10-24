"""MemoryStore composition for the read-only Status application."""

from __future__ import annotations


from collections.abc import Mapping
from typing import Any

from memcommit.source_projection.model import SourceDisplayFacts

from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)
from memcommit.application.operations.profile.config import (
    active_profile_registry_for_store,
)
from memcommit.application.operations.status.application import (
    FrozenStatusContext,
    FrozenStatusFrame,
    NoCurrentStatusContextError,
    StatusCheckpoint,
    StatusMemory,
    StatusRequest,
    StatusResult,
    inspect_status,
)
from memcommit.persistence.store import MemoryStore


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
    description_value = record.get("checkpoint_message")
    description = (
        description_value.strip()
        if isinstance(description_value, str) and description_value.strip()
        else command
    )
    return StatusCheckpoint(
        uid=uid,
        timestamp=timestamp,
        command=command,
        description=description,
        automatic=automatic,
    )


class MemoryStoreStatusSource:
    """Freeze the local namespace, Memory preview and retained checkpoint summaries."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def freeze(self, request: StatusRequest) -> FrozenStatusFrame:
        current = self._store.current_context_name()
        if current is None:
            raise NoCurrentStatusContextError(
                "No current Context. Run 'mem init <name>' to get started."
            )
        registry = active_profile_registry_for_store(self._store.store_dir)
        profile_name = registry.active.name if registry else "standalone"
        catalog_names = self._store.list_context_names()
        names = (
            list_context_and_descendant_names((current,), catalog_names)
            if request.include_descendants
            else (current,)
        )
        contexts = []
        for name in names:
            context = self._store.load_direct(name)
            contexts.append(
                FrozenStatusContext(
                    uid=context.uid,
                    name=context.name,
                    source=SourceDisplayFacts(),
                    memories=tuple(
                        StatusMemory(item.uid, item.content)
                        for item in context.iter_memories()
                    ),
                    checkpoints=tuple(
                        _checkpoint(record)
                        for record in self._store.list_checkpoints(name)
                    ),
                )
            )
        return FrozenStatusFrame(current, profile_name, tuple(contexts))


def execute_status(
    request: StatusRequest,
    *,
    store: MemoryStore,
) -> StatusResult:
    """Execute Status against one explicit Store without terminal effects."""

    return inspect_status(request, source=MemoryStoreStatusSource(store))


__all__ = ["MemoryStoreStatusSource", "execute_status"]
