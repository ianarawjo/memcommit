"""Convert frozen quality-finding evidence into a Resolve request."""

from __future__ import annotations

from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
    QualityFindingHandoffError,
)
from memcommit.application.operations.quality_resolution.repair.resolve.application import (
    ResolveFitTarget,
    ResolveRequest,
    ResolveSourcePrecondition,
)


def conflict_handoff_to_resolve_request(
    handoff: QualityFindingHandoff,
    *,
    allow_create: bool = True,
    allow_delete: bool = False,
    guidance: str = "",
    target_fit: ResolveFitTarget = "MAY",
) -> ResolveRequest:
    """Enter Resolve only for one conflict from one exact direct Context.

    ``review_draft`` is deliberately ignored. A caller may pass separately
    submitted guidance, but merely typing or selecting inside the finder review
    cannot expand Resolve semantics or authorize DELETE.
    """

    if not isinstance(handoff, QualityFindingHandoff):
        raise TypeError("Conflict-to-Resolve conversion requires a typed handoff.")
    if handoff.kind != "CONFLICT" or handoff.route != "RESOLVE":
        raise QualityFindingHandoffError("Only a conflict finding can enter Resolve.")
    if len(handoff.sources) != 1:
        raise QualityFindingHandoffError(
            "Resolve v1 requires a conflict found in one exact Context; "
            "cross-Context findings need a separate reconciliation operation."
        )
    source = handoff.sources[0]
    if len(handoff.memory_uids) != 2 or any(
        name != source.display_name for name in handoff.memory_context_names
    ):
        raise QualityFindingHandoffError(
            "Resolve v1 requires both conflicting Memories to be directly owned "
            "by the same Context."
        )
    return ResolveRequest(
        context_name=source.display_name,
        memory_selectors=handoff.memory_uids,
        allow_create=allow_create,
        allow_delete=allow_delete,
        guidance=guidance,
        target_fit=target_fit,
        source_precondition=ResolveSourcePrecondition(
            context_uid=source.context_uid,
            display_name=source.display_name,
            direct_memory_digest=source.direct_memory_digest,
        ),
    )


__all__ = ["conflict_handoff_to_resolve_request"]
