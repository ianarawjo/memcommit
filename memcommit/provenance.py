"""Read-only reconstruction of per-Memory history and lineage.

The current store records complete Context snapshots rather than a canonical
event ledger.  This module therefore keeps an explicit distinction between
relations written by an operation and relations reconstructed from adjacent
snapshots.  In particular, equal content alone is never treated as lineage:
independent Memories may legitimately contain the same text.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Literal
import uuid

from memcommit.chunking import chunk_content
from memcommit.context import Context, Memory
from memcommit.store import MemoryStore


Evidence = Literal["RECORDED", "RECONSTRUCTED", "INFERRED", "UNRECORDED"]
EventKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "SPLIT",
    "ABSORBED",
    "MERGED_IN",
    "RESTORED",
    "ATOMIZE_KEEP",
    "ATOMIZE_PRESERVED",
    "REORDERED",
    "HISTORY_GAP",
]

TRACE_METADATA_SCHEMA_VERSION = 3
TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION = 2
TRACE_METADATA_LEGACY_SCHEMA_VERSION = 1


class ProvenanceError(RuntimeError):
    """Safe, user-facing failure while reading provenance."""


@dataclass(frozen=True)
class MemoryState:
    uid: str
    content: str
    position: int

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class SourceOccurrence:
    mode: str
    ordinal: int
    total: int
    line_number: int | None = None
    raw_line: str | None = None
    exact_raw_source: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ordinal": self.ordinal,
            "total": self.total,
            "line_number": self.line_number,
            "raw_line": self.raw_line,
            "exact_raw_source": self.exact_raw_source,
        }


@dataclass(frozen=True)
class TraceChildEvidence:
    """Recorded source/frame citations for one applied result Memory."""

    result_uid: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "result_uid": self.result_uid,
            "source_spans": list(self.source_spans),
            "frame_spans": list(self.frame_spans),
        }


@dataclass(frozen=True)
class TraceEvent:
    kind: EventKind
    evidence: Evidence
    timestamp: str | None
    checkpoint_uid: str | None
    command: str
    description: str
    before: tuple[MemoryState, ...] = ()
    after: tuple[MemoryState, ...] = ()
    reason: str | None = None
    reason_codes: tuple[str, ...] = ()
    source_occurrence: SourceOccurrence | None = None
    operation_id: str | None = None
    child_evidence: tuple[TraceChildEvidence, ...] = ()
    declared_frame: str | None = None
    declared_frame_digest: str | None = None
    uncertainty_reason: str | None = None
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    source_analysis_uid: str | None = None

    @property
    def uids(self) -> set[str]:
        return {
            state.uid
            for state in (*self.before, *self.after)
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "checkpoint_uid": self.checkpoint_uid,
            "command": self.command,
            "description": self.description,
            "before": [state.to_dict() for state in self.before],
            "after": [state.to_dict() for state in self.after],
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "source_occurrence": (
                self.source_occurrence.to_dict()
                if self.source_occurrence is not None
                else None
            ),
            "operation_id": self.operation_id,
            "child_evidence": [
                evidence.to_dict() for evidence in self.child_evidence
            ],
            "declared_frame": self.declared_frame,
            "declared_frame_digest": self.declared_frame_digest,
            "uncertainty_reason": self.uncertainty_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_analysis_uid": self.source_analysis_uid,
        }


@dataclass(frozen=True)
class TraceAnalysisChild:
    content: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "content": self.content,
            "source_spans": list(self.source_spans),
            "frame_spans": list(self.frame_spans),
        }


@dataclass(frozen=True)
class TraceAnalysis:
    """Saved semantic analysis attached to, but not changing, a lineage."""

    kind: str
    status: Literal["CURRENT", "STALE", "APPLIED"]
    analysis_uid: str
    created_at: str
    memory_uid: str
    classification: str
    action: str
    reason: str
    reason_codes: tuple[str, ...]
    children: tuple[TraceAnalysisChild, ...]
    lint: tuple[str, ...]
    declared_frame: str | None
    declared_frame_reason: str | None
    source_review_uid: str | None
    source_review_digest: str | None
    source_review_analysis_uid: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "status": self.status,
            "analysis_uid": self.analysis_uid,
            "created_at": self.created_at,
            "memory_uid": self.memory_uid,
            "classification": self.classification,
            "action": self.action,
            "reason": self.reason,
            "reason_codes": list(self.reason_codes),
            "children": [child.to_dict() for child in self.children],
            "lint": list(self.lint),
            "declared_frame": self.declared_frame,
            "declared_frame_reason": self.declared_frame_reason,
            "source_review_uid": self.source_review_uid,
            "source_review_digest": self.source_review_digest,
            "source_review_analysis_uid": self.source_review_analysis_uid,
        }


@dataclass(frozen=True)
class TraceReport:
    context_uid: str
    context_name: str
    selected_uid: str
    component_uids: tuple[str, ...]
    originals: tuple[MemoryState, ...]
    current: tuple[MemoryState, ...]
    events: tuple[TraceEvent, ...]
    analyses: tuple[TraceAnalysis, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "context": {
                "uid": self.context_uid,
                "name": self.context_name,
            },
            "selected_uid": self.selected_uid,
            "component_uids": list(self.component_uids),
            "originals": [state.to_dict() for state in self.originals],
            "current": [state.to_dict() for state in self.current],
            "events": [event.to_dict() for event in self.events],
            "analyses": [
                analysis.to_dict() for analysis in self.analyses
            ],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _Frame:
    context_uid: str
    context_name: str
    memories: dict[str, MemoryState]
    order: tuple[str, ...]


def _empty_frame(context_uid: str, context_name: str) -> _Frame:
    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories={},
        order=(),
    )


def _frame_from_snapshot(value: object, *, label: str) -> _Frame:
    if not isinstance(value, dict):
        raise ProvenanceError(f"{label} is not a valid Context snapshot.")
    context_uid = value.get("uid")
    context_name = value.get("name")
    serialized = value.get("memories")
    if (
        not isinstance(context_uid, str)
        or not context_uid
        or not isinstance(context_name, str)
        or not context_name
        or not isinstance(serialized, dict)
    ):
        raise ProvenanceError(f"{label} is not a valid Context snapshot.")

    requested_order = value.get("order")
    ordered_uids: list[str] = []
    seen: set[str] = set()
    if isinstance(requested_order, list):
        for uid in requested_order:
            if (
                isinstance(uid, str)
                and uid in serialized
                and uid not in seen
            ):
                ordered_uids.append(uid)
                seen.add(uid)
    for uid in serialized:
        if isinstance(uid, str) and uid not in seen:
            ordered_uids.append(uid)
            seen.add(uid)

    memories: dict[str, MemoryState] = {}
    memory_order: list[str] = []
    for uid in ordered_uids:
        item = serialized.get(uid)
        if not isinstance(item, dict):
            raise ProvenanceError(f"{label} contains an invalid direct item.")
        if item.get("type") != "memory":
            continue
        item_uid = item.get("uid")
        content = item.get("content")
        if item_uid != uid or not isinstance(content, str):
            raise ProvenanceError(f"{label} contains an invalid Memory.")
        memories[uid] = MemoryState(
            uid=uid,
            content=content,
            position=len(memory_order),
        )
        memory_order.append(uid)

    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories=memories,
        order=tuple(memory_order),
    )


def _frame_from_context(ctx: Context) -> _Frame:
    memories: dict[str, MemoryState] = {}
    order: list[str] = []
    for item in ctx.iter_items():
        if not isinstance(item, Memory):
            continue
        memories[item.uid] = MemoryState(
            uid=item.uid,
            content=item.content,
            position=len(order),
        )
        order.append(item.uid)
    return _Frame(
        context_uid=ctx.uid,
        context_name=ctx.name,
        memories=memories,
        order=tuple(order),
    )


def _frame_equal(left: _Frame, right: _Frame) -> bool:
    return (
        left.order == right.order
        and {
            uid: state.content
            for uid, state in left.memories.items()
        }
        == {
            uid: state.content
            for uid, state in right.memories.items()
        }
    )


def _checkpoint_entries(store: MemoryStore, context_name: str) -> list[dict]:
    """Return current and revert-retained checkpoint records, oldest first."""
    pending: list[object] = list(store.list_checkpoints(context_name))
    by_uid: dict[str, dict] = {}
    inspected = 0
    while pending:
        inspected += 1
        if inspected > 100_000:
            raise ProvenanceError("Checkpoint history is too large to trace.")
        value = pending.pop()
        if not isinstance(value, dict):
            raise ProvenanceError("Checkpoint history contains an invalid record.")
        uid = value.get("uid")
        timestamp = value.get("timestamp")
        snapshot = value.get("snapshot")
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(timestamp, str)
            or not timestamp
            or not isinstance(snapshot, dict)
        ):
            raise ProvenanceError("Checkpoint history contains an invalid record.")
        by_uid.setdefault(uid, value)
        args = value.get("args")
        log_snapshot = args.get("log_snapshot") if isinstance(args, dict) else None
        if log_snapshot is not None:
            if not isinstance(log_snapshot, list):
                raise ProvenanceError(
                    "A revert checkpoint contains an invalid log snapshot."
                )
            pending.extend(log_snapshot)
    return sorted(
        by_uid.values(),
        key=lambda entry: (entry["timestamp"], entry["uid"]),
    )


def _checkpoint_fields(entry: dict) -> tuple[str, str, str, str, dict[str, Any]]:
    uid = entry["uid"]
    timestamp = entry["timestamp"]
    command = entry.get("command")
    description = entry.get("description") or entry.get("message") or ""
    args = entry.get("args")
    return (
        uid,
        timestamp,
        command if isinstance(command, str) and command else "checkpoint",
        description if isinstance(description, str) else "",
        args if isinstance(args, dict) else {},
    )


def _ordered_states(frame: _Frame, uids: Iterable[str]) -> tuple[MemoryState, ...]:
    wanted = set(uids)
    return tuple(
        frame.memories[uid]
        for uid in frame.order
        if uid in wanted
    )


def _source_occurrences(
    *,
    args: dict[str, Any],
    after: _Frame,
    added_uids: set[str],
) -> dict[str, tuple[SourceOccurrence, Evidence]]:
    if not added_uids:
        return {}
    added = [
        uid
        for uid in after.order
        if uid in added_uids
    ]
    mode = args.get("mode")
    mode = mode if isinstance(mode, str) and mode else "single"
    declared_uids = args.get("memory_uids")
    source = args.get("source")
    raw_text = source.get("raw_text") if isinstance(source, dict) else None
    declared_hash = source.get("sha256") if isinstance(source, dict) else None
    source_integrity = (
        isinstance(raw_text, str)
        and isinstance(declared_hash, str)
        and hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        == declared_hash
    )
    explicit = (
        isinstance(declared_uids, list)
        and all(isinstance(uid, str) for uid in declared_uids)
        and len(declared_uids) == len(set(declared_uids))
        and declared_uids == added
        and source_integrity
    )
    ordered = list(declared_uids) if explicit else added

    raw_records: list[tuple[int, str]] = []
    if source_integrity:
        raw_records = [
            (line_number, raw_line)
            for line_number, raw_line in enumerate(raw_text.splitlines(), 1)
            if raw_line.strip()
        ]
    contents = args.get("contents")
    normalized_contents = contents if isinstance(contents, list) else None
    total_value = args.get("count")
    total = (
        total_value
        if isinstance(total_value, int) and total_value > 0
        else len(ordered)
    )

    result: dict[str, tuple[SourceOccurrence, Evidence]] = {}
    for index, uid in enumerate(ordered):
        if uid not in after.memories:
            continue
        line_number: int | None = None
        raw_line: str | None = None
        exact_raw_source = False
        if len(raw_records) == len(ordered):
            candidate_line_number, candidate_raw_line = raw_records[index]
            if candidate_raw_line.strip() == after.memories[uid].content:
                line_number = candidate_line_number
                raw_line = candidate_raw_line
                exact_raw_source = explicit
        elif (
            normalized_contents is not None
            and len(normalized_contents) == len(ordered)
            and normalized_contents[index] == after.memories[uid].content
        ):
            raw_line = normalized_contents[index]

        result[uid] = (
            SourceOccurrence(
                mode=mode,
                ordinal=index + 1,
                total=total,
                line_number=line_number,
                raw_line=raw_line,
                exact_raw_source=exact_raw_source,
            ),
            "RECORDED" if explicit else "RECONSTRUCTED",
        )
    return result


def _grounding_change_evidence(
    *,
    args: dict[str, Any],
    before: _Frame,
    after: _Frame,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Validate recorded conversational edits/additions against snapshots."""
    grounding = args.get("grounding")
    if not isinstance(grounding, dict):
        return {}, "has no valid grounding record"
    required = {
        "schema_version",
        "session_uid",
        "turn_uid",
        "change_set_digest",
        "change_set",
        "source_analysis_uid",
        "source_workbench_uid",
        "anchor",
        "turns",
        "decisions",
        "active_understanding",
        "changes",
    }
    schema_version = grounding.get("schema_version")
    if (
        set(grounding) != required
        or type(schema_version) is not int
        or schema_version != 1
    ):
        return {}, "has an unsupported grounding record"
    session_uid = grounding.get("session_uid")
    turn_uid = grounding.get("turn_uid")
    change_set_digest = grounding.get("change_set_digest")
    raw_change_set = grounding.get("change_set")
    analysis_uid = grounding.get("source_analysis_uid")
    workbench_uid = grounding.get("source_workbench_uid")
    anchor = grounding.get("anchor")
    turns = grounding.get("turns")
    decisions = grounding.get("decisions")
    understanding = grounding.get("active_understanding")
    changes = grounding.get("changes")
    try:
        canonical_session_uid = str(uuid.UUID(session_uid))
        canonical_turn_uid = str(uuid.UUID(turn_uid))
        canonical_analysis_uid = str(uuid.UUID(analysis_uid))
        canonical_workbench_uid = str(uuid.UUID(workbench_uid))
    except (AttributeError, TypeError, ValueError):
        return {}, "has invalid grounding identities"
    if (
        canonical_session_uid != session_uid
        or canonical_turn_uid != turn_uid
        or canonical_analysis_uid != analysis_uid
        or canonical_workbench_uid != workbench_uid
        or not isinstance(change_set_digest, str)
        or len(change_set_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in change_set_digest
        )
        or not isinstance(anchor, dict)
        or not isinstance(raw_change_set, dict)
        or not isinstance(turns, list)
        or not isinstance(decisions, list)
        or not isinstance(understanding, list)
        or any(not isinstance(item, str) for item in understanding)
        or not isinstance(changes, list)
    ):
        return {}, "has malformed grounding evidence"

    from memcommit.atomize_grounding import (
        AtomizeGroundingChangeSet,
        AtomizeGroundingError,
        AtomizeGroundingSession,
    )

    turn_comments: dict[str, str] = {}
    session_turns: list[dict[str, Any]] = []
    for value in turns:
        if not isinstance(value, dict) or set(value) != {
            "uid",
            "sequence",
            "revision",
            "comment",
            "revises_turn_uids",
            "answers_question_uids",
            "assessment",
            "comment_digest",
        }:
            return {}, "has malformed grounding turns"
        turn_data = {
            key: item
            for key, item in value.items()
            if key != "comment_digest"
        }
        uid = turn_data.get("uid")
        comment = turn_data.get("comment")
        digest = value["comment_digest"]
        if (
            not isinstance(uid, str)
            or not isinstance(comment, str)
            or not isinstance(digest, str)
            or hashlib.sha256(comment.encode("utf-8")).hexdigest() != digest
            or uid in turn_comments
        ):
            return {}, "has malformed grounding turns"
        turn_comments[uid] = comment
        session_turns.append(turn_data)
    try:
        change_set = AtomizeGroundingChangeSet.from_dict(raw_change_set)
        grounding_session = AtomizeGroundingSession.from_dict(
            {
                "schema_version": 1,
                "uid": session_uid,
                "bindings": {
                    "context": {
                        "uid": before.context_uid,
                        "name": before.context_name,
                        "digest": change_set.context_digest,
                    },
                    "analysis": {
                        "uid": analysis_uid,
                        "digest": change_set.analysis_digest,
                    },
                    "workbench": {
                        "uid": workbench_uid,
                        "digest": change_set.workbench_digest,
                        "response_digest": change_set.response_digest,
                    },
                },
                "anchor": anchor,
                "state": "READY_TO_APPLY",
                "turns": session_turns,
                "decisions": decisions,
                "application": None,
            }
        )
        prepared_change_set = grounding_session.prepare_changes()
    except AtomizeGroundingError:
        return {}, "has an invalid grounding session or change set"
    current_turn = grounding_session.current_turn
    current_assessment = grounding_session.current_assessment
    if (
        current_turn is None
        or current_turn.uid != turn_uid
        or current_assessment is None
        or list(current_assessment.active_understanding) != understanding
    ):
        return {}, "has mismatched grounding understanding or turn"
    assert current_assessment is not None
    current_proposals = {
        proposal.uid: proposal
        for proposal in current_assessment.proposals
    }
    change_set_proposals = {
        proposal.uid: proposal
        for proposal in change_set.proposals
    }
    if (
        change_set.digest != change_set_digest
        or change_set.session_uid != session_uid
        or change_set.turn_uid != turn_uid
        or change_set.context_uid != before.context_uid
        or prepared_change_set.to_dict() != change_set.to_dict()
        or any(
            proposal.to_dict()
            != current_proposals[uid].to_dict()
            for uid, proposal in change_set_proposals.items()
        )
    ):
        return {}, "has mismatched grounding change-set evidence"

    by_uid: dict[str, dict[str, Any]] = {}
    seen_change_proposals: set[str] = set()
    for value in changes:
        if not isinstance(value, dict) or set(value) != {
            "proposal_uid",
            "operation",
            "memory_uid",
            "before_content",
            "after_content",
            "reason",
            "issue_uids",
            "grounded_by_turn_uids",
        }:
            return {}, "has malformed grounding changes"
        operation = value["operation"]
        proposal_uid = value["proposal_uid"]
        memory_uid = value["memory_uid"]
        before_content = value["before_content"]
        after_content = value["after_content"]
        reason = value["reason"]
        issue_uids = value["issue_uids"]
        grounded_by = value["grounded_by_turn_uids"]
        recorded_proposal = change_set_proposals.get(proposal_uid)
        if (
            operation not in {"EDIT", "ADD"}
            or not isinstance(proposal_uid, str)
            or proposal_uid in seen_change_proposals
            or recorded_proposal is None
            or operation != recorded_proposal.operation
            or memory_uid != recorded_proposal.memory_uid
            or after_content != recorded_proposal.content
            or reason != recorded_proposal.reason
            or issue_uids != list(recorded_proposal.issue_uids)
            or grounded_by
            != list(recorded_proposal.grounded_by_turn_uids)
            or not isinstance(memory_uid, str)
            or memory_uid in by_uid
            or not isinstance(after_content, str)
            or not isinstance(reason, str)
            or not reason
            or not isinstance(issue_uids, list)
            or not issue_uids
            or any(not isinstance(item, str) for item in issue_uids)
            or not isinstance(grounded_by, list)
            or not grounded_by
            or any(uid not in turn_comments for uid in grounded_by)
        ):
            return {}, "has malformed grounding changes"
        if operation == "EDIT":
            if (
                not isinstance(before_content, str)
                or recorded_proposal.expected_content_digest
                != hashlib.sha256(
                    before_content.encode("utf-8")
                ).hexdigest()
                or memory_uid not in before.memories
                or memory_uid not in after.memories
                or before.memories[memory_uid].content != before_content
                or after.memories[memory_uid].content != after_content
            ):
                return {}, "does not match its recorded EDIT snapshot"
        elif (
            before_content is not None
            or memory_uid in before.memories
            or memory_uid not in after.memories
            or after.memories[memory_uid].content != after_content
        ):
            return {}, "does not match its recorded ADD snapshot"
        declared_evidence: list[str] = []
        if grounding_session.anchor.selected_reading_uid is not None:
            declared_evidence.append(
                "Saved workbench selected reading: "
                + grounding_session.anchor.selected_reading_text
            )
        if grounding_session.anchor.workbench_response:
            declared_evidence.append(
                "Saved workbench response: "
                + grounding_session.anchor.workbench_response
            )
        declared_evidence.extend(
            f"Turn {turn_uid[:8]}: {turn_comments[turn_uid]}"
            for turn_uid in grounded_by
        )
        declared_frame = "\n\n".join(declared_evidence)
        by_uid[memory_uid] = {
            **value,
            "session_uid": session_uid,
            "change_set_digest": change_set_digest,
            "source_analysis_uid": analysis_uid,
            "declared_frame": declared_frame,
        }
        seen_change_proposals.add(proposal_uid)
    if seen_change_proposals != set(change_set_proposals):
        return {}, "has incomplete grounding change evidence"
    return by_uid, None


