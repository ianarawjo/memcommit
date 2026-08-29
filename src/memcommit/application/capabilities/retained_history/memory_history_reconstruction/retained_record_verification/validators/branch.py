"""Validate retained Branch ownership and Memory-lineage transitions."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.retained_history.command_history import (
    CommandHistoryError,
    branch_tree_receipt,
)
from memcommit.application.capabilities.retained_history.memory_lineage import (
    MemoryLineageEdge,
    parse_memory_lineage_receipt,
)

from ..checkpoint import _checkpoint_fields
from ..frame import _Frame
from ..model import MemoryHistoryCommandContext, MemoryHistoryCommandOperation


@dataclass(frozen=True)
class _RecordedBranchTransition:
    """Validated Context movement retained by one automatic Branch checkpoint."""

    operation_uid: str
    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext
    command_operation: MemoryHistoryCommandOperation
    memory_edges: tuple[MemoryLineageEdge, ...]


def _recorded_branch_transition(
    *,
    entry: dict,
    frame: _Frame,
) -> tuple[_RecordedBranchTransition | None, str | None]:
    """Validate the Branch receipt that owns ``frame`` without guessing lineage."""

    checkpoint_uid, _timestamp, command, _description, args = _checkpoint_fields(entry)
    if command != "branch" or "branch_tree" not in args:
        return None, None
    try:
        receipt = branch_tree_receipt(args)
    except CommandHistoryError:
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch creation "
            "metadata; inherited lineage could not be connected to its target.",
        )
    mapping = next(
        (
            item
            for item in receipt.contexts
            if item.target_uid == frame.context_uid
            and item.target_name == frame.context_name
        ),
        None,
    )
    if mapping is None or entry.get("auto") is not True:
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch creation "
            "ownership; inherited lineage could not be connected to its target.",
        )
    try:
        memory_edges = parse_memory_lineage_receipt(args)
    except (TypeError, ValueError):
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch Memory "
            "lineage metadata; inherited lineage could not be connected to "
            "its target.",
        )
    target_memory_edges = tuple(
        edge
        for edge in memory_edges
        if edge.source_context_uid == mapping.source_uid
        and edge.target_context_uid == mapping.target_uid
    )
    for edge in target_memory_edges:
        target_state = frame.memories.get(edge.target_memory_uid)
        if (
            target_state is None
            or target_state.content_digest != edge.target_content_sha256
        ):
            return (
                None,
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch Memory "
                "lineage evidence; inherited lineage could not be connected "
                "to its target.",
            )
    operation_uid = f"branch:{receipt.operation_uid}"
    return (
        _RecordedBranchTransition(
            operation_uid=operation_uid,
            source=MemoryHistoryCommandContext(
                uid=mapping.source_uid,
                name=mapping.source_name,
            ),
            target=MemoryHistoryCommandContext(
                uid=mapping.target_uid,
                name=mapping.target_name,
            ),
            command_operation=MemoryHistoryCommandOperation(
                uid=operation_uid,
                command="branch",
                contexts=tuple(
                    MemoryHistoryCommandContext(
                        uid=item.target_uid, name=item.target_name
                    )
                    for item in receipt.contexts
                ),
            ),
            memory_edges=target_memory_edges,
        ),
        None,
    )
