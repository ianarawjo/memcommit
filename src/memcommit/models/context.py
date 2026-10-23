"""An ordered collection of directly owned Memories and its document layout."""

from __future__ import annotations

import uuid
from typing import Any, Iterator, Protocol, runtime_checkable

from memcommit.core.context_name_validation import validate_context_name
from memcommit.models.asset_metadata import AssetMetadata
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)
from memcommit.models.memory import Memory


@runtime_checkable
class Identifiable(Protocol):
    uid: str


class Context:
    """An ordered collection of Memories belonging to one named Context."""

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Memory] = {}
        self.order: list[str] = []
        self.corresponding_document_metadata: CorrespondingDocumentMetadata | None = (
            None
        )
        self.asset_metadata: list[AssetMetadata] = []

    @classmethod
    def create(cls, name: str) -> Context:
        return cls(
            uid=str(uuid.uuid4()),
            name=validate_context_name(name),
        )

    def get_ordered_memory_uids(self) -> list[str]:
        return self.order.copy()

    def iter_memories(self) -> Iterator[Memory]:
        for uid in self.get_ordered_memory_uids():
            yield self.memories[uid]

    def add(
        self,
        memory: Memory,
        position: int | None = None,
    ) -> Memory:

        if not isinstance(memory, Memory):
            raise TypeError("A Context can contain only Memories.")

        ordered_memory_uids = self.get_ordered_memory_uids()
        already_present = memory.uid in self.memories

        if already_present:
            self.order = ordered_memory_uids
        elif position is None:
            self.order = [*ordered_memory_uids, memory.uid]
        else:
            index = max(0, min(position, len(ordered_memory_uids)))
            self.order = [
                *ordered_memory_uids[:index],
                memory.uid,
                *ordered_memory_uids[index:],
            ]
        self.memories[memory.uid] = memory
        return memory

    def remove(self, uid: str) -> None:
        if uid not in self.memories:
            raise KeyError(f"No memory with uid '{uid}' in context '{self.name}'.")
        del self.memories[uid]
        self.order = [item_uid for item_uid in self.order if item_uid != uid]

    def clear(self) -> None:
        self.memories.clear()
        self.order.clear()

    def get_all_memories(self) -> dict[str, Memory]:
        return self.memories

    def replace_memory(self, memory: Memory) -> None:
        if not isinstance(memory, Memory):
            raise TypeError("A Context can contain only Memories.")
        if memory.uid not in self.memories:
            raise KeyError(
                f"No memory with uid '{memory.uid}' in context '{self.name}'."
            )
        self.memories[memory.uid] = memory

    def to_dict(self) -> dict[str, Any]:
        record = {
            "uid": self.uid,
            "name": self.name,
            "memories": {
                memory.uid: memory.to_dict() for memory in self.iter_memories()
            },
            "order": self.get_ordered_memory_uids(),
        }
        if self.corresponding_document_metadata:
            record["document"] = self.corresponding_document_metadata.to_dict()
        if self.asset_metadata:
            record["attached_files"] = [item.to_dict() for item in self.asset_metadata]
        return record

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Context:
        allowed_fields = {
            "uid",
            "name",
            "memories",
            "order",
            "document",
            "attached_files",
        }
        if not isinstance(data, dict) or data.keys() - allowed_fields:
            raise ValueError("Invalid Context record fields.")
        context_uid = data["uid"]
        context_name = validate_context_name(data["name"])

        memory_records = data.get("memories", {})
        if not isinstance(memory_records, dict):
            raise ValueError("Context Memories must be a mapping.")
        memories_by_uid: dict[str, Memory] = {}
        for uid, item in memory_records.items():
            if (
                not isinstance(item, dict)
                or set(item) != {"type", "uid", "content"}
                or item.get("type") != "memory"
            ):
                raise ValueError("A Context record can contain only Memories.")
            if (
                not isinstance(uid, str)
                or not uid
                or not isinstance(item.get("content"), str)
            ):
                raise ValueError("A Context Memory requires a UID and text content.")
            memory = Memory.from_dict(item)
            memories_by_uid[memory.uid] = memory

        memory_order = list(memories_by_uid)
        if "order" in data:
            requested_order = data["order"]
            if (
                not isinstance(requested_order, list)
                or any(not isinstance(uid, str) for uid in requested_order)
                or len(requested_order) != len(memories_by_uid)
                or set(requested_order) != memories_by_uid.keys()
            ):
                raise ValueError(
                    "Context order must contain every Memory UID exactly once."
                )
            memory_order = requested_order.copy()

        document_metadata = None
        if "document" in data:
            document_metadata = CorrespondingDocumentMetadata.from_dict(data["document"])
        asset_metadata = []
        if "attached_files" in data:
            if not isinstance(data["attached_files"], list):
                raise ValueError("Attached files must be a list.")
            asset_metadata = [
                AssetMetadata.from_dict(item) for item in data["attached_files"]
            ]
            if len({item.path for item in asset_metadata}) != len(asset_metadata):
                raise ValueError("Duplicate attached-file path.")

        context = cls(uid=context_uid, name=context_name)
        for memory in memories_by_uid.values():
            context.add(memory)
        context.order = memory_order
        context.corresponding_document_metadata = document_metadata
        context.asset_metadata = asset_metadata
        return context
