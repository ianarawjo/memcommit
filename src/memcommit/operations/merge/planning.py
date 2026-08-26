"""Pure deterministic classification and materialization for structural Merge."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping
import uuid

from memcommit.context import Context, Information, Memory, MemoryRef, QueryContextRef
from memcommit.retained_history.context_snapshot import ContextSnapshotRef
from memcommit.operations.merge.application import (
    MergeAddition,
    MergeConflict,
    MergeConflictKind,
    MergeDecision,
    MergeItemKind,
    MergeItemSnapshot,
    MergeResolution,
)


@dataclass(frozen=True)
class MergeMemoryMapping:
    """One Source Memory occurrence and its exact planned Target occurrence."""

    source_uid: str
    target_uid: str


@dataclass(frozen=True)
class PlannedContextMerge:
    """Complete deterministic classification for one Source/Target mapping."""

    additions: tuple[MergeAddition, ...]
    unchanged: tuple[MergeItemSnapshot, ...]
    conflicts: tuple[MergeConflict, ...]
    memory_mappings: tuple[MergeMemoryMapping, ...]


def merge_item_kind(item: Information) -> MergeItemKind:
    if isinstance(item, Memory):
        return MergeItemKind.MEMORY
    if isinstance(item, MemoryRef):
        return MergeItemKind.MEMORY_REF
    if isinstance(item, QueryContextRef):
        return MergeItemKind.QUERY_VIEW
    if isinstance(item, Context):
        return MergeItemKind.CONTEXT
    raise TypeError("Merge received an unsupported direct item.")


def merge_item_snapshot(item: Information) -> MergeItemSnapshot:
    """Project one direct item into stable review evidence."""

    kind = merge_item_kind(item)
    if isinstance(item, Memory):
        return MergeItemSnapshot(
            uid=item.uid,
            kind=kind,
            description=f"Memory [{item.uid[:8]}]",
            content=item.content,
        )
    if isinstance(item, MemoryRef):
        description = (
            f"Memory reference [{item.uid[:8]}] → "
            f"{item.target_context_name} / [{item.target_memory_uid[:8]}]"
        )
    elif isinstance(item, QueryContextRef):
        description = (
            f"Query view [{item.uid[:8]}] · {item.name} → "
            f"[{item.target_source_uid[:8]}] via {item.provider}"
        )
    else:
        assert isinstance(item, Context)
        description = f"Context placement [{item.uid[:8]}] · {item.name}"
    return MergeItemSnapshot(
        uid=item.uid,
        kind=kind,
        description=description,
    )


def copy_merge_item(
    item: Information,
    *,
    memory_uid: str | None = None,
) -> Information:
    """Copy a direct item without sharing a writable Memory value."""

    if isinstance(item, Memory):
        return Memory(uid=memory_uid or item.uid, content=item.content)
    if memory_uid is not None:
        raise ValueError("Only a Memory may receive a new Merge occurrence UID.")
    if isinstance(item, (MemoryRef, QueryContextRef)):
        return item.copy()
    if isinstance(item, ContextSnapshotRef):
        return item.copy()
    if isinstance(item, Context):
        # A Context item is a placement pointer. Copy only that pointer here;
        # recursive path materialization is handled before this layer.
        copied = Context(uid=item.uid, name=item.name)
        copied._granted_link = item._granted_link  # noqa: SLF001
        return copied
    raise TypeError("Merge received an unsupported direct item.")


def copy_merge_context(context: Context) -> Context:
    """Copy one direct Context record while preserving canonical order."""

    copied = Context(uid=context.uid, name=context.name)
    for item in context.iter_items():
        copied.add(copy_merge_item(item))
    copied._store_digest = context._store_digest  # noqa: SLF001
    return copied


def _record(item: Information) -> dict[str, object]:
    value = item.to_dict()
    if not isinstance(value, dict):  # pragma: no cover - closed direct item model.
        raise TypeError("Merge item serialization is invalid.")
    return value


def _logical_reference_match(left: Information, right: Information) -> bool:
    if isinstance(left, MemoryRef) and isinstance(right, MemoryRef):
        return (
            left.is_snapshot == right.is_snapshot
            and left.target_context_uid == right.target_context_uid
            and left.target_memory_uid == right.target_memory_uid
            and (
                left.is_live
                or left.snapshot_content_sha256 == right.snapshot_content_sha256
            )
        )
    if isinstance(left, QueryContextRef) and isinstance(right, QueryContextRef):
        return left.target_source_uid == right.target_source_uid
    return False


def _context_like_name_match(left: Information, right: Information) -> bool:
    return (
        isinstance(left, (Context, QueryContextRef))
        and isinstance(right, (Context, QueryContextRef))
        and left.name == right.name
    )


def _conflict_kind(source: Information, target: Information) -> MergeConflictKind:
    if type(source) is not type(target):
        return MergeConflictKind.TYPE_COLLISION
    if isinstance(source, Memory):
        return MergeConflictKind.CONTENT_DIVERGENCE
    if isinstance(source, Context):
        return MergeConflictKind.PLACEMENT_COLLISION
    return MergeConflictKind.REFERENCE_COLLISION


def _conflict_reason(kind: MergeConflictKind) -> str:
    return {
        MergeConflictKind.CONTENT_DIVERGENCE: (
            "The Source Memory is related to an existing Target occurrence "
            "but their content differs."
        ),
        MergeConflictKind.TYPE_COLLISION: (
            "The same direct-item identity is used by unlike item types."
        ),
        MergeConflictKind.REFERENCE_COLLISION: (
            "Source and Target contain incompatible or duplicate logical references."
        ),
        MergeConflictKind.PLACEMENT_COLLISION: (
            "Source and Target claim an incompatible Context-like placement."
        ),
    }[kind]


def _conflict_uid(
    *,
    source_name: str,
    target_name: str,
    source: Information,
    targets: tuple[Information, ...],
    kind: MergeConflictKind,
) -> str:
    # Include the complete mapping and every member identity so recursive or
    # repeated placements cannot accidentally share a decision key.
    payload = {
        "source_name": source_name,
        "target_name": target_name,
        "source_uid": source.uid,
        "source_record": _record(source),
        "target_uids": [item.uid for item in targets],
        "target_records": [_record(item) for item in targets],
        "kind": kind.value,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"merge-conflict:{digest[:20]}"


def plan_context_merge(
    source: Context,
    target: Context,
    *,
    source_name: str,
    target_name: str,
    take_source_allowed: bool = True,
    target_context_mutable: bool = True,
    protected_target_uids: frozenset[str] = frozenset(),
    lineage_target_uids: Mapping[str, str] | None = None,
) -> PlannedContextMerge:
    """Classify every direct Source item once without mutating either Context."""

    if type(take_source_allowed) is not bool:
        raise TypeError("Merge Take Source availability must be a boolean.")
    if type(target_context_mutable) is not bool:
        raise TypeError("Merge Target mutability must be a boolean.")
    if not isinstance(protected_target_uids, frozenset) or any(
        not isinstance(uid, str) or not uid for uid in protected_target_uids
    ):
        raise TypeError("Merge protected Target identities must be frozen text.")
    lineage_targets = dict(lineage_target_uids or {})
    if any(
        not isinstance(source_uid, str)
        or not source_uid
        or not isinstance(target_uid, str)
        or not target_uid
        for source_uid, target_uid in lineage_targets.items()
    ):
        raise TypeError("Merge lineage target identities must be text.")

    additions: list[MergeAddition] = []
    unchanged: list[MergeItemSnapshot] = []
    conflicts: list[MergeConflict] = []
    memory_mappings: list[MergeMemoryMapping] = []
    target_items = tuple(target.iter_items())

    for source_item in source.iter_items():
        same_uid = target.memories.get(source_item.uid)
        if same_uid is None and isinstance(source_item, Memory):
            lineage_target_uid = lineage_targets.get(source_item.uid)
            if lineage_target_uid is not None:
                candidate = target.memories.get(lineage_target_uid)
                if not isinstance(candidate, Memory):
                    raise ValueError(
                        "Checkpoint lineage names an unavailable Target Memory."
                    )
                same_uid = candidate
        if same_uid is not None:
            if isinstance(source_item, Memory) and isinstance(same_uid, Memory):
                memory_mappings.append(
                    MergeMemoryMapping(
                        source_uid=source_item.uid,
                        target_uid=same_uid.uid,
                    )
                )
            equivalent = (
                source_item.content == same_uid.content
                if isinstance(source_item, Memory) and isinstance(same_uid, Memory)
                else type(source_item) is type(same_uid)
                and _record(source_item) == _record(same_uid)
            )
            if equivalent:
                unchanged.append(merge_item_snapshot(source_item))
                continue
            colliders = (same_uid,)
            kind = _conflict_kind(source_item, same_uid)
        else:
            reference_colliders = tuple(
                item
                for item in target_items
                if _logical_reference_match(source_item, item)
            )
            placement_colliders = tuple(
                item
                for item in target_items
                if _context_like_name_match(source_item, item)
            )
            colliders = tuple(
                dict.fromkeys((*reference_colliders, *placement_colliders))
            )
            if reference_colliders:
                kind = MergeConflictKind.REFERENCE_COLLISION
            elif placement_colliders:
                kind = MergeConflictKind.PLACEMENT_COLLISION
            else:
                target_uid = (
                    str(uuid.uuid4()) if isinstance(source_item, Memory) else None
                )
                additions.append(
                    MergeAddition(
                        uid=source_item.uid,
                        kind=merge_item_kind(source_item),
                        target_uid=target_uid,
                    )
                )
                if target_uid is not None:
                    memory_mappings.append(
                        MergeMemoryMapping(
                            source_uid=source_item.uid,
                            target_uid=target_uid,
                        )
                    )
                continue

        conflicts.append(
            MergeConflict(
                uid=_conflict_uid(
                    source_name=source_name,
                    target_name=target_name,
                    source=source_item,
                    targets=colliders,
                    kind=kind,
                ),
                kind=kind,
                source_name=source_name,
                target_name=target_name,
                source=merge_item_snapshot(source_item),
                targets=tuple(merge_item_snapshot(item) for item in colliders),
                reason=_conflict_reason(kind),
                allowed_decisions=(
                    (
                        MergeDecision.KEEP_TARGET,
                        MergeDecision.TAKE_SOURCE,
                    )
                    if take_source_allowed
                    and target_context_mutable
                    and not any(
                        item.uid in protected_target_uids for item in colliders
                    )
                    else (MergeDecision.KEEP_TARGET,)
                ),
            )
        )

    return PlannedContextMerge(
        additions=tuple(additions),
        unchanged=tuple(unchanged),
        conflicts=tuple(conflicts),
        memory_mappings=tuple(memory_mappings),
    )


def materialize_context_merge(
    source: Context,
    target: Context,
    plan: PlannedContextMerge,
    *,
    resolutions: Mapping[str, MergeDecision],
) -> Context:
    """Build the exact post-image selected for one frozen mapping."""

    candidate = copy_merge_context(target)
    for addition in plan.additions:
        candidate.add(
            copy_merge_item(
                source.memories[addition.uid],
                memory_uid=addition.target_uid,
            )
        )

    for conflict in plan.conflicts:
        decision = resolutions.get(conflict.uid)
        if decision is None:
            raise ValueError(f"Merge conflict '{conflict.uid}' is unresolved.")
        if decision is MergeDecision.KEEP_TARGET:
            continue
        if decision is not MergeDecision.TAKE_SOURCE:
            raise TypeError("Merge materialization received an invalid decision.")
        target_uids = [item.uid for item in conflict.targets]
        positions = [
            candidate.ordered_uids().index(uid)
            for uid in target_uids
            if uid in candidate.memories
        ]
        position = min(positions) if positions else None
        for uid in target_uids:
            if uid in candidate.memories:
                candidate.remove(uid)
        source_item = source.memories[conflict.source.uid]
        replacement_uid = (
            target_uids[0]
            if isinstance(source_item, Memory)
            and len(target_uids) == 1
            and isinstance(target.memories.get(target_uids[0]), Memory)
            else None
        )
        candidate.add(
            copy_merge_item(source_item, memory_uid=replacement_uid),
            position=position,
        )
    return candidate


def resolution_map(
    resolutions: tuple[MergeResolution, ...],
) -> dict[str, MergeDecision]:
    """Project a validated ordered resolution tuple for materialization."""

    result: dict[str, MergeDecision] = {}
    for resolution in resolutions:
        if resolution.conflict_uid in result:
            raise ValueError("Merge materialization received a duplicate resolution.")
        result[resolution.conflict_uid] = resolution.decision
    return result
