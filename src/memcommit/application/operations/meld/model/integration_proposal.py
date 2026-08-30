"""Meld relation-backed integration proposals and their evidence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from memcommit.application.capabilities.memory_issue_analysis.peer_relations.model import (
    MEMORY_RELATION_DESCENDANT_SCHEMA_VERSION,
    MemoryRelationAnalysis,
    MemoryRelationMemory,
)

from .source_snapshot import (
    MELD_NAME_LIMIT,
    MeldDisposition,
    MeldError,
    MeldFrame,
    MeldIssuePriority,
    MeldProposalOperation,
    MeldRelationKind,
    MeldRelationStatus,
    MeldRevision,
    MeldTurnScope,
    _DISPOSITIONS,
    _OPERATIONS,
    _PRIORITIES,
    _RELATIONS,
    _RELATION_STATUSES,
    _REVISIONS,
    _SCOPES,
    _array,
    _canonical_uuid,
    _exact_dict,
    _integer,
    _literal,
    _string,
    _unique_identifiers,
)

if TYPE_CHECKING:
    from .proposal_session import MeldSession


@dataclass(frozen=True)
class MeldMember:
    frame_uid: str
    memory_uid: str

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_uid": self.frame_uid,
            "memory_uid": self.memory_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldMember":
        data = _exact_dict(
            value,
            {"frame_uid", "memory_uid"},
            "meld relation member",
        )
        return cls(
            frame_uid=_canonical_uuid(
                data["frame_uid"],
                "meld member frame uid",
            ),
            memory_uid=_canonical_uuid(
                data["memory_uid"],
                "meld member Memory uid",
            ),
        )


@dataclass(frozen=True)
class MeldRelation:
    uid: str
    kind: MeldRelationKind
    status: MeldRelationStatus
    members: tuple[MeldMember, ...]
    summary: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "kind": self.kind,
            "status": self.status,
            "members": [member.to_dict() for member in self.members],
            "summary": self.summary,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldRelation":
        data = _exact_dict(
            value,
            {"uid", "kind", "status", "members", "summary", "reason"},
            "meld relation",
        )
        members = tuple(
            MeldMember.from_dict(item)
            for item in _array(data["members"], "meld relation members")
        )
        if not members or len(
            {(member.frame_uid, member.memory_uid) for member in members}
        ) != len(members):
            raise MeldError("Invalid meld relation members.")
        return cls(
            uid=_canonical_uuid(data["uid"], "meld relation uid"),
            kind=_literal(
                data["kind"],
                _RELATIONS,
                "meld relation kind",
            ),  # type: ignore[arg-type]
            status=_literal(
                data["status"],
                _RELATION_STATUSES,
                "meld relation status",
            ),  # type: ignore[arg-type]
            members=members,
            summary=_string(data["summary"], "meld relation summary"),
            reason=_string(data["reason"], "meld relation reason"),
        )


@dataclass(frozen=True)
class MeldOption:
    uid: str
    label: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"uid": self.uid, "label": self.label, "text": self.text}

    @classmethod
    def from_dict(cls, value: object) -> "MeldOption":
        data = _exact_dict(
            value,
            {"uid", "label", "text"},
            "meld issue option",
        )
        return cls(
            uid=_canonical_uuid(data["uid"], "meld option uid"),
            label=_string(data["label"], "meld option label"),
            text=_string(data["text"], "meld option text"),
        )


@dataclass(frozen=True)
class MeldIssue:
    uid: str
    relation_uids: tuple[str, ...]
    priority: MeldIssuePriority
    title: str
    question: str
    why_it_matters: str
    options: tuple[MeldOption, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "relation_uids": list(self.relation_uids),
            "priority": self.priority,
            "title": self.title,
            "question": self.question,
            "why_it_matters": self.why_it_matters,
            "options": [option.to_dict() for option in self.options],
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldIssue":
        data = _exact_dict(
            value,
            {
                "uid",
                "relation_uids",
                "priority",
                "title",
                "question",
                "why_it_matters",
                "options",
            },
            "meld issue",
        )
        options = tuple(
            MeldOption.from_dict(item)
            for item in _array(data["options"], "meld issue options")
        )
        if len({option.uid for option in options}) != len(options):
            raise MeldError("Duplicate meld issue option.")
        return cls(
            uid=_canonical_uuid(data["uid"], "meld issue uid"),
            relation_uids=_unique_identifiers(
                data["relation_uids"],
                "meld issue relation uids",
                uuids=True,
            ),
            priority=_literal(
                data["priority"],
                _PRIORITIES,
                "meld issue priority",
            ),  # type: ignore[arg-type]
            title=_string(data["title"], "meld issue title"),
            question=_string(data["question"], "meld issue question"),
            why_it_matters=_string(
                data["why_it_matters"],
                "meld issue consequence",
            ),
            options=options,
        )


@dataclass(frozen=True)
class MeldProposal:
    uid: str
    operation: MeldProposalOperation
    disposition: MeldDisposition
    memory_uid: str
    content: str
    reason: str
    relation_uids: tuple[str, ...]
    source_members: tuple[MeldMember, ...]
    grounded_by_turn_uids: tuple[str, ...]
    owner_context_uid: str | None = None
    owner_context_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "operation": self.operation,
            "disposition": self.disposition,
            "memory_uid": self.memory_uid,
            "content": self.content,
            "reason": self.reason,
            "relation_uids": list(self.relation_uids),
            "source_members": [member.to_dict() for member in self.source_members],
            "grounded_by_turn_uids": list(self.grounded_by_turn_uids),
        }
        if self.owner_context_uid is not None:
            result["owner_context"] = {
                "uid": self.owner_context_uid,
                "name": self.owner_context_name,
            }
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldProposal":
        keys = {
            "uid",
            "operation",
            "disposition",
            "memory_uid",
            "content",
            "reason",
            "relation_uids",
            "source_members",
            "grounded_by_turn_uids",
        }
        if isinstance(value, dict) and "owner_context" in value:
            keys.add("owner_context")
        data = _exact_dict(value, keys, "meld proposal")
        owner_uid = None
        owner_name = None
        if "owner_context" in data:
            owner = _exact_dict(
                data["owner_context"],
                {"uid", "name"},
                "meld proposal owner",
            )
            owner_uid = _canonical_uuid(
                owner["uid"],
                "meld proposal owner Context uid",
            )
            owner_name = _string(
                owner["name"],
                "meld proposal owner Context name",
                limit=MELD_NAME_LIMIT,
            )
        source_members = tuple(
            MeldMember.from_dict(item)
            for item in _array(
                data["source_members"],
                "meld proposal source members",
            )
        )
        if len(
            {(member.frame_uid, member.memory_uid) for member in source_members}
        ) != len(source_members):
            raise MeldError("Duplicate meld proposal source member.")
        grounded_by = _unique_identifiers(
            data["grounded_by_turn_uids"],
            "meld proposal grounding turn uids",
            empty=True,
            uuids=True,
        )
        if not source_members and not grounded_by:
            raise MeldError(
                "A meld proposal requires source Memory or user-turn evidence."
            )
        return cls(
            uid=_canonical_uuid(data["uid"], "meld proposal uid"),
            operation=_literal(
                data["operation"],
                _OPERATIONS,
                "meld proposal operation",
            ),  # type: ignore[arg-type]
            disposition=_literal(
                data["disposition"],
                _DISPOSITIONS,
                "meld proposal disposition",
            ),  # type: ignore[arg-type]
            memory_uid=_canonical_uuid(
                data["memory_uid"],
                "meld proposal Memory uid",
            ),
            content=_string(data["content"], "meld proposal content"),
            reason=_string(data["reason"], "meld proposal reason"),
            relation_uids=_unique_identifiers(
                data["relation_uids"],
                "meld proposal relation uids",
                empty=True,
                uuids=True,
            ),
            source_members=source_members,
            grounded_by_turn_uids=grounded_by,
            owner_context_uid=owner_uid,
            owner_context_name=owner_name,
        )


@dataclass(frozen=True)
class MeldAssessment:
    overview: str
    relations: tuple[MeldRelation, ...]
    issues: tuple[MeldIssue, ...]
    proposals: tuple[MeldProposal, ...]
    ready_to_apply: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "overview": self.overview,
            "relations": [relation.to_dict() for relation in self.relations],
            "issues": [issue.to_dict() for issue in self.issues],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "ready_to_apply": self.ready_to_apply,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldAssessment":
        data = _exact_dict(
            value,
            {
                "overview",
                "relations",
                "issues",
                "proposals",
                "ready_to_apply",
            },
            "meld assessment",
        )
        relations = tuple(
            MeldRelation.from_dict(item)
            for item in _array(data["relations"], "meld relations")
        )
        issues = tuple(
            MeldIssue.from_dict(item) for item in _array(data["issues"], "meld issues")
        )
        proposals = tuple(
            MeldProposal.from_dict(item)
            for item in _array(data["proposals"], "meld proposals")
        )
        if (
            not relations
            or len({item.uid for item in relations}) != len(relations)
            or len({item.uid for item in issues}) != len(issues)
            or len({item.uid for item in proposals}) != len(proposals)
            or len({item.memory_uid for item in proposals}) != len(proposals)
            or not isinstance(data["ready_to_apply"], bool)
        ):
            raise MeldError("Invalid meld assessment collections.")
        relation_uids = {relation.uid for relation in relations}
        if any(
            not set(issue.relation_uids) <= relation_uids for issue in issues
        ) or any(
            not set(proposal.relation_uids) <= relation_uids for proposal in proposals
        ):
            raise MeldError("Meld issue or proposal references an unknown relation.")
        if data["ready_to_apply"] and (
            any(issue.priority == "REQUIRED" for issue in issues)
            or any(relation.status == "UNRESOLVED" for relation in relations)
        ):
            raise MeldError(
                "A ready meld assessment cannot retain required or unresolved work."
            )
        return cls(
            overview=_string(data["overview"], "meld assessment overview"),
            relations=relations,
            issues=issues,
            proposals=proposals,
            ready_to_apply=data["ready_to_apply"],
        )


def default_meld_revision(has_prior_user_turn: bool) -> MeldRevision:
    """Return the ordinary conversational relation for a new user turn."""
    return "EXTEND" if has_prior_user_turn else "INITIAL"


def validate_meld_turn_lineage(
    *,
    sequence: int,
    revision: str,
    revises_turn_uids: Iterable[str],
    known_turn_uids: Iterable[str],
) -> None:
    """Validate turn lineage for one Meld review session."""
    revises = tuple(revises_turn_uids)
    known = set(known_turn_uids)
    if revision not in _REVISIONS:
        raise MeldError("Invalid meld turn revision.")
    if sequence == 0:
        if revision != "INITIAL" or revises:
            raise MeldError("The first meld turn must be INITIAL.")
    elif revision == "INITIAL":
        raise MeldError("Only the first meld turn can be INITIAL.")
    if revision in {"CORRECT", "RETRACT"} and not revises:
        raise MeldError("CORRECT and RETRACT meld turns must identify revised turns.")
    if len(revises) != len(set(revises)) or not set(revises) <= known:
        raise MeldError("A meld turn revises an unknown or future turn.")


@dataclass(frozen=True)
class MeldTurn:
    uid: str
    sequence: int
    revision: MeldRevision
    scope: MeldTurnScope
    issue_uids: tuple[str, ...]
    comment: str
    revises_turn_uids: tuple[str, ...]
    assessment: MeldAssessment | None

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "sequence": self.sequence,
            "revision": self.revision,
            "scope": self.scope,
            "issue_uids": list(self.issue_uids),
            "comment": self.comment,
            "revises_turn_uids": list(self.revises_turn_uids),
            "assessment": (
                self.assessment.to_dict() if self.assessment is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldTurn":
        data = _exact_dict(
            value,
            {
                "uid",
                "sequence",
                "revision",
                "scope",
                "issue_uids",
                "comment",
                "revises_turn_uids",
                "assessment",
            },
            "meld turn",
        )
        assessment = data["assessment"]
        return cls(
            uid=_canonical_uuid(data["uid"], "meld turn uid"),
            sequence=_integer(data["sequence"], "meld turn sequence"),
            revision=_literal(
                data["revision"],
                _REVISIONS,
                "meld turn revision",
            ),  # type: ignore[arg-type]
            scope=_literal(
                data["scope"],
                _SCOPES,
                "meld turn scope",
            ),  # type: ignore[arg-type]
            issue_uids=_unique_identifiers(
                data["issue_uids"],
                "meld turn issue uids",
                empty=True,
                uuids=True,
            ),
            comment=_string(
                data["comment"],
                "meld turn comment",
                empty=True,
            ),
            revises_turn_uids=_unique_identifiers(
                data["revises_turn_uids"],
                "meld turn revised uids",
                empty=True,
                uuids=True,
            ),
            assessment=(
                None if assessment is None else MeldAssessment.from_dict(assessment)
            ),
        )


def meld_turn_evidence_payload(turn: MeldTurn) -> dict[str, object]:
    """Return the user-visible turn fields bound into an applied change set."""
    if not isinstance(turn, MeldTurn):
        raise MeldError("Invalid meld turn evidence.")
    return {
        "uid": turn.uid,
        "sequence": turn.sequence,
        "revision": turn.revision,
        "scope": turn.scope,
        "issue_uids": list(turn.issue_uids),
        "comment": turn.comment,
        "revises_turn_uids": list(turn.revises_turn_uids),
    }


def _relation_analysis_meld_frames(
    analysis: MemoryRelationAnalysis,
) -> tuple[MeldFrame, MeldFrame]:
    """Project ordered relation frames without changing durable identities."""
    frames: list[MeldFrame] = []
    for index, frame in enumerate(analysis.frames):
        owner_aware = (
            analysis.schema_version >= MEMORY_RELATION_DESCENDANT_SCHEMA_VERSION
            and analysis.include_descendants[index]
        )
        memories: list[dict[str, object]] = []
        for memory in frame.memories:
            item: dict[str, object] = {
                "uid": memory.uid,
                "content": memory.content,
                "position": memory.position,
                "content_digest": memory.content_digest,
            }
            if owner_aware and memory.source is not None:
                item["owner_context"] = {
                    "uid": memory.source.owner_context_uid,
                    "name": memory.source.owner_context_name,
                }
            memories.append(item)
        value: dict[str, object] = {
            "uid": frame.uid,
            "context_uid": frame.context_uid,
            "context_name": frame.context_name,
            "context_digest": frame.context_digest,
            "role": "PEER",
            # Meld consumes the ordinary semantic content but must not
            # parse capability-only source forms as part of its Memory schema.
            # Descendant scopes retain their established owner grouping.
            "memories": memories,
        }
        if analysis.schema_version >= MEMORY_RELATION_DESCENDANT_SCHEMA_VERSION:
            value["include_descendants"] = analysis.include_descendants[index]
        frames.append(MeldFrame.from_dict(value))
    return frames[0], frames[1]


def _relation_analysis_meld_assessment(
    analysis: MemoryRelationAnalysis,
    *,
    include_materialization_review: bool = True,
) -> MeldAssessment:
    """Import read-only relation semantics without inventing target results."""
    imported_issues = [issue.to_dict() for issue in analysis.issues]
    if include_materialization_review:
        already_reviewed_relations = {
            relation_uid
            for issue in analysis.issues
            for relation_uid in issue.relation_uids
        }
        for relation in analysis.relations:
            if (
                relation.kind not in {"COMPATIBLE", "SCOPED"}
                or relation.uid in already_reviewed_relations
            ):
                continue
            issue_uid = str(
                uuid.uuid5(
                    uuid.UUID(relation.uid),
                    # Stable UUID namespace input; Python ownership moves must
                    # not change previously derived review identities.
                    "memcommit.meld.materialization-review.v1",
                )
            )
            scoped = relation.kind == "SCOPED"
            imported_issues.append(
                {
                    "uid": issue_uid,
                    "relation_uids": [relation.uid],
                    "priority": "HELPFUL",
                    "title": (
                        "Scoped guidance materialization"
                        if scoped
                        else "Compatible guidance materialization"
                    ),
                    "question": (
                        "Should these source Memories remain separately editable, "
                        "or can they become one independently revisable Memory "
                        "without losing any supported detail?"
                    ),
                    "why_it_matters": (
                        "Keeping them separate preserves independent revision; "
                        "combining them reduces repetition only when every scope "
                        "and condition remains explicit."
                    ),
                    "options": [
                        {
                            "uid": str(uuid.uuid5(uuid.UUID(issue_uid), "preserve")),
                            "label": "Keep separately",
                            "text": (
                                "Preserve each independently useful source Memory "
                                "as its own target Memory."
                            ),
                        },
                        {
                            "uid": str(uuid.uuid5(uuid.UUID(issue_uid), "combine")),
                            "label": "Combine if lossless",
                            "text": (
                                "Combine these members only if one atomic target "
                                "Memory retains every supported condition, scope, "
                                "audience, modality, rate, and exception."
                            ),
                        },
                    ],
                }
            )
    return MeldAssessment.from_dict(
        {
            "overview": analysis.overview,
            "relations": [relation.to_dict() for relation in analysis.relations],
            "issues": imported_issues,
            "proposals": [],
            # Relation analysis has no mutation authority. Even an entirely resolved
            # ledger needs a later explicit Meld materialization turn.
            "ready_to_apply": False,
        }
    )


def directional_relation_basis_assessment(
    analysis: MemoryRelationAnalysis,
    frames: tuple[MeldFrame, MeldFrame],
) -> MeldAssessment:
    """Project one ordered relation ledger onto owner-aware directional frames.

    Analysis keeps content text untouched, but a directional Meld additionally
    needs an exact writable owner. Memory identity and typed host provenance
    bridge those contracts; the relation frames themselves are not writable
    source frames.
    """
    if tuple(analysis.include_descendants) != tuple(
        bool(frame.include_descendants) for frame in frames
    ):
        raise MeldError(
            "Directional meld descendant scopes do not match their relation seed."
        )
    frame_uid_map: dict[str, str] = {}
    for frame_index, (relation_frame, directional_frame) in enumerate(
        zip(analysis.frames, frames, strict=True)
    ):

        def is_directional_source(memory: MemoryRelationMemory) -> bool:
            if memory.source is None:
                # Older saved relation analyses predate typed provenance. Their
                # exact identity checks below remain the compatibility guard.
                return True
            source = memory.source
            if source.source_form == "OWNED":
                return source.owner_context_uid == relation_frame.context_uid
            return (
                source.source_form == "CONTEXT_GRAPH"
                and analysis.include_descendants[frame_index]
                and source.owner_context_name.startswith(
                    relation_frame.context_name + "/"
                )
            )

        if any(
            not is_directional_source(memory) for memory in relation_frame.memories
        ):
            raise MeldError(
                "Directional Meld cannot mutate through non-owned evidence "
                "from its relation basis; choose a symmetric Result Context "
                "or target the owning Context explicitly."
            )
        if (
            relation_frame.context_uid != directional_frame.context_uid
            or relation_frame.context_name != directional_frame.context_name
            or tuple(memory.uid for memory in relation_frame.memories)
            != tuple(memory.uid for memory in directional_frame.memories)
        ):
            raise MeldError(
                "Directional meld source Memories do not match their relation seed."
            )
        frame_uid_map[relation_frame.uid] = directional_frame.uid

    relation_values: list[dict[str, object]] = []
    # Provider output separates paired and one-sided relations. Canonicalize
    # once here so the visible basis and decoded result share one stable order
    # even when an older artifact interleaved the two categories.
    ordered_relations = (
        *(relation for relation in analysis.relations if relation.kind != "DISTINCT"),
        *(relation for relation in analysis.relations if relation.kind == "DISTINCT"),
    )
    for relation in ordered_relations:
        value = relation.to_dict()
        value["members"] = [
            {
                "frame_uid": frame_uid_map[member.frame_uid],
                "memory_uid": member.memory_uid,
            }
            for member in relation.members
        ]
        relation_values.append(value)

    # The provider decoder derives option identities from the stable issue
    # identity and ordinal. Normalize the imported options to that same rule so
    # local validation can prove that a reviewed relation issue was not dropped
    # or rewritten during Directional materialization.
    issue_values: list[dict[str, object]] = []
    for issue in analysis.issues:
        value = issue.to_dict()
        value["options"] = [
            {
                **option.to_dict(),
                "uid": str(
                    uuid.uuid5(
                        uuid.UUID(issue.uid),
                        f"option:{index}",
                    )
                ),
            }
            for index, option in enumerate(issue.options, start=1)
        ]
        issue_values.append(value)

    return MeldAssessment.from_dict(
        {
            "overview": analysis.overview,
            "relations": relation_values,
            "issues": issue_values,
            "proposals": [],
            "ready_to_apply": False,
        }
    )


# Compatibility names keep old imports valid without making Compare the owner.
_comparison_meld_frames = _relation_analysis_meld_frames
_comparison_meld_assessment = _relation_analysis_meld_assessment
directional_comparison_basis_assessment = directional_relation_basis_assessment


def _relation_local_preservation_assessment(
    session: MeldSession,
    basis: MeldAssessment,
    *,
    turn_uid: str,
    user_grounded: bool,
) -> MeldAssessment:
    """Project one exhaustive relation ledger into minimal target Memories."""
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    proposals: list[MeldProposal] = []
    namespace = uuid.UUID(session.uid)
    for relation in basis.relations:
        member_groups = (
            (relation.members,)
            if relation.kind == "EQUIVALENT"
            else tuple((member,) for member in relation.members)
        )
        for member_index, members in enumerate(member_groups, start=1):
            first = members[0]
            memory = memory_by_key[(first.frame_uid, first.memory_uid)]
            result_key = f"preserve:{turn_uid}:{relation.uid}:{member_index}"
            proposals.append(
                MeldProposal.from_dict(
                    {
                        "uid": str(uuid.uuid5(namespace, f"proposal:{result_key}")),
                        "operation": "ADD",
                        "disposition": (
                            "COALESCE" if relation.kind == "EQUIVALENT" else "PRESERVE"
                        ),
                        "memory_uid": str(
                            uuid.uuid5(namespace, f"memory:{result_key}")
                        ),
                        # Preservation is a copy operation. It deliberately
                        # avoids a second semantic rewrite that could omit a
                        # relation while appearing to cover it in prose.
                        "content": memory.content,
                        "reason": (
                            "Equivalent source Memories were coalesced without "
                            "changing their supported claim."
                            if relation.kind == "EQUIVALENT"
                            else "This supported source distinction remains "
                            "independently revisable under the conservative "
                            "Meld execution policy."
                        ),
                        "relation_uids": [relation.uid],
                        "source_members": [member.to_dict() for member in members],
                        "grounded_by_turn_uids": (
                            [turn_uid]
                            if user_grounded and relation.kind == "CONFLICT"
                            else []
                        ),
                    }
                )
            )

    return MeldAssessment.from_dict(
        {
            "overview": (
                "Every supported source distinction is preserved in a "
                "relation-local target Memory, while equivalent Memories are "
                "coalesced without a semantic rewrite."
            ),
            "relations": [
                {**relation.to_dict(), "status": "RESOLVED"}
                for relation in basis.relations
            ],
            "issues": [],
            "proposals": [proposal.to_dict() for proposal in proposals],
            "ready_to_apply": True,
        }
    )
