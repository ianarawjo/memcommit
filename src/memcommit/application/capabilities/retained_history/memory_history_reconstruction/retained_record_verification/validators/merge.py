"""Validate retained Merge decisions and cross-Context lineage transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from memcommit.application.capabilities.retained_history.memory_lineage import (
    MemoryLineageEdge,
    parse_memory_lineage_receipt,
)

from ..checkpoint import _checkpoint_fields
from ..frame import _Frame, _empty_frame, _frame_from_snapshot
from ..model import (
    MemoryHistoryCommandContext,
    MemoryHistoryCommandOperation,
    MemoryHistoryReconstructionError,
)


@dataclass(frozen=True)
class _RecordedMergeEdge:
    """One disposition-complete Source/Target occurrence mapping."""

    edge: MemoryLineageEdge
    disposition: Literal[
        "NEW",
        "ALREADY_PRESENT",
        "TAKE_SOURCE",
        "KEEP_TARGET",
    ]


@dataclass(frozen=True)
class _RecordedMergeTransition:
    """Validated same-Store Merge evidence anchored by its target checkpoint."""

    checkpoint_uid: str
    timestamp: str
    description: str
    operation_uid: str
    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext
    command_operation: MemoryHistoryCommandOperation
    before: _Frame
    after: _Frame
    edges: tuple[_RecordedMergeEdge, ...]


def _merge_decisions(
    args: dict[str, Any],
) -> dict[tuple[str, str], Literal["TAKE_SOURCE", "KEEP_TARGET"]]:
    """Validate the reviewed per-occurrence Merge dispositions."""

    record = args.get("merge_decisions")
    if not isinstance(record, dict) or set(record) != {"version", "decisions"}:
        raise ValueError("Merge decision metadata is invalid.")
    raw_decisions = record.get("decisions")
    if record.get("version") != 1 or not isinstance(raw_decisions, list):
        raise ValueError("Merge decision metadata is invalid.")
    result: dict[tuple[str, str], Literal["TAKE_SOURCE", "KEEP_TARGET"]] = {}
    expected = {
        "conflict_uid",
        "kind",
        "decision",
        "source_name",
        "target_name",
        "source_uid",
        "target_uids",
    }
    for raw in raw_decisions:
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("Merge decision metadata is invalid.")
        decision = raw.get("decision")
        source_uid = raw.get("source_uid")
        target_uids = raw.get("target_uids")
        if (
            decision not in {"TAKE_SOURCE", "KEEP_TARGET"}
            or not isinstance(source_uid, str)
            or not source_uid
            or not isinstance(target_uids, list)
            or not target_uids
            or any(not isinstance(uid, str) or not uid for uid in target_uids)
            or len(target_uids) != len(set(target_uids))
        ):
            raise ValueError("Merge decision metadata is invalid.")
        for target_uid in target_uids:
            key = (source_uid, target_uid)
            if key in result:
                raise ValueError("Merge decision metadata repeats an occurrence.")
            result[key] = decision
    return result


def _recorded_merge_transition(
    entry: dict,
) -> tuple[_RecordedMergeTransition | None, str | None]:
    """Validate one Merge checkpoint before it can join two Trace owners."""

    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "merge" or "memory_lineage" not in args:
        return None, None
    warning = (
        f"Checkpoint [{checkpoint_uid[:8]}] has invalid Merge Memory lineage "
        "metadata; Source and Target histories were not connected."
    )
    tree = args.get("merge_tree")
    source_name = args.get("source")
    contexts = args.get("command_contexts")
    try:
        after = _frame_from_snapshot(
            entry.get("snapshot"),
            label=f"Checkpoint [{checkpoint_uid[:8]}]",
        )
        command_before = entry.get("command_before")
        before = (
            _frame_from_snapshot(
                command_before,
                label=f"Checkpoint [{checkpoint_uid[:8]}] command pre-image",
            )
            if isinstance(command_before, dict)
            else _empty_frame(after.context_uid, after.context_name)
        )
        memory_edges = parse_memory_lineage_receipt(args)
        decisions = _merge_decisions(args)
    except (MemoryHistoryReconstructionError, TypeError, ValueError):
        return None, warning
    target_created = tree.get("target_created") if isinstance(tree, dict) else None
    has_command_preimage = isinstance(command_before, dict)
    if (
        entry.get("auto") is not True
        or not isinstance(tree, dict)
        or tree.get("version") != 2
        or type(target_created) is not bool
        # Creation has no Target pre-image; an existing Target must retain one.
        or target_created == has_command_preimage
        or not isinstance(tree.get("operation_uid"), str)
        or not isinstance(source_name, str)
        or not source_name
        or not isinstance(contexts, list)
        or not any(
            isinstance(item, dict)
            and item.get("uid") == after.context_uid
            and item.get("name") == after.context_name
            for item in contexts
        )
        or before.context_uid != after.context_uid
    ):
        return None, warning
    anchored = tuple(
        edge for edge in memory_edges if edge.target_context_uid == after.context_uid
    )
    source_context_uids = {edge.source_context_uid for edge in anchored}
    if not anchored or len(source_context_uids) != 1:
        return None, warning

    recorded_edges: list[_RecordedMergeEdge] = []
    for edge in anchored:
        target_after = after.memories.get(edge.target_memory_uid)
        if (
            target_after is None
            or target_after.content_digest != edge.target_content_sha256
        ):
            return None, warning
        target_before = before.memories.get(edge.target_memory_uid)
        decision = decisions.get((edge.source_memory_uid, edge.target_memory_uid))
        if target_before is None:
            if decision is not None or (
                edge.source_content_sha256 != edge.target_content_sha256
            ):
                return None, warning
            disposition: Literal[
                "NEW", "ALREADY_PRESENT", "TAKE_SOURCE", "KEEP_TARGET"
            ] = "NEW"
        elif decision == "TAKE_SOURCE":
            if edge.source_content_sha256 != edge.target_content_sha256:
                return None, warning
            disposition = "TAKE_SOURCE"
        elif decision == "KEEP_TARGET":
            if target_before.content_digest != edge.target_content_sha256:
                return None, warning
            disposition = "KEEP_TARGET"
        elif (
            decision is None
            and target_before.content_digest == edge.target_content_sha256
            and edge.source_content_sha256 == edge.target_content_sha256
        ):
            disposition = "ALREADY_PRESENT"
        else:
            return None, warning
        recorded_edges.append(_RecordedMergeEdge(edge=edge, disposition=disposition))

    operation_uid = f"merge:{tree['operation_uid']}"
    context_records: list[MemoryHistoryCommandContext] = []
    for item in contexts:
        if not isinstance(item, dict):
            return None, warning
        uid = item.get("uid")
        name = item.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None, warning
        context_records.append(MemoryHistoryCommandContext(uid=uid, name=name))
    source_context_uid = next(iter(source_context_uids))
    return (
        _RecordedMergeTransition(
            checkpoint_uid=checkpoint_uid,
            timestamp=timestamp,
            description=description,
            operation_uid=operation_uid,
            source=MemoryHistoryCommandContext(
                uid=source_context_uid, name=source_name
            ),
            target=MemoryHistoryCommandContext(
                uid=after.context_uid,
                name=after.context_name,
            ),
            command_operation=MemoryHistoryCommandOperation(
                uid=operation_uid,
                command="merge",
                contexts=tuple(context_records),
            ),
            before=before,
            after=after,
            edges=tuple(recorded_edges),
        ),
        None,
    )
