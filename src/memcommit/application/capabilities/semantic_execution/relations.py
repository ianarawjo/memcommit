"""Application-owned block exposure and relation-component mechanics."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar


L = TypeVar("L")
R = TypeVar("R")


class RelationScheduleError(RuntimeError):
    """A block schedule or observed relation graph violates frozen coverage."""


@dataclass(frozen=True)
class RelationBlock(Generic[L, R]):
    """One exact left × right block in a complete matrix schedule."""

    left_batch_index: int
    right_batch_index: int
    left: tuple[L, ...]
    right: tuple[R, ...]


def build_relation_block_matrix(
    left_batches: Sequence[tuple[L, ...]],
    right_batches: Sequence[tuple[R, ...]],
    *,
    left_id: Callable[[L], str],
    right_id: Callable[[R], str],
) -> tuple[RelationBlock[L, R], ...]:
    """Expose every batch coordinate once without materializing item pairs."""

    frozen_left = tuple(tuple(batch) for batch in left_batches)
    frozen_right = tuple(tuple(batch) for batch in right_batches)
    if (
        not frozen_left
        or not frozen_right
        or any(not batch for batch in (*frozen_left, *frozen_right))
    ):
        raise RelationScheduleError(
            "Relation block scheduling requires nonempty batches on both sides."
        )
    left_ids = tuple(left_id(item) for batch in frozen_left for item in batch)
    right_ids = tuple(right_id(item) for batch in frozen_right for item in batch)
    if (
        any(not isinstance(value, str) or not value for value in (*left_ids, *right_ids))
        or len(left_ids) != len(set(left_ids))
        or len(right_ids) != len(set(right_ids))
    ):
        raise RelationScheduleError(
            "Each relation side requires unique nonempty frozen item ids."
        )
    return tuple(
        RelationBlock(
            left_batch_index=left_index,
            right_batch_index=right_index,
            left=left,
            right=right,
        )
        for left_index, left in enumerate(frozen_left, start=1)
        for right_index, right in enumerate(frozen_right, start=1)
    )


def connected_relation_components(
    node_ids: Sequence[str],
    hyperedges: Iterable[Sequence[str]],
) -> tuple[tuple[str, ...], ...]:
    """Merge positive relation observations while retaining singleton coverage."""

    nodes = tuple(node_ids)
    if (
        any(not isinstance(node, str) or not node for node in nodes)
        or len(nodes) != len(set(nodes))
    ):
        raise RelationScheduleError("Relation component nodes must be unique ids.")
    allowed = set(nodes)
    parent = {node: node for node in nodes}

    def find(node: str) -> str:
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != node:
            next_node = parent[node]
            parent[node] = root
            node = next_node
        return root

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for raw_edge in hyperedges:
        edge = tuple(raw_edge)
        if (
            not edge
            or len(edge) != len(set(edge))
            or any(node not in allowed for node in edge)
        ):
            raise RelationScheduleError(
                "A relation observation contains duplicate or unknown nodes."
            )
        anchor = edge[0]
        for node in edge[1:]:
            union(anchor, node)

    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for node in nodes:
        root = find(node)
        if root not in grouped:
            grouped[root] = []
            order.append(root)
        grouped[root].append(node)
    return tuple(tuple(grouped[root]) for root in order)