def _legacy_chunk_event(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> TraceEvent | None:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(
        entry
    )
    if command != "chunk":
        return None
    source_uid = args.get("uid")
    method = args.get("method")
    if (
        not isinstance(source_uid, str)
        or source_uid not in before.memories
        or removed != {source_uid}
        or not added
        or not isinstance(method, str)
    ):
        return None

    children = [
        after.memories[uid]
        for uid in after.order
        if uid in added
    ]
    source_position = before.order.index(source_uid)
    child_positions = [child.position for child in children]
    if child_positions != list(
        range(source_position, source_position + len(children))
    ):
        return None
    before_without_source = [
        uid for uid in before.order if uid != source_uid
    ]
    after_without_children = [
        uid for uid in after.order if uid not in added
    ]
    if before_without_source != after_without_children:
        return None
    try:
        expected_contents = chunk_content(
            before.memories[source_uid].content,
            method,
        )
    except ValueError:
        return None
    if expected_contents != [child.content for child in children]:
        return None

    return TraceEvent(
        kind="SPLIT",
        evidence="RECONSTRUCTED",
        timestamp=timestamp,
        checkpoint_uid=checkpoint_uid,
        command=command,
        description=description,
        before=(before.memories[source_uid],),
        after=tuple(children),
        reason=f"Legacy structural split using method '{method}'.",
    )


def _trace_change_matches_snapshot(
    *,
    kind: str,
    source_uids: list[str],
    result_uids: list[str],
    before: _Frame,
    after: _Frame,
) -> bool:
    """Validate the structural claim made by one explicit lineage record.

    Explicit metadata is stronger evidence than a snapshot diff, so mere UID
    presence is not enough.  Each relation must describe the transition its
    name promises; otherwise a corrupt checkpoint could suppress the ordinary
    diff events by falsely consuming their UIDs.
    """
    if (
        len(source_uids) != len(set(source_uids))
        or len(result_uids) != len(set(result_uids))
    ):
        return False

    source_set = set(source_uids)
    result_set = set(result_uids)
    if kind in {"KEEP", "PRESERVE"}:
        if (
            len(source_uids) != 1
            or result_uids != source_uids
            or source_uids[0] not in before.memories
            or source_uids[0] not in after.memories
        ):
            return False
        uid = source_uids[0]
        return before.memories[uid].content == after.memories[uid].content

    if kind == "SPLIT":
        return (
            len(source_uids) == 1
            and bool(result_uids)
            and source_set.isdisjoint(result_set)
            and source_set <= set(before.memories)
            and source_set.isdisjoint(after.memories)
            and result_set <= set(after.memories)
            and result_set.isdisjoint(before.memories)
        )

    if kind == "ABSORB":
        if (
            len(source_uids) < 2
            or len(result_uids) != 1
            or not source_set <= set(before.memories)
        ):
            return False
        result_uid = result_uids[0]
        if result_uid not in after.memories:
            return False

        if result_uid in source_set:
            # Dedup-style absorption normally retains one stable source UID.
            # Its wording remains intact; every other named source disappears.
            if (
                result_uid not in before.memories
                or before.memories[result_uid].content
                != after.memories[result_uid].content
            ):
                return False
            absorbed = source_set - {result_uid}
        else:
            # Integration may instead create one fresh result, in which case
            # every source disappears from the resulting snapshot.
            if result_uid in before.memories:
                return False
            absorbed = source_set
        return absorbed.isdisjoint(after.memories)

    return False


def _atomize_evidence(
    record: dict,
    *,
    schema_version: int,
    kind: str,
    source_uids: list[str],
    result_uids: list[str],
    before: _Frame,
    args: dict,
) -> tuple[tuple[TraceChildEvidence, ...], dict[str, str] | None] | None:
    """Validate optional reviewed evidence without weakening lineage checks."""
    if set(record) != {
        "kind",
        "classification",
        "source_uids",
        "result_uids",
        "reason",
        "reason_codes",
        "child_evidence",
        "review_evidence",
    }:
        return None
    classification = record["classification"]
    expected_kind = {
        "ATOMIC": "KEEP",
        "COMPOSITE": "SPLIT",
        "UNCERTAIN": "PRESERVE",
        "NON_PROPOSITIONAL": "PRESERVE",
    }
    if schema_version not in {
        TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
        TRACE_METADATA_SCHEMA_VERSION,
    }:
        return None
    if (
        not isinstance(classification, str)
        or expected_kind.get(classification) != kind
        or len(source_uids) != 1
        or source_uids[0] not in before.memories
    ):
        return None

    raw_children = record["child_evidence"]
    if not isinstance(raw_children, list) or (
        kind == "SPLIT"
        and len(raw_children) != len(result_uids)
    ) or (kind != "SPLIT" and raw_children):
        return None
    source_content = before.memories[source_uids[0]].content
    parsed_children: list[TraceChildEvidence] = []
    for index, value in enumerate(raw_children):
        if (
            not isinstance(value, dict)
            or set(value) != {"result_uid", "source_spans", "frame_spans"}
        ):
            return None
        result_uid = value["result_uid"]
        source_spans = value["source_spans"]
        frame_spans = value["frame_spans"]
        if (
            result_uid != result_uids[index]
            or not isinstance(source_spans, list)
            or not source_spans
            or any(
                not isinstance(span, str)
                or not span
                or span not in source_content
                for span in source_spans
            )
            or len(set(source_spans)) != len(source_spans)
            or not isinstance(frame_spans, list)
            or any(not isinstance(span, str) or not span for span in frame_spans)
            or len(set(frame_spans)) != len(frame_spans)
        ):
            return None
        parsed_children.append(
            TraceChildEvidence(
                result_uid=result_uid,
                source_spans=tuple(source_spans),
                frame_spans=tuple(frame_spans),
            )
        )

    raw_review = record["review_evidence"]
    if raw_review is None:
        if any(child.frame_spans for child in parsed_children):
            return None
        return tuple(parsed_children), None
    if (
        not isinstance(raw_review, dict)
        or set(raw_review)
        != {
            "review_uid",
            "response_digest",
            "memory_uid",
            "review_item_uid",
            "source_analysis_uid",
            "uncertainty_reason",
            "text",
            "digest",
        }
    ):
        return None
    review_uid = raw_review["review_uid"]
    response_digest = raw_review["response_digest"]
    memory_uid = raw_review["memory_uid"]
    review_item_uid = raw_review["review_item_uid"]
    source_analysis_uid = raw_review["source_analysis_uid"]
    uncertainty_reason = raw_review["uncertainty_reason"]
    text = raw_review["text"]
    digest = raw_review["digest"]
    if not all(
        isinstance(value, str)
        for value in (
            memory_uid,
            review_item_uid,
            source_analysis_uid,
            uncertainty_reason,
            text,
        )
    ):
        return None
    if schema_version == TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION:
        valid_review_item = review_item_uid == memory_uid
        expected_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    else:
        from memcommit.atomize import atomize_declared_frame_digest

        valid_review_item = review_item_uid in {
            memory_uid,
            f"ambiguity:{memory_uid}",
            f"atomize:{memory_uid}",
        }
        expected_digest = atomize_declared_frame_digest(
            memory_uid=memory_uid,
            review_item_uid=review_item_uid,
            source_analysis_uid=source_analysis_uid,
            uncertainty_reason=uncertainty_reason,
            text=text,
        )
    if (
        not isinstance(review_uid, str)
        or not isinstance(response_digest, str)
        or memory_uid != source_uids[0]
        or not valid_review_item
        or not uncertainty_reason.strip()
        or not text.strip()
        or not isinstance(digest, str)
        or digest != expected_digest
        or len(response_digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in response_digest
        )
        or args.get("source_review_uid") != review_uid
        or args.get("source_review_digest") != response_digest
        or not isinstance(args.get("analysis_uid"), str)
        or args.get("analysis_uid") == source_analysis_uid
        or any(
            span not in text
            for child in parsed_children
            for span in child.frame_spans
        )
    ):
        return None
    try:
        uuid.UUID(review_uid)
        uuid.UUID(source_analysis_uid)
    except ValueError:
        return None
    return (
        tuple(parsed_children),
        {
            "review_uid": review_uid,
            "response_digest": response_digest,
            "source_analysis_uid": source_analysis_uid,
            "uncertainty_reason": uncertainty_reason,
            "text": text,
            "digest": digest,
        },
    )


def _explicit_trace_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> tuple[list[TraceEvent], set[str], set[str], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(
        entry
    )
    metadata = args.get("trace")
    if metadata is None:
        return [], set(), set(), []
    schema_version = metadata.get("schema_version") if isinstance(
        metadata,
        dict,
    ) else None
    if (
        not isinstance(metadata, dict)
        or isinstance(schema_version, bool)
        or schema_version
        not in {
            TRACE_METADATA_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_SCHEMA_VERSION,
        }
        or not isinstance(metadata.get("changes"), list)
    ):
        return (
            [],
            set(),
            set(),
            [
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid trace metadata; "
                "snapshot differences were used instead."
            ],
        )
    operation_id = metadata.get("operation_id")
    if operation_id is not None and not isinstance(operation_id, str):
        operation_id = None

    events: list[TraceEvent] = []
    consumed_before: set[str] = set()
    consumed_after: set[str] = set()
    warnings: list[str] = []
    for record in metadata["changes"]:
        if not isinstance(record, dict):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid "
                "trace change."
            )
            continue
        kind = record.get("kind")
        source_uids = record.get("source_uids")
        result_uids = record.get("result_uids")
        reason = record.get("reason")
        reason_codes = record.get("reason_codes", [])
        if (
            kind not in {"KEEP", "PRESERVE", "SPLIT", "ABSORB"}
            or not isinstance(source_uids, list)
            or not source_uids
            or any(
                not isinstance(uid, str) or not uid
                for uid in source_uids
            )
            or not isinstance(result_uids, list)
            or not result_uids
            or any(
                not isinstance(uid, str) or not uid
                for uid in result_uids
            )
            or (reason is not None and not isinstance(reason, str))
            or not isinstance(reason_codes, list)
            or any(not isinstance(code, str) for code in reason_codes)
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid "
                "trace change."
            )
            continue

        involved_uids = set(source_uids) | set(result_uids)
        if (
            involved_uids & (consumed_before | consumed_after)
            or not _trace_change_matches_snapshot(
                kind=kind,
                source_uids=source_uids,
                result_uids=result_uids,
                before=before,
                after=after,
            )
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] trace metadata does not "
                "match its snapshot; snapshot differences were used instead."
            )
            continue

        before_states = tuple(
            before.memories[uid]
            for uid in source_uids
        )
        after_states = tuple(
            after.memories[uid]
            for uid in result_uids
        )

        event_kind: EventKind = {
            "KEEP": "ATOMIZE_KEEP",
            "PRESERVE": "ATOMIZE_PRESERVED",
            "SPLIT": "SPLIT",
            "ABSORB": "ABSORBED",
        }[kind]
        child_evidence: tuple[TraceChildEvidence, ...] = ()
        review_evidence: dict[str, str] | None = None
        if schema_version in {
            TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
            TRACE_METADATA_SCHEMA_VERSION,
        }:
            parsed_evidence = _atomize_evidence(
                record,
                schema_version=schema_version,
                kind=kind,
                source_uids=source_uids,
                result_uids=result_uids,
                before=before,
                args=args,
            )
            if parsed_evidence is None:
                warnings.append(
                    f"Checkpoint [{checkpoint_uid[:8]}] has invalid reviewed "
                    "atomize evidence; lineage was retained without that "
                    "evidence."
                )
            else:
                child_evidence, review_evidence = parsed_evidence
        events.append(
            TraceEvent(
                kind=event_kind,
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=before_states,
                after=after_states,
                reason=reason,
                reason_codes=tuple(reason_codes),
                operation_id=operation_id,
                child_evidence=child_evidence,
                declared_frame=(
                    review_evidence["text"]
                    if review_evidence is not None
                    else None
                ),
                declared_frame_digest=(
                    review_evidence["digest"]
                    if review_evidence is not None
                    else None
                ),
                uncertainty_reason=(
                    review_evidence["uncertainty_reason"]
                    if review_evidence is not None
                    else None
                ),
                source_review_uid=(
                    review_evidence["review_uid"]
                    if review_evidence is not None
                    else None
                ),
                source_review_digest=(
                    review_evidence["response_digest"]
                    if review_evidence is not None
                    else None
                ),
                source_analysis_uid=(
                    review_evidence["source_analysis_uid"]
                    if review_evidence is not None
                    else None
                ),
            )
        )
        consumed_before.update(source_uids)
        consumed_after.update(result_uids)

    return events, consumed_before, consumed_after, warnings


