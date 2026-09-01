"""Core Context, Memory, reference, and checkpoint domain values."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Callable,
    Iterator,
    Optional,
    Protocol,
    TypeAlias,
    runtime_checkable,
)


@runtime_checkable
class Identifiable(Protocol):
    uid: str


class Memory:
    """Atomic chunk of information."""

    def __init__(self, uid: str, content: str):
        self.uid = uid
        self.content = content

    def to_dict(self) -> dict[str, Any]:
        return {"type": "memory", "uid": self.uid, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        return cls(uid=data["uid"], content=data["content"])


@dataclass(frozen=True)
class GrantedMemorySource:
    """Exact authority provenance behind a granted Memory relationship.

    Snapshot Reference retains this value as historical provenance. Live Embed
    additionally reauthorizes the same binding whenever its target is opened.
    Keeping the binding separate from ``MemoryRef`` time semantics prevents an
    exported snapshot from accidentally becoming revocable and prevents a live
    pointer from being mistaken for retained content.
    """

    context_uid: str
    access_name: str
    authority_context_name: str
    authority_profile_uid: str
    grantee_profile_uid: str
    grant_uid: str
    grant_revision_at_creation: int
    resource_uid: str
    resource_name: str
    memory_uid: str

    def __post_init__(self) -> None:
        text_fields = (
            self.context_uid,
            self.access_name,
            self.authority_context_name,
            self.authority_profile_uid,
            self.grantee_profile_uid,
            self.grant_uid,
            self.resource_uid,
            self.resource_name,
            self.memory_uid,
        )
        if any(not isinstance(value, str) or not value for value in text_fields):
            raise ValueError("Granted Memory Source fields must be nonempty text.")
        if (
            isinstance(self.grant_revision_at_creation, bool)
            or not isinstance(self.grant_revision_at_creation, int)
            or self.grant_revision_at_creation < 1
        ):
            raise ValueError("Granted Memory Source revision must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_uid": self.context_uid,
            "access_name": self.access_name,
            "authority_context_name": self.authority_context_name,
            "authority_profile_uid": self.authority_profile_uid,
            "grantee_profile_uid": self.grantee_profile_uid,
            "grant_uid": self.grant_uid,
            "grant_revision_at_creation": self.grant_revision_at_creation,
            "resource_uid": self.resource_uid,
            "resource_name": self.resource_name,
            "memory_uid": self.memory_uid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrantedMemorySource":
        expected = {
            "context_uid",
            "access_name",
            "authority_context_name",
            "authority_profile_uid",
            "grantee_profile_uid",
            "grant_uid",
            "grant_revision_at_creation",
            "resource_uid",
            "resource_name",
            "memory_uid",
        }
        if set(data) != expected:
            raise ValueError("Granted Memory Source fields are invalid.")
        return cls(
            context_uid=data["context_uid"],
            access_name=data["access_name"],
            authority_context_name=data["authority_context_name"],
            authority_profile_uid=data["authority_profile_uid"],
            grantee_profile_uid=data["grantee_profile_uid"],
            grant_uid=data["grant_uid"],
            grant_revision_at_creation=data["grant_revision_at_creation"],
            resource_uid=data["resource_uid"],
            resource_name=data["resource_name"],
            memory_uid=data["memory_uid"],
        )


class MemoryRef:
    """Read-only live embed or immutable snapshot of one Source Memory.

    Legacy ``memory_ref`` records are live links and deliberately persist no
    content. New ``memory_snapshot_ref`` records retain the exact reviewed
    content. Keeping both modes in one direct-item class preserves existing
    operation guards that already prevent references from being edited as
    directly owned Memories.
    """

    def __init__(
        self,
        uid: str,
        target_context_uid: str,
        target_context_name: str,
        target_memory_uid: str,
        target: Memory | None = None,
        *,
        snapshot_content_sha256: str | None = None,
        granted_source: GrantedMemorySource | None = None,
    ):
        relation_fields = (
            uid,
            target_context_uid,
            target_context_name,
            target_memory_uid,
        )
        if any(not isinstance(value, str) or not value for value in relation_fields):
            raise ValueError("Memory relationship fields must be nonempty text.")
        self.uid = uid
        self.target_context_uid = target_context_uid
        self.target_context_name = target_context_name
        self.target_memory_uid = target_memory_uid
        self.snapshot_content_sha256 = snapshot_content_sha256
        self.granted_source = granted_source
        if granted_source is not None and (
            granted_source.context_uid != target_context_uid
            or granted_source.access_name != target_context_name
            or granted_source.memory_uid != target_memory_uid
        ):
            raise ValueError(
                "Granted Memory Source does not match its relationship target."
            )
        if snapshot_content_sha256 is not None:
            if target is None:
                raise ValueError("A Memory snapshot reference requires content.")
            expected = hashlib.sha256(target.content.encode("utf-8")).hexdigest()
            if snapshot_content_sha256 != expected:
                raise ValueError("Memory snapshot content digest does not match.")
        # Keep a detached view so mutating ref.target cannot write through to
        # a source Context object. Live-parent serialization ignores this
        # content; snapshot serialization retains the detached exact value.
        self.target = (
            Memory(uid=target.uid, content=target.content)
            if target is not None
            else None
        )

    @property
    def is_resolved(self) -> bool:
        return self.target is not None

    @property
    def is_snapshot(self) -> bool:
        return self.snapshot_content_sha256 is not None

    @property
    def is_live(self) -> bool:
        return not self.is_snapshot

    @property
    def is_granted(self) -> bool:
        return self.granted_source is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialize one live identity link or exact immutable snapshot."""
        record: dict[str, Any] = {
            "type": (
                "memory_snapshot_ref"
                if self.is_snapshot
                else "granted_memory_ref"
                if self.is_granted
                else "memory_ref"
            ),
            "uid": self.uid,
            "target_context": {
                "uid": self.target_context_uid,
                "name": self.target_context_name,
            },
            "target_memory_uid": self.target_memory_uid,
        }
        if self.is_snapshot:
            if self.target is None or self.snapshot_content_sha256 is None:
                raise ValueError("Memory snapshot reference has no retained content.")
            expected = hashlib.sha256(self.target.content.encode("utf-8")).hexdigest()
            if expected != self.snapshot_content_sha256:
                raise ValueError("Memory snapshot content digest does not match.")
            record["content"] = self.target.content
            record["content_sha256"] = self.snapshot_content_sha256
        if self.granted_source is not None:
            record["grant_source"] = self.granted_source.to_dict()
        return record

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        target: Memory | None = None,
    ) -> MemoryRef:
        target_context = data["target_context"]
        kind = data.get("type")
        if kind not in {
            "memory_ref",
            "memory_snapshot_ref",
            "granted_memory_ref",
        }:
            raise ValueError("Memory relationship type is invalid.")
        if not isinstance(target_context, dict):
            raise ValueError("Memory relationship target Context is invalid.")
        if kind == "memory_snapshot_ref":
            content = data.get("content")
            digest = data.get("content_sha256")
            if not isinstance(content, str) or not isinstance(digest, str):
                raise ValueError("Memory snapshot reference is incomplete.")
            target = Memory(uid=data["target_memory_uid"], content=content)
        else:
            digest = None
        raw_granted_source = data.get("grant_source")
        if raw_granted_source is not None and not isinstance(raw_granted_source, dict):
            raise ValueError("Memory relationship Grant Source is invalid.")
        granted_source = (
            GrantedMemorySource.from_dict(raw_granted_source)
            if isinstance(raw_granted_source, dict)
            else None
        )
        if kind == "granted_memory_ref" and granted_source is None:
            raise ValueError("Granted Memory reference has no Grant Source.")
        if kind == "memory_ref" and granted_source is not None:
            raise ValueError("Local Memory Embed cannot carry Grant provenance.")
        return cls(
            uid=data["uid"],
            target_context_uid=target_context["uid"],
            target_context_name=target_context["name"],
            target_memory_uid=data["target_memory_uid"],
            target=target,
            snapshot_content_sha256=digest,
            granted_source=granted_source,
        )

    def copy(self) -> MemoryRef:
        """Copy the reference record while keeping the same target identity."""
        return MemoryRef(
            uid=self.uid,
            target_context_uid=self.target_context_uid,
            target_context_name=self.target_context_name,
            target_memory_uid=self.target_memory_uid,
            target=self.target,
            snapshot_content_sha256=self.snapshot_content_sha256,
            granted_source=self.granted_source,
        )


