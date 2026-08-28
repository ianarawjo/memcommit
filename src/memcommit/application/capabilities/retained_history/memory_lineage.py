"""Checkpoint-authored lineage edges between independently owned Memories.

Memory UIDs identify writable occurrences.  Branch and Merge therefore retain
their cross-Context ancestry as operation evidence instead of making two
independent objects share one address.  The receipt is intentionally generic:
future many-to-one semantic operations may publish more than one parent edge
for a result without forcing lineage into one scalar Memory field.
"""

from __future__ import annotations

from collections import defaultdict
import copy
from dataclasses import dataclass
import hashlib
from typing import Any, Iterable
import uuid

from memcommit.core.context import Context, Memory


@dataclass(frozen=True)
class MemoryLineageEdge:
    """One exact parent-to-result occurrence relation published by a command."""

    source_context_uid: str
    source_memory_uid: str
    target_context_uid: str
    target_memory_uid: str
    source_content_sha256: str
    target_content_sha256: str

    @property
    def source_node(self) -> tuple[str, str]:
        return self.source_context_uid, self.source_memory_uid

    @property
    def target_node(self) -> tuple[str, str]:
        return self.target_context_uid, self.target_memory_uid


def memory_content_sha256(content: str) -> str:
    """Return the stable digest used to bind an edge to its exact values."""

    if not isinstance(content, str):
        raise TypeError("Memory lineage content must be text.")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def memory_lineage_record(
    operation_uid: str,
    edges: Iterable[MemoryLineageEdge],
) -> dict[str, object]:
    """Serialize one operation-owned, target-verifiable lineage receipt."""

    try:
        canonical_operation_uid = str(uuid.UUID(operation_uid))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Memory lineage operation uid is invalid.") from error
    if canonical_operation_uid != operation_uid:
        raise ValueError("Memory lineage operation uid is not canonical.")
    frozen = tuple(edges)
    _validate_edges(frozen)
    return {
        "version": 1,
        "operation_uid": operation_uid,
        "edges": [
            {
                "source_context_uid": edge.source_context_uid,
                "source_memory_uid": edge.source_memory_uid,
                "target_context_uid": edge.target_context_uid,
                "target_memory_uid": edge.target_memory_uid,
                "source_content_sha256": edge.source_content_sha256,
                "target_content_sha256": edge.target_content_sha256,
            }
            for edge in frozen
        ],
    }


def _operation_uid(args: dict[str, Any]) -> str | None:
    matches: list[str] = []
    for key in ("branch_tree", "merge_tree"):
        value = args.get(key)
        if not isinstance(value, dict):
            continue
        operation_uid = value.get("operation_uid")
        if isinstance(operation_uid, str) and operation_uid:
            matches.append(operation_uid)
    return matches[0] if len(matches) == 1 else None


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_edges(edges: tuple[MemoryLineageEdge, ...]) -> None:
    identities: set[tuple[object, ...]] = set()
    for edge in edges:
        if not isinstance(edge, MemoryLineageEdge):
            raise TypeError("Memory lineage edges must be typed values.")
        if not all(
            isinstance(value, str) and value
            for value in (
                edge.source_context_uid,
                edge.source_memory_uid,
                edge.target_context_uid,
                edge.target_memory_uid,
            )
        ):
            raise ValueError("Memory lineage edge identity is incomplete.")
        if edge.source_node == edge.target_node:
            raise ValueError("Memory lineage edge must connect distinct occurrences.")
        if not _valid_sha256(edge.source_content_sha256) or not _valid_sha256(
            edge.target_content_sha256
        ):
            raise ValueError("Memory lineage edge content digest is invalid.")
        identity = (
            edge.source_node,
            edge.target_node,
            edge.source_content_sha256,
            edge.target_content_sha256,
        )
        if identity in identities:
            raise ValueError("Memory lineage receipt contains duplicate edges.")
        identities.add(identity)


def parse_memory_lineage_receipt(args: object) -> tuple[MemoryLineageEdge, ...]:
    """Validate one receipt and bind it to its owning operation metadata."""

    if not isinstance(args, dict):
        raise ValueError("Memory lineage command arguments are invalid.")
    record = args.get("memory_lineage")
    if record is None:
        return ()
    if not isinstance(record, dict) or set(record) != {
        "version",
        "operation_uid",
        "edges",
    }:
        raise ValueError("Memory lineage receipt is invalid.")
    operation_uid = record.get("operation_uid")
    raw_edges = record.get("edges")
    try:
        canonical_operation_uid = str(uuid.UUID(operation_uid))
    except (AttributeError, TypeError, ValueError):
        canonical_operation_uid = None
    if (
        record.get("version") != 1
        or operation_uid != canonical_operation_uid
        or operation_uid != _operation_uid(args)
        or not isinstance(raw_edges, list)
    ):
        raise ValueError("Memory lineage receipt is invalid.")
    edges: list[MemoryLineageEdge] = []
    expected_fields = {
        "source_context_uid",
        "source_memory_uid",
        "target_context_uid",
        "target_memory_uid",
        "source_content_sha256",
        "target_content_sha256",
    }
    for raw in raw_edges:
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise ValueError("Memory lineage edge is invalid.")
        edges.append(
            MemoryLineageEdge(
                source_context_uid=raw["source_context_uid"],
                source_memory_uid=raw["source_memory_uid"],
                target_context_uid=raw["target_context_uid"],
                target_memory_uid=raw["target_memory_uid"],
                source_content_sha256=raw["source_content_sha256"],
                target_content_sha256=raw["target_content_sha256"],
            )
        )
    frozen = tuple(edges)
    _validate_edges(frozen)
    return frozen


