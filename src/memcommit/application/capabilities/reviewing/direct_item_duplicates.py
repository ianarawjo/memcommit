"""Pure role-aware exact-duplicate discovery for one direct Context.

Occurrence UIDs deliberately do not participate in equality.  Every other
identity field remains role-owned so equal visible content cannot collapse an
owned Memory, live Embed, or immutable Reference into another role.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.capabilities.context_snapshot import ContextSnapshotRef


ExactDuplicateKind = Literal[
    "MEMORY",
    "MEMORY_EMBED",
    "CONTEXT_EMBED",
    "MEMORY_REFERENCE",
    "CONTEXT_REFERENCE",
]


@dataclass(frozen=True)
class ExactDuplicateGroup:
    """One same-role exact-identity group in direct Context order."""

    item_kind: ExactDuplicateKind
    survivor_uid: str
    absorbed_uids: tuple[str, ...]
    summary: str
    content: str | None = None

    @property
    def duplicate_count(self) -> int:
        return len(self.absorbed_uids)


@dataclass(frozen=True)
class _ExactItem:
    uid: str
    kind: ExactDuplicateKind
    key: tuple[str, ...]
    summary: str
    content: str | None = None


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _exact_item(item: object) -> _ExactItem | None:
    if isinstance(item, Memory):
        return _ExactItem(
            uid=item.uid,
            kind="MEMORY",
            key=("MEMORY", item.content),
            summary=item.content,
            content=item.content,
        )

    if isinstance(item, MemoryRef):
        target = (
            item.target_context_uid,
            item.target_context_name,
            item.target_memory_uid,
        )
        if item.is_live:
            return _ExactItem(
                uid=item.uid,
                kind="MEMORY_EMBED",
                key=("MEMORY_EMBED", *target),
                summary=(
                    f"{item.target_context_name}#{item.target_memory_uid[:8]} "
                    "\u00b7 LIVE"
                ),
            )
        # Snapshot construction verifies that the retained content matches the
        # digest.  Keep both in the key so exact equality never relies on a
        # digest collision or loses Source-version provenance.
        snapshot_content = item.target.content if item.target is not None else ""
        snapshot_digest = item.snapshot_content_sha256 or ""
        return _ExactItem(
            uid=item.uid,
            kind="MEMORY_REFERENCE",
            key=(
                "MEMORY_REFERENCE",
                *target,
                snapshot_digest,
                snapshot_content,
            ),
            summary=(
                f"{item.target_context_name}#{item.target_memory_uid[:8]} "
                f"\u00b7 SNAPSHOT {snapshot_digest[:12]}"
            ),
            content=snapshot_content,
        )

    # ContextSnapshotRef is a Context subclass and must be classified before
    # live Context embeds.  Its package preserves scope and Source bindings.
    if isinstance(item, ContextSnapshotRef):
        package = _canonical_json(item.snapshot_package)
        return _ExactItem(
            uid=item.uid,
            kind="CONTEXT_REFERENCE",
            key=(
                "CONTEXT_REFERENCE",
                item.target_context_uid,
                item.target_context_name,
                item.snapshot_content_sha256,
                package,
            ),
            summary=(
                f"{item.target_context_name} \u00b7 SNAPSHOT "
                f"{item.snapshot_content_sha256[:12]}"
            ),
        )

    if isinstance(item, Context):
        if item._granted_link is not None:
            binding = _canonical_json(item._granted_link.to_dict())
            summary = f"{item.name} \u00b7 GRANT {item._granted_link.grant_uid[:8]}"
        else:
            binding = _canonical_json({"uid": item.uid, "name": item.name})
            summary = f"{item.name} \u00b7 LIVE"
        return _ExactItem(
            uid=item.uid,
            kind="CONTEXT_EMBED",
            key=("CONTEXT_EMBED", binding),
            summary=summary,
        )

    if isinstance(item, QueryContextRef):
        # Query-only routes have a separate authorization and execution
        # contract.  Treating them as ordinary References would erase that
        # boundary, so their cleanup remains an intentional non-goal.
        return None
    return None


def find_exact_duplicate_groups(
    context: Context,
) -> tuple[ExactDuplicateGroup, ...]:
    """Group same-role exact direct items while preserving first occurrence."""

    if not isinstance(context, Context):
        raise TypeError("Exact duplicate discovery requires one Context.")
    members_by_key: dict[tuple[str, ...], list[_ExactItem]] = {}
    key_order: list[tuple[str, ...]] = []
    for item in context.iter_items():
        candidate = _exact_item(item)
        if candidate is None:
            continue
        if candidate.key not in members_by_key:
            members_by_key[candidate.key] = []
            key_order.append(candidate.key)
        members_by_key[candidate.key].append(candidate)

    groups: list[ExactDuplicateGroup] = []
    for key in key_order:
        members = members_by_key[key]
        if len(members) < 2:
            continue
        first = members[0]
        groups.append(
            ExactDuplicateGroup(
                item_kind=first.kind,
                survivor_uid=first.uid,
                absorbed_uids=tuple(member.uid for member in members[1:]),
                summary=first.summary,
                content=first.content,
            )
        )
    return tuple(groups)


__all__ = [
    "ExactDuplicateGroup",
    "ExactDuplicateKind",
    "find_exact_duplicate_groups",
]
