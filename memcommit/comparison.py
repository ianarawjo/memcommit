"""Strict immutable state for one targetless peer-Context comparison.

Compare is deliberately smaller than Meld.  It binds two equal-authority
Context snapshots and records a complete primary relation ledger plus visible
grounding candidates.  It has no target, conversational turns, result
proposals, readiness flag, or application authority.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from memcommit.context import Context, Memory
from memcommit.store import context_record_digest


COMPARISON_SCHEMA_VERSION = 1
COMPARISON_RULESET_VERSION = "peer-relations-v2"
SUPPORTED_COMPARISON_RULESET_VERSIONS = {
    "peer-relations-v1",
    COMPARISON_RULESET_VERSION,
}
COMPARISON_TEXT_LIMIT = 20_000
COMPARISON_NAME_LIMIT = COMPARISON_TEXT_LIMIT
COMPARISON_ID_LIMIT = 240

ComparisonSide = Literal["REFERENCE", "COMPARED"]
ComparisonRelationKind = Literal[
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
]
ComparisonRelationStatus = Literal["RESOLVED", "UNRESOLVED"]
ComparisonIssuePriority = Literal["REQUIRED", "HELPFUL"]

_SIDES = {"REFERENCE", "COMPARED"}
_RELATIONS = {
    "EQUIVALENT",
    "COMPATIBLE",
    "SCOPED",
    "CONFLICT",
    "DISTINCT",
    "UNCLEAR",
}
_STATUSES = {"RESOLVED", "UNRESOLVED"}
_PRIORITIES = {"REQUIRED", "HELPFUL"}


class ComparisonError(ValueError):
    """Invalid, unsupported, or internally inconsistent comparison state."""


def _exact_dict(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ComparisonError(f"Invalid {label}.")
    return value


def _array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ComparisonError(f"Invalid {label}.")
    return value


def _string(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = COMPARISON_TEXT_LIMIT,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
    ):
        raise ComparisonError(f"Invalid {label}.")
    return value


def _identifier(value: object, label: str) -> str:
    return _string(value, label, limit=COMPARISON_ID_LIMIT)


def _canonical_uuid(value: object, label: str) -> str:
    text = _string(value, label, limit=36)
    try:
        canonical = str(uuid.UUID(text))
    except (AttributeError, TypeError, ValueError) as error:
        raise ComparisonError(f"Invalid {label}.") from error
    if canonical != text:
        raise ComparisonError(f"Invalid {label}.")
    return text


def _digest(value: object, label: str) -> str:
    text = _string(value, label, limit=64)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ComparisonError(f"Invalid {label}.")
    return text


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ComparisonError(f"Invalid {label}.")
    return value


def _literal(value: object, allowed: set[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ComparisonError(f"Invalid {label}.")
    return value


def _unique_uuid_tuple(
    value: object,
    label: str,
    *,
    empty: bool = False,
) -> tuple[str, ...]:
    values = _array(value, label)
    if not empty and not values:
        raise ComparisonError(f"Invalid {label}.")
    result = tuple(_canonical_uuid(item, label) for item in values)
    if len(result) != len(set(result)):
        raise ComparisonError(f"Duplicate {label}.")
    return result


def _timestamp(value: object, label: str) -> str:
    text = _string(value, label, limit=80)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise ComparisonError(f"Invalid {label}.") from error
    if parsed.tzinfo is None:
        raise ComparisonError(f"Invalid {label}.")
    return text


@dataclass(frozen=True)
class ComparisonMemory:
    uid: str
    content: str
    position: int
    content_digest: str

    @classmethod
    def create(
        cls,
        memory: Memory,
        position: int,
    ) -> "ComparisonMemory":
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
    def from_dict(cls, value: object) -> "ComparisonMemory":
        data = _exact_dict(
            value,
            {"uid", "content", "position", "content_digest"},
            "comparison Memory",
        )
        result = cls(
            uid=_canonical_uuid(data["uid"], "comparison Memory uid"),
            content=_string(data["content"], "comparison Memory content"),
            position=_integer(
                data["position"],
                "comparison Memory position",
            ),
            content_digest=_digest(
                data["content_digest"],
                "comparison Memory content digest",
            ),
        )
        if result.content_digest != hashlib.sha256(
            result.content.encode("utf-8")
        ).hexdigest():
            raise ComparisonError(
                "Comparison Memory content digest does not match."
            )
        return result


@dataclass(frozen=True)
class ComparisonFrame:
    uid: str
    context_uid: str
    context_name: str
    context_digest: str
    side: ComparisonSide
    memories: tuple[ComparisonMemory, ...]

    @classmethod
    def from_context(
        cls,
        context: Context,
        *,
        side: ComparisonSide,
    ) -> "ComparisonFrame":
        if not isinstance(context, Context):
            raise ComparisonError("Compare source must be a Context.")
        unsupported = [
            uid
            for uid, item in context.iter_entries()
            if not isinstance(item, Memory)
        ]
        if unsupported:
            raise ComparisonError(
                "Compare version 1 supports direct owned Memories only; "
                "unsupported direct item(s): "
                + ", ".join(uid[:8] for uid in unsupported)
                + "."
            )
        memories = tuple(
            ComparisonMemory.create(item, position)
            for position, item in enumerate(context.iter_items())
            if isinstance(item, Memory)
        )
        if not memories:
            raise ComparisonError(
                f"Source Context '{context.name}' has no direct Memories."
            )
        return cls.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "context_uid": context.uid,
                "context_name": context.name,
                "context_digest": context_record_digest(context),
                "side": side,
                "memories": [memory.to_dict() for memory in memories],
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "side": self.side,
            "memories": [memory.to_dict() for memory in self.memories],
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonFrame":
        data = _exact_dict(
            value,
            {
                "uid",
                "context_uid",
                "context_name",
                "context_digest",
                "side",
                "memories",
            },
            "comparison frame",
        )
        memories = tuple(
            ComparisonMemory.from_dict(item)
            for item in _array(
                data["memories"],
                "comparison frame Memories",
            )
        )
        if (
            not memories
            or len({memory.uid for memory in memories}) != len(memories)
            or [memory.position for memory in memories]
            != list(range(len(memories)))
        ):
            raise ComparisonError(
                "Invalid comparison frame Memory order."
            )
        result = cls(
            uid=_canonical_uuid(data["uid"], "comparison frame uid"),
            context_uid=_canonical_uuid(
                data["context_uid"],
                "comparison frame Context uid",
            ),
            context_name=_string(
                data["context_name"],
                "comparison frame Context name",
                limit=COMPARISON_NAME_LIMIT,
            ),
            context_digest=_digest(
                data["context_digest"],
                "comparison frame Context digest",
            ),
            side=_literal(  # type: ignore[arg-type]
                data["side"],
                _SIDES,
                "comparison frame side",
            ),
            memories=memories,
        )
        snapshot = Context(
            uid=result.context_uid,
            name=result.context_name,
        )
        for memory in result.memories:
            snapshot.add(
                Memory(
                    uid=memory.uid,
                    content=memory.content,
                )
            )
        if context_record_digest(snapshot) != result.context_digest:
            raise ComparisonError(
                "Comparison frame snapshot does not match its Context digest."
            )
        return result


@dataclass(frozen=True)
class ComparisonMember:
    frame_uid: str
    memory_uid: str

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_uid": self.frame_uid,
            "memory_uid": self.memory_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonMember":
        data = _exact_dict(
            value,
            {"frame_uid", "memory_uid"},
            "comparison member",
        )
        return cls(
            frame_uid=_canonical_uuid(
                data["frame_uid"],
                "comparison member frame uid",
            ),
            memory_uid=_canonical_uuid(
                data["memory_uid"],
                "comparison member Memory uid",
            ),
        )


@dataclass(frozen=True)
class ComparisonRelation:
    uid: str
    kind: ComparisonRelationKind
    status: ComparisonRelationStatus
    members: tuple[ComparisonMember, ...]
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
    def from_dict(cls, value: object) -> "ComparisonRelation":
        data = _exact_dict(
            value,
            {"uid", "kind", "status", "members", "summary", "reason"},
            "comparison relation",
        )
        members = tuple(
            ComparisonMember.from_dict(item)
            for item in _array(
                data["members"],
                "comparison relation members",
            )
        )
        if not members or len(
            {(member.frame_uid, member.memory_uid) for member in members}
        ) != len(members):
            raise ComparisonError("Invalid comparison relation members.")
        kind = _literal(  # type: ignore[assignment]
            data["kind"],
            _RELATIONS,
            "comparison relation kind",
        )
        status = _literal(  # type: ignore[assignment]
            data["status"],
            _STATUSES,
            "comparison relation status",
        )
        expected_status = (
            "UNRESOLVED"
            if kind in {"CONFLICT", "UNCLEAR"}
            else "RESOLVED"
        )
        if status != expected_status:
            raise ComparisonError(
                f"Comparison relation {kind} must be {expected_status}."
            )
        return cls(
            uid=_canonical_uuid(data["uid"], "comparison relation uid"),
            kind=kind,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            members=members,
            summary=_string(
                data["summary"],
                "comparison relation summary",
            ),
            reason=_string(
                data["reason"],
                "comparison relation reason",
            ),
        )


@dataclass(frozen=True)
class ComparisonOption:
    uid: str
    label: str
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "label": self.label,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonOption":
        data = _exact_dict(
            value,
            {"uid", "label", "text"},
            "comparison issue option",
        )
        return cls(
            uid=_canonical_uuid(data["uid"], "comparison option uid"),
            label=_string(data["label"], "comparison option label"),
            text=_string(data["text"], "comparison option text"),
        )


@dataclass(frozen=True)
class ComparisonIssue:
    uid: str
    relation_uids: tuple[str, ...]
    priority: ComparisonIssuePriority
    title: str
    question: str
    why_it_matters: str
    options: tuple[ComparisonOption, ...]

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
    def from_dict(cls, value: object) -> "ComparisonIssue":
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
            "comparison issue",
        )
        options = tuple(
            ComparisonOption.from_dict(item)
            for item in _array(
                data["options"],
                "comparison issue options",
            )
        )
        if len({option.uid for option in options}) != len(options):
            raise ComparisonError("Duplicate comparison issue option.")
        return cls(
            uid=_canonical_uuid(data["uid"], "comparison issue uid"),
            relation_uids=_unique_uuid_tuple(
                data["relation_uids"],
                "comparison issue relation uids",
            ),
            priority=_literal(  # type: ignore[arg-type]
                data["priority"],
                _PRIORITIES,
                "comparison issue priority",
            ),
            title=_string(data["title"], "comparison issue title"),
            question=_string(
                data["question"],
                "comparison issue question",
            ),
            why_it_matters=_string(
                data["why_it_matters"],
                "comparison issue consequence",
            ),
            options=options,
        )


@dataclass(frozen=True)
class ComparisonInput:
    uid: str
    created_at: str
    ruleset_version: str
    frames: tuple[ComparisonFrame, ComparisonFrame]

    @classmethod
    def from_contexts(
        cls,
        reference: Context,
        compared: Context,
    ) -> "ComparisonInput":
        if (
            reference.uid == compared.uid
            or reference.name == compared.name
        ):
            raise ComparisonError(
                "Compare requires two distinct Contexts."
            )
        result = cls(
            uid=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            ruleset_version=COMPARISON_RULESET_VERSION,
            frames=(
                ComparisonFrame.from_context(
                    reference,
                    side="REFERENCE",
                ),
                ComparisonFrame.from_context(
                    compared,
                    side="COMPARED",
                ),
            ),
        )
        result.validate()
        return result

    def validate(self) -> None:
        _canonical_uuid(self.uid, "comparison uid")
        _timestamp(self.created_at, "comparison creation time")
        if (
            self.ruleset_version
            not in SUPPORTED_COMPARISON_RULESET_VERSIONS
        ):
            raise ComparisonError(
                "Unsupported comparison ruleset version."
            )
        if (
            len(self.frames) != 2
            or tuple(frame.side for frame in self.frames)
            != ("REFERENCE", "COMPARED")
            or len({frame.uid for frame in self.frames}) != 2
            or len({frame.context_uid for frame in self.frames}) != 2
            or len({frame.context_name for frame in self.frames}) != 2
        ):
            raise ComparisonError(
                "Compare requires ordered distinct REFERENCE and COMPARED "
                "frames."
            )


@dataclass(frozen=True)
class ComparisonAnalysis:
    uid: str
    created_at: str
    ruleset_version: str
    frames: tuple[ComparisonFrame, ComparisonFrame]
    overview: str
    relations: tuple[ComparisonRelation, ...]
    issues: tuple[ComparisonIssue, ...]

    @classmethod
    def create(
        cls,
        comparison_input: ComparisonInput,
        *,
        overview: str,
        relations: Iterable[ComparisonRelation],
        issues: Iterable[ComparisonIssue],
    ) -> "ComparisonAnalysis":
        result = cls(
            uid=comparison_input.uid,
            created_at=comparison_input.created_at,
            ruleset_version=comparison_input.ruleset_version,
            frames=comparison_input.frames,
            overview=overview,
            relations=tuple(relations),
            issues=tuple(issues),
        )
        return cls.from_dict(result.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "uid": self.uid,
            "created_at": self.created_at,
            "ruleset_version": self.ruleset_version,
            "frames": [frame.to_dict() for frame in self.frames],
            "overview": self.overview,
            "relations": [
                relation.to_dict() for relation in self.relations
            ],
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonAnalysis":
        data = _exact_dict(
            value,
            {
                "schema_version",
                "uid",
                "created_at",
                "ruleset_version",
                "frames",
                "overview",
                "relations",
                "issues",
            },
            "comparison analysis",
        )
        if (
            isinstance(data["schema_version"], bool)
            or data["schema_version"] != COMPARISON_SCHEMA_VERSION
        ):
            raise ComparisonError(
                "Unsupported comparison analysis schema version."
            )
        frames = tuple(
            ComparisonFrame.from_dict(item)
            for item in _array(data["frames"], "comparison frames")
        )
        if len(frames) != 2:
            raise ComparisonError(
                "Comparison analysis requires exactly two frames."
            )
        relations = tuple(
            ComparisonRelation.from_dict(item)
            for item in _array(
                data["relations"],
                "comparison relations",
            )
        )
        issues = tuple(
            ComparisonIssue.from_dict(item)
            for item in _array(data["issues"], "comparison issues")
        )
        result = cls(
            uid=_canonical_uuid(data["uid"], "comparison uid"),
            created_at=_timestamp(
                data["created_at"],
                "comparison creation time",
            ),
            ruleset_version=_identifier(
                data["ruleset_version"],
                "comparison ruleset version",
            ),
            frames=(frames[0], frames[1]),
            overview=_string(
                data["overview"],
                "comparison overview",
            ),
            relations=relations,
            issues=issues,
        )
        result._validate()
        return result

    def matches(
        self,
        reference: Context,
        compared: Context,
    ) -> bool:
        return all(
            (
                context.uid == frame.context_uid
                and context.name == frame.context_name
                and context_record_digest(context) == frame.context_digest
            )
            for frame, context in zip(
                self.frames,
                (reference, compared),
                strict=True,
            )
        )

    def _validate(self) -> None:
        ComparisonInput(
            uid=self.uid,
            created_at=self.created_at,
            ruleset_version=self.ruleset_version,
            frames=self.frames,
        ).validate()
        if (
            not self.relations
            or len({relation.uid for relation in self.relations})
            != len(self.relations)
            or len({issue.uid for issue in self.issues}) != len(self.issues)
        ):
            raise ComparisonError(
                "Invalid comparison relation or issue collection."
            )

        frame_by_uid = {frame.uid: frame for frame in self.frames}
        expected_members = {
            (frame.uid, memory.uid)
            for frame in self.frames
            for memory in frame.memories
        }
        observed_members: list[tuple[str, str]] = []
        relation_by_uid = {
            relation.uid: relation for relation in self.relations
        }
        for relation in self.relations:
            relation_sides: set[str] = set()
            for member in relation.members:
                frame = frame_by_uid.get(member.frame_uid)
                if frame is None or member.memory_uid not in {
                    memory.uid for memory in frame.memories
                }:
                    raise ComparisonError(
                        "Comparison relation references an unknown source "
                        "Memory."
                    )
                observed_members.append(
                    (member.frame_uid, member.memory_uid)
                )
                relation_sides.add(frame.side)
            if relation.kind == "DISTINCT":
                if len(relation_sides) != 1:
                    raise ComparisonError(
                        "DISTINCT comparison relation must contain exactly "
                        "one source side."
                    )
            elif relation_sides != {"REFERENCE", "COMPARED"}:
                raise ComparisonError(
                    "Cross-source comparison relation must contain both "
                    "source sides."
                )
        if (
            set(observed_members) != expected_members
            or len(observed_members) != len(expected_members)
        ):
            raise ComparisonError(
                "Every source Memory must appear in exactly one primary "
                "comparison relation."
            )

        unresolved_uids = {
            relation.uid
            for relation in self.relations
            if relation.status == "UNRESOLVED"
        }
        required_issue_relations: set[str] = set()
        for issue in self.issues:
            unknown = set(issue.relation_uids) - relation_by_uid.keys()
            if unknown:
                raise ComparisonError(
                    "Comparison issue references an unknown relation."
                )
            if issue.priority == "REQUIRED":
                required_issue_relations.update(issue.relation_uids)
        if not unresolved_uids <= required_issue_relations:
            raise ComparisonError(
                "Every unresolved comparison relation must appear in a "
                "visible REQUIRED issue."
            )