def checkpoint_memory_lineage_edges(
    histories: Iterable[list[dict[str, Any]]],
) -> tuple[MemoryLineageEdge, ...]:
    """Read only target-anchored edges from complete retained histories.

    A receipt is accepted only from an automatic Branch or Merge checkpoint
    whose post-image contains the exact target occurrence and content digest.
    This prevents a copied or hand-edited argument record from creating
    callable lineage without matching durable result evidence.
    """

    accepted: list[MemoryLineageEdge] = []
    seen: set[MemoryLineageEdge] = set()
    # Import locally because history reconstruction itself depends on Store.
    from memcommit.application.capabilities.retained_history.reconstruction import HistoryError, flatten_checkpoint_entries

    for physical in histories:
        try:
            entries, _ = flatten_checkpoint_entries(physical)
        except HistoryError as error:
            raise ValueError("Memory lineage checkpoint history is invalid.") from error
        for entry in entries:
            args = entry.get("args")
            if not isinstance(args, dict) or "memory_lineage" not in args:
                continue
            if entry.get("auto") is not True or entry.get("command") not in {
                "branch",
                "merge",
            }:
                raise ValueError("Memory lineage receipt has invalid ownership.")
            edges = parse_memory_lineage_receipt(args)
            snapshot = entry.get("snapshot")
            if not isinstance(snapshot, dict):
                raise ValueError("Memory lineage checkpoint has no target snapshot.")
            target_context_uid = snapshot.get("uid")
            serialized = snapshot.get("memories")
            if not isinstance(target_context_uid, str) or not isinstance(
                serialized, dict
            ):
                raise ValueError("Memory lineage checkpoint target is invalid.")
            anchored = tuple(
                edge for edge in edges if edge.target_context_uid == target_context_uid
            )
            accepted_from_entry = anchored
            if entry.get("command") == "branch":
                branch_tree = args.get("branch_tree")
                raw_contexts = (
                    branch_tree.get("contexts")
                    if isinstance(branch_tree, dict)
                    else None
                )
                if not isinstance(raw_contexts, list):
                    raise ValueError("Branch Memory lineage membership is invalid.")
                declared_targets = {
                    item.get("target_uid")
                    for item in raw_contexts
                    if isinstance(item, dict)
                    and isinstance(item.get("target_uid"), str)
                }
                if target_context_uid not in declared_targets or any(
                    edge.target_context_uid not in declared_targets for edge in edges
                ):
                    raise ValueError("Branch Memory lineage membership is invalid.")
                # The complete receipt is repeated on every subtree target
                # while the Store holds all Source/Target locks. This lets a
                # root Revert retarget an internal MemoryRef without opening a
                # sibling Context; the local target edges below remain bound
                # to this checkpoint's exact post-image.
                accepted_from_entry = edges
            for edge in anchored:
                item = serialized.get(edge.target_memory_uid)
                if (
                    not isinstance(item, dict)
                    or item.get("type") != "memory"
                    or item.get("uid") != edge.target_memory_uid
                    or not isinstance(item.get("content"), str)
                    or memory_content_sha256(item["content"])
                    != edge.target_content_sha256
                ):
                    raise ValueError(
                        "Memory lineage receipt does not match its target snapshot."
                    )
            for edge in accepted_from_entry:
                if edge not in seen:
                    accepted.append(edge)
                    seen.add(edge)
    return tuple(accepted)


