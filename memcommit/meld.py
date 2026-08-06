"""Strict state for bounded conversational semantic melding.

The public version-one command binds two direct-Memory Contexts and an empty
target Context.  A semantic provider proposes a complete relation ledger and
an exact target change set, but this module owns identities, validation,
conversation history, acceptance, and application receipts.

Meld is always batch-shaped.  Selecting one issue narrows the scope of a turn;
it does not switch to a second "atomic" execution model.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Iterable, Literal

from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    COMPARISON_SCHEMA_VERSION,
    ComparisonAnalysis,
    comparison_canonical_digest,
)
from memcommit.context import Context, Memory
from memcommit.store import context_record_digest
from memcommit.update import GrantedUpdateTarget


MELD_SCHEMA_VERSION = 3
MELD_GRANTED_SCHEMA_VERSION = 4
MELD_COMPARISON_SCHEMA_VERSION = 2
MELD_LEGACY_SCHEMA_VERSION = 1
MELD_TEXT_LIMIT = 20_000
MELD_NAME_LIMIT = 500
MELD_ID_LIMIT = 240

MeldMode = Literal["DIRECTIONAL", "SYMMETRIC"]
MeldRole = Literal["INCOMING", "BASELINE", "PEER"]
MeldState = Literal[
    "PENDING_ANALYSIS",
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
]
MeldRevision = Literal[
    "INITIAL",
    "CONFIRM",
    "EXTEND",
    "CORRECT",
    "RETRACT",
]
MeldTurnScope = Literal["ISSUE", "REMAINING", "ALL"]
MeldRelationKind = Literal[
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
]
MeldRelationStatus = Literal["RESOLVED", "UNRESOLVED"]
MeldIssuePriority = Literal["REQUIRED", "HELPFUL"]
MeldDisposition = Literal[
    "COALESCE",
    "PRESERVE",
    "SYNTHESIZE",
    "USER_ADD",
]
MeldProposalOperation = Literal["ADD", "EDIT"]

_MODES = {"DIRECTIONAL", "SYMMETRIC"}
_ROLES = {"INCOMING", "BASELINE", "PEER"}
_STATES = {
    "PENDING_ANALYSIS",
    "AWAITING_REPLY",
    "READY_TO_APPLY",
    "KEPT_REVIEW_ONLY",
    "APPLIED",
}
_REVISIONS = {"INITIAL", "CONFIRM", "EXTEND", "CORRECT", "RETRACT"}
_SCOPES = {"ISSUE", "REMAINING", "ALL"}
_RELATIONS = {
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
}
_RELATION_STATUSES = {"RESOLVED", "UNRESOLVED"}
_PRIORITIES = {"REQUIRED", "HELPFUL"}
_DISPOSITIONS = {"COALESCE", "PRESERVE", "SYNTHESIZE", "USER_ADD"}
_OPERATIONS = {"ADD", "EDIT"}


class MeldError(ValueError):
    """Invalid, stale, or internally inconsistent meld state."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise MeldError(f"Invalid {label}.")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise MeldError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = MELD_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise MeldError(f"Invalid {label}.")
    return value


