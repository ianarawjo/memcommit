"""Strict immutable state for one targetless peer-Context comparison.

Compare is deliberately smaller than Meld.  It binds two equal-authority
Context snapshots and records a complete primary relation ledger plus visible
grounding candidates.  It has no target, conversational turns, result
proposals, readiness flag, or application authority.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from memcommit.core.context import Context, Memory
from memcommit.application.operations.compare.ledger.evidence import (
    ComparisonEvidenceError,
    ComparisonEvidenceSource,
    ProjectedComparisonMemory,
    project_comparison_context,
)
from memcommit.core.context_targeting.memory_focus import (
    MemoryFocusError,
    resolve_memory_focus,
)
from memcommit.persistence.store import context_record_digest
from memcommit.application.capabilities.semantic.understanding import (
    UnderstandingSummary,
)


COMPARISON_SCHEMA_VERSION = 4
COMPARISON_DESCENDANT_SCHEMA_VERSION = 3
COMPARISON_REPORTS_SCHEMA_VERSION = 2
COMPARISON_LEGACY_SCHEMA_VERSION = 1
COMPARISON_RULESET_VERSION = "peer-relations-v4"
SUPPORTED_COMPARISON_RULESET_VERSIONS = {
    "peer-relations-v1",
    "peer-relations-v2",
    "peer-relations-v3",
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


def comparison_canonical_digest(value: object) -> str:
    """Return one deterministic digest for an exact comparison artifact."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ComparisonError("Invalid comparison digest payload.") from error
    return hashlib.sha256(encoded).hexdigest()


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
    source: ComparisonEvidenceSource | None = None

    @classmethod
    def create(
        cls,
        memory: Memory,
        position: int,
    ) -> "ComparisonMemory":
        value: dict[str, object] = {
            "uid": memory.uid,
            "content": memory.content,
            "position": position,
            "content_digest": hashlib.sha256(
                memory.content.encode("utf-8")
            ).hexdigest(),
        }
        if isinstance(memory, ProjectedComparisonMemory):
            value["source"] = memory.comparison_source.to_dict()
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
            "content_digest": self.content_digest,
        }
        if self.source is not None:
            result["source"] = self.source.to_dict()
        return result

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonMemory":
        keys = {"uid", "content", "position", "content_digest"}
        if isinstance(value, dict) and "source" in value:
            keys.add("source")
        data = _exact_dict(
            value,
            keys,
            "comparison Memory",
        )
        try:
            source = (
                ComparisonEvidenceSource.from_dict(data["source"])
                if "source" in data
                else None
            )
        except ComparisonEvidenceError as error:
            raise ComparisonError(str(error)) from error
        uid = _canonical_uuid(data["uid"], "comparison Memory uid")
        result = cls(
            uid=uid,
            content=_string(data["content"], "comparison Memory content"),
            position=_integer(
                data["position"],
                "comparison Memory position",
            ),
            content_digest=_digest(
                data["content_digest"],
                "comparison Memory content digest",
            ),
            source=source,
        )
        if source is not None and source.evidence_uid != uid:
            raise ComparisonError(
                "Comparison Memory source identity does not match its evidence uid."
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
    context_evidence: tuple[ComparisonMemory, ...] = ()
    selected_memory_uid: str | None = None

    @classmethod
    def from_context(
        cls,
        context: Context,
        *,
        side: ComparisonSide,
    ) -> "ComparisonFrame":
        if not isinstance(context, Context):
            raise ComparisonError("Compare source must be a Context.")
        try:
            context = project_comparison_context(context)
        except ComparisonEvidenceError as error:
            raise ComparisonError(str(error)) from error
        memories = tuple(
            ComparisonMemory.create(item, position)
            for position, item in enumerate(context.iter_items())
            if isinstance(item, Memory)
        )
        if not memories:
            raise ComparisonError(
                f"Source Context '{context.name}' has no readable Memory content."
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

    @classmethod
    def focused_from_context(
        cls,
        context: Context,
        *,
        side: ComparisonSide,
        memory_selector: str | None,
    ) -> tuple["ComparisonFrame", tuple[ComparisonMemory, ...]]:
        """Build one actionable frame plus non-actionable Context evidence."""

        complete = cls.from_context(context, side=side)
        try:
            focus = resolve_memory_focus(
                complete.memories,
                memory_selector,
                label=f"{side} Memory",
            )
        except MemoryFocusError as error:
            raise ComparisonError(str(error)) from error
        if focus.selected_uid is None:
            return complete, ()
        actionable = focus.actionable
        frame = cls.from_dict(
            {
                **complete.to_dict(),
                "memories": [memory.to_dict() for memory in actionable],
                "context_evidence": [
                    memory.to_dict() for memory in focus.context_only
                ],
                # Evidence is empty when the Context has only one Memory, so
                # selection identity must be stored independently. Otherwise
                # a later Refresh could silently broaden an explicit focus
                # after neighboring Memories are added.
                "selected_memory_uid": focus.selected_uid,
            }
        )
        return frame, frame.context_evidence

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "uid": self.uid,
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "context_digest": self.context_digest,
            "side": self.side,
            "memories": [memory.to_dict() for memory in self.memories],
        }
        if self.context_evidence:
            result["context_evidence"] = [
                memory.to_dict() for memory in self.context_evidence
            ]
        if self.selected_memory_uid is not None:
            result["selected_memory_uid"] = self.selected_memory_uid
        return result

    def source_state(
        self,
        *,
        include_provenance: bool = True,
    ) -> tuple[object, ...]:
        """Return the exact source state without the call-local frame UID."""

        def memory_state(memory: ComparisonMemory) -> tuple[object, ...]:
            return (
                memory.uid,
                memory.content,
                memory.position,
                memory.content_digest,
                (
                    memory.source.to_dict()
                    if include_provenance and memory.source is not None
                    else None
                ),
            )

        return (
            self.context_uid,
            self.context_name,
            self.context_digest,
            self.side,
            self.selected_memory_uid,
            tuple(memory_state(memory) for memory in self.memories),
            tuple(memory_state(memory) for memory in self.context_evidence),
        )

    def matches_context(self, context: Context) -> bool:
        """Check current content plus live provenance against this frozen frame."""

        try:
            current, _evidence = ComparisonFrame.focused_from_context(
                context,
                side=self.side,
                memory_selector=self.selected_memory_uid,
            )
        except ComparisonError:
            return False
        # Older artifacts did not retain provenance. Preserve their direct
        # owned-Memory readability while current-rule artifacts bind every
        # Embed/Reference owner and placement explicitly.
        include_provenance = any(
            memory.source is not None
            for memory in (*self.memories, *self.context_evidence)
        )
        return self.source_state(
            include_provenance=include_provenance
        ) == current.source_state(
            include_provenance=include_provenance
        )

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonFrame":
        keys = {
            "uid",
            "context_uid",
            "context_name",
            "context_digest",
            "side",
            "memories",
        }
        if isinstance(value, dict) and "context_evidence" in value:
            keys.add("context_evidence")
        if isinstance(value, dict) and "selected_memory_uid" in value:
            keys.add("selected_memory_uid")
        data = _exact_dict(
            value,
            keys,
            "comparison frame",
        )
        memories = tuple(
            ComparisonMemory.from_dict(item)
            for item in _array(
                data["memories"],
                "comparison frame Memories",
            )
        )
        context_evidence = tuple(
            ComparisonMemory.from_dict(item)
            for item in _array(
                data.get("context_evidence", []),
                "comparison Context evidence",
            )
        )
        selected_memory_uid = (
            _canonical_uuid(
                data["selected_memory_uid"],
                "selected comparison Memory uid",
            )
            if "selected_memory_uid" in data
            else (
                # Older focused frames can be identified by their neighboring
                # evidence. Singleton legacy frames remain intentionally
                # unmarked because whole-Context and explicit-focus intent
                # cannot be reconstructed from their payload.
                memories[0].uid
                if context_evidence and len(memories) == 1
                else None
            )
        )
        all_memories = (*memories, *context_evidence)
        if (
            not memories
            or len({memory.uid for memory in all_memories}) != len(all_memories)
            or sorted(memory.position for memory in all_memories)
            != list(range(len(all_memories)))
            or (
                not context_evidence
                and [memory.position for memory in memories]
                != list(range(len(memories)))
            )
        ):
            raise ComparisonError(
                "Invalid comparison frame Memory order."
            )
        if selected_memory_uid is not None and (
            len(memories) != 1
            or memories[0].uid != selected_memory_uid
        ):
            raise ComparisonError(
                "Selected comparison Memory does not match its frame."
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
            context_evidence=context_evidence,
            selected_memory_uid=selected_memory_uid,
        )
        snapshot = Context(
            uid=result.context_uid,
            name=result.context_name,
        )
        for memory in sorted(all_memories, key=lambda item: item.position):
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
class ComparisonReports:
    """Compact semantic reports backed by the exhaustive relation ledger."""

    both: str
    differences: str
    reference_only: str
    compared_only: str

    def to_dict(self) -> dict[str, object]:
        return {
            "both": self.both,
            "differences": self.differences,
            "reference_only": self.reference_only,
            "compared_only": self.compared_only,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonReports":
        data = _exact_dict(
            value,
            {
                "both",
                "differences",
                "reference_only",
                "compared_only",
            },
            "comparison reports",
        )
        return cls(
            both=_string(
                data["both"],
                "comparison both report",
                empty=True,
            ),
            differences=_string(
                data["differences"],
                "comparison differences report",
                empty=True,
            ),
            reference_only=_string(
                data["reference_only"],
                "comparison reference-only report",
                empty=True,
            ),
            compared_only=_string(
                data["compared_only"],
                "comparison compared-only report",
                empty=True,
            ),
        )


@dataclass(frozen=True)
class ComparisonInput:
    uid: str
    created_at: str
    ruleset_version: str
    frames: tuple[ComparisonFrame, ComparisonFrame]
    include_descendants: tuple[bool, bool] = (False, False)
    context_evidence: tuple[
        tuple[ComparisonMemory, ...],
        tuple[ComparisonMemory, ...],
    ] = ((), ())

    @classmethod
    def from_contexts(
        cls,
        reference: Context,
        compared: Context,
        *,
        reference_descendants: bool = False,
        compared_descendants: bool = False,
        reference_memory_selector: str | None = None,
        compared_memory_selector: str | None = None,
    ) -> "ComparisonInput":
        if (
            reference.uid == compared.uid
            or reference.name == compared.name
        ):
            raise ComparisonError(
                "Compare requires two distinct Contexts."
            )
        reference_frame, reference_evidence = ComparisonFrame.focused_from_context(
            reference,
            side="REFERENCE",
            memory_selector=reference_memory_selector,
        )
        compared_frame, compared_evidence = ComparisonFrame.focused_from_context(
            compared,
            side="COMPARED",
            memory_selector=compared_memory_selector,
        )
        result = cls(
            uid=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            ruleset_version=COMPARISON_RULESET_VERSION,
            frames=(
                reference_frame,
                compared_frame,
            ),
            include_descendants=(
                reference_descendants,
                compared_descendants,
            ),
            context_evidence=(reference_evidence, compared_evidence),
        )
        result.validate()
        return result

    def validate(self) -> None:
        _canonical_uuid(self.uid, "comparison uid")
        _timestamp(self.created_at, "comparison creation time")
        if (
            len(self.include_descendants) != 2
            or any(type(value) is not bool for value in self.include_descendants)
        ):
            raise ComparisonError("Invalid comparison descendant scopes.")
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
        if (
            len(self.context_evidence) != 2
            or any(
                len({memory.uid for memory in evidence}) != len(evidence)
                for evidence in self.context_evidence
            )
            or any(
                {memory.uid for memory in frame.memories}
                & {memory.uid for memory in evidence}
                for frame, evidence in zip(
                    self.frames,
                    self.context_evidence,
                    strict=True,
                )
            )
        ):
            raise ComparisonError("Invalid comparison Context evidence.")


def comparison_analysis_matches_input(
    analysis: "ComparisonAnalysis",
    comparison_input: ComparisonInput,
) -> bool:
    """Return whether a saved result has the exact requested actionable scope."""

    return (
        analysis.include_descendants == comparison_input.include_descendants
        and all(
            saved.source_state() == requested.source_state()
            for saved, requested in zip(
                analysis.frames,
                comparison_input.frames,
                strict=True,
            )
        )
    )
@dataclass(frozen=True)
class ComparisonAnalysis:
    uid: str
    created_at: str
    ruleset_version: str
    frames: tuple[ComparisonFrame, ComparisonFrame]
    understanding: UnderstandingSummary
    reports: ComparisonReports | None
    relations: tuple[ComparisonRelation, ...]
    issues: tuple[ComparisonIssue, ...]
    include_descendants: tuple[bool, bool] = (False, False)
    schema_version: int = COMPARISON_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        comparison_input: ComparisonInput,
        *,
        overview: str,
        reports: ComparisonReports,
        relations: Iterable[ComparisonRelation],
        issues: Iterable[ComparisonIssue],
    ) -> "ComparisonAnalysis":
        result = cls(
            uid=comparison_input.uid,
            created_at=comparison_input.created_at,
            ruleset_version=comparison_input.ruleset_version,
            frames=comparison_input.frames,
            understanding=UnderstandingSummary(
                text=overview,
                # Recursive parent/child comparisons may expose the same
                # Memory on both sides. Understanding provenance names the
                # evidence once even though the relation ledger preserves
                # both frame memberships.
                source_uids=tuple(
                    dict.fromkeys(
                        memory.uid
                        for frame in comparison_input.frames
                        for memory in frame.memories
                    )
                ),
            ),
            reports=reports,
            relations=tuple(relations),
            issues=tuple(issues),
            include_descendants=comparison_input.include_descendants,
            schema_version=COMPARISON_SCHEMA_VERSION,
        )
        return cls.from_dict(result.to_dict())

    def to_dict(self) -> dict[str, object]:
        # A legacy analysis remains serializable without fabricating prose
        # that was never returned by its provider call.
        schema_version = (
            self.schema_version
            if self.reports is not None
            else COMPARISON_LEGACY_SCHEMA_VERSION
        )
        result: dict[str, object] = {
            "schema_version": schema_version,
            "uid": self.uid,
            "created_at": self.created_at,
            "ruleset_version": self.ruleset_version,
            "frames": [frame.to_dict() for frame in self.frames],
            "overview": self.understanding.text,
            "relations": [
                relation.to_dict() for relation in self.relations
            ],
            "issues": [issue.to_dict() for issue in self.issues],
        }
        if self.reports is not None:
            result["reports"] = self.reports.to_dict()
        if schema_version >= COMPARISON_DESCENDANT_SCHEMA_VERSION:
            result["include_descendants"] = list(self.include_descendants)
        return result

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonAnalysis":
        if not isinstance(value, dict):
            raise ComparisonError("Invalid comparison analysis.")
        schema_version = value.get("schema_version")
        if (
            isinstance(schema_version, bool)
            or schema_version
            not in {
                COMPARISON_LEGACY_SCHEMA_VERSION,
                COMPARISON_REPORTS_SCHEMA_VERSION,
                COMPARISON_DESCENDANT_SCHEMA_VERSION,
                COMPARISON_SCHEMA_VERSION,
            }
        ):
            raise ComparisonError(
                "Unsupported comparison analysis schema version."
            )
        keys = {
            "schema_version",
            "uid",
            "created_at",
            "ruleset_version",
            "frames",
            "overview",
            "relations",
            "issues",
        }
        if schema_version >= COMPARISON_REPORTS_SCHEMA_VERSION:
            keys.add("reports")
        if schema_version >= COMPARISON_DESCENDANT_SCHEMA_VERSION:
            keys.add("include_descendants")
        data = _exact_dict(
            value,
            keys,
            "comparison analysis",
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
        raw_descendant_scopes = (
            data["include_descendants"]
            if schema_version >= COMPARISON_DESCENDANT_SCHEMA_VERSION
            else [False, False]
        )
        if (
            not isinstance(raw_descendant_scopes, list)
            or len(raw_descendant_scopes) != 2
            or any(type(value) is not bool for value in raw_descendant_scopes)
        ):
            raise ComparisonError("Invalid comparison descendant scopes.")
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
            understanding=UnderstandingSummary(
                text=_string(data["overview"], "comparison overview"),
                source_uids=tuple(
                    dict.fromkeys(
                        memory.uid
                        for frame in frames
                        for memory in frame.memories
                    )
                ),
            ),
            reports=(
                ComparisonReports.from_dict(data["reports"])
                if schema_version >= COMPARISON_REPORTS_SCHEMA_VERSION
                else None
            ),
            relations=relations,
            issues=issues,
            include_descendants=tuple(raw_descendant_scopes),  # type: ignore[arg-type]
            schema_version=schema_version,
        )
        result._validate()
        return result

    @property
    def overview(self) -> str:
        """Compatibility text view for older renderers and stored artifacts."""
        return self.understanding.text

    def matches(
        self,
        reference: Context,
        compared: Context,
    ) -> bool:
        return all(
            frame.matches_context(context)
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
            include_descendants=self.include_descendants,
        ).validate()
        if self.schema_version not in {
            COMPARISON_LEGACY_SCHEMA_VERSION,
            COMPARISON_REPORTS_SCHEMA_VERSION,
            COMPARISON_DESCENDANT_SCHEMA_VERSION,
            COMPARISON_SCHEMA_VERSION,
        }:
            raise ComparisonError("Unsupported comparison analysis schema version.")
        if (
            self.schema_version < COMPARISON_DESCENDANT_SCHEMA_VERSION
            and any(self.include_descendants)
        ):
            raise ComparisonError(
                "Legacy comparison analysis cannot include descendant scopes."
            )
        if (
            not self.relations
            or len({relation.uid for relation in self.relations})
            != len(self.relations)
            or len({issue.uid for issue in self.issues}) != len(self.issues)
        ):
            raise ComparisonError(
                "Invalid comparison relation or issue collection."
            )
        expected_source_uids = {
            memory.uid for frame in self.frames for memory in frame.memories
        }
        if (
            not isinstance(self.understanding, UnderstandingSummary)
            or not self.understanding.text.strip()
            or set(self.understanding.source_uids) != expected_source_uids
        ):
            raise ComparisonError("Invalid comparison understanding summary.")
        if (
            self.ruleset_version == COMPARISON_RULESET_VERSION
            and self.reports is None
        ):
            raise ComparisonError(
                "The current comparison ruleset requires semantic reports."
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

        if self.reports is not None:
            reference_uid, compared_uid = (
                frame.uid for frame in self.frames
            )
            # The ledger, rather than provider-authored counts or labels, is
            # authoritative for whether each compact report may exist.
            report_groups = {
                "both": any(
                    relation.kind in {"EQUIVALENT", "COMPATIBLE"}
                    for relation in self.relations
                ),
                "differences": any(
                    relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"}
                    for relation in self.relations
                ),
                "reference_only": any(
                    relation.kind == "DISTINCT"
                    and all(
                        member.frame_uid == reference_uid
                        for member in relation.members
                    )
                    for relation in self.relations
                ),
                "compared_only": any(
                    relation.kind == "DISTINCT"
                    and all(
                        member.frame_uid == compared_uid
                        for member in relation.members
                    )
                    for relation in self.relations
                ),
            }
            for name, present in report_groups.items():
                report = getattr(self.reports, name)
                if (present and not report.strip()) or (
                    not present and report != ""
                ):
                    raise ComparisonError(
                        f"Comparison {name.replace('_', '-')} report does "
                        "not match its relation group."
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