def resolve_lineage_target_uids(
    source: Context,
    target: Context,
    edges: Iterable[MemoryLineageEdge],
) -> dict[str, str]:
    """Map current Source Memories to one related current Target occurrence."""

    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source_node].add(edge.target_node)
        adjacency[edge.target_node].add(edge.source_node)

    target_uids = {item.uid for item in target.iter_items() if isinstance(item, Memory)}
    result: dict[str, str] = {}
    claimed_targets: dict[str, str] = {}
    for source_item in source.iter_items():
        if not isinstance(source_item, Memory):
            continue
        start = (source.uid, source_item.uid)
        visited = {start}
        pending = [start]
        matches: set[str] = set()
        while pending:
            node = pending.pop()
            if node[0] == target.uid and node[1] in target_uids:
                matches.add(node[1])
            for neighbor in adjacency.get(node, ()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                pending.append(neighbor)
        if len(matches) > 1:
            raise ValueError(
                "Checkpoint lineage maps one Source Memory to multiple current "
                "Target Memories."
            )
        if not matches:
            continue
        (target_uid,) = matches
        prior_source = claimed_targets.get(target_uid)
        if prior_source is not None and prior_source != source_item.uid:
            raise ValueError(
                "Checkpoint lineage maps multiple current Source Memories to one "
                "structural Merge target."
            )
        result[source_item.uid] = target_uid
        claimed_targets[target_uid] = source_item.uid
    return result


def _connected_memory_uid(
    starts: Iterable[tuple[str, str]],
    *,
    target_context_uid: str,
    adjacency: dict[tuple[str, str], set[tuple[str, str]]],
) -> str | None:
    visited = set(starts)
    pending = list(visited)
    matches: set[str] = set()
    while pending:
        node = pending.pop()
        if node[0] == target_context_uid:
            matches.add(node[1])
        for neighbor in adjacency.get(node, ()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            pending.append(neighbor)
    if len(matches) > 1:
        raise ValueError(
            "Checkpoint lineage maps one historical Memory to multiple Target "
            "occurrences."
        )
    return next(iter(matches), None)


def remap_restoration_snapshot(
    snapshot: object,
    *,
    target: Context,
    edges: Iterable[MemoryLineageEdge],
) -> dict[str, object]:
    """Project an inherited checkpoint into its Branch occurrence namespace.

    Copied Source checkpoints remain authentic historical evidence and retain
    Source Memory UIDs. Revert may restore their values only after every direct
    Memory can be mapped through a recorded Branch/Merge edge to the selected
    Target Context. Historical-only values with no published edge fail closed
    instead of recreating a Source UID beside its live owner.
    """

    if not isinstance(snapshot, dict):
        raise ValueError("Restoration snapshot is invalid.")
    rewritten = copy.deepcopy(snapshot)
    source_context_uid = rewritten.get("uid")
    memories = rewritten.get("memories")
    if not isinstance(source_context_uid, str) or not isinstance(memories, dict):
        raise ValueError("Restoration snapshot identity is invalid.")
    if source_context_uid == target.uid:
        return rewritten

    adjacency: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    all_nodes: set[tuple[str, str]] = set()
    for edge in edges:
        adjacency[edge.source_node].add(edge.target_node)
        adjacency[edge.target_node].add(edge.source_node)
        all_nodes.update((edge.source_node, edge.target_node))
    current_target_uids = {
        item.uid for item in target.iter_items() if isinstance(item, Memory)
    }
    item_uid_mapping: dict[str, str] = {}
    next_memories: dict[str, object] = {}
    for item_uid, item in memories.items():
        if not isinstance(item_uid, str) or not isinstance(item, dict):
            raise ValueError("Restoration snapshot contains an invalid direct item.")
        next_uid = item_uid
        if item.get("type") == "memory":
            mapped = _connected_memory_uid(
                ((source_context_uid, item_uid),),
                target_context_uid=target.uid,
                adjacency=adjacency,
            )
            if mapped is None:
                if item_uid not in current_target_uids:
                    raise ValueError(
                        "Inherited checkpoint Memory has no recorded Branch "
                        "occurrence in this Context."
                    )
                mapped = item_uid  # Legacy same-UID Branch compatibility.
            next_uid = mapped
            item["uid"] = mapped
        elif item.get("type") == "memory_ref":
            target_context = item.get("target_context")
            target_memory_uid = item.get("target_memory_uid")
            if (
                isinstance(target_context, dict)
                and isinstance(target_context.get("uid"), str)
                and isinstance(target_memory_uid, str)
            ):
                starts = tuple(
                    node for node in all_nodes if node[1] == target_memory_uid
                )
                mapped = _connected_memory_uid(
                    starts,
                    target_context_uid=target_context["uid"],
                    adjacency=adjacency,
                )
                if mapped is not None:
                    item["target_memory_uid"] = mapped
        if next_uid in next_memories:
            raise ValueError("Restoration Memory identity mapping collides.")
        next_memories[next_uid] = item
        item_uid_mapping[item_uid] = next_uid
    rewritten["memories"] = next_memories
    order = rewritten.get("order")
    if isinstance(order, list):
        rewritten["order"] = [
            item_uid_mapping.get(item_uid, item_uid) for item_uid in order
        ]
    return rewritten


__all__ = [
    "MemoryLineageEdge",
    "checkpoint_memory_lineage_edges",
    "memory_content_sha256",
    "memory_lineage_record",
    "parse_memory_lineage_receipt",
    "resolve_lineage_target_uids",
    "remap_restoration_snapshot",
]
