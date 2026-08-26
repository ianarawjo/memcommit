"""Operation-owned contracts for applying complete DUN redundancy.

Dedun consumes deterministic exact-DUP and semantic-DUN evidence, keeps one
existing Memory per connected group, and removes the other existing UIDs after
exact whole-set review. It never authors canonical replacement text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from memcommit.reviewing.direct_item_duplicates import ExactDuplicateGroup
from memcommit.reviewing.quality.handoff import (
    QualityFindingHandoff,
    QualityFindingSource,
)
from memcommit.resolution import (
    ResolutionAttempt,
    ResolutionBinding,
    ResolutionCase,
    ResolutionRequirement,
    ResolutionSubmission,
    ResolutionValidationError,
    require_resolution_ready,
)

if TYPE_CHECKING:
    from memcommit.update import GrantedUpdateTarget


DEDUP_CONTRACT_VERSION = "dedun-v3"
DEDUP_ELIGIBLE_RELATIONS = frozenset(
    {"EXACT", "SURFACE_EQUIVALENT", "SEMANTIC_EQUIVALENT"}
)


class DedupError(RuntimeError):
    """A Dedun request, frozen plan, decision, or Apply is invalid."""


class DedupAuthorityError(DedupError):
    """The current authority cannot apply the confirmed redundancy plan."""


class DedupConflictError(DedupError):
    """The frozen Source or exact Dedun decision changed before Apply."""


@dataclass(frozen=True)
class DedupRequest:
    """Typed semantic edges plus optional complete role-aware exact scope."""

    handoffs: tuple[QualityFindingHandoff, ...]
    exact_source: QualityFindingSource | None = None
    exact_source_frame_digest: str | None = None

    def __post_init__(self) -> None:
        if any(
            not isinstance(handoff, QualityFindingHandoff) for handoff in self.handoffs
        ):
            raise DedupError("Dedun requires typed redundancy evidence items.")
        if (self.exact_source is None) != (self.exact_source_frame_digest is None):
            raise DedupError("Dedun exact scope requires both Source and frame digest.")
        if self.exact_source is not None and (
            not isinstance(self.exact_source, QualityFindingSource)
            or not isinstance(self.exact_source_frame_digest, str)
            or len(self.exact_source_frame_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.exact_source_frame_digest
            )
        ):
            raise DedupError("Dedun exact scope binding is invalid.")
        if not self.handoffs:
            if self.exact_source is None:
                raise DedupError(
                    "Dedun requires redundancy evidence or one complete exact scope."
                )
            return
        first = self.handoffs[0]
        if len(first.sources) != 1:
            raise DedupError("Dedun requires evidence from one exact direct Context.")
        source = first.sources[0]
        seen_edges: set[frozenset[str]] = set()
        seen_findings: set[str] = set()
        for handoff in self.handoffs:
            if handoff.kind != "DUPLICATE" or handoff.route != "DEDUP":
                raise DedupError(
                    "Dedun accepts only positive exact or semantic redundancy evidence."
                )
            if (
                len(handoff.sources) != 1
                or handoff.sources[0] != source
                or handoff.source_frame_digest != first.source_frame_digest
            ):
                raise DedupError(
                    "All Dedun evidence must share one exact frozen Source frame."
                )
            if len(handoff.memory_uids) != 2 or any(
                name != source.display_name for name in handoff.memory_context_names
            ):
                raise DedupError(
                    "Each Dedun evidence item must name two directly owned Memories."
                )
            if handoff.classification not in DEDUP_ELIGIBLE_RELATIONS:
                raise DedupError(
                    f"Dedun cannot apply relation '{handoff.classification}'."
                )
            edge = frozenset(handoff.memory_uids)
            if (
                len(edge) != 2
                or edge in seen_edges
                or handoff.finding_uid in seen_findings
            ):
                raise DedupError("Dedun evidence repeats or contains an invalid pair.")
            seen_edges.add(edge)
            seen_findings.add(handoff.finding_uid)
        if self.exact_source is not None and (
            self.exact_source != source
            or self.exact_source_frame_digest != first.source_frame_digest
        ):
            raise DedupError(
                "Dedun exact scope must match the semantic evidence frame."
            )

    @property
    def source(self) -> QualityFindingSource:
        if self.handoffs:
            return self.handoffs[0].sources[0]
        assert self.exact_source is not None
        return self.exact_source

    @property
    def source_frame_digest(self) -> str:
        if self.handoffs:
            return self.handoffs[0].source_frame_digest
        assert self.exact_source_frame_digest is not None
        return self.exact_source_frame_digest


@dataclass(frozen=True)
class DedupMember:
    """One existing Memory that may survive or be absorbed."""

    uid: str
    content: str
    ordinal: int

    def __post_init__(self) -> None:
        if not isinstance(self.uid, str) or not self.uid:
            raise DedupError("Dedun member UID must be nonempty text.")
        if not isinstance(self.content, str):
            raise DedupError("Dedun member content must be text.")
        if (
            isinstance(self.ordinal, bool)
            or not isinstance(self.ordinal, int)
            or self.ordinal < 1
        ):
            raise DedupError("Dedun member ordinal must be positive.")


@dataclass(frozen=True)
class DedupEvidence:
    """One finder-confirmed edge retained beside its exact members."""

    finding_uid: str
    handoff_uid: str
    left_uid: str
    right_uid: str
    relation: str
    reason: str


@dataclass(frozen=True)
class DedupComponent:
    """One connected duplicate group requiring exactly one survivor."""

    uid: str
    members: tuple[DedupMember, ...]
    evidence: tuple[DedupEvidence, ...]
    recommended_survivor_uid: str

    def __post_init__(self) -> None:
        member_uids = tuple(member.uid for member in self.members)
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or len(self.members) < 2
            or len(set(member_uids)) != len(member_uids)
            or not self.evidence
            or self.recommended_survivor_uid not in member_uids
        ):
            raise DedupError("Dedun redundancy group is invalid.")


@dataclass(frozen=True)
class DedupSelection:
    """One exact existing survivor for one frozen component."""

    component_uid: str
    survivor_uid: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (self.component_uid, self.survivor_uid)
        ):
            raise DedupError("Dedun selection identities must be nonempty text.")


@dataclass(frozen=True)
class FrozenDedupPlan:
    """Source-bound component plan plus current mutation authority binding."""

    request: DedupRequest
    context_uid: str
    context_name: str
    display_name: str
    context_digest: str
    revision: str
    components: tuple[DedupComponent, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()
    granted_binding: "GrantedUpdateTarget | None" = None

    def __post_init__(self) -> None:
        if not self.components and not self.exact_item_groups:
            raise DedupError("Dedun plan requires at least one redundancy group.")


@dataclass(frozen=True)
class DedupReceipt:
    """One checkpointed whole-set Dedup application receipt."""

    context_uid: str
    context_name: str
    revision: str
    checkpoint_uid: str
    selections: tuple[DedupSelection, ...]
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()


@dataclass(frozen=True)
class DedupProjection:
    """Provider-free complete survivor effect before Store publication.

    Standalone Dedun publishes this effect through ``DedupPort``. Composite
    operations may instead apply the same reviewed effect to an unpublished
    Context projection and let the outer user command own the sole checkpoint.
    """

    selections: tuple[DedupSelection, ...]
    survivor_uids: tuple[str, ...]
    absorbed_uids: tuple[str, ...]
    exact_item_groups: tuple[ExactDuplicateGroup, ...] = ()


def dedup_projection_record(
    plan: FrozenDedupPlan,
    projection: DedupProjection,
) -> dict[str, object]:
    """Serialize the complete reviewed Dedun effect without Store metadata."""

    if not isinstance(plan, FrozenDedupPlan) or not isinstance(
        projection,
        DedupProjection,
    ):
        raise TypeError("Dedun evidence projection requires typed inputs.")
    selections = projection.selections
    return {
        "contract": DEDUP_CONTRACT_VERSION,
        "revision": plan.revision,
        "selections": [
            {
                "component_uid": selection.component_uid,
                "survivor_uid": selection.survivor_uid,
            }
            for selection in selections
        ],
        # This evidence remains complete when an outer operation owns the
        # checkpoint; otherwise composition would erase why a UID disappeared.
        "components": [
            {
                "component_uid": component.uid,
                "survivor_uid": selection.survivor_uid,
                "members": [
                    {
                        "uid": member.uid,
                        "content": member.content,
                        "ordinal": member.ordinal,
                        "selected": member.uid == selection.survivor_uid,
                    }
                    for member in component.members
                ],
                "evidence": [
                    {
                        "finding_uid": item.finding_uid,
                        "handoff_uid": item.handoff_uid,
                        "left_uid": item.left_uid,
                        "right_uid": item.right_uid,
                        "relation": item.relation,
                        "reason": item.reason,
                    }
                    for item in component.evidence
                ],
            }
            for component, selection in zip(
                plan.components,
                selections,
                strict=True,
            )
        ],
        "exact_item_groups": [
            {
                "item_kind": group.item_kind,
                "survivor_uid": group.survivor_uid,
                "absorbed_uids": list(group.absorbed_uids),
                "summary": group.summary,
            }
            for group in projection.exact_item_groups
        ],
        "redundancy_evidence_uids": [
            handoff.uid for handoff in plan.request.handoffs
        ],
        "survivor_uids": list(projection.survivor_uids),
        "absorbed_uids": list(projection.absorbed_uids),
    }


class DedupPort(Protocol):
    """Freeze and atomically apply one confirmed duplicate request."""

    def freeze(self, request: DedupRequest) -> FrozenDedupPlan:
        """Revalidate the Source and current DELETE authority."""

    def apply(
        self,
        plan: FrozenDedupPlan,
        projection: DedupProjection,
    ) -> DedupReceipt:
        """Apply one exact complete survivor set or publish nothing."""


def dedup_resolution_case(plan: FrozenDedupPlan) -> ResolutionCase:
    """Project component survivor choices into the common exact validator."""

    if not isinstance(plan, FrozenDedupPlan):
        raise TypeError("Dedun resolution requires a frozen plan.")
    return ResolutionCase(
        binding=ResolutionBinding(
            operation="dedun",
            artifact_uid="dedun:" + plan.context_uid,
            revision=plan.revision,
        ),
        requirements=tuple(
            ResolutionRequirement(
                item_uid=component.uid,
                choice_uids=tuple(member.uid for member in component.members),
            )
            for component in plan.components
        ),
    )


def validate_dedup_selections(
    plan: FrozenDedupPlan,
    selections: tuple[DedupSelection, ...],
) -> tuple[DedupSelection, ...]:
    """Return exact component-ordered selections after shared validation."""

    if not isinstance(plan, FrozenDedupPlan) or any(
        not isinstance(selection, DedupSelection) for selection in selections
    ):
        raise TypeError("Dedun selection validation requires typed values.")
    if not plan.components:
        if selections:
            raise DedupError("Dedun exact-only plan accepts no Memory selections.")
        return ()
    case = dedup_resolution_case(plan)
    try:
        progress = require_resolution_ready(
            case,
            ResolutionAttempt(
                binding=case.binding,
                submissions=tuple(
                    ResolutionSubmission(
                        item_uid=selection.component_uid,
                        choice_uid=selection.survivor_uid,
                    )
                    for selection in selections
                ),
            ),
        )
    except ResolutionValidationError as error:
        if error.code == "UNRESOLVED_REQUIRED":
            raise DedupError(
                "Dedun has unresolved redundancy groups: " + ", ".join(error.item_uids)
            ) from error
        if error.code == "UNKNOWN_ITEM":
            raise DedupError(
                f"Dedun selection names an unknown group '{error.item_uids[0]}'."
            ) from error
        if error.code == "DUPLICATE_ITEM":
            raise DedupError(
                f"Dedun selection repeats group '{error.item_uids[0]}'."
            ) from error
        if error.code == "UNAVAILABLE_CHOICE":
            raise DedupError(
                f"Memory '{error.choice_uid}' is not a member of component "
                f"'{error.item_uids[0]}'."
            ) from error
        raise DedupError(str(error)) from error
    selected_by_component = {
        submission.item_uid: submission.choice_uid
        for submission in progress.submissions
    }
    return tuple(
        DedupSelection(component.uid, selected_by_component[component.uid])
        for component in plan.components
    )


def recommended_dedup_selections(
    plan: FrozenDedupPlan,
) -> tuple[DedupSelection, ...]:
    """Return the deterministic first-in-Context survivor proposal."""

    return tuple(
        DedupSelection(component.uid, component.recommended_survivor_uid)
        for component in plan.components
    )


def project_dedup(
    plan: FrozenDedupPlan,
    selections: tuple[DedupSelection, ...],
) -> DedupProjection:
    """Return the exact complete Dedun effect without publishing a checkpoint."""

    exact = validate_dedup_selections(plan, selections)
    semantic_survivor_uids = tuple(
        selection.survivor_uid for selection in exact
    )
    semantic_absorbed_uids = tuple(
        member.uid
        for component, selection in zip(plan.components, exact, strict=True)
        for member in component.members
        if member.uid != selection.survivor_uid
    )
    exact_survivor_uids = tuple(
        group.survivor_uid for group in plan.exact_item_groups
    )
    exact_absorbed_uids = tuple(
        uid for group in plan.exact_item_groups for uid in group.absorbed_uids
    )
    absorbed_uids = semantic_absorbed_uids + exact_absorbed_uids
    if not absorbed_uids:
        raise DedupError("Dedun Apply requires at least one absorbed direct item.")
    return DedupProjection(
        selections=exact,
        survivor_uids=semantic_survivor_uids + exact_survivor_uids,
        absorbed_uids=absorbed_uids,
        exact_item_groups=plan.exact_item_groups,
    )


def prepare_dedup(request: DedupRequest, *, port: DedupPort) -> FrozenDedupPlan:
    if not isinstance(request, DedupRequest):
        raise TypeError("Dedun requires a typed request.")
    return port.freeze(request)


def apply_dedup(
    plan: FrozenDedupPlan,
    selections: tuple[DedupSelection, ...],
    *,
    port: DedupPort,
) -> DedupReceipt:
    """Validate and atomically apply one complete survivor selection."""

    return port.apply(plan, project_dedup(plan, selections))


__all__ = [
    "DEDUP_CONTRACT_VERSION",
    "DEDUP_ELIGIBLE_RELATIONS",
    "DedupAuthorityError",
    "DedupComponent",
    "DedupConflictError",
    "DedupError",
    "DedupEvidence",
    "DedupMember",
    "DedupPort",
    "DedupProjection",
    "DedupReceipt",
    "DedupRequest",
    "DedupSelection",
    "FrozenDedupPlan",
    "apply_dedup",
    "dedup_projection_record",
    "dedup_resolution_case",
    "prepare_dedup",
    "project_dedup",
    "recommended_dedup_selections",
    "validate_dedup_selections",
]