def _identifier(value: object, label: str) -> str:
    return _string(value, label, limit=MELD_ID_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except ValueError as error:
        raise MeldError(f"Invalid {label}.") from error
    if canonical != text:
        raise MeldError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise MeldError(f"Invalid {label}.")
    return text


def _literal(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise MeldError(f"Invalid {label}.")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MeldError(f"Invalid {label}.")
    return value


def _unique_identifiers(
    value: object,
    label: str,
    *,
    empty: bool = False,
    uuids: bool = False,
) -> tuple[str, ...]:
    values = _array(value, label)
    if not empty and not values:
        raise MeldError(f"Invalid {label}.")
    parser = _canonical_uuid if uuids else _identifier
    result = tuple(parser(item, label) for item in values)
    if len(result) != len(set(result)):
        raise MeldError(f"Duplicate {label}.")
    return result


def meld_canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    """Validate turn lineage shared by meld and atomize-grounding adapters."""
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
class MeldMemory:
    uid: str
    content: str
    position: int
    content_digest: str

    @classmethod
    def create(cls, memory: Memory, position: int) -> "MeldMemory":
        return cls.from_dict(
            {
                "uid": memory.uid,
                "content": memory.content,
                "position": position,
                "content_digest": hashlib.sha256(
                    memory.content.encode("utf-8")
                ).hexdigest(),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldMemory":
        data = _exact_dict(
            value,
            {"uid", "content", "position", "content_digest"},
            "meld Memory",
        )
        result = cls(
            uid=_canonical_uuid(data["uid"], "meld Memory uid"),
            content=_string(data["content"], "meld Memory content"),
            position=_integer(data["position"], "meld Memory position"),
            content_digest=_digest(
                data["content_digest"],
                "meld Memory content digest",
            ),
        )
        if (
            result.content_digest
            != hashlib.sha256(result.content.encode("utf-8")).hexdigest()
        ):
            raise MeldError("Meld Memory content digest does not match.")
        return result


@dataclass(frozen=True)
class MeldFrame:
    uid: str
    context_uid: str
    context_name: str
    context_digest: str
    role: MeldRole
    memories: tuple[MeldMemory, ...]
    include_descendants: bool | None = None

    @classmethod
    def from_context(
        cls,
        ctx: Context,
        *,
        role: MeldRole,
        include_descendants: bool | None = None,
    ) -> "MeldFrame":
        if not isinstance(ctx, Context):
            raise MeldError("Meld source must be a Context.")
        non_memories = [
            uid for uid, item in ctx.iter_entries() if not isinstance(item, Memory)
        ]
        if non_memories:
            raise MeldError(
                "Context-to-Context meld version 1 supports direct owned "
                "Memories only; unsupported direct item(s): "
                + ", ".join(uid[:8] for uid in non_memories)
                + "."
            )
        memories = tuple(
            MeldMemory.create(item, position)
            for position, item in enumerate(ctx.iter_items())
            if isinstance(item, Memory)
        )
        if not memories:
            raise MeldError(f"Source Context '{ctx.name}' has no direct Memories.")
        value: dict[str, object] = {
                "uid": str(uuid.uuid4()),
                "context_uid": ctx.uid,
                "context_name": ctx.name,
                "context_digest": context_record_digest(ctx),
                "role": role,
                "memories": [memory.to_dict() for memory in memories],
            }
        if include_descendants is not None:
            value["include_descendants"] = include_descendants
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "role": self.role,
            "memories": [memory.to_dict() for memory in self.memories],
        }
        if self.include_descendants is not None:
            result["include_descendants"] = self.include_descendants
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldFrame":
        keys = {
                "uid",
                "context_uid",
                "context_name",
                "context_digest",
                "role",
                "memories",
            }
        if isinstance(value, dict) and "include_descendants" in value:
            keys.add("include_descendants")
        data = _exact_dict(value, keys, "meld frame")
        memories = tuple(
            MeldMemory.from_dict(item)
            for item in _array(data["memories"], "meld frame Memories")
        )
        if (
            not memories
            or len({memory.uid for memory in memories}) != len(memories)
            or [memory.position for memory in memories] != list(range(len(memories)))
        ):
            raise MeldError("Invalid meld frame Memory order.")
        include_descendants = data.get("include_descendants")
        if include_descendants is not None and type(include_descendants) is not bool:
            raise MeldError("Invalid meld frame descendant scope.")
        return cls(
            uid=_canonical_uuid(data["uid"], "meld frame uid"),
            context_uid=_canonical_uuid(
                data["context_uid"],
                "meld frame Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "meld frame Context name",
                limit=MELD_NAME_LIMIT,
            ),
            context_digest=_digest(
                data["context_digest"],
                "meld frame Context digest",
            ),
            role=_literal(data["role"], _ROLES, "meld frame role"),  # type: ignore[arg-type]
            memories=memories,
            include_descendants=include_descendants,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class MeldTarget:
    context_uid: str
    context_name: str
    context_digest: str

    @classmethod
    def from_context(cls, ctx: Context) -> "MeldTarget":
        """Bind the empty result Context required by a symmetric meld."""
        if tuple(ctx.iter_items()):
            raise MeldError(
                "Symmetric Context meld version 1 requires an empty active "
                "target Context."
            )
        return cls.from_baseline_context(ctx)

    @classmethod
    def from_baseline_context(cls, ctx: Context) -> "MeldTarget":
        """Bind an existing Context as a directional meld baseline/target."""
        if not isinstance(ctx, Context):
            raise MeldError("Meld target must be a Context.")
        return cls.from_dict(
            {
                "context_uid": ctx.uid,
                "context_name": ctx.name,
                "context_digest": context_record_digest(ctx),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldTarget":
        data = _exact_dict(
            value,
            {"context_uid", "context_name", "context_digest"},
            "meld target",
        )
        return cls(
            context_uid=_canonical_uuid(
                data["context_uid"],
                "meld target Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "meld target Context name",
                limit=MELD_NAME_LIMIT,
            ),
            context_digest=_digest(
                data["context_digest"],
                "meld target Context digest",
            ),
        )


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

    def to_dict(self) -> dict[str, object]:
        return {
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

    @classmethod
    def from_dict(cls, value: object) -> "MeldProposal":
        data = _exact_dict(
            value,
            {
                "uid",
                "operation",
                "disposition",
                "memory_uid",
                "content",
                "reason",
                "relation_uids",
                "source_members",
                "grounded_by_turn_uids",
            },
            "meld proposal",
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


@dataclass(frozen=True)
class MeldChangeSet:
    session_uid: str
    turn_uid: str
    mode: MeldMode
    target_uid: str
    target_digest: str
    source_frame_digests: tuple[tuple[str, str], ...]
    turn_digests: tuple[tuple[str, str], ...]
    proposals: tuple[MeldProposal, ...]
    digest: str

    def _payload(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "turn_uid": self.turn_uid,
            "mode": self.mode,
            "target_uid": self.target_uid,
            "target_digest": self.target_digest,
            "source_frame_digests": [
                {"frame_uid": frame_uid, "digest": digest}
                for frame_uid, digest in self.source_frame_digests
            ],
            "turn_digests": [
                {"turn_uid": turn_uid, "digest": digest}
                for turn_uid, digest in self.turn_digests
            ],
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }

    @classmethod
    def create(
        cls,
        *,
        session_uid: str,
        turn_uid: str,
        mode: MeldMode,
        target: MeldTarget,
        frames: tuple[MeldFrame, ...],
        turns: tuple[MeldTurn, ...],
        proposals: tuple[MeldProposal, ...],
    ) -> "MeldChangeSet":
        payload = {
            "session_uid": session_uid,
            "turn_uid": turn_uid,
            "mode": mode,
            "target_uid": target.context_uid,
            "target_digest": target.context_digest,
            "source_frame_digests": [
                {
                    "frame_uid": frame.uid,
                    "digest": frame.context_digest,
                }
                for frame in frames
            ],
            "turn_digests": [
                {
                    "turn_uid": turn.uid,
                    "digest": meld_canonical_digest(meld_turn_evidence_payload(turn)),
                }
                for turn in turns
            ],
            "proposals": [proposal.to_dict() for proposal in proposals],
        }
        return cls.from_dict(
            {
                **payload,
                "digest": meld_canonical_digest(payload),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, value: object) -> "MeldChangeSet":
        data = _exact_dict(
            value,
            {
                "session_uid",
                "turn_uid",
                "mode",
                "target_uid",
                "target_digest",
                "source_frame_digests",
                "turn_digests",
                "proposals",
                "digest",
            },
            "meld change set",
        )
        source_frame_digests: list[tuple[str, str]] = []
        for item in _array(
            data["source_frame_digests"],
            "meld change-set source frame digests",
        ):
            record = _exact_dict(
                item,
                {"frame_uid", "digest"},
                "meld change-set source frame digest",
            )
            source_frame_digests.append(
                (
                    _canonical_uuid(
                        record["frame_uid"],
                        "meld change-set frame uid",
                    ),
                    _digest(
                        record["digest"],
                        "meld change-set frame digest",
                    ),
                )
            )
        turn_digests: list[tuple[str, str]] = []
        for item in _array(
            data["turn_digests"],
            "meld change-set turn digests",
        ):
            record = _exact_dict(
                item,
                {"turn_uid", "digest"},
                "meld change-set turn digest",
            )
            turn_digests.append(
                (
                    _canonical_uuid(
                        record["turn_uid"],
                        "meld change-set turn uid",
                    ),
                    _digest(
                        record["digest"],
                        "meld change-set turn digest",
                    ),
                )
            )
        proposals = tuple(
            MeldProposal.from_dict(item)
            for item in _array(
                data["proposals"],
                "meld change-set proposals",
            )
        )
        mode = _literal(
            data["mode"],
            _MODES,
            "meld change-set mode",
        )
        if (
            not source_frame_digests
            or len({uid for uid, _ in source_frame_digests})
            != len(source_frame_digests)
            or not turn_digests
            or len({uid for uid, _ in turn_digests}) != len(turn_digests)
            or (
                mode == "SYMMETRIC"
                and (
                    not proposals
                    or any(proposal.operation != "ADD" for proposal in proposals)
                )
            )
        ):
            raise MeldError("Invalid meld change set.")
        result = cls(
            session_uid=_canonical_uuid(
                data["session_uid"],
                "meld change-set session uid",
            ),
            turn_uid=_canonical_uuid(
                data["turn_uid"],
                "meld change-set turn uid",
            ),
            mode=mode,  # type: ignore[arg-type]
            target_uid=_canonical_uuid(
                data["target_uid"],
                "meld change-set target uid",
            ),
            target_digest=_digest(
                data["target_digest"],
                "meld change-set target digest",
            ),
            source_frame_digests=tuple(source_frame_digests),
            turn_digests=tuple(turn_digests),
            proposals=proposals,
            digest=_digest(data["digest"], "meld change-set digest"),
        )
        frame_uids = {frame_uid for frame_uid, _ in result.source_frame_digests}
        turn_uids = {turn_uid for turn_uid, _ in result.turn_digests}
        if (
            result.turn_uid not in turn_uids
            or any(
                member.frame_uid not in frame_uids
                for proposal in result.proposals
                for member in proposal.source_members
            )
            or any(
                not set(proposal.grounded_by_turn_uids) <= turn_uids
                for proposal in result.proposals
            )
            or any(
                proposal.disposition == "USER_ADD" and proposal.source_members
                for proposal in result.proposals
            )
            or any(
                proposal.disposition != "USER_ADD" and not proposal.source_members
                for proposal in result.proposals
            )
        ):
            raise MeldError("Invalid meld change-set evidence.")
        if result.digest != meld_canonical_digest(result._payload()):
            raise MeldError("Meld change-set digest does not match.")
        return result


@dataclass(frozen=True)
class MeldApplication:
    change_set_digest: str
    checkpoint_uid: str
    result_memory_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "change_set_digest": self.change_set_digest,
            "checkpoint_uid": self.checkpoint_uid,
            "result_memory_uids": list(self.result_memory_uids),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldApplication":
        data = _exact_dict(
            value,
            {
                "change_set_digest",
                "checkpoint_uid",
                "result_memory_uids",
            },
            "meld application",
        )
        return cls(
            change_set_digest=_digest(
                data["change_set_digest"],
                "meld application change-set digest",
            ),
            checkpoint_uid=_canonical_uuid(
                data["checkpoint_uid"],
                "meld application checkpoint uid",
            ),
            result_memory_uids=_unique_identifiers(
                data["result_memory_uids"],
                "meld application result Memory uids",
                empty=True,
                uuids=True,
            ),
        )


@dataclass(frozen=True)
class MeldComparisonSeed:
    """Exact ordered Compare snapshot that supplied turn zero."""

    analysis_digest: str
    analysis: ComparisonAnalysis

    @classmethod
    def create(
        cls,
        analysis: ComparisonAnalysis,
    ) -> "MeldComparisonSeed":
        if not isinstance(analysis, ComparisonAnalysis):
            raise MeldError("Meld comparison seed must be a comparison.")
        restored = ComparisonAnalysis.from_dict(analysis.to_dict())
        if restored.ruleset_version != COMPARISON_RULESET_VERSION:
            raise MeldError(
                "Meld requires a comparison from the current relation ruleset."
            )
        return cls.from_dict(
            {
                "analysis_digest": comparison_canonical_digest(restored.to_dict()),
                "analysis": restored.to_dict(),
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_digest": self.analysis_digest,
            "analysis": self.analysis.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> "MeldComparisonSeed":
        data = _exact_dict(
            value,
            {"analysis_digest", "analysis"},
            "meld comparison seed",
        )
        try:
            analysis = ComparisonAnalysis.from_dict(data["analysis"])
        except (TypeError, ValueError) as error:
            raise MeldError("Invalid meld comparison seed analysis.") from error
        result = cls(
            analysis_digest=_digest(
                data["analysis_digest"],
                "meld comparison seed analysis digest",
            ),
            analysis=analysis,
        )
        if result.analysis_digest != comparison_canonical_digest(
            result.analysis.to_dict()
        ):
            raise MeldError("Meld comparison seed digest does not match its analysis.")
        return result


def _comparison_meld_frames(
    analysis: ComparisonAnalysis,
) -> tuple[MeldFrame, MeldFrame]:
    """Project ordered Compare frames without changing durable identities."""
    frames: list[MeldFrame] = []
    for index, frame in enumerate(analysis.frames):
        value: dict[str, object] = {
                "uid": frame.uid,
                "context_uid": frame.context_uid,
                "context_name": frame.context_name,
                "context_digest": frame.context_digest,
                "role": "PEER",
                "memories": [memory.to_dict() for memory in frame.memories],
            }
        if analysis.schema_version == COMPARISON_SCHEMA_VERSION:
            value["include_descendants"] = analysis.include_descendants[index]
        frames.append(MeldFrame.from_dict(value))
    return frames[0], frames[1]


def _comparison_meld_assessment(
    analysis: ComparisonAnalysis,
    *,
    include_materialization_review: bool = True,
) -> MeldAssessment:
    """Import read-only Compare semantics without inventing target results."""
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
            # Compare has no mutation authority. Even an entirely resolved
            # ledger needs a later explicit Meld materialization turn.
            "ready_to_apply": False,
        }
    )


@dataclass
class MeldSession:
    uid: str
    mode: MeldMode
    frames: tuple[MeldFrame, ...]
    target: MeldTarget
    schema_version: int = MELD_LEGACY_SCHEMA_VERSION
    comparison_seed: MeldComparisonSeed | None = None
    granted_incoming: GrantedUpdateTarget | None = None
    granted_target: GrantedUpdateTarget | None = None
    state: MeldState = "PENDING_ANALYSIS"
    turns: tuple[MeldTurn, ...] = ()
    application: MeldApplication | None = None

    @classmethod
    def create_symmetric(
        cls,
        left: Context,
        right: Context,
        target: Context,
    ) -> "MeldSession":
        if left.uid == right.uid or left.name == right.name:
            raise MeldError("Meld source Contexts must be distinct.")
        if target.uid in {left.uid, right.uid} or target.name in {
            left.name,
            right.name,
        }:
            raise MeldError("Symmetric meld target must differ from both sources.")
        session = cls(
            uid=str(uuid.uuid4()),
            mode="SYMMETRIC",
            frames=(
                MeldFrame.from_context(left, role="PEER"),
                MeldFrame.from_context(right, role="PEER"),
            ),
            target=MeldTarget.from_context(target),
        )
        return cls.from_dict(session.to_dict())

    @classmethod
    def create_symmetric_from_comparison(
        cls,
        analysis: ComparisonAnalysis,
        target: Context,
    ) -> "MeldSession":
        """Start one target-bound Meld from an exact reviewed comparison."""
        seed = MeldComparisonSeed.create(analysis)
        frames = _comparison_meld_frames(seed.analysis)
        if target.uid in {frame.context_uid for frame in frames} or (
            target.name in {frame.context_name for frame in frames}
        ):
            raise MeldError("Symmetric meld target must differ from both sources.")
        session = cls(
            uid=str(uuid.uuid4()),
            mode="SYMMETRIC",
            frames=frames,
            target=MeldTarget.from_context(target),
            schema_version=MELD_SCHEMA_VERSION,
            comparison_seed=seed,
        )
        session = cls.from_dict(session.to_dict())
        turn = session.start_initial_analysis()
        session.record_assessment(
            turn.uid,
            _comparison_meld_assessment(seed.analysis),
        )
        return session

    @classmethod
    def create_directional(
        cls,
        incoming: Context,
        baseline: Context,
        *,
        incoming_descendants: bool | None = None,
        baseline_descendants: bool | None = None,
        granted_incoming: GrantedUpdateTarget | None = None,
        granted_target: GrantedUpdateTarget | None = None,
    ) -> "MeldSession":
        """Bind one incoming Context to an authoritative mutable baseline."""
        if incoming.uid == baseline.uid or incoming.name == baseline.name:
            raise MeldError(
                "Directional meld requires distinct INCOMING and BASELINE Contexts."
            )
        session = cls(
            uid=str(uuid.uuid4()),
            mode="DIRECTIONAL",
            frames=(
                MeldFrame.from_context(
                    incoming,
                    role="INCOMING",
                    include_descendants=incoming_descendants,
                ),
                MeldFrame.from_context(
                    baseline,
                    role="BASELINE",
                    include_descendants=baseline_descendants,
                ),
            ),
            target=MeldTarget.from_baseline_context(baseline),
            # Directional schema four freezes authorization independently for
            # each endpoint.  Public names alone are not stable authority.
            schema_version=MELD_GRANTED_SCHEMA_VERSION,
            granted_incoming=granted_incoming,
            granted_target=granted_target,
        )
        return cls.from_dict(session.to_dict())

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema_version": self.schema_version,
            "uid": self.uid,
            "mode": self.mode,
            "frames": [frame.to_dict() for frame in self.frames],
            "target": self.target.to_dict(),
            "state": self.state,
            "turns": [turn.to_dict() for turn in self.turns],
            "application": (
                self.application.to_dict() if self.application is not None else None
            ),
        }
        if self.schema_version >= MELD_COMPARISON_SCHEMA_VERSION:
            result["comparison_seed"] = (
                self.comparison_seed.to_dict()
                if self.comparison_seed is not None
                else None
            )
        if self.schema_version >= MELD_GRANTED_SCHEMA_VERSION:
            result["granted_incoming"] = (
                None
                if self.granted_incoming is None
                else self.granted_incoming.to_dict()
            )
            result["granted_target"] = (
                None
                if self.granted_target is None
                else self.granted_target.to_dict()
            )
        return result

    @classmethod
    def from_dict(cls, value: object) -> "MeldSession":
        if not isinstance(value, dict):
            raise MeldError("Invalid meld session.")
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool) or schema_version not in {
            MELD_LEGACY_SCHEMA_VERSION,
            MELD_COMPARISON_SCHEMA_VERSION,
            MELD_SCHEMA_VERSION,
            MELD_GRANTED_SCHEMA_VERSION,
        }:
            raise MeldError("Unsupported meld session schema version.")
        keys = {
            "schema_version",
            "uid",
            "mode",
            "frames",
            "target",
            "state",
            "turns",
            "application",
        }
        if schema_version >= MELD_COMPARISON_SCHEMA_VERSION:
            keys.add("comparison_seed")
        if schema_version >= MELD_GRANTED_SCHEMA_VERSION:
            keys.update({"granted_incoming", "granted_target"})
        data = _exact_dict(
            value,
            keys,
            "meld session",
        )
        frames = tuple(
            MeldFrame.from_dict(item)
            for item in _array(data["frames"], "meld session frames")
        )
        turns = tuple(
            MeldTurn.from_dict(item)
            for item in _array(data["turns"], "meld session turns")
        )
        raw_application = data["application"]
        raw_comparison_seed = (
            data["comparison_seed"]
            if schema_version >= MELD_COMPARISON_SCHEMA_VERSION
            else None
        )
        session = cls(
            uid=_canonical_uuid(data["uid"], "meld session uid"),
            mode=_literal(
                data["mode"],
                _MODES,
                "meld session mode",
            ),  # type: ignore[arg-type]
            frames=frames,
            target=MeldTarget.from_dict(data["target"]),
            schema_version=schema_version,
            comparison_seed=(
                None
                if raw_comparison_seed is None
                else MeldComparisonSeed.from_dict(raw_comparison_seed)
            ),
            granted_incoming=(
                None
                if schema_version < MELD_GRANTED_SCHEMA_VERSION
                or data["granted_incoming"] is None
                else GrantedUpdateTarget.from_dict(data["granted_incoming"])
            ),
            granted_target=(
                None
                if schema_version < MELD_GRANTED_SCHEMA_VERSION
                or data["granted_target"] is None
                else GrantedUpdateTarget.from_dict(data["granted_target"])
            ),
            state=_literal(
                data["state"],
                _STATES,
                "meld session state",
            ),  # type: ignore[arg-type]
            turns=turns,
            application=(
                None
                if raw_application is None
                else MeldApplication.from_dict(raw_application)
            ),
        )
        session._validate()
        return session

    @property
    def current_turn(self) -> MeldTurn | None:
        return self.turns[-1] if self.turns else None

    @property
    def current_assessment(self) -> MeldAssessment | None:
        turn = self.current_turn
        return turn.assessment if turn is not None else None

    @property
    def user_turns(self) -> tuple[MeldTurn, ...]:
        return self.turns[1:] if self.turns else ()

    def start_initial_analysis(self) -> MeldTurn:
        if self.turns or self.state != "PENDING_ANALYSIS":
            raise MeldError("Meld initial analysis is already started.")
        turn = MeldTurn.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "sequence": 0,
                "revision": "INITIAL",
                "scope": "ALL",
                "issue_uids": [],
                "comment": "",
                "revises_turn_uids": [],
                "assessment": None,
            }
        )
        self.turns = (turn,)
        self._validate()
        return turn

    def start_turn(
        self,
        comment: str,
        *,
        scope: MeldTurnScope,
        issue_uids: Iterable[str] = (),
        revision: MeldRevision = "EXTEND",
        revises_turn_uids: Iterable[str] = (),
    ) -> MeldTurn:
        if self.state in {"PENDING_ANALYSIS", "APPLIED", "KEPT_REVIEW_ONLY"}:
            raise MeldError(f"Cannot add a turn while meld is {self.state}.")
        if self.current_turn is None or self.current_turn.assessment is None:
            raise MeldError("The prior meld turn has not been assessed.")
        parsed_issue_uids = tuple(issue_uids)
        current_issue_uids = {issue.uid for issue in self.current_assessment.issues}
        if scope == "ISSUE":
            if (
                not parsed_issue_uids
                or not set(parsed_issue_uids) <= current_issue_uids
            ):
                raise MeldError(
                    "Issue-scoped meld turn names an unknown current issue."
                )
        elif parsed_issue_uids:
            raise MeldError("Only an issue-scoped meld turn may name issue uids.")
        turn = MeldTurn.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "sequence": len(self.turns),
                "revision": revision,
                "scope": scope,
                "issue_uids": list(parsed_issue_uids),
                "comment": comment,
                "revises_turn_uids": list(revises_turn_uids),
                "assessment": None,
            }
        )
        self.turns = (*self.turns, turn)
        self.state = "AWAITING_REPLY"
        self.application = None
        self._validate()
        return turn

    def record_assessment(
        self,
        turn_uid: str,
        assessment: MeldAssessment,
    ) -> None:
        if self.current_turn is None or self.current_turn.uid != turn_uid:
            raise MeldError("Only the latest meld turn can be assessed.")
        if self.current_turn.assessment is not None:
            raise MeldError("The latest meld turn is already assessed.")
        if not isinstance(assessment, MeldAssessment):
            raise MeldError("Invalid meld assessment.")
        self.turns = (
            *self.turns[:-1],
            replace(self.current_turn, assessment=assessment),
        )
        self.state = "READY_TO_APPLY" if assessment.ready_to_apply else "AWAITING_REPLY"
        self._validate()

    def prepare_changes(self) -> MeldChangeSet:
        # The exact change set remains derivable after application so retry
        # recovery can verify the saved receipt and current target instead of
        # treating an APPLIED flag as sufficient evidence.
        if self.state not in {"READY_TO_APPLY", "APPLIED"}:
            raise MeldError("Meld is not ready to apply.")
        turn = self.current_turn
        assessment = self.current_assessment
        assert turn is not None and assessment is not None
        return MeldChangeSet.create(
            session_uid=self.uid,
            turn_uid=turn.uid,
            mode=self.mode,
            target=self.target,
            frames=self.frames,
            turns=self.turns,
            proposals=assessment.proposals,
        )

    def keep_review_only(self) -> None:
        if self.state == "APPLIED":
            raise MeldError("An applied meld cannot become review-only.")
        self.state = "KEPT_REVIEW_ONLY"
        self.application = None
        self._validate()

    def record_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
        result_memory_uids: Iterable[str],
    ) -> None:
        change_set = self.prepare_changes()
        if change_set.digest != change_set_digest:
            raise MeldError("Applied meld change-set digest does not match.")
        result_uids = tuple(result_memory_uids)
        if result_uids != tuple(
            proposal.memory_uid for proposal in change_set.proposals
        ):
            raise MeldError("Applied meld result identities do not match.")
        self.application = MeldApplication.from_dict(
            {
                "change_set_digest": change_set_digest,
                "checkpoint_uid": checkpoint_uid,
                "result_memory_uids": list(result_uids),
            }
        )
        self.state = "APPLIED"
        self._validate()

    def clear_application(
        self,
        *,
        change_set_digest: str,
        checkpoint_uid: str,
    ) -> None:
        """Return one exact applied session to its reviewed ready state."""
        if self.state != "APPLIED" or self.application is None:
            raise MeldError("Meld application is not currently applied.")
        if (
            self.application.change_set_digest != change_set_digest
            or self.application.checkpoint_uid != checkpoint_uid
        ):
            raise MeldError("Meld application receipt does not match this undo.")
        self.application = None
        self.state = "READY_TO_APPLY"
        self._validate()

    def _validate(self) -> None:
        if self.schema_version not in {
            MELD_LEGACY_SCHEMA_VERSION,
            MELD_COMPARISON_SCHEMA_VERSION,
            MELD_SCHEMA_VERSION,
            MELD_GRANTED_SCHEMA_VERSION,
        }:
            raise MeldError("Unsupported meld session schema version.")
        if self.schema_version == MELD_LEGACY_SCHEMA_VERSION:
            if self.comparison_seed is not None:
                raise MeldError(
                    "A legacy meld session cannot contain a comparison seed."
                )
        elif (
            self.mode == "SYMMETRIC"
            and self.comparison_seed is None
        ):
            raise MeldError("A current meld session requires a comparison seed.")
        if self.schema_version < MELD_GRANTED_SCHEMA_VERSION and (
            self.granted_incoming is not None or self.granted_target is not None
        ):
            raise MeldError("A legacy meld session cannot contain Grant bindings.")
        if len(self.frames) != 2:
            raise MeldError("Context meld requires exactly two source frames.")
        if len({frame.uid for frame in self.frames}) != len(self.frames):
            raise MeldError("Duplicate meld frame identity.")
        if len({frame.context_uid for frame in self.frames}) != len(self.frames) or len(
            {frame.context_name for frame in self.frames}
        ) != len(self.frames):
            raise MeldError("Duplicate meld source Context.")
        if self.mode == "SYMMETRIC":
            if self.target.context_uid in {
                frame.context_uid for frame in self.frames
            } or self.target.context_name in {
                frame.context_name for frame in self.frames
            }:
                raise MeldError("Symmetric meld target overlaps a source Context.")
            if any(frame.role != "PEER" for frame in self.frames):
                raise MeldError("Symmetric meld requires two PEER frames.")
        else:
            if self.comparison_seed is not None:
                raise MeldError("Directional meld cannot use a peer comparison seed.")
            incoming, baseline = self.frames
            if incoming.role != "INCOMING" or baseline.role != "BASELINE":
                raise MeldError(
                    "Directional meld requires ordered INCOMING and BASELINE frames."
                )
            if (
                self.target.context_uid != baseline.context_uid
                or self.target.context_name != baseline.context_name
                or self.target.context_digest != baseline.context_digest
            ):
                raise MeldError(
                    "Directional meld target must exactly match its BASELINE frame."
                )
            if (
                self.target.context_uid == incoming.context_uid
                or self.target.context_name == incoming.context_name
            ):
                raise MeldError(
                    "Directional meld target overlaps its INCOMING Context."
                )
            for binding, frame, label in (
                (self.granted_incoming, incoming, "INCOMING"),
                (self.granted_target, baseline, "BASELINE"),
            ):
                if binding is not None and binding.public_name != frame.context_name:
                    raise MeldError(
                        f"Directional {label} Grant binding does not match its frame."
                    )

        if self.comparison_seed is not None:
            analysis = self.comparison_seed.analysis
            if analysis.ruleset_version != COMPARISON_RULESET_VERSION:
                raise MeldError(
                    "Meld comparison seed uses an unsupported relation ruleset."
                )
            expected_frames = _comparison_meld_frames(analysis)
            if tuple(frame.to_dict() for frame in self.frames) != tuple(
                frame.to_dict() for frame in expected_frames
            ):
                raise MeldError(
                    "Meld source frames do not match their comparison seed."
                )

        known_turn_uids: list[str] = []
        seen_turn_uids: set[str] = set()
        seen_pending = False
        for sequence, turn in enumerate(self.turns):
            if turn.sequence != sequence:
                raise MeldError("Meld turn sequence is not contiguous.")
            if turn.uid in seen_turn_uids:
                raise MeldError("Duplicate meld turn uid.")
            validate_meld_turn_lineage(
                sequence=sequence,
                revision=turn.revision,
                revises_turn_uids=turn.revises_turn_uids,
                known_turn_uids=known_turn_uids,
            )
            if sequence == 0:
                if turn.comment or turn.scope != "ALL" or turn.issue_uids:
                    raise MeldError(
                        "Initial meld analysis must cover ALL without a "
                        "synthetic user comment."
                    )
            elif not turn.comment.strip():
                raise MeldError("A user meld turn requires a comment.")
            if turn.assessment is None:
                seen_pending = True
                if sequence != len(self.turns) - 1:
                    raise MeldError("Only the latest meld turn may await assessment.")
            elif seen_pending:
                raise MeldError("An assessed meld turn follows a pending turn.")
            else:
                self._validate_assessment(turn)
            known_turn_uids.append(turn.uid)
            seen_turn_uids.add(turn.uid)

        if (
            self.comparison_seed is not None
            and self.turns
            and self.turns[0].assessment is not None
            and self.turns[0].assessment.to_dict()
            != _comparison_meld_assessment(
                self.comparison_seed.analysis,
                include_materialization_review=(
                    self.schema_version >= MELD_SCHEMA_VERSION
                ),
            ).to_dict()
        ):
            raise MeldError("Meld turn zero does not match its imported comparison.")

        if not self.turns:
            if self.state != "PENDING_ANALYSIS" or self.application is not None:
                raise MeldError("Invalid empty meld session state.")
            return
        latest = self.current_turn
        assert latest is not None
        assessment = latest.assessment
        if assessment is None:
            if self.state not in {
                "PENDING_ANALYSIS",
                "AWAITING_REPLY",
                "KEPT_REVIEW_ONLY",
            }:
                raise MeldError("Pending meld turn has an invalid state.")
        elif self.state == "PENDING_ANALYSIS":
            raise MeldError("An assessed meld turn cannot remain PENDING_ANALYSIS.")
        elif self.state == "READY_TO_APPLY" and not assessment.ready_to_apply:
            raise MeldError("READY meld state has a non-ready assessment.")
        elif self.state == "AWAITING_REPLY" and assessment.ready_to_apply:
            raise MeldError("Ready meld assessment cannot await a reply.")
        if self.state == "APPLIED":
            if (
                assessment is None
                or not assessment.ready_to_apply
                or self.application is None
            ):
                raise MeldError("Invalid applied meld state.")
            expected = MeldChangeSet.create(
                session_uid=self.uid,
                turn_uid=latest.uid,
                mode=self.mode,
                target=self.target,
                frames=self.frames,
                turns=self.turns,
                proposals=assessment.proposals,
            )
            if (
                self.application.change_set_digest != expected.digest
                or self.application.result_memory_uids
                != tuple(proposal.memory_uid for proposal in expected.proposals)
            ):
                raise MeldError(
                    "Applied meld receipt does not match its exact proposal."
                )
        elif self.application is not None:
            raise MeldError("Only an applied meld may retain an application.")

    def _validate_assessment(self, turn: MeldTurn) -> None:
        assessment = turn.assessment
        assert assessment is not None
        incoming_frame = self.frames[0] if self.mode == "DIRECTIONAL" else None
        baseline_frame = self.frames[1] if self.mode == "DIRECTIONAL" else None
        baseline_memory_by_uid = (
            {memory.uid: memory for memory in baseline_frame.memories}
            if baseline_frame is not None
            else {}
        )
        source_memory_uids = {
            memory.uid for frame in self.frames for memory in frame.memories
        }
        memory_keys = {
            (frame.uid, memory.uid)
            for frame in self.frames
            for memory in frame.memories
        }
        relation_member_keys: list[tuple[str, str]] = []
        relation_members_by_uid: dict[str, set[tuple[str, str]]] = {}
        relation_by_uid = {relation.uid: relation for relation in assessment.relations}
        for relation in assessment.relations:
            members = {
                (member.frame_uid, member.memory_uid) for member in relation.members
            }
            if not members <= memory_keys:
                raise MeldError("Meld relation references an unknown source Memory.")
            member_frame_uids = {member.frame_uid for member in relation.members}
            if relation.kind == "DISTINCT" and len(member_frame_uids) != 1:
                raise MeldError(
                    "A DISTINCT meld relation must belong to one source frame."
                )
            if relation.kind != "DISTINCT" and len(member_frame_uids) < 2:
                raise MeldError(
                    "A cross-source meld relation requires both source frames."
                )
            relation_member_keys.extend(members)
            relation_members_by_uid[relation.uid] = members
        # One primary group per source prevents a hidden Cartesian pair list
        # while still allowing one-to-many and many-to-one relations.
        if set(relation_member_keys) != memory_keys or len(relation_member_keys) != len(
            memory_keys
        ):
            raise MeldError(
                "Every source Memory must appear in exactly one primary meld relation."
            )
        required_relation_uids = {
            relation_uid
            for issue in assessment.issues
            if issue.priority == "REQUIRED"
            for relation_uid in issue.relation_uids
        }
        unresolved_relation_uids = {
            relation.uid
            for relation in assessment.relations
            if relation.status == "UNRESOLVED"
        }
        if not unresolved_relation_uids <= required_relation_uids:
            raise MeldError(
                "Every unresolved meld relation requires a visible REQUIRED issue."
            )
        known_turn_uids = {
            prior.uid for prior in self.turns if prior.sequence <= turn.sequence
        }
        actual_user_turn_uids = {
            prior.uid for prior in self.turns if 0 < prior.sequence <= turn.sequence
        }
        proposed_source_keys: set[tuple[str, str]] = set()
        proposed_relation_uids: set[str] = set()
        proposals_by_relation: dict[str, list[MeldProposal]] = defaultdict(list)
        for proposal in assessment.proposals:
            source_keys = {
                (member.frame_uid, member.memory_uid)
                for member in proposal.source_members
            }
            if not source_keys <= memory_keys:
                raise MeldError("Meld proposal cites an unknown source Memory.")
            linked_keys = {
                key
                for relation_uid in proposal.relation_uids
                for key in relation_members_by_uid[relation_uid]
            }
            if source_keys and not source_keys <= linked_keys:
                raise MeldError("Meld proposal source is outside its linked relation.")
            if not set(proposal.grounded_by_turn_uids) <= known_turn_uids:
                raise MeldError("Meld proposal cites an unknown or future user turn.")
            if proposal.disposition == "USER_ADD" and (
                proposal.source_members
                or not (set(proposal.grounded_by_turn_uids) & actual_user_turn_uids)
            ):
                raise MeldError(
                    "A user-added meld proposal must cite a user turn and "
                    "must not claim PEER source evidence."
                )
            if proposal.disposition != "USER_ADD" and not proposal.source_members:
                raise MeldError(
                    "A source-derived meld proposal must cite source Memory evidence."
                )
            if proposal.disposition != "USER_ADD":
                proposed_source_keys.update(source_keys)
                proposed_relation_uids.update(proposal.relation_uids)
                for relation_uid in proposal.relation_uids:
                    proposals_by_relation[relation_uid].append(proposal)
            if self.mode == "SYMMETRIC":
                if proposal.operation != "ADD":
                    raise MeldError(
                        "Symmetric Context meld may only ADD to its empty target."
                    )
                continue

            assert incoming_frame is not None and baseline_frame is not None
            incoming_evidence = any(
                frame_uid == incoming_frame.uid for frame_uid, _ in source_keys
            )
            if proposal.disposition == "USER_ADD":
                if proposal.operation != "ADD":
                    raise MeldError(
                        "A user-added directional meld result must use ADD."
                    )
            elif not incoming_evidence:
                raise MeldError(
                    "A directional meld change must cite INCOMING Memory evidence."
                )
            if proposal.operation == "EDIT":
                target_memory = baseline_memory_by_uid.get(proposal.memory_uid)
                if (
                    target_memory is None
                    or (
                        baseline_frame.uid,
                        proposal.memory_uid,
                    )
                    not in source_keys
                ):
                    raise MeldError(
                        "A directional EDIT must target and cite one BASELINE Memory."
                    )
                if proposal.content == target_memory.content:
                    raise MeldError(
                        "A directional EDIT must materially change its BASELINE Memory."
                    )
            elif proposal.memory_uid in source_memory_uids:
                raise MeldError("A directional ADD must use a fresh Memory uid.")
        if (
            self.schema_version >= MELD_SCHEMA_VERSION
            and self.mode == "SYMMETRIC"
            and assessment.ready_to_apply
        ):
            if any(
                proposal.disposition != "USER_ADD" and len(proposal.relation_uids) != 1
                for proposal in assessment.proposals
            ):
                raise MeldError(
                    "A preservation-first symmetric result must belong to "
                    "exactly one primary relation."
                )
            for relation_uid, relation in relation_by_uid.items():
                relation_proposals = proposals_by_relation.get(relation_uid, [])
                relation_members = relation_members_by_uid[relation_uid]
                if not relation_proposals:
                    raise MeldError(
                        "Every resolved symmetric relation requires a material result."
                    )
                if relation.kind == "EQUIVALENT":
                    if (
                        len(relation_proposals) != 1
                        or relation_proposals[0].disposition != "COALESCE"
                        or {
                            (member.frame_uid, member.memory_uid)
                            for member in relation_proposals[0].source_members
                        }
                        != relation_members
                    ):
                        raise MeldError(
                            "An EQUIVALENT relation must produce exactly one "
                            "complete COALESCE result."
                        )
                    continue
                for proposal in relation_proposals:
                    proposal_sources = {
                        (member.frame_uid, member.memory_uid)
                        for member in proposal.source_members
                    }
                    if len(proposal_sources) == 1:
                        if proposal.disposition != "PRESERVE":
                            raise MeldError(
                                "A single-source symmetric result must preserve "
                                "one independently useful source Memory."
                            )
                    elif relation.kind in {"COMPATIBLE", "SCOPED"}:
                        if proposal.disposition != "SYNTHESIZE" or not (
                            set(proposal.grounded_by_turn_uids) & actual_user_turn_uids
                        ):
                            raise MeldError(
                                "Combining COMPATIBLE or SCOPED Memories "
                                "requires an explicit user-grounded SYNTHESIZE "
                                "result."
                            )
                if relation.kind == "DISTINCT" and (
                    len(relation_proposals) != len(relation_members)
                    or any(
                        len(proposal.source_members) != 1
                        for proposal in relation_proposals
                    )
                ):
                    raise MeldError(
                        "A DISTINCT relation must preserve every source Memory "
                        "as its own result."
                    )
        if (
            self.mode == "SYMMETRIC"
            and assessment.ready_to_apply
            and (
                proposed_source_keys != memory_keys
                or proposed_relation_uids
                != {relation.uid for relation in assessment.relations}
            )
        ):
            raise MeldError(
                "A ready symmetric meld must represent every source Memory "
                "and primary relation in its exact result proposal."
            )


@dataclass(frozen=True)
class MeldAccounting:
    """Host-computed source-to-result accounting for one current assessment."""

    source_memories: int
    represented_sources: int
    primary_relations: int
    represented_relations: int
    final_memories: int
    preserve_results: int
    coalesce_results: int
    synthesize_results: int
    user_add_results: int
    required_issues: int
    helpful_issues: int
    cross_relation_results: int


def meld_accounting(session: MeldSession) -> MeldAccounting:
    """Compute exact accounting without trusting provider-authored counts."""
    if not isinstance(session, MeldSession):
        raise TypeError("Expected a MeldSession.")
    assessment = session.current_assessment
    source_count = sum(len(frame.memories) for frame in session.frames)
    if assessment is None:
        return MeldAccounting(
            source_memories=source_count,
            represented_sources=0,
            primary_relations=0,
            represented_relations=0,
            final_memories=0,
            preserve_results=0,
            coalesce_results=0,
            synthesize_results=0,
            user_add_results=0,
            required_issues=0,
            helpful_issues=0,
            cross_relation_results=0,
        )
    represented_sources = {
        (member.frame_uid, member.memory_uid)
        for proposal in assessment.proposals
        for member in proposal.source_members
    }
    represented_relations = {
        relation_uid
        for proposal in assessment.proposals
        for relation_uid in proposal.relation_uids
    }
    dispositions = Counter(proposal.disposition for proposal in assessment.proposals)
    priorities = Counter(issue.priority for issue in assessment.issues)
    return MeldAccounting(
        source_memories=source_count,
        represented_sources=len(represented_sources),
        primary_relations=len(assessment.relations),
        represented_relations=len(represented_relations),
        final_memories=len(assessment.proposals),
        preserve_results=dispositions["PRESERVE"],
        coalesce_results=dispositions["COALESCE"],
        synthesize_results=dispositions["SYNTHESIZE"],
        user_add_results=dispositions["USER_ADD"],
        required_issues=priorities["REQUIRED"],
        helpful_issues=priorities["HELPFUL"],
        cross_relation_results=sum(
            proposal.disposition != "USER_ADD" and len(proposal.relation_uids) != 1
            for proposal in assessment.proposals
        ),
    )


def materialize_preservation_assessment(session: MeldSession) -> MeldAssessment:
    """Build an exact provider-free preserve-all result for symmetric v3 Meld."""
    if not isinstance(session, MeldSession):
        raise TypeError("Expected a MeldSession.")
    if session.mode != "SYMMETRIC" or session.schema_version < MELD_SCHEMA_VERSION:
        raise MeldError(
            "Provider-free preservation requires a symmetric schema v3 meld."
        )
    turn = session.current_turn
    if turn is None or turn.assessment is not None or len(session.turns) < 2:
        raise MeldError(
            "Provider-free preservation requires one pending user meld turn."
        )
    prior = session.turns[-2].assessment
    if prior is None:
        raise MeldError("Provider-free preservation requires a prior assessment.")

    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in session.frames
        for memory in frame.memories
    }
    proposals: list[MeldProposal] = []
    namespace = uuid.UUID(session.uid)
    for relation in prior.relations:
        member_groups = (
            (relation.members,)
            if relation.kind == "EQUIVALENT"
            else tuple((member,) for member in relation.members)
        )
        for member_index, members in enumerate(member_groups, start=1):
            first = members[0]
            memory = memory_by_key[(first.frame_uid, first.memory_uid)]
            result_key = f"preserve:{turn.uid}:{relation.uid}:{member_index}"
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
                            else "The user requested that this supported source "
                            "distinction remain independently revisable."
                        ),
                        "relation_uids": [relation.uid],
                        "source_members": [member.to_dict() for member in members],
                        "grounded_by_turn_uids": (
                            [turn.uid] if relation.kind == "CONFLICT" else []
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
                for relation in prior.relations
            ],
            "issues": [],
            "proposals": [proposal.to_dict() for proposal in proposals],
            "ready_to_apply": True,
        }
    )