class QueryContextRef:
    """Opaque reference to a Context that can be accessed only through queries."""

    def __init__(
        self,
        uid: str,
        name: str,
        target_source_uid: str,
        provider: str,
    ):
        self.uid = uid
        self.name = name
        self.target_source_uid = target_source_uid
        self.provider = provider

    def to_dict(self) -> dict[str, Any]:
        """Serialize query routing metadata without serializing source content."""
        return {
            "type": "query_context_ref",
            "uid": self.uid,
            "name": self.name,
            "target_source_uid": self.target_source_uid,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryContextRef:
        return cls(
            uid=data["uid"],
            name=data["name"],
            target_source_uid=data["target_source_uid"],
            provider=data["provider"],
        )

    def copy(self) -> QueryContextRef:
        """Copy the pointer record while preserving its source identity."""
        return QueryContextRef(
            uid=self.uid,
            name=self.name,
            target_source_uid=self.target_source_uid,
            provider=self.provider,
        )


@dataclass(frozen=True)
class GrantedContextLink:
    """Revocable authority binding persisted without copied Context content."""

    context_uid: str
    access_name: str
    authority_context_name: str
    authority_profile_uid: str
    grantee_profile_uid: str
    grant_uid: str
    grant_revision_at_creation: int
    resource_uid: str
    resource_name: str

    def __post_init__(self) -> None:
        text_fields = (
            self.context_uid,
            self.access_name,
            self.authority_context_name,
            self.authority_profile_uid,
            self.grantee_profile_uid,
            self.grant_uid,
            self.resource_uid,
            self.resource_name,
        )
        if any(not isinstance(value, str) or not value for value in text_fields):
            raise ValueError("Granted Context link fields must be nonempty text.")
        if (
            isinstance(self.grant_revision_at_creation, bool)
            or not isinstance(self.grant_revision_at_creation, int)
            or self.grant_revision_at_creation < 1
        ):
            raise ValueError("Granted Context link revision must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "granted_context_ref",
            "uid": self.context_uid,
            "name": self.access_name,
            "authority_context_name": self.authority_context_name,
            "authority_profile_uid": self.authority_profile_uid,
            "grantee_profile_uid": self.grantee_profile_uid,
            "grant_uid": self.grant_uid,
            "grant_revision_at_creation": self.grant_revision_at_creation,
            "resource_uid": self.resource_uid,
            "resource_name": self.resource_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrantedContextLink":
        expected = {
            "type",
            "uid",
            "name",
            "authority_context_name",
            "authority_profile_uid",
            "grantee_profile_uid",
            "grant_uid",
            "grant_revision_at_creation",
            "resource_uid",
            "resource_name",
        }
        if not isinstance(data, dict) or set(data) != expected:
            raise ValueError("Granted Context link fields are invalid.")
        if data["type"] != "granted_context_ref":
            raise ValueError("Granted Context link type is invalid.")
        return cls(
            context_uid=data["uid"],
            access_name=data["name"],
            authority_context_name=data["authority_context_name"],
            authority_profile_uid=data["authority_profile_uid"],
            grantee_profile_uid=data["grantee_profile_uid"],
            grant_uid=data["grant_uid"],
            grant_revision_at_creation=data["grant_revision_at_creation"],
            resource_uid=data["resource_uid"],
            resource_name=data["resource_name"],
        )


class Context:
    """
    Abstract memory store.
    A Context is an ordered collection of Memories, MemoryRefs,
    QueryContextRefs, or other Contexts (nested by reference).
    """

    def __init__(self, uid: str, name: str):
        self.uid = uid
        self.name = name
        self.memories: dict[str, Information] = {}
        self.order: list[str] = []
        # A resolved granted embed remains a Context for every existing graph
        # traversal, but serialization must retain the revocable Grant binding
        # instead of degrading it into an ordinary same-Store context_ref.
        self._granted_link: GrantedContextLink | None = None
        # Set by MemoryStore loads and deliberately excluded from JSON. It is
        # the optimistic-concurrency base for a later save of this object.
        self._store_digest: str | None = None

    def ordered_uids(self) -> list[str]:
        """
        Return the canonical direct-item order.

        Invalid/duplicate entries are ignored and any items missing from an
        externally modified order list are appended in dict insertion order.
        """
        result: list[str] = []
        seen: set[str] = set()
        for uid in [*self.order, *self.memories.keys()]:
            if uid in self.memories and uid not in seen:
                result.append(uid)
                seen.add(uid)
        return result

    def iter_entries(self) -> Iterator[tuple[str, Information]]:
        """Iterate direct items in explicit Context order."""
        for uid in self.ordered_uids():
            yield uid, self.memories[uid]

    def iter_items(self) -> Iterator[Information]:
        """Iterate direct items in explicit Context order."""
        for _, info in self.iter_entries():
            yield info

    def add(
        self,
        info: str | Information,
        position: int | None = None,
    ) -> Information:
        """
        Add information to this context.
        If info is a plain string, it is wrapped in a new Memory automatically.
        New items are appended unless position is supplied. Replacing an
        existing uid keeps its current position.
        Returns the added Information (useful when a string was auto-promoted).
        """
        if isinstance(info, str):
            info = Memory(uid=str(uuid.uuid4()), content=info)

        current_order = self.ordered_uids()
        already_present = info.uid in self.memories
        self.memories[info.uid] = info

        if already_present:
            self.order = current_order
        elif position is None:
            self.order = [*current_order, info.uid]
        else:
            index = max(0, min(position, len(current_order)))
            self.order = [*current_order[:index], info.uid, *current_order[index:]]
        return info

    def remove(self, uid: str) -> None:
        if uid not in self.memories:
            raise KeyError(f"No item with uid '{uid}' in context '{self.name}'.")
        del self.memories[uid]
        self.order = [item_uid for item_uid in self.order if item_uid != uid]

    def clear(self) -> None:
        """Remove all direct items and their ordering metadata."""
        self.memories.clear()
        self.order.clear()

    def get_all(self) -> dict[str, Information]:
        return self.memories

    def replace(self, memory: Memory) -> None:
        """Replace a directly owned Memory in-place, preserving its position."""
        if memory.uid not in self.memories:
            raise KeyError(
                f"No memory with uid '{memory.uid}' in context '{self.name}'."
            )
        if not isinstance(self.memories[memory.uid], Memory):
            raise TypeError(f"'{memory.uid}' is not a directly owned Memory.")
        self.memories[memory.uid] = memory

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict. References are stored without target contents."""
        memories: dict[str, Any] = {}
        order: list[str] = []
        for uid, info in self.iter_entries():
            if isinstance(info, Memory):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, MemoryRef):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, QueryContextRef):
                memories[uid] = info.to_dict()
                order.append(uid)
            elif isinstance(info, Context):
                # Import lazily to keep the core Context model independent of
                # the snapshot package implementation. A Context Reference is
                # a Context subclass for read traversal but has its own durable
                # self-contained record and must be classified before a live
                # Context placement.
                from memcommit.application.capabilities.context_snapshot import (
                    ContextSnapshotRef,
                )

                memories[uid] = (
                    info.to_dict()
                    if isinstance(info, ContextSnapshotRef)
                    else (
                        info._granted_link.to_dict()
                        if info._granted_link is not None
                        else {
                            "type": "context_ref",
                            "uid": info.uid,
                            "name": info.name,
                        }
                    )
                )
                order.append(uid)
        return {
            "uid": self.uid,
            "name": self.name,
            "memories": memories,
            "order": order,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        loader: Callable[[str], Context | None] | None = None,
        memory_loader: Callable[[str, str, str], Memory | None] | None = None,
        granted_memory_loader: Callable[[GrantedMemorySource], Memory | None]
        | None = None,
        granted_loader: Callable[[GrantedContextLink], Context | None] | None = None,
    ) -> Context:
        """
        Deserialize from a dict produced by to_dict().
        loader(name) is called to resolve context_refs. If no loader is
        supplied, the pointer is retained as an empty Context carrying only
        its serialized uid and name; referenced content is not opened. If a
        supplied loader returns None, the unresolved ref is skipped.

        memory_loader(context_name, context_uid, memory_uid) resolves memory_refs.
        A memory_ref is retained with target=None when it cannot be resolved.
        Files without an explicit order use their memories key order.
        """
        ctx = cls(uid=data["uid"], name=data["name"])
        serialized = data.get("memories", {})
        requested_order = data.get("order")
        keys: list[str] = []
        seen: set[str] = set()

        if isinstance(requested_order, list):
            for uid in requested_order:
                if isinstance(uid, str) and uid in serialized and uid not in seen:
                    keys.append(uid)
                    seen.add(uid)
        for uid in serialized:
            if uid not in seen:
                keys.append(uid)
                seen.add(uid)

        for uid in keys:
            item = serialized[uid]
            if item["type"] == "memory":
                ctx.add(Memory.from_dict(item))
            elif item["type"] in {
                "memory_ref",
                "memory_snapshot_ref",
                "granted_memory_ref",
            }:
                # Validate the complete relationship and Grant-to-target
                # identity binding before any live loader can open Source
                # bytes. A malformed durable pointer must fail closed without
                # turning one tampered field into an external read request.
                reference = MemoryRef.from_dict(item)
                target_context = item["target_context"]
                target = None
                if item["type"] == "memory_ref" and memory_loader is not None:
                    target = memory_loader(
                        target_context["name"],
                        target_context["uid"],
                        item["target_memory_uid"],
                    )
                elif (
                    item["type"] == "granted_memory_ref"
                    and granted_memory_loader is not None
                ):
                    assert reference.granted_source is not None
                    target = granted_memory_loader(reference.granted_source)
                ctx.add(
                    reference
                    if target is None
                    else MemoryRef.from_dict(item, target=target)
                )
            elif item["type"] == "query_context_ref":
                ctx.add(QueryContextRef.from_dict(item))
            elif item["type"] == "context_ref":
                # Direct, non-resolving reads still need the pointer's slot in
                # canonical order. Dropping it can shift a later insertion and
                # makes a read-only Context impossible to serialize faithfully.
                nested = (
                    Context(uid=item["uid"], name=item["name"])
                    if loader is None
                    else loader(item["name"])
                )
                # Names are locators, not identity. A deleted/recreated
                # Context must never silently capture an old embed merely
                # because it reused the same path; this also makes Context
                # namespace rename safe to drive by the persisted target UID.
                if nested is not None and nested.uid != item["uid"]:
                    nested = None
                if nested is not None:
                    ctx.add(nested)
            elif item["type"] == "context_snapshot_ref":
                from memcommit.application.capabilities.context_snapshot import (
                    ContextSnapshotRef,
                )

                ctx.add(ContextSnapshotRef.from_dict(item))
            elif item["type"] == "granted_context_ref":
                link = GrantedContextLink.from_dict(item)
                # Direct reads retain an opaque, serializable placeholder.
                # Recursive reads supply a reauthorizing loader; it may raise
                # when the Grant or exact authority identity is unavailable.
                nested = (
                    Context(uid=link.context_uid, name=link.access_name)
                    if granted_loader is None
                    else granted_loader(link)
                )
                if nested is not None and nested.uid != link.context_uid:
                    nested = None
                if nested is not None:
                    if granted_loader is None:
                        nested.name = link.access_name
                    if nested._granted_link is None:
                        nested._granted_link = link
                    ctx.add(nested)
        return ctx


# A direct item is an atomic Memory, a read-only live/snapshot MemoryRef, an
# opaque QueryContextRef, or a nested Context.
Information: TypeAlias = Memory | MemoryRef | QueryContextRef | Context


@dataclass
class AutoCheckpoint:
    """Passed to store.save() to trigger an automatic post-operation checkpoint."""

    command: str
    args: dict[str, Any]
    description: str


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a context's direct state."""

    uid: str
    message: str
    timestamp: datetime
    snapshot: dict[str, Any]  # result of ctx.to_dict() at checkpoint time
    command: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    description: Optional[str] = None
    auto: bool = False
