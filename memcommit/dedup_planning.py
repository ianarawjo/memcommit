"""Pure connected-component planning for confirmed duplicate edges."""

from __future__ import annotations

import hashlib
import json

from memcommit.dedup_application import (
    DedupComponent,
    DedupEvidence,
    DedupMember,
    DedupRequest,
)
from memcommit.context import Memory


def _component_uid(
    *,
    member_uids: tuple[str, ...],
    finding_uids: tuple[str, ...],
) -> str:
    payload = {
        "findings": list(finding_uids),
        "members": list(member_uids),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return "dedup-component-" + digest


def build_dedup_components(
    request: DedupRequest,
    memories: tuple[Memory, ...],
) -> tuple[DedupComponent, ...]:
    """Return stable Context-ordered components from all confirmed edges.

    Edge order cannot choose the survivor. The existing direct Context order is
    the deterministic recommendation and also stabilizes every projected row.
    """

    if not isinstance(request, DedupRequest) or any(
        not isinstance(memory, Memory) for memory in memories
    ):
        raise TypeError("Dedup component planning requires typed inputs.")
    memory_by_uid = {memory.uid: memory for memory in memories}
    order = {memory.uid: index for index, memory in enumerate(memories, 1)}
    requested_uids = {
        uid for handoff in request.handoffs for uid in handoff.memory_uids
    }
    missing = sorted(requested_uids - set(memory_by_uid))
    if missing:
        from memcommit.dedup_application import DedupConflictError

        raise DedupConflictError(
            "Confirmed duplicate Memories are no longer directly owned by the "
            "Source: " + ", ".join(uid[:8] for uid in missing)
        )

    parent = {uid: uid for uid in requested_uids}

    def find(uid: str) -> str:
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        # Root choice is irrelevant to semantics, but Context order makes the
        # intermediate graph deterministic for debugging and receipts.
        if order[left_root] <= order[right_root]:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for handoff in request.handoffs:
        union(*handoff.memory_uids)

    groups: dict[str, list[str]] = {}
    for uid in requested_uids:
        groups.setdefault(find(uid), []).append(uid)

    components: list[DedupComponent] = []
    for member_uids in sorted(
        groups.values(),
        key=lambda values: min(order[uid] for uid in values),
    ):
        ordered_uids = tuple(sorted(member_uids, key=order.__getitem__))
        member_set = set(ordered_uids)
        component_handoffs = tuple(
            handoff
            for handoff in request.handoffs
            if set(handoff.memory_uids).issubset(member_set)
        )
        components.append(
            DedupComponent(
                uid=_component_uid(
                    member_uids=ordered_uids,
                    finding_uids=tuple(
                        sorted(handoff.finding_uid for handoff in component_handoffs)
                    ),
                ),
                members=tuple(
                    DedupMember(
                        uid=uid,
                        content=memory_by_uid[uid].content,
                        ordinal=order[uid],
                    )
                    for uid in ordered_uids
                ),
                evidence=tuple(
                    DedupEvidence(
                        finding_uid=handoff.finding_uid,
                        handoff_uid=handoff.uid,
                        left_uid=handoff.memory_uids[0],
                        right_uid=handoff.memory_uids[1],
                        relation=handoff.classification,
                        reason=handoff.reason,
                    )
                    for handoff in component_handoffs
                ),
                recommended_survivor_uid=ordered_uids[0],
            )
        )
    return tuple(components)


__all__ = ["build_dedup_components"]
