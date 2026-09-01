"""Self-contained immutable snapshots of one local Context scope.

Context Embed stores a live pointer.  A Context Reference instead stores a
versioned package of direct Context records.  Direct scope freezes only the
selected record; recursive scope additionally freezes lexical descendants and
authorized Contexts reached through Embed edges.  Granted edges encountered
incidentally remain opaque; an explicitly selected READ-granted root may carry
frozen Grant provenance for the records the operation retained.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from memcommit.core.context import (
    Context,
    GrantedContextLink,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.application.context_access.model import GrantedContextBinding


CONTEXT_SNAPSHOT_SCHEMA_VERSION = 1


def context_snapshot_digest(package: Mapping[str, object]) -> str:
    """Hash one complete immutable package with a canonical JSON encoding."""

    encoded = json.dumps(
        package,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Context snapshot {label} must be nonempty text.")
    return value


def _records(package: Mapping[str, object]) -> tuple[dict[str, Any], ...]:
    raw_records = package.get("contexts")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("Context snapshot package requires Context records.")
    records: list[dict[str, Any]] = []
    names: set[str] = set()
    uids: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise ValueError("Context snapshot record must be an object.")
        # Context.from_dict is the authored direct-record validator.  Parse it
        # without loaders so package validation never reaches live storage.
        parsed = Context.from_dict(raw)
        if parsed.name in names or parsed.uid in uids:
            raise ValueError("Context snapshot records must have unique identities.")
        names.add(parsed.name)
        uids.add(parsed.uid)
        records.append(raw)
    return tuple(records)


def validate_context_snapshot_package(
    package: Mapping[str, object],
) -> dict[str, object]:
    """Return a detached validated package or fail closed."""

    if not isinstance(package, Mapping):
        raise TypeError("Context snapshot package must be an object.")
    if set(package) != {
        "schema_version",
        "root",
        "recursive",
        "lexical_context_names",
        "contexts",
    }:
        raise ValueError("Context snapshot package has unsupported fields.")
    if package.get("schema_version") != CONTEXT_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Unsupported Context snapshot schema version.")
    root = package.get("root")
    if not isinstance(root, Mapping):
        raise ValueError("Context snapshot package requires one root identity.")
    root_uid = _text(root.get("uid"), label="root UID")
    root_name = _text(root.get("name"), label="root name")
    recursive = package.get("recursive")
    if type(recursive) is not bool:
        raise ValueError("Context snapshot recursive scope must be boolean.")
    lexical = package.get("lexical_context_names")
    if not isinstance(lexical, list) or any(
        not isinstance(name, str) or not name for name in lexical
    ):
        raise ValueError("Context snapshot lexical names are invalid.")
    if len(set(lexical)) != len(lexical) or not lexical or lexical[0] != root_name:
        raise ValueError("Context snapshot lexical names must start at the root.")
    if not recursive and lexical != [root_name]:
        raise ValueError("A direct Context snapshot cannot include descendants.")
    records = _records(package)
    by_name = {record["name"]: record for record in records}
    if root_name not in by_name or by_name[root_name]["uid"] != root_uid:
        raise ValueError("Context snapshot root does not match its retained record.")
    if any(name not in by_name for name in lexical):
        raise ValueError("Context snapshot lexical scope is incomplete.")
    # Round-trip through canonical JSON to detach caller-owned nested values.
    return json.loads(
        json.dumps(package, ensure_ascii=False, separators=(",", ":"))
    )


def _hydrate_package(package: Mapping[str, object]) -> Context:
    """Build an in-memory read-only graph without consulting live storage."""

    records = _records(package)
    shells = {
        record["name"]: Context(uid=record["uid"], name=record["name"])
        for record in records
    }
    records_by_name = {record["name"]: record for record in records}

    for name, shell in shells.items():
        record = records_by_name[name]
        serialized = record.get("memories", {})
        if not isinstance(serialized, dict):
            raise ValueError("Context snapshot record has invalid direct items.")
        order = record.get("order")
        ordered = list(order) if isinstance(order, list) else list(serialized)
        ordered.extend(uid for uid in serialized if uid not in ordered)
        seen: set[str] = set()
        for uid in ordered:
            if not isinstance(uid, str) or uid in seen or uid not in serialized:
                continue
            seen.add(uid)
            item = serialized[uid]
            if not isinstance(item, dict):
                raise ValueError("Context snapshot direct item must be an object.")
            kind = item.get("type")
            if kind == "memory":
                shell.add(Memory.from_dict(item))
            elif kind in {
                "memory_ref",
                "memory_snapshot_ref",
                "granted_memory_ref",
            }:
                shell.add(MemoryRef.from_dict(item))
            elif kind == "query_context_ref":
                shell.add(QueryContextRef.from_dict(item))
            elif kind == "context_ref":
                target_name = _text(item.get("name"), label="embedded Context name")
                target_uid = _text(item.get("uid"), label="embedded Context UID")
                target = shells.get(target_name)
                if target is None or target.uid != target_uid:
                    target = Context(uid=target_uid, name=target_name)
                shell.add(target)
            elif kind == "granted_context_ref":
                link = GrantedContextLink.from_dict(item)
                target = Context(uid=link.context_uid, name=link.public_name)
                target._granted_link = link
                shell.add(target)
            elif kind == "context_snapshot_ref":
                shell.add(ContextSnapshotRef.from_dict(item))
            else:
                raise ValueError(f"Unsupported Context snapshot item type: {kind!r}.")

    root_info = package["root"]
    assert isinstance(root_info, Mapping)
    root_name = str(root_info["name"])
    root = shells[root_name]
    # Lexical descendants are an independent axis from Embed reach. Attach each
    # otherwise-unreachable row to its nearest retained lexical parent so the
    # frozen public hierarchy stays inspectable without inventing Embed edges.
    reachable: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in reachable:
            return
        reachable.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    lexical = package["lexical_context_names"]
    assert isinstance(lexical, list)
    for name in lexical[1:]:
        child = shells[name]
        if child.uid not in reachable:
            child._snapshot_relation = "DESCENDANT"
            parent_name = max(
                (
                    candidate
                    for candidate in lexical
                    if candidate != name and name.startswith(candidate + "/")
                ),
                key=len,
                default=root_name,
            )
            shells[parent_name].add(child)
            visit(child)
    return root


class ContextSnapshotRef(Context):
    """One direct immutable Context Reference with a frozen readable body.

    It subclasses ``Context`` so existing read-only graph traversal can inspect
    retained content.  Its direct-item UID is distinct from the Source Context
    UID, which is kept as provenance just like a Memory Reference.
    """

    def __init__(
        self,
        *,
        uid: str,
        target_context_uid: str,
        target_context_name: str,
        snapshot_package: Mapping[str, object],
        snapshot_content_sha256: str,
        granted_sources: tuple[GrantedContextBinding, ...] = (),
    ) -> None:
        package = validate_context_snapshot_package(snapshot_package)
        expected = context_snapshot_digest(package)
        if snapshot_content_sha256 != expected:
            raise ValueError("Context snapshot content digest does not match.")
        root = package["root"]
        assert isinstance(root, Mapping)
        if (
            root.get("uid") != target_context_uid
            or root.get("name") != target_context_name
        ):
            raise ValueError("Context snapshot provenance does not match its root.")
        if (
            not isinstance(granted_sources, tuple)
            or any(
                not isinstance(source, GrantedContextBinding)
                for source in granted_sources
            )
            or len({source.public_name for source in granted_sources})
            != len(granted_sources)
            or any("READ" not in source.permissions for source in granted_sources)
        ):
            raise ValueError("Context snapshot granted Source provenance is invalid.")
        super().__init__(uid=uid, name=target_context_name)
        retained = _hydrate_package(package)
        self.memories = retained.memories
        self.order = retained.order
        self.target_context_uid = target_context_uid
        self.target_context_name = target_context_name
        self.snapshot_package = package
        self.snapshot_content_sha256 = snapshot_content_sha256
        self.include_descendants = bool(package["recursive"])
        self.follow_embeds = bool(package["recursive"])
        self.granted_sources = granted_sources

    @property
    def is_snapshot(self) -> bool:
        return True

    def to_dict(self) -> dict[str, object]:
        package = validate_context_snapshot_package(self.snapshot_package)
        digest = context_snapshot_digest(package)
        if digest != self.snapshot_content_sha256:
            raise ValueError("Context snapshot content digest does not match.")
        record: dict[str, object] = {
            "type": "context_snapshot_ref",
            "uid": self.uid,
            "target_context": {
                "uid": self.target_context_uid,
                "name": self.target_context_name,
            },
            "snapshot": package,
            "content_sha256": self.snapshot_content_sha256,
        }
        if self.granted_sources:
            record["grant_sources"] = [
                source.to_dict() for source in self.granted_sources
            ]
        return record

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ContextSnapshotRef":
        target = data.get("target_context")
        if not isinstance(target, Mapping):
            raise ValueError("Context snapshot reference has no Source identity.")
        snapshot = data.get("snapshot")
        if not isinstance(snapshot, Mapping):
            raise ValueError("Context snapshot reference has no retained package.")
        digest = data.get("content_sha256")
        raw_granted_sources = data.get("grant_sources", [])
        if not isinstance(raw_granted_sources, list):
            raise ValueError("Context snapshot granted Sources must be a list.")
        return cls(
            uid=_text(data.get("uid"), label="reference UID"),
            target_context_uid=_text(target.get("uid"), label="Source UID"),
            target_context_name=_text(target.get("name"), label="Source name"),
            snapshot_package=snapshot,
            snapshot_content_sha256=_text(digest, label="content digest"),
            granted_sources=tuple(
                GrantedContextBinding.from_dict(source)
                for source in raw_granted_sources
            ),
        )

    def copy(self) -> "ContextSnapshotRef":
        return ContextSnapshotRef.from_dict(self.to_dict())


def snapshot_record_with_frozen_memory_embeds(
    direct: Context,
    resolved: Context,
) -> dict[str, object]:
    """Freeze one direct record and any currently resolved live Memory links."""

    record = direct.to_dict()
    raw_items = record.get("memories")
    if not isinstance(raw_items, dict):
        raise ValueError("Context snapshot Source record is invalid.")
    for uid, direct_item in direct.iter_entries():
        if not isinstance(direct_item, MemoryRef) or direct_item.is_snapshot:
            continue
        if direct_item.is_granted:
            # Preserve the live authority boundary. Freezing resolved bytes
            # here would silently change this revocable relationship into a
            # retained value, so keep its content-free binding opaque.
            continue
        resolved_item = resolved.memories.get(uid)
        if not isinstance(resolved_item, MemoryRef) or resolved_item.target is None:
            # A dangling live link stays as frozen dangling provenance.
            continue
        digest = hashlib.sha256(
            resolved_item.target.content.encode("utf-8")
        ).hexdigest()
        raw_items[uid] = {
            "type": "memory_snapshot_ref",
            "uid": uid,
            "target_context": {
                "uid": direct_item.target_context_uid,
                "name": direct_item.target_context_name,
            },
            "target_memory_uid": direct_item.target_memory_uid,
            "content": resolved_item.target.content,
            "content_sha256": digest,
            "snapshot_origin": "embed",
        }
    return record


__all__ = [
    "CONTEXT_SNAPSHOT_SCHEMA_VERSION",
    "ContextSnapshotRef",
    "context_snapshot_digest",
    "snapshot_record_with_frozen_memory_embeds",
    "validate_context_snapshot_package",
]