def _transition_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    restoration: bool = False,
) -> tuple[list[TraceEvent], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(
        entry
    )
    removed = set(before.memories) - set(after.memories)
    added = set(after.memories) - set(before.memories)
    changed = {
        uid
        for uid in set(before.memories) & set(after.memories)
        if before.memories[uid].content != after.memories[uid].content
    }

    if restoration:
        events: list[TraceEvent] = []
        affected = removed | added | changed
        if affected:
            events.append(
                TraceEvent(
                    kind="RESTORED",
                    evidence="RECORDED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command="revert",
                    description=description,
                    before=_ordered_states(before, affected),
                    after=_ordered_states(after, affected),
                )
            )
        return events, []

    events, consumed_before, consumed_after, warnings = _explicit_trace_events(
        before=before,
        after=after,
        entry=entry,
    )
    removed -= consumed_before
    added -= consumed_after
    changed -= consumed_before | consumed_after

    grounding_changes: dict[str, dict[str, Any]] = {}
    if command == "atomize-grounding":
        grounding_changes, grounding_error = _grounding_change_evidence(
            args=args,
            before=before,
            after=after,
        )
        if grounding_error is not None:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] {grounding_error}; "
                "its changes were reconstructed from snapshots."
            )

    chunk_event = _legacy_chunk_event(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
    )
    if chunk_event is not None:
        events.append(chunk_event)
        removed -= {state.uid for state in chunk_event.before}
        added -= {state.uid for state in chunk_event.after}
    elif command == "chunk" and (removed or added):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] is a legacy chunk whose "
            "parent-child mapping could not be reconstructed safely."
        )

    for uid in sorted(changed, key=lambda item: after.memories[item].position):
        grounding = grounding_changes.get(uid)
        events.append(
            TraceEvent(
                kind="EDITED",
                evidence=(
                    "RECORDED"
                    if command == "edit" or grounding is not None
                    else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
                after=(after.memories[uid],),
                reason=(
                    grounding["reason"]
                    if grounding is not None
                    else None
                ),
                reason_codes=(
                    ("ATOMIZE_GROUNDING",)
                    if grounding is not None
                    else ()
                ),
                operation_id=(
                    grounding["session_uid"]
                    if grounding is not None
                    else None
                ),
                declared_frame=(
                    grounding["declared_frame"]
                    if grounding is not None
                    else None
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        grounding["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if grounding is not None
                    else None
                ),
                uncertainty_reason=(
                    "Applied after a multi-turn atomize grounding dialogue."
                    if grounding is not None
                    else None
                ),
                source_review_uid=(
                    grounding["session_uid"]
                    if grounding is not None
                    else None
                ),
                source_review_digest=(
                    grounding["change_set_digest"]
                    if grounding is not None
                    else None
                ),
                source_analysis_uid=(
                    grounding["source_analysis_uid"]
                    if grounding is not None
                    else None
                ),
            )
        )

    occurrences = _source_occurrences(
        args=args,
        after=after,
        added_uids=added,
    ) if command == "add" else {}
    if command == "add":
        source = args.get("source")
        if isinstance(source, dict):
            raw_text = source.get("raw_text")
            declared_hash = source.get("sha256")
            if not (
                isinstance(raw_text, str)
                and isinstance(declared_hash, str)
                and hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                == declared_hash
            ):
                warnings.append(
                    f"Checkpoint [{checkpoint_uid[:8]}] has an invalid add "
                    "source hash; source occurrence evidence was reconstructed."
                )
        declared_uids = args.get("memory_uids")
        added_in_context_order = [
            uid for uid in after.order if uid in added
        ]
        if (
            isinstance(declared_uids, list)
            and set(
                uid for uid in declared_uids if isinstance(uid, str)
            )
            == added
            and declared_uids != added_in_context_order
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] records add Memory UIDs "
                "out of Context order; occurrence order was reconstructed."
            )
    source_context = args.get("source_context")
    init_memory_uids = args.get("memory_uids")
    recorded_init_copy = (
        command == "init"
        and isinstance(source_context, dict)
        and isinstance(source_context.get("uid"), str)
        and isinstance(source_context.get("name"), str)
        and isinstance(init_memory_uids, list)
        and all(isinstance(uid, str) for uid in init_memory_uids)
        and len(init_memory_uids) == len(set(init_memory_uids))
        and set(init_memory_uids) == added
    )
    for uid in sorted(added, key=lambda item: after.memories[item].position):
        occurrence, occurrence_evidence = occurrences.get(uid, (None, None))
        grounding = grounding_changes.get(uid)
        event_kind: EventKind = "MERGED_IN" if command == "merge" else "CREATED"
        evidence: Evidence
        if grounding is not None:
            evidence = "RECORDED"
        elif occurrence_evidence is not None:
            evidence = occurrence_evidence
        elif recorded_init_copy:
            evidence = "RECORDED"
        elif command in {"add", "merge", "integrate"}:
            evidence = "RECONSTRUCTED"
        else:
            evidence = "INFERRED"
        events.append(
            TraceEvent(
                kind=event_kind,
                evidence=evidence,
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                after=(after.memories[uid],),
                reason=(
                    grounding["reason"]
                    if grounding is not None
                    else (
                        "Copied into this Context's source-based initial frame "
                        f"from '{source_context['name']}'."
                        if recorded_init_copy
                        else None
                    )
                ),
                reason_codes=(
                    ("ATOMIZE_GROUNDING",)
                    if grounding is not None
                    else ()
                ),
                source_occurrence=occurrence,
                operation_id=(
                    grounding["session_uid"]
                    if grounding is not None
                    else None
                ),
                declared_frame=(
                    grounding["declared_frame"]
                    if grounding is not None
                    else None
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        grounding["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if grounding is not None
                    else None
                ),
                uncertainty_reason=(
                    "Created after a multi-turn atomize grounding dialogue."
                    if grounding is not None
                    else None
                ),
                source_review_uid=(
                    grounding["session_uid"]
                    if grounding is not None
                    else None
                ),
                source_review_digest=(
                    grounding["change_set_digest"]
                    if grounding is not None
                    else None
                ),
                source_analysis_uid=(
                    grounding["source_analysis_uid"]
                    if grounding is not None
                    else None
                ),
            )
        )

    for uid in sorted(removed, key=lambda item: before.memories[item].position):
        events.append(
            TraceEvent(
                kind="REMOVED",
                evidence=(
                    "RECORDED"
                    if command in {"remove", "clear"}
                    else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
            )
        )
    if (
        set(before.memories) == set(after.memories)
        and before.order != after.order
    ):
        moved = {
            uid
            for uid in before.memories
            if before.memories[uid].position != after.memories[uid].position
        }
        if moved:
            events.append(
                TraceEvent(
                    kind="REORDERED",
                    evidence="RECONSTRUCTED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command=command,
                    description=description,
                    before=_ordered_states(before, moved),
                    after=_ordered_states(after, moved),
                    reason="Canonical direct Memory order changed.",
                )
            )
    return events, warnings


def _history(
    store: MemoryStore,
    ctx: Context,
) -> tuple[list[TraceEvent], list[str], list[_Frame]]:
    entries = _checkpoint_entries(store, ctx.name)
    frames_by_checkpoint: dict[str, _Frame] = {}
    for entry in entries:
        frames_by_checkpoint[entry["uid"]] = _frame_from_snapshot(
            entry["snapshot"],
            label=f"Checkpoint [{entry['uid'][:8]}]",
        )

    events: list[TraceEvent] = []
    warnings: list[str] = []
    frames: list[_Frame] = []
    previous: _Frame | None = None
    for entry in entries:
        frame = frames_by_checkpoint[entry["uid"]]
        if frame.context_uid != ctx.uid or frame.context_name != ctx.name:
            warnings.append(
                f"Checkpoint [{entry['uid'][:8]}] was inherited from "
                f"'{frame.context_name}'; the branch creation event was not "
                "recorded."
            )
        if previous is None:
            previous = _empty_frame(frame.context_uid, frame.context_name)

        transition, transition_warnings = _transition_events(
            before=previous,
            after=frame,
            entry=entry,
        )
        events.extend(transition)
        warnings.extend(transition_warnings)
        frames.append(frame)
        previous = frame

        _, _, command, _, args = _checkpoint_fields(entry)
        if command == "revert":
            target_uid = args.get("target_uid")
            target = (
                frames_by_checkpoint.get(target_uid)
                if isinstance(target_uid, str)
                else None
            )
            if target is None:
                warnings.append(
                    f"Revert checkpoint [{entry['uid'][:8]}] does not retain "
                    "its target snapshot."
                )
                continue
            restored_events, restored_warnings = _transition_events(
                before=frame,
                after=target,
                entry=entry,
                restoration=True,
            )
            events.extend(restored_events)
            warnings.extend(restored_warnings)
            frames.append(target)
            previous = target

    current = _frame_from_context(ctx)
    if previous is None:
        previous = _empty_frame(ctx.uid, ctx.name)
    if not _frame_equal(previous, current):
        synthetic_entry = {
            "uid": "current-unrecorded",
            "timestamp": "",
            "snapshot": ctx.to_dict(),
            "command": "current",
            "args": {},
            "description": (
                "Current Context differs from the last reconstructable "
                "checkpoint state."
            ),
        }
        gap_events, _ = _transition_events(
            before=previous,
            after=current,
            entry=synthetic_entry,
        )
        affected_before = tuple(
            state
            for event in gap_events
            for state in event.before
        )
        affected_after = tuple(
            state
            for event in gap_events
            for state in event.after
        )
        if gap_events:
            events.append(
                TraceEvent(
                    kind="HISTORY_GAP",
                    evidence="UNRECORDED",
                    timestamp=None,
                    checkpoint_uid=None,
                    command="current",
                    description=synthetic_entry["description"],
                    before=affected_before,
                    after=affected_after,
                )
            )
            warnings.append(
                "The current Context contains changes that no retained "
                "checkpoint explains."
            )
    frames.append(current)
    return events, warnings, frames


def _resolve_historical_uid(
    selector: str,
    events: Iterable[TraceEvent],
    frames: Iterable[_Frame],
) -> str:
    if not isinstance(selector, str) or not selector:
        raise ProvenanceError("Memory selector must be non-empty.")
    known = {
        uid
        for frame in frames
        for uid in frame.memories
    }
    known.update(
        state.uid
        for event in events
        for state in (*event.before, *event.after)
    )
    matches = sorted(uid for uid in known if uid.startswith(selector))
    if not matches:
        raise ProvenanceError(
            f"No direct Memory with uid starting with '{selector}' exists "
            "in the current or retained history."
        )
    if len(matches) > 1:
        raise ProvenanceError(
            f"Ambiguous prefix '{selector}' matches {len(matches)} Memories: "
            + ", ".join(uid[:8] for uid in matches)
        )
    return matches[0]


def _lineage_component(selected_uid: str, events: Iterable[TraceEvent]) -> set[str]:
    adjacency: dict[str, set[str]] = {}
    for event in events:
        if event.kind not in {"SPLIT", "ABSORBED"}:
            continue
        sources = {state.uid for state in event.before}
        results = {state.uid for state in event.after}
        for source in sources:
            adjacency.setdefault(source, set()).update(results)
        for result in results:
            adjacency.setdefault(result, set()).update(sources)
    component = {selected_uid}
    pending = [selected_uid]
    while pending:
        uid = pending.pop()
        for neighbor in adjacency.get(uid, ()):
            if neighbor in component:
                continue
            component.add(neighbor)
            pending.append(neighbor)
    return component


def _original_states(
    component: set[str],
    events: Iterable[TraceEvent],
    frames: Iterable[_Frame],
) -> tuple[MemoryState, ...]:
    parented = {
        state.uid
        for event in events
        if event.kind in {"SPLIT", "ABSORBED"}
        for state in event.after
        if state.uid not in {item.uid for item in event.before}
    }
    roots = component - parented
    earliest: dict[str, MemoryState] = {}
    for frame in frames:
        for uid in frame.order:
            if uid in roots and uid not in earliest:
                earliest[uid] = frame.memories[uid]
    for event in events:
        if event.kind == "HISTORY_GAP":
            # The uncheckpointed current frame proves only that the state is
            # present now, not that it is the lineage's retained origin.
            continue
        for state in (*event.before, *event.after):
            if state.uid in roots and state.uid not in earliest:
                earliest[state.uid] = state
    return tuple(
        sorted(earliest.values(), key=lambda state: (state.position, state.uid))
    )


def _analysis_attachments(
    store: MemoryStore,
    ctx: Context,
    component: set[str],
    events: Iterable[TraceEvent],
) -> tuple[tuple[TraceAnalysis, ...], list[str]]:
    from memcommit.atomize import atomize_analysis_matches_context

    try:
        session = store.load_atomize_analysis(ctx.uid)
    except ValueError as error:
        return (), [f"Saved atomize analysis could not be read: {error}"]
    if session is None:
        return (), []
    if session.context_uid != ctx.uid or session.context_name != ctx.name:
        return (), []
    current_frame = _frame_from_context(ctx)
    applied = False
    for checkpoint in store.list_checkpoints(ctx.name):
        args = checkpoint.get("args")
        trace = args.get("trace") if isinstance(args, dict) else None
        if not (
            isinstance(trace, dict)
            and trace.get("operation_id") == session.uid
        ):
            continue
        try:
            checkpoint_frame = _frame_from_snapshot(
                checkpoint.get("snapshot"),
                label=f"Checkpoint [{checkpoint.get('uid', '')[:8]}]",
            )
        except ProvenanceError:
            continue
        if (
            checkpoint_frame.context_uid == current_frame.context_uid
            and checkpoint_frame.context_name == current_frame.context_name
            and _frame_equal(checkpoint_frame, current_frame)
        ):
            applied = True
            break
    status: Literal["CURRENT", "STALE", "APPLIED"]
    if applied:
        status = "APPLIED"
    elif atomize_analysis_matches_context(session, ctx):
        status = "CURRENT"
    else:
        status = "STALE"
    declared_frame_by_memory_uid = {
        frame.memory_uid: frame
        for frame in session.declared_frames
    }
    analyses = tuple(
        TraceAnalysis(
            kind="ATOMIZE_PREVIEW",
            status=status,
            analysis_uid=session.uid,
            created_at=session.created_at,
            memory_uid=item.memory_uid,
            classification=item.classification,
            action=item.action,
            reason=item.reason,
            reason_codes=item.reason_codes,
            children=tuple(
                TraceAnalysisChild(
                    content=child.content,
                    source_spans=child.source_spans,
                    frame_spans=child.frame_spans,
                )
                for child in item.children
            ),
            lint=item.lint,
            declared_frame=(
                declared_frame_by_memory_uid[item.memory_uid].text
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
            declared_frame_reason=(
                declared_frame_by_memory_uid[
                    item.memory_uid
                ].uncertainty_reason
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
            source_review_uid=session.source_review_uid,
            source_review_digest=session.source_review_digest,
            source_review_analysis_uid=(
                declared_frame_by_memory_uid[
                    item.memory_uid
                ].source_analysis_uid
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
        )
        for item in session.items
        if item.memory_uid in component
    )
    return analyses, []


def build_trace(
    store: MemoryStore,
    ctx: Context,
    selector: str,
) -> TraceReport:
    """Reconstruct one selected Memory's retained content lineage."""
    events, warnings, frames = _history(store, ctx)
    selected_uid = _resolve_historical_uid(selector, events, frames)
    component = _lineage_component(selected_uid, events)
    relevant_events = tuple(
        event
        for event in events
        if event.uids & component
    )
    current_frame = frames[-1]
    current = tuple(
        current_frame.memories[uid]
        for uid in current_frame.order
        if uid in component
    )
    # _history always appends the live Context as its final frame.  Origins
    # must come from retained checkpoints or recorded/reconstructed events,
    # never solely from that live frame.
    originals = _original_states(component, relevant_events, frames[:-1])
    analyses, analysis_warnings = _analysis_attachments(
        store,
        ctx,
        component,
        relevant_events,
    )
    return TraceReport(
        context_uid=ctx.uid,
        context_name=ctx.name,
        selected_uid=selected_uid,
        component_uids=tuple(sorted(component)),
        originals=originals,
        current=current,
        events=relevant_events,
        analyses=analyses,
        warnings=tuple(dict.fromkeys((*warnings, *analysis_warnings))),
    )
