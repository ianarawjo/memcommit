"""Analyze confirmed Dedun relations into stable cleanup components."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
)
from memcommit.application.capabilities.semantic_execution.relations import (
    connected_relation_components,
)
from memcommit.application.operations.quality_resolution.repair.dedun.application import (
    DEDUN_CONTRACT_VERSION,
    DedunComponent,
    DedunEvidence,
    DedunMember,
    DedunRequest,
    FrozenDedunPlan,
)
from memcommit.core.context import Memory

if TYPE_CHECKING:
    from memcommit.application.operations.semantic_updates.foundation.update.model import GrantedUpdateTarget


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
    # Component UIDs remain durable checkpoint identities even though the
    # console replay path that once exposed them has been retired.
    return "dedup-component-" + digest


def analyze_dedun_components(
    request: DedunRequest,
    memories: tuple[Memory, ...],
) -> tuple[DedunComponent, ...]:
    """Return stable Context-ordered components from confirmed relations.

    Relation order cannot choose the survivor. Existing direct Context order
    determines component rows and the unchanged UID retained by immediate Dedun.
    """

    if not isinstance(request, DedunRequest) or any(
        not isinstance(memory, Memory) for memory in memories
    ):
        raise TypeError("Dedun component analysis requires typed inputs.")
    memory_by_uid = {memory.uid: memory for memory in memories}
    order = {memory.uid: index for index, memory in enumerate(memories, 1)}
    requested_uids = {
        uid for handoff in request.handoffs for uid in handoff.memory_uids
    }
    missing = sorted(requested_uids - set(memory_by_uid))
    if missing:
        from memcommit.application.operations.quality_resolution.repair.dedun.application import (
            DedunConflictError,
        )

        raise DedunConflictError(
            "Confirmed duplicate Memories are no longer directly owned by the "
            "Source: " + ", ".join(uid[:8] for uid in missing)
        )

    ordered_requested_uids = tuple(
        memory.uid for memory in memories if memory.uid in requested_uids
    )
    component_uids = connected_relation_components(
        ordered_requested_uids,
        (handoff.memory_uids for handoff in request.handoffs),
    )
    components: list[DedunComponent] = []
    for ordered_uids in component_uids:
        member_set = set(ordered_uids)
        component_handoffs = tuple(
            handoff
            for handoff in request.handoffs
            if set(handoff.memory_uids).issubset(member_set)
        )
        components.append(
            DedunComponent(
                uid=_component_uid(
                    member_uids=ordered_uids,
                    finding_uids=tuple(
                        sorted(handoff.finding_uid for handoff in component_handoffs)
                    ),
                ),
                members=tuple(
                    DedunMember(
                        uid=uid,
                        content=memory_by_uid[uid].content,
                        ordinal=order[uid],
                    )
                    for uid in ordered_uids
                ),
                evidence=tuple(
                    DedunEvidence(
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


def dedun_analysis_revision(
    request: DedunRequest,
    *,
    context_uid: str,
    context_name: str,
    display_name: str,
    context_digest: str,
    component_uids: tuple[str, ...],
    exact_item_groups: tuple[ExactDuplicateGroup, ...],
) -> str:
    """Bind analyzed relations to their complete direct-item Source frame."""

    payload = {
        "contract": DEDUN_CONTRACT_VERSION,
        "context": {
            "uid": context_uid,
            "name": context_name,
            "display_name": display_name,
            "digest": context_digest,
        },
        "components": list(component_uids),
        "exact_item_groups": [
            {
                "item_kind": group.item_kind,
                "survivor_uid": group.survivor_uid,
                "absorbed_uids": list(group.absorbed_uids),
                "summary": group.summary,
            }
            for group in exact_item_groups
        ],
        "handoffs": [handoff.uid for handoff in request.handoffs],
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def freeze_dedun_analysis(
    request: DedunRequest,
    memories: tuple[Memory, ...],
    *,
    context_uid: str,
    context_name: str,
    display_name: str,
    context_digest: str,
    direct_memory_digest: str,
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = (),
    granted_binding: "GrantedUpdateTarget | None" = None,
) -> FrozenDedunPlan:
    """Freeze analyzed Dedun evidence for a stored or projected Context."""

    source = request.source
    if (
        source.context_uid != context_uid
        or source.display_name != display_name
        or source.direct_memory_digest != direct_memory_digest
    ):
        from memcommit.application.operations.quality_resolution.repair.dedun.application import (
            DedunConflictError,
        )

        raise DedunConflictError(
            "The confirmed duplicate Source changed. Run the finder again."
        )
    components = analyze_dedun_components(request, memories)
    revision = dedun_analysis_revision(
        request,
        context_uid=context_uid,
        context_name=context_name,
        display_name=display_name,
        context_digest=context_digest,
        component_uids=tuple(component.uid for component in components),
        exact_item_groups=exact_item_groups,
    )
    return FrozenDedunPlan(
        request=request,
        context_uid=context_uid,
        context_name=context_name,
        display_name=display_name,
        context_digest=context_digest,
        revision=revision,
        components=components,
        exact_item_groups=exact_item_groups,
        granted_binding=granted_binding,
    )


__all__ = [
    "analyze_dedun_components",
    "dedun_analysis_revision",
    "freeze_dedun_analysis",
]
