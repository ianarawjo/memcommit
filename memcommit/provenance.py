"""Read-only reconstruction of per-Memory history and lineage.

The current store records complete Context snapshots rather than a canonical
event ledger.  This module therefore keeps an explicit distinction between
relations written by an operation and relations reconstructed from adjacent
snapshots.  In particular, equal content alone is never treated as lineage:
independent Memories may legitimately contain the same text.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Iterable, Literal, Sequence
import uuid

from memcommit.chunking import chunk_content
from memcommit.command_history import CommandHistoryError, branch_tree_receipt
from memcommit.context import Context, Memory
from memcommit.history import HistoryError, flatten_checkpoint_entries
from memcommit.memory_lineage import (
    MemoryLineageEdge,
    memory_content_sha256,
    parse_memory_lineage_receipt,
)
from memcommit.store import (
    MemoryStore,
    canonical_context_record,
    context_record_digest,
)
from memcommit.temporal_history import direct_memory_deltas
from memcommit.translate import TRANSLATION_TARGET_CHAR_LIMIT


Evidence = Literal["RECORDED", "RECONSTRUCTED", "INFERRED", "UNRECORDED"]
EventKind = Literal[
    "CREATED",
    "EDITED",
    "REMOVED",
    "SPLIT",
    "ABSORBED",
    "MERGED_IN",
    "RESTORED",
    "TRANSLATED",
    "ATOMIZE_KEEP",
    "ATOMIZE_PRESERVED",
    "MELDED",
    "BRANCHED",
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
class TraceCandidate:
    """One full-UID Memory choice for trace/rationale selection."""

    uid: str
    content: str
    position: int
    status: Literal["CURRENT", "HISTORICAL"]
    # ``None`` is an authority boundary, not a zero: granted READ content may
    # be selectable for Rationale without exposing its owner's retained log.
    change_count: int | None = None


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
class TraceCommandContext:
    """One Context named by a retained command-unit receipt."""

    uid: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "name": self.name}


@dataclass(frozen=True)
class TraceCommandOperation:
    """The command boundary shared by one or more Context checkpoints."""

    uid: str
    command: str
    contexts: tuple[TraceCommandContext, ...]
    source_uid: str | None = None
    source_command: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "command": self.command,
            "contexts": [context.to_dict() for context in self.contexts],
            "source_uid": self.source_uid,
            "source_command": self.source_command,
        }


@dataclass(frozen=True)
class TraceContextTransition:
    """One recorded ancestry transition between Context-bound occurrences."""

    source: TraceCommandContext
    target: TraceCommandContext

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
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
    command_operation: TraceCommandOperation | None = None
    context_transition: TraceContextTransition | None = None
    child_evidence: tuple[TraceChildEvidence, ...] = ()
    declared_frame: str | None = None
    declared_frame_digest: str | None = None
    uncertainty_reason: str | None = None
    source_review_uid: str | None = None
    source_review_digest: str | None = None
    source_analysis_uid: str | None = None

    @property
    def uids(self) -> set[str]:
        return {state.uid for state in (*self.before, *self.after)}

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
            "command_operation": (
                self.command_operation.to_dict()
                if self.command_operation is not None
                else None
            ),
            "context_transition": (
                self.context_transition.to_dict()
                if self.context_transition is not None
                else None
            ),
            "child_evidence": [evidence.to_dict() for evidence in self.child_evidence],
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
            "analyses": [analysis.to_dict() for analysis in self.analyses],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class _Frame:
    context_uid: str
    context_name: str
    memories: dict[str, MemoryState]
    order: tuple[str, ...]
    record: dict[str, Any]
    record_digest: str


def _empty_frame(context_uid: str, context_name: str) -> _Frame:
    record: dict[str, Any] = {
        "uid": context_uid,
        "name": context_name,
        "memories": {},
        "order": [],
    }
    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories={},
        order=(),
        record=record,
        record_digest=context_record_digest(record),
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
            if isinstance(uid, str) and uid in serialized and uid not in seen:
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

    canonical_record = canonical_context_record(value)
    return _Frame(
        context_uid=context_uid,
        context_name=context_name,
        memories=memories,
        order=tuple(memory_order),
        record=canonical_record,
        record_digest=context_record_digest(canonical_record),
    )


def _frame_from_context(ctx: Context) -> _Frame:
    record = ctx.to_dict()
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
        record=record,
        record_digest=context_record_digest(record),
    )


def _atomize_save_as_source_frame(
    args: dict[str, Any],
    after: _Frame,
) -> _Frame | None:
    """Recover the non-published branch baseline retained for Trace only."""

    receipt = args.get("atomize_save_as")
    if not isinstance(receipt, dict) or receipt.get("version") != 1:
        return None
    raw_frame = receipt.get("source_frame")
    declared_digest = receipt.get("source_frame_digest")
    if not isinstance(raw_frame, list) or not isinstance(declared_digest, str):
        return None
    ordered: list[dict[str, object]] = []
    seen: set[str] = set()
    for position, item in enumerate(raw_frame):
        if (
            not isinstance(item, dict)
            or set(item) != {"uid", "content", "position"}
            or not isinstance(item.get("uid"), str)
            or not isinstance(item.get("content"), str)
            or item.get("position") != position
            or item["uid"] in seen
        ):
            return None
        seen.add(item["uid"])
        ordered.append(item)
    actual_digest = hashlib.sha256(
        json.dumps(
            [{"uid": item["uid"], "content": item["content"]} for item in ordered],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if actual_digest != declared_digest:
        return None
    return _frame_from_snapshot(
        {
            "uid": after.context_uid,
            "name": after.context_name,
            "memories": {
                item["uid"]: {
                    "type": "memory",
                    "uid": item["uid"],
                    "content": item["content"],
                }
                for item in ordered
            },
            "order": [item["uid"] for item in ordered],
        },
        label="Atomize Save As Source frame",
    )


def _frame_equal(left: _Frame, right: _Frame) -> bool:
    return left.order == right.order and {
        uid: state.content for uid, state in left.memories.items()
    } == {uid: state.content for uid, state in right.memories.items()}


def _checkpoint_entries(store: MemoryStore, context_name: str) -> list[dict]:
    """Return the common current and revert-retained checkpoint catalog."""
    try:
        entries, _physical_uids = flatten_checkpoint_entries(
            store.list_checkpoints(context_name)
        )
    except HistoryError as error:
        raise ProvenanceError(str(error)) from error
    return entries


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
    return tuple(frame.memories[uid] for uid in frame.order if uid in wanted)


def _source_occurrences(
    *,
    args: dict[str, Any],
    after: _Frame,
    added_uids: set[str],
) -> dict[str, tuple[SourceOccurrence, Evidence]]:
    if not added_uids:
        return {}
    added = [uid for uid in after.order if uid in added_uids]
    mode = args.get("mode")
    mode = mode if isinstance(mode, str) and mode else "single"
    declared_uids = args.get("memory_uids")
    source = args.get("source")
    raw_text = source.get("raw_text") if isinstance(source, dict) else None
    declared_hash = source.get("sha256") if isinstance(source, dict) else None
    source_integrity = (
        isinstance(raw_text, str)
        and isinstance(declared_hash, str)
        and hashlib.sha256(raw_text.encode("utf-8")).hexdigest() == declared_hash
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
        or any(character not in "0123456789abcdef" for character in change_set_digest)
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
            key: item for key, item in value.items() if key != "comment_digest"
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
        proposal.uid: proposal for proposal in current_assessment.proposals
    }
    change_set_proposals = {proposal.uid: proposal for proposal in change_set.proposals}
    if (
        change_set.digest != change_set_digest
        or change_set.session_uid != session_uid
        or change_set.turn_uid != turn_uid
        or change_set.context_uid != before.context_uid
        or prepared_change_set.to_dict() != change_set.to_dict()
        or any(
            proposal.to_dict() != current_proposals[uid].to_dict()
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
            or grounded_by != list(recorded_proposal.grounded_by_turn_uids)
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
                != hashlib.sha256(before_content.encode("utf-8")).hexdigest()
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


def _owner_aware_meld_change_evidence(
    *,
    record: dict[str, Any],
    before: _Frame,
    after: _Frame,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Validate one owner checkpoint from a directional subtree Meld."""
    required = {
        "schema_version",
        "session_uid",
        "turn_uid",
        "mode",
        "change_set_digest",
        "change_set",
        "sources",
        "target_baseline",
        "turns",
        "results",
        "owner_context_uid",
        "owner_context_name",
    }
    if set(record) != required or record.get("mode") != "DIRECTIONAL":
        return {}, "has no valid owner-aware meld record"
    if (
        record.get("owner_context_uid") != before.context_uid
        or record.get("owner_context_name") != before.context_name
        or before.context_uid != after.context_uid
        or before.context_name != after.context_name
    ):
        return {}, "has a mismatched owner-aware meld checkpoint"
    try:
        from memcommit.meld import (
            MeldChangeSet,
            MeldFrame,
            meld_canonical_digest,
        )

        change_set = MeldChangeSet.from_dict(record["change_set"])
    except (KeyError, TypeError, ValueError):
        return {}, "has an invalid meld change set"
    if (
        record.get("session_uid") != change_set.session_uid
        or record.get("turn_uid") != change_set.turn_uid
        or record.get("change_set_digest") != change_set.digest
        or change_set.mode != "DIRECTIONAL"
    ):
        return {}, "has mismatched meld identities"
    target = record.get("target_baseline")
    if (
        not isinstance(target, dict)
        or set(target) != {"context_uid", "context_name", "context_digest"}
        or target.get("context_uid") != change_set.target_uid
        or target.get("context_digest") != change_set.target_digest
    ):
        return {}, "has a mismatched meld target baseline"

    sources = record.get("sources")
    expected_frame_digests = dict(change_set.source_frame_digests)
    if not isinstance(sources, list) or len(sources) != len(expected_frame_digests):
        return {}, "has invalid meld source bindings"
    source_labels: dict[str, str] = {}
    source_roles: dict[str, str] = {}
    source_memory_text: dict[tuple[str, str], str] = {}
    source_memory_owner: dict[tuple[str, str], tuple[str, str]] = {}
    baseline_contexts: set[tuple[str, str]] = set()
    for source in sources:
        if not isinstance(source, dict):
            return {}, "has invalid meld source bindings"
        keys = {
            "frame_uid",
            "role",
            "context_uid",
            "context_name",
            "context_digest",
            "memories",
            "contexts",
        }
        if "include_descendants" in source:
            keys.add("include_descendants")
        if set(source) != keys:
            return {}, "has invalid meld source bindings"
        frame_value: dict[str, object] = {
            "uid": source["frame_uid"],
            "role": source["role"],
            "context_uid": source["context_uid"],
            "context_name": source["context_name"],
            "context_digest": source["context_digest"],
            "memories": source["memories"],
            "contexts": source["contexts"],
        }
        if "include_descendants" in source:
            frame_value["include_descendants"] = source["include_descendants"]
        try:
            frame = MeldFrame.from_dict(frame_value)
        except (TypeError, ValueError):
            return {}, "has invalid owner-aware meld source snapshots"
        if (
            frame.uid not in expected_frame_digests
            or frame.context_digest != expected_frame_digests[frame.uid]
            or frame.role not in {"INCOMING", "BASELINE"}
            or frame.role in source_roles.values()
        ):
            return {}, "has invalid directional meld source roles"
        source_roles[frame.uid] = frame.role
        label = f"{frame.role} {frame.context_name}#{frame.context_uid[:8]}"
        source_labels[frame.uid] = label
        for memory in frame.memories:
            if memory.owner_context_uid is None or memory.owner_context_name is None:
                return {}, "has incomplete owner-aware source evidence"
            key = (frame.uid, memory.uid)
            source_memory_text[key] = memory.content
            source_memory_owner[key] = (
                memory.owner_context_uid,
                memory.owner_context_name,
            )
        if frame.role == "BASELINE":
            baseline_contexts = {
                (context.uid, context.name) for context in (frame.contexts or ())
            }
            if (
                target.get("context_uid") != frame.context_uid
                or target.get("context_name") != frame.context_name
                or target.get("context_digest") != frame.context_digest
            ):
                return {}, "has a mismatched directional BASELINE binding"
    if (
        set(source_roles.values()) != {"INCOMING", "BASELINE"}
        or (
            before.context_uid,
            before.context_name,
        )
        not in baseline_contexts
    ):
        return {}, "has incomplete directional meld source roles"

    turns = record.get("turns")
    expected_turn_digests = dict(change_set.turn_digests)
    if not isinstance(turns, list) or len(turns) != len(expected_turn_digests):
        return {}, "has invalid meld turns"
    turn_comments: dict[str, str] = {}
    for turn in turns:
        if (
            not isinstance(turn, dict)
            or set(turn)
            != {
                "uid",
                "sequence",
                "revision",
                "scope",
                "issue_uids",
                "comment",
                "comment_sha256",
                "revises_turn_uids",
            }
            or not isinstance(turn.get("uid"), str)
            or not isinstance(turn.get("comment"), str)
            or hashlib.sha256(turn["comment"].encode("utf-8")).hexdigest()
            != turn.get("comment_sha256")
            or turn["uid"] in turn_comments
        ):
            return {}, "has invalid meld turns"
        evidence_payload = {
            key: turn[key]
            for key in (
                "uid",
                "sequence",
                "revision",
                "scope",
                "issue_uids",
                "comment",
                "revises_turn_uids",
            )
        }
        if (
            turn["uid"] not in expected_turn_digests
            or meld_canonical_digest(evidence_payload)
            != expected_turn_digests[turn["uid"]]
        ):
            return {}, "has meld turns outside the accepted change set"
        turn_comments[turn["uid"]] = turn["comment"]

    results = record.get("results")
    if not isinstance(results, list) or len(results) != len(change_set.proposals):
        return {}, "has invalid meld result records"
    proposal_by_uid = {proposal.uid: proposal for proposal in change_set.proposals}
    if len(proposal_by_uid) != len(change_set.proposals):
        return {}, "has duplicate directional meld proposals"
    owner_identity = (before.context_uid, before.context_name)
    by_uid: dict[str, dict[str, Any]] = {}
    seen_proposals: set[str] = set()
    expected_adds: list[str] = []
    expected_edits: list[str] = []
    for result in results:
        expected_result_keys = {
            "proposal_uid",
            "operation",
            "owner_context",
            "memory_uid",
            "disposition",
            "content_sha256",
            "source_members",
            "grounded_by_turn_uids",
            "relation_uids",
            "reason",
        }
        if not isinstance(result, dict) or set(result) != expected_result_keys:
            return {}, "has invalid owner-aware meld result records"
        proposal_uid = result.get("proposal_uid")
        proposal = proposal_by_uid.get(proposal_uid)
        proposal_owner = (
            (
                proposal.owner_context_uid,
                proposal.owner_context_name,
            )
            if proposal is not None
            else None
        )
        expected_owner = (
            {
                "uid": proposal_owner[0],
                "name": proposal_owner[1],
            }
            if proposal_owner is not None
            else None
        )
        if (
            proposal is None
            or proposal_uid in seen_proposals
            or result.get("operation") != proposal.operation
            or result.get("owner_context") != expected_owner
            or result.get("memory_uid") != proposal.memory_uid
            or result.get("disposition") != proposal.disposition
            or result.get("content_sha256")
            != hashlib.sha256(proposal.content.encode("utf-8")).hexdigest()
            or result.get("source_members")
            != [member.to_dict() for member in proposal.source_members]
            or result.get("grounded_by_turn_uids")
            != list(proposal.grounded_by_turn_uids)
            or result.get("relation_uids") != list(proposal.relation_uids)
            or result.get("reason") != proposal.reason
            or proposal_owner not in baseline_contexts
            or any(
                (member.frame_uid, member.memory_uid) not in source_memory_text
                for member in proposal.source_members
            )
        ):
            return {}, "does not match its recorded owner-aware meld result"
        assert isinstance(proposal_uid, str)
        seen_proposals.add(proposal_uid)
        if proposal_owner != owner_identity:
            continue
        memory_uid = proposal.memory_uid
        if memory_uid not in after.memories or after.memories[memory_uid].content != (
            proposal.content
        ):
            return {}, "does not match its owner target snapshot"
        member_roles = {
            source_roles[member.frame_uid] for member in proposal.source_members
        }
        if proposal.disposition == "USER_ADD":
            if proposal.operation != "ADD":
                return {}, "has an invalid directional USER_ADD operation"
        elif "INCOMING" not in member_roles:
            return {}, "has a directional result without INCOMING evidence"
        if proposal.operation == "EDIT":
            baseline_members = [
                member
                for member in proposal.source_members
                if source_roles[member.frame_uid] == "BASELINE"
                and member.memory_uid == memory_uid
            ]
            if (
                memory_uid not in before.memories
                or before.memories[memory_uid].content == proposal.content
                or len(baseline_members) != 1
                or source_memory_owner[
                    (baseline_members[0].frame_uid, baseline_members[0].memory_uid)
                ]
                != owner_identity
            ):
                return {}, "has an invalid directional EDIT result"
            expected_edits.append(memory_uid)
        elif proposal.operation == "ADD":
            if memory_uid in before.memories:
                return {}, "has an invalid directional ADD result"
            expected_adds.append(memory_uid)
        else:
            return {}, "has an unknown directional meld operation"
        source_lines = [
            (
                f"Source {source_labels[member.frame_uid]} "
                f"Memory [{member.memory_uid[:8]}]: "
                f"{source_memory_text[(member.frame_uid, member.memory_uid)]}"
            )
            for member in proposal.source_members
        ]
        turn_lines = [
            f"Turn [{turn_uid[:8]}]: {turn_comments[turn_uid]}"
            for turn_uid in proposal.grounded_by_turn_uids
            if turn_uid in turn_comments and turn_comments[turn_uid]
        ]
        by_uid[memory_uid] = {
            "session_uid": change_set.session_uid,
            "change_set_digest": change_set.digest,
            "mode": "DIRECTIONAL",
            "operation": proposal.operation,
            "disposition": proposal.disposition,
            "reason": proposal.reason,
            "declared_frame": "\n".join([*source_lines, *turn_lines]),
        }
    if seen_proposals != set(proposal_by_uid):
        return {}, "has incomplete meld result evidence"
    added = set(after.memories) - set(before.memories)
    removed = set(before.memories) - set(after.memories)
    changed = {
        uid
        for uid in set(before.memories) & set(after.memories)
        if before.memories[uid].content != after.memories[uid].content
    }
    if (
        added != set(expected_adds)
        or changed != set(expected_edits)
        or removed
        or after.order != (*before.order, *expected_adds)
        or len(expected_adds) != len(set(expected_adds))
        or len(expected_edits) != len(set(expected_edits))
    ):
        return {}, "does not match the owner-aware Meld target transition"
    return by_uid, None


def _meld_change_evidence(
    *,
    args: dict[str, Any],
    before: _Frame,
    after: _Frame,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    """Validate one applied meld receipt against its target snapshots.

    Schema version 1 is the original symmetric, empty-target contract.
    Directional meld uses version 2 for one direct BASELINE and version 3 for
    owner-aware subtree application. Keeping the formats separate prevents an
    older receipt from acquiring broader mutation authority merely because a
    newer reader understands descendant targeting.
    """
    record = args.get("meld")
    if isinstance(record, dict) and record.get("schema_version") == 3:
        return _owner_aware_meld_change_evidence(
            record=record,
            before=before,
            after=after,
        )
    required = {
        "schema_version",
        "session_uid",
        "turn_uid",
        "mode",
        "change_set_digest",
        "change_set",
        "sources",
        "target_baseline",
        "turns",
        "results",
    }
    if not isinstance(record, dict) or set(record) != required:
        return {}, "has no valid meld record"
    schema_version = record.get("schema_version")
    mode = record.get("mode")
    if type(schema_version) is not int or (schema_version, mode) not in {
        (1, "SYMMETRIC"),
        (2, "DIRECTIONAL"),
    }:
        return {}, "has an unsupported meld record"
    try:
        from memcommit.meld import MeldChangeSet, meld_canonical_digest

        change_set = MeldChangeSet.from_dict(record["change_set"])
    except (KeyError, TypeError, ValueError):
        return {}, "has an invalid meld change set"
    if (
        record.get("session_uid") != change_set.session_uid
        or record.get("turn_uid") != change_set.turn_uid
        or record.get("change_set_digest") != change_set.digest
        or change_set.mode != mode
        or change_set.target_uid != before.context_uid
        or change_set.target_digest != before.record_digest
    ):
        return {}, "has mismatched meld identities or target binding"
    target = record.get("target_baseline")
    if (
        not isinstance(target, dict)
        or set(target)
        != {
            "context_uid",
            "context_name",
            "context_digest",
        }
        or target.get("context_uid") != before.context_uid
        or target.get("context_name") != before.context_name
        or target.get("context_digest") != before.record_digest
    ):
        return {}, "has a mismatched meld target baseline"
    sources = record.get("sources")
    if not isinstance(sources, list) or len(sources) != len(
        change_set.source_frame_digests
    ):
        return {}, "has invalid meld source bindings"
    expected_frame_digests = dict(change_set.source_frame_digests)
    source_labels: dict[str, str] = {}
    source_memory_text: dict[tuple[str, str], str] = {}
    source_role_by_frame: dict[str, str] = {}
    source_binding_by_role: dict[str, tuple[str, str, str]] = {}
    for source in sources:
        expected_source_keys = {
            "frame_uid",
            "context_uid",
            "context_name",
            "context_digest",
            "memories",
        }
        if schema_version == 2:
            expected_source_keys.add("role")
        if (
            not isinstance(source, dict)
            or set(source) != expected_source_keys
            or source.get("frame_uid") not in expected_frame_digests
            or source.get("context_digest")
            != expected_frame_digests[source["frame_uid"]]
            or not isinstance(source.get("context_uid"), str)
            or not isinstance(source.get("context_name"), str)
        ):
            return {}, "has invalid meld source bindings"
        role = source.get("role")
        if schema_version == 2:
            if role not in {"INCOMING", "BASELINE"} or role in source_binding_by_role:
                return {}, "has invalid directional meld source roles"
            source_role_by_frame[source["frame_uid"]] = role
            source_binding_by_role[role] = (
                source["context_uid"],
                source["context_name"],
                source["context_digest"],
            )
        raw_memories = source.get("memories")
        if not isinstance(raw_memories, list) or not raw_memories:
            return {}, "has invalid meld source snapshots"
        memory_records: dict[str, dict[str, object]] = {}
        order: list[str] = []
        for position, memory in enumerate(raw_memories):
            if (
                not isinstance(memory, dict)
                or set(memory)
                != {
                    "uid",
                    "content",
                    "position",
                    "content_digest",
                }
                or not isinstance(memory.get("uid"), str)
                or not isinstance(memory.get("content"), str)
                or memory.get("position") != position
                or memory["uid"] in memory_records
                or memory.get("content_digest")
                != hashlib.sha256(memory["content"].encode("utf-8")).hexdigest()
            ):
                return {}, "has invalid meld source snapshots"
            memory_records[memory["uid"]] = {
                "type": "memory",
                "uid": memory["uid"],
                "content": memory["content"],
            }
            order.append(memory["uid"])
            source_memory_text[(source["frame_uid"], memory["uid"])] = memory["content"]
        try:
            source_context = Context.from_dict(
                {
                    "uid": source["context_uid"],
                    "name": source["context_name"],
                    "memories": memory_records,
                    "order": order,
                }
            )
        except (KeyError, TypeError, ValueError):
            return {}, "has invalid meld source snapshots"
        if context_record_digest(source_context) != source["context_digest"]:
            return {}, "has source snapshots that do not match their digest"
        label = f"{source['context_name']}#{source['context_uid'][:8]}"
        source_labels[source["frame_uid"]] = (
            f"{role} {label}" if schema_version == 2 else label
        )
    if set(source_labels) != set(expected_frame_digests):
        return {}, "has incomplete meld source bindings"
    if schema_version == 2:
        if set(source_binding_by_role) != {"INCOMING", "BASELINE"}:
            return {}, "has incomplete directional meld source roles"
        baseline_binding = source_binding_by_role["BASELINE"]
        incoming_binding = source_binding_by_role["INCOMING"]
        if (
            baseline_binding
            != (
                before.context_uid,
                before.context_name,
                before.record_digest,
            )
            or incoming_binding[0] == before.context_uid
            or incoming_binding[1] == before.context_name
        ):
            return {}, "has a mismatched directional BASELINE binding"

    turns = record.get("turns")
    expected_turn_digests = dict(change_set.turn_digests)
    if not isinstance(turns, list) or len(turns) != len(expected_turn_digests):
        return {}, "has invalid meld turns"
    turn_comments: dict[str, str] = {}
    for turn in turns:
        if (
            not isinstance(turn, dict)
            or set(turn)
            != {
                "uid",
                "sequence",
                "revision",
                "scope",
                "issue_uids",
                "comment",
                "comment_sha256",
                "revises_turn_uids",
            }
            or not isinstance(turn.get("uid"), str)
            or not isinstance(turn.get("comment"), str)
            or not isinstance(turn.get("comment_sha256"), str)
            or hashlib.sha256(turn["comment"].encode("utf-8")).hexdigest()
            != turn["comment_sha256"]
            or turn["uid"] in turn_comments
        ):
            return {}, "has invalid meld turns"
        evidence_payload = {
            key: turn[key]
            for key in (
                "uid",
                "sequence",
                "revision",
                "scope",
                "issue_uids",
                "comment",
                "revises_turn_uids",
            )
        }
        if (
            turn["uid"] not in expected_turn_digests
            or meld_canonical_digest(evidence_payload)
            != expected_turn_digests[turn["uid"]]
        ):
            return {}, "has meld turns outside the accepted change set"
        turn_comments[turn["uid"]] = turn["comment"]
    if set(turn_comments) != set(expected_turn_digests):
        return {}, "has incomplete meld turn evidence"

    results = record.get("results")
    if not isinstance(results, list) or len(results) != len(change_set.proposals):
        return {}, "has invalid meld result records"
    proposal_by_uid = {proposal.uid: proposal for proposal in change_set.proposals}
    if schema_version == 2 and len(proposal_by_uid) != len(change_set.proposals):
        return {}, "has duplicate directional meld proposals"
    by_uid: dict[str, dict[str, Any]] = {}
    seen_proposal_uids: set[str] = set()
    expected_add_uids: list[str] = []
    expected_edit_uids: list[str] = []
    for result in results:
        expected_result_keys = {
            "proposal_uid",
            "memory_uid",
            "disposition",
            "content_sha256",
            "source_members",
            "grounded_by_turn_uids",
            "relation_uids",
            "reason",
        }
        if schema_version == 2:
            expected_result_keys.add("operation")
        if not isinstance(result, dict) or set(result) != expected_result_keys:
            return {}, "has invalid meld result records"
        proposal_uid = result.get("proposal_uid")
        proposal = proposal_by_uid.get(proposal_uid)
        memory_uid = result.get("memory_uid")
        operation = proposal.operation if proposal is not None else None
        if (
            proposal is None
            or proposal_uid in seen_proposal_uids
            or memory_uid != proposal.memory_uid
            or memory_uid not in after.memories
            or after.memories[memory_uid].content != proposal.content
            or (schema_version == 2 and result.get("operation") != operation)
            or result.get("disposition") != proposal.disposition
            or result.get("content_sha256")
            != hashlib.sha256(proposal.content.encode("utf-8")).hexdigest()
            or result.get("source_members")
            != [member.to_dict() for member in proposal.source_members]
            or result.get("grounded_by_turn_uids")
            != list(proposal.grounded_by_turn_uids)
            or result.get("relation_uids") != list(proposal.relation_uids)
            or result.get("reason") != proposal.reason
            or any(
                (member.frame_uid, member.memory_uid) not in source_memory_text
                for member in proposal.source_members
            )
        ):
            return {}, "does not match its recorded meld result"
        assert isinstance(proposal_uid, str)
        assert isinstance(memory_uid, str)
        seen_proposal_uids.add(proposal_uid)
        if schema_version == 1:
            if memory_uid in before.memories:
                return {}, "does not match its recorded meld result"
        else:
            member_roles = {
                source_role_by_frame[member.frame_uid]
                for member in proposal.source_members
            }
            if proposal.disposition == "USER_ADD":
                if operation != "ADD":
                    return {}, "has an invalid directional USER_ADD operation"
            elif "INCOMING" not in member_roles:
                return {}, "has a directional result without INCOMING evidence"
            if operation == "EDIT":
                baseline_frame_uid = next(
                    frame_uid
                    for frame_uid, role in source_role_by_frame.items()
                    if role == "BASELINE"
                )
                if (
                    memory_uid not in before.memories
                    or before.memories[memory_uid].content == proposal.content
                    or (baseline_frame_uid, memory_uid)
                    not in {
                        (member.frame_uid, member.memory_uid)
                        for member in proposal.source_members
                    }
                ):
                    return {}, "has an invalid directional EDIT result"
                expected_edit_uids.append(memory_uid)
            elif operation == "ADD":
                if memory_uid in before.memories:
                    return {}, "has an invalid directional ADD result"
                expected_add_uids.append(memory_uid)
            else:
                return {}, "has an unknown directional meld operation"
            if memory_uid in by_uid:
                return {}, "has duplicate directional meld result targets"
        source_lines = [
            (
                f"Source {source_labels[member.frame_uid]} "
                f"Memory [{member.memory_uid[:8]}]: "
                f"{source_memory_text[(member.frame_uid, member.memory_uid)]}"
            )
            for member in proposal.source_members
            if member.frame_uid in source_labels
        ]
        turn_lines = [
            f"Turn [{turn_uid[:8]}]: {turn_comments[turn_uid]}"
            for turn_uid in proposal.grounded_by_turn_uids
            if turn_uid in turn_comments and turn_comments[turn_uid]
        ]
        by_uid[memory_uid] = {
            "session_uid": change_set.session_uid,
            "change_set_digest": change_set.digest,
            "mode": mode,
            "operation": operation,
            "disposition": proposal.disposition,
            "reason": proposal.reason,
            "declared_frame": "\n".join([*source_lines, *turn_lines]),
        }
    if seen_proposal_uids != set(proposal_by_uid) or set(by_uid) != {
        proposal.memory_uid for proposal in change_set.proposals
    }:
        return {}, "has incomplete meld result evidence"
    added_uids = set(after.memories) - set(before.memories)
    removed_uids = set(before.memories) - set(after.memories)
    changed_uids = {
        uid
        for uid in set(before.memories) & set(after.memories)
        if before.memories[uid].content != after.memories[uid].content
    }
    if schema_version == 1:
        if added_uids != set(by_uid) or removed_uids or changed_uids:
            return {}, "does not match the meld target snapshot transition"
    elif (
        added_uids != set(expected_add_uids)
        or changed_uids != set(expected_edit_uids)
        or removed_uids
        # Context.replace retains order and directional ADD appends in exact
        # proposal order.  Accepting a reorder here would let a receipt attest
        # to a different post-image than the operation actually authorizes.
        or after.order != (*before.order, *expected_add_uids)
        or len(expected_add_uids) != len(set(expected_add_uids))
        or len(expected_edit_uids) != len(set(expected_edit_uids))
    ):
        return {}, "does not match the directional meld target transition"
    return by_uid, None


def _checkpoint_chunk_options(args: dict) -> dict[str, object] | None:
    options: dict[str, object] = {}
    if "break_on" in args:
        break_on = args.get("break_on")
        if not isinstance(break_on, str) or not break_on:
            return None
        options["break_on"] = break_on
    for key in ("min_chars", "max_chars"):
        if key not in args:
            continue
        value = args.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        options[key] = value
    min_chars = options.get("min_chars")
    max_chars = options.get("max_chars")
    if (
        isinstance(min_chars, int)
        and isinstance(max_chars, int)
        and min_chars > max_chars
    ):
        return None
    return options


def _replay_checkpoint_chunk(
    content: str,
    method: str,
    args: dict,
) -> list[str]:
    """Replay every authored mechanical boundary recorded by Chunk."""

    return chunk_content(
        content,
        method,
        break_on=args.get("break_on"),
        min_chars=args.get("min_chars"),
        max_chars=args.get("max_chars"),
    )


def _legacy_chunk_event(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> TraceEvent | None:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
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
    options = _checkpoint_chunk_options(args)
    if options is None:
        return None

    children = [after.memories[uid] for uid in after.order if uid in added]
    source_position = before.order.index(source_uid)
    child_positions = [child.position for child in children]
    if child_positions != list(range(source_position, source_position + len(children))):
        return None
    before_without_source = [uid for uid in before.order if uid != source_uid]
    after_without_children = [uid for uid in after.order if uid not in added]
    if before_without_source != after_without_children:
        return None
    try:
        expected_contents = _replay_checkpoint_chunk(
            before.memories[source_uid].content,
            method,
            args,
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


def _recorded_context_chunk_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
) -> list[TraceEvent]:
    """Validate a Context-scoped chunk checkpoint without content guessing."""

    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    records = args.get("splits")
    method = args.get("method")
    if command != "chunk" or not isinstance(records, list) or not records:
        return []
    if not isinstance(method, str):
        return []
    options = _checkpoint_chunk_options(args)
    if options is None:
        return []

    parsed: list[tuple[str, tuple[str, ...]]] = []
    source_uids: set[str] = set()
    chunk_uids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"uid", "chunk_uids"}:
            return []
        source_uid = record.get("uid")
        children = record.get("chunk_uids")
        if (
            not isinstance(source_uid, str)
            or source_uid in source_uids
            or source_uid not in before.memories
            or not isinstance(children, list)
            or len(children) < 2
            or not all(isinstance(uid, str) for uid in children)
            or len(children) != len(set(children))
            or any(uid in chunk_uids for uid in children)
        ):
            return []
        child_uids = tuple(children)
        source_uids.add(source_uid)
        chunk_uids.update(child_uids)
        parsed.append((source_uid, child_uids))

    if removed != source_uids or added != chunk_uids:
        return []
    replacements = dict(parsed)
    expected_after_order: list[str] = []
    for uid in before.order:
        expected_after_order.extend(replacements.get(uid, (uid,)))
    if tuple(expected_after_order) != after.order:
        return []

    events: list[TraceEvent] = []
    for source_uid, child_uids in parsed:
        try:
            expected_contents = _replay_checkpoint_chunk(
                before.memories[source_uid].content,
                method,
                args,
            )
        except ValueError:
            return []
        children = tuple(after.memories.get(uid) for uid in child_uids)
        if any(child is None for child in children) or expected_contents != [
            child.content for child in children if child is not None
        ]:
            return []
        events.append(
            TraceEvent(
                kind="SPLIT",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[source_uid],),
                after=tuple(child for child in children if child is not None),
                reason=f"Context structural split using method '{method}'.",
            )
        )
    return events


def _translation_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    removed: set[str],
    added: set[str],
    changed: set[str],
) -> tuple[list[TraceEvent], set[str], set[str], list[str]]:
    """Validate legacy sibling copies or derived-Context replacements."""
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "translate":
        return [], set(), set(), []

    def valid_digest(value: object) -> bool:
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    operation_uid = args.get("operation_uid")
    target_language = args.get("target_language")
    source_context = args.get("source_context")
    destination_context = args.get("destination_context")
    scope = args.get("scope")
    response_digest = args.get("provider_response_sha256")
    records = args.get("translations")
    schema_version = args.get("schema_version")
    required_keys = {
        "schema_version",
        "operation_uid",
        "target_language",
        "source_context",
        "scope",
        "provider_response_sha256",
        "translations",
    }
    if schema_version == 2:
        required_keys.add("destination_context")
    valid = (
        set(args) == required_keys
        and schema_version in {1, 2}
        and isinstance(operation_uid, str)
        and isinstance(target_language, str)
        and bool(target_language.strip())
        # Trace validation must accept the same semantic target that the
        # translation boundary accepted.  A second, shorter limit here would
        # make a valid checkpoint look unrecorded merely because its audience
        # or terminology guidance was descriptive.
        and len(target_language) <= TRANSLATION_TARGET_CHAR_LIMIT
        and all(character.isprintable() for character in target_language)
        and isinstance(source_context, dict)
        and set(source_context) == {"uid", "name", "digest"}
        and isinstance(source_context.get("uid"), str)
        and bool(source_context.get("uid"))
        and isinstance(source_context.get("name"), str)
        and bool(source_context.get("name"))
        and valid_digest(source_context.get("digest"))
        and isinstance(scope, dict)
        and valid_digest(response_digest)
        and isinstance(records, list)
        and bool(records)
        and not changed
    )
    if valid and schema_version == 1:
        valid = (
            source_context.get("uid") == before.context_uid
            and source_context.get("name") == before.context_name
            and source_context.get("digest") == before.record_digest
            and not removed
        )
    elif valid and schema_version == 2:
        normalized_source_record = {
            **before.record,
            "uid": source_context.get("uid"),
            "name": source_context.get("name"),
        }
        valid = (
            isinstance(destination_context, dict)
            and set(destination_context) == {"uid", "name", "baseline_digest"}
            and destination_context.get("uid") == before.context_uid
            and destination_context.get("name") == before.context_name
            and valid_digest(destination_context.get("baseline_digest"))
            and destination_context.get("baseline_digest") == before.record_digest
            and source_context.get("uid") != before.context_uid
            and source_context.get("name") != before.context_name
            and source_context.get("digest")
            == context_record_digest(normalized_source_record)
        )
    try:
        uuid.UUID(operation_uid if isinstance(operation_uid, str) else "")
    except ValueError:
        valid = False

    parsed: list[tuple[str, str]] = []
    if valid:
        for record in records:
            if not isinstance(record, dict) or set(record) != {
                "source_uid",
                "result_uid",
                "source_sha256",
                "result_sha256",
            }:
                valid = False
                break
            source_uid = record.get("source_uid")
            result_uid = record.get("result_uid")
            source_digest = record.get("source_sha256")
            result_digest = record.get("result_sha256")
            common_invalid = (
                not isinstance(source_uid, str)
                or not isinstance(result_uid, str)
                or source_uid == result_uid
                or source_uid not in before.memories
                or result_uid in before.memories
                or result_uid not in after.memories
                or not valid_digest(source_digest)
                or not valid_digest(result_digest)
                or before.memories[source_uid].content_digest != source_digest
                or after.memories[result_uid].content_digest != result_digest
            )
            version_invalid = (
                (
                    source_uid not in after.memories
                    or before.memories[source_uid].content
                    != after.memories[source_uid].content
                )
                if schema_version == 1
                else source_uid in after.memories
            )
            if common_invalid or version_invalid:
                valid = False
                break
            parsed.append((source_uid, result_uid))

    source_uids = [source_uid for source_uid, _ in parsed]
    result_uids = [result_uid for _, result_uid in parsed]
    if valid and (
        len(source_uids) != len(set(source_uids))
        or len(result_uids) != len(set(result_uids))
        or set(source_uids) & set(result_uids)
    ):
        valid = False
    if valid and schema_version == 1:
        after_memories = after.record.get("memories")
        after_order = after.record.get("order")
        before_order = before.record.get("order")
        after_without_results = (
            {
                **after.record,
                "memories": {
                    uid: item
                    for uid, item in after_memories.items()
                    if uid not in set(result_uids)
                },
                "order": [uid for uid in after_order if uid not in set(result_uids)],
            }
            if (
                isinstance(after_memories, dict)
                and isinstance(after_order, list)
                and isinstance(before_order, list)
            )
            else None
        )
        valid = (
            set(result_uids) == added
            and after_without_results == before.record
            and [uid for uid in after.order if uid not in set(result_uids)]
            == list(before.order)
            and all(
                after.order.index(result_uid) == after.order.index(source_uid) + 1
                for source_uid, result_uid in parsed
            )
        )
    elif valid and schema_version == 2:
        before_memories = before.record.get("memories")
        before_order = before.record.get("order")
        after_memories = after.record.get("memories")
        source_to_result = dict(parsed)
        expected_memories = (
            {
                source_to_result.get(uid, uid): (
                    after_memories[source_to_result[uid]]
                    if uid in source_to_result
                    else item
                )
                for uid, item in before_memories.items()
            }
            if (
                isinstance(before_memories, dict)
                and isinstance(before_order, list)
                and isinstance(after_memories, dict)
            )
            else None
        )
        expected_after = (
            {
                **before.record,
                "memories": expected_memories,
                "order": [source_to_result.get(uid, uid) for uid in before_order],
            }
            if expected_memories is not None
            else None
        )
        valid = (
            set(source_uids) == removed
            and set(result_uids) == added
            and expected_after == after.record
        )
    if valid and scope == {"kind": "all"} and source_uids == list(before.order):
        pass
    elif (
        valid
        and isinstance(scope, dict)
        and set(scope) == {"kind", "memory_uid"}
        and scope.get("kind") == "memory"
        and len(source_uids) == 1
        and scope.get("memory_uid") == source_uids[0]
    ):
        pass
    else:
        valid = False

    if not valid:
        return (
            [],
            set(),
            set(),
            [
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid translation "
                "lineage metadata; snapshot differences were used instead."
            ],
        )

    return (
        [
            TraceEvent(
                kind="TRANSLATED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[source_uid],),
                after=(after.memories[result_uid],),
                reason=(
                    f"Created a translated copy in {target_language}."
                    if schema_version == 1
                    else (
                        "Replaced the source occurrence in this derived "
                        f"Context with a translation in {target_language}."
                    )
                ),
                reason_codes=("TRANSLATION",),
                operation_id=operation_uid,
            )
            for source_uid, result_uid in parsed
        ],
        set(source_uids) if schema_version == 2 else set(),
        set(result_uids),
        [],
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
    if len(source_uids) != len(set(source_uids)) or len(result_uids) != len(
        set(result_uids)
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
    if (
        not isinstance(raw_children, list)
        or (kind == "SPLIT" and len(raw_children) != len(result_uids))
        or (kind != "SPLIT" and raw_children)
    ):
        return None
    source_content = before.memories[source_uids[0]].content
    parsed_children: list[TraceChildEvidence] = []
    for index, value in enumerate(raw_children):
        if not isinstance(value, dict) or set(value) != {
            "result_uid",
            "source_spans",
            "frame_spans",
        }:
            return None
        result_uid = value["result_uid"]
        source_spans = value["source_spans"]
        frame_spans = value["frame_spans"]
        if (
            result_uid != result_uids[index]
            or not isinstance(source_spans, list)
            or not source_spans
            or any(
                not isinstance(span, str) or not span or span not in source_content
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
    if not isinstance(raw_review, dict) or set(raw_review) != {
        "review_uid",
        "response_digest",
        "memory_uid",
        "review_item_uid",
        "source_analysis_uid",
        "uncertainty_reason",
        "text",
        "digest",
    }:
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
        or any(character not in "0123456789abcdef" for character in response_digest)
        or args.get("source_review_uid") != review_uid
        or args.get("source_review_digest") != response_digest
        or not isinstance(args.get("analysis_uid"), str)
        or args.get("analysis_uid") == source_analysis_uid
        or any(
            span not in text for child in parsed_children for span in child.frame_spans
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
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    metadata = args.get("trace")
    if metadata is None:
        return [], set(), set(), []
    schema_version = (
        metadata.get("schema_version")
        if isinstance(
            metadata,
            dict,
        )
        else None
    )
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
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid trace change."
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
            or any(not isinstance(uid, str) or not uid for uid in source_uids)
            or not isinstance(result_uids, list)
            or not result_uids
            or any(not isinstance(uid, str) or not uid for uid in result_uids)
            or (reason is not None and not isinstance(reason, str))
            or not isinstance(reason_codes, list)
            or any(not isinstance(code, str) for code in reason_codes)
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] contains an invalid trace change."
            )
            continue

        involved_uids = set(source_uids) | set(result_uids)
        if involved_uids & (
            consumed_before | consumed_after
        ) or not _trace_change_matches_snapshot(
            kind=kind,
            source_uids=source_uids,
            result_uids=result_uids,
            before=before,
            after=after,
        ):
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] trace metadata does not "
                "match its snapshot; snapshot differences were used instead."
            )
            continue

        before_states = tuple(before.memories[uid] for uid in source_uids)
        after_states = tuple(after.memories[uid] for uid in result_uids)

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
                    review_evidence["text"] if review_evidence is not None else None
                ),
                declared_frame_digest=(
                    review_evidence["digest"] if review_evidence is not None else None
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


def _command_restore_operation(
    *,
    command: str,
    args: dict[str, Any],
    context_uid: str,
    context_name: str,
) -> TraceCommandOperation | None:
    """Validate the operation boundary retained by one Undo/Redo checkpoint.

    A Trace is reconstructed one Context at a time, but the receipt deliberately
    repeats the complete affected-Context membership.  Keeping that boundary on
    every resulting Memory event lets traces from different owners correlate the
    same user action without treating each checkpoint as an independent Undo.
    """
    if command not in {"undo", "redo"}:
        return None
    value = args.get("command_restore")
    if not isinstance(value, dict) or set(value) != {
        "version",
        "receipt_uid",
        "direction",
        "source_unit_uid",
        "source_command",
        "contexts",
    }:
        return None
    receipt_uid = value.get("receipt_uid")
    direction = value.get("direction")
    source_uid = value.get("source_unit_uid")
    source_command = value.get("source_command")
    raw_contexts = value.get("contexts")
    if (
        value.get("version") != 1
        or not isinstance(receipt_uid, str)
        or not receipt_uid
        or direction != command
        or not isinstance(source_uid, str)
        or not source_uid
        or not isinstance(source_command, str)
        or not source_command
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        return None
    contexts: list[TraceCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(TraceCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return TraceCommandOperation(
        uid=receipt_uid,
        command=command,
        contexts=tuple(contexts),
        source_uid=source_uid,
        source_command=source_command,
    )


def _update_command_operation(
    *,
    command: str,
    args: dict[str, Any],
    context_uid: str,
    context_name: str,
) -> TraceCommandOperation | None:
    """Recover the shared command unit recorded by a semantic Update."""
    if command != "update":
        return None
    session_uid = args.get("update_session_uid")
    operation_digest = args.get("operation_digest")
    raw_contexts = args.get("command_contexts")
    if (
        not isinstance(session_uid, str)
        or not session_uid
        or not isinstance(operation_digest, str)
        or not operation_digest
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        return None
    contexts: list[TraceCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(TraceCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return TraceCommandOperation(
        uid=f"update:{session_uid}:{operation_digest}",
        command=command,
        contexts=tuple(contexts),
    )


def _transition_events(
    *,
    before: _Frame,
    after: _Frame,
    entry: dict,
    restoration: TraceCommandOperation | bool = False,
) -> tuple[list[TraceEvent], list[str]]:
    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    deltas = direct_memory_deltas(
        before.memories,
        after.memories,
        before_order=before.order,
        after_order=after.order,
        content=lambda state: state.content,
    )
    removed = {delta.memory_uid for delta in deltas if delta.kind == "REMOVED"}
    added = {delta.memory_uid for delta in deltas if delta.kind == "CREATED"}
    changed = {delta.memory_uid for delta in deltas if delta.kind == "EDITED"}

    if restoration:
        command_operation = (
            restoration if isinstance(restoration, TraceCommandOperation) else None
        )
        events: list[TraceEvent] = []
        affected = removed | added | changed
        if affected:
            events.append(
                TraceEvent(
                    kind="RESTORED",
                    evidence="RECORDED",
                    timestamp=timestamp,
                    checkpoint_uid=checkpoint_uid,
                    command=command,
                    description=description,
                    before=_ordered_states(before, affected),
                    after=_ordered_states(after, affected),
                    operation_id=(
                        command_operation.uid if command_operation is not None else None
                    ),
                    command_operation=command_operation,
                )
            )
        return events, []

    trace_before = (
        _atomize_save_as_source_frame(args, after) if command == "atomize" else None
    )
    events, consumed_before, consumed_after, warnings = _explicit_trace_events(
        before=trace_before or before,
        after=after,
        entry=entry,
    )
    if trace_before is not None:
        receipt = args["atomize_save_as"]
        source_context = receipt.get("source_context")
        source_name = (
            source_context.get("name") if isinstance(source_context, dict) else None
        )
        events = [
            TraceEvent(
                kind="CREATED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                after=(trace_before.memories[uid],),
                reason=(
                    f"Copied into this Context from '{source_name}' before "
                    "the reviewed Atomize transform."
                    if isinstance(source_name, str)
                    else "Copied into this Context before Atomize."
                ),
                operation_id=(
                    args.get("analysis_uid")
                    if isinstance(args.get("analysis_uid"), str)
                    else None
                ),
            )
            for uid in trace_before.order
        ] + events
    command_operation = _update_command_operation(
        command=command,
        args=args,
        context_uid=after.context_uid,
        context_name=after.context_name,
    )
    if (
        command == "update"
        and any(
            key in args
            for key in (
                "update_session_uid",
                "operation_digest",
                "command_contexts",
            )
        )
        and command_operation is None
    ):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Update command-unit "
            "metadata; its changes cannot be correlated across Contexts."
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
    meld_changes: dict[str, dict[str, Any]] = {}
    if command == "meld":
        meld_changes, meld_error = _meld_change_evidence(
            args=args,
            before=before,
            after=after,
        )
        if meld_error is not None:
            warnings.append(
                f"Checkpoint [{checkpoint_uid[:8]}] {meld_error}; "
                "its results were reconstructed from snapshots."
            )

    (
        translation_events,
        translation_sources,
        translation_results,
        translation_warnings,
    ) = _translation_events(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
        changed=changed,
    )
    events.extend(translation_events)
    removed -= translation_sources
    added -= translation_results
    warnings.extend(translation_warnings)

    chunk_event = None
    context_chunk_events = _recorded_context_chunk_events(
        before=before,
        after=after,
        entry=entry,
        removed=removed,
        added=added,
    )
    if context_chunk_events:
        events.extend(context_chunk_events)
        removed -= {
            state.uid for event in context_chunk_events for state in event.before
        }
        added -= {state.uid for event in context_chunk_events for state in event.after}
    else:
        chunk_event = _legacy_chunk_event(
            before=before,
            after=after,
            entry=entry,
            removed=removed,
            added=added,
        )
    if not context_chunk_events and chunk_event is not None:
        events.append(chunk_event)
        removed -= {state.uid for state in chunk_event.before}
        added -= {state.uid for state in chunk_event.after}
    elif not context_chunk_events and command == "chunk" and (removed or added):
        warnings.append(
            f"Checkpoint [{checkpoint_uid[:8]}] is a legacy chunk whose "
            "parent-child mapping could not be reconstructed safely."
        )

    for uid in sorted(changed, key=lambda item: after.memories[item].position):
        grounding = grounding_changes.get(uid)
        meld = meld_changes.get(uid)
        events.append(
            TraceEvent(
                kind="EDITED",
                evidence=(
                    "RECORDED"
                    if (command == "edit" or grounding is not None or meld is not None)
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
                    else (meld["reason"] if meld is not None else None)
                ),
                reason_codes=(
                    ("ATOMIZE_GROUNDING",)
                    if grounding is not None
                    else (
                        (
                            "MELD",
                            "EDIT",
                            meld["disposition"],
                        )
                        if meld is not None
                        else ()
                    )
                ),
                operation_id=(
                    grounding["session_uid"]
                    if grounding is not None
                    else (meld["session_uid"] if meld is not None else None)
                ),
                declared_frame=(
                    grounding["declared_frame"]
                    if grounding is not None
                    else (meld["declared_frame"] if meld is not None else None)
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        grounding["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if grounding is not None
                    else (
                        hashlib.sha256(
                            meld["declared_frame"].encode("utf-8")
                        ).hexdigest()
                        if meld is not None
                        else None
                    )
                ),
                uncertainty_reason=(
                    "Applied after a multi-turn atomize grounding dialogue."
                    if grounding is not None
                    else (
                        "Edited by an accepted directional Context meld."
                        if meld is not None
                        else None
                    )
                ),
                source_review_uid=(
                    grounding["session_uid"]
                    if grounding is not None
                    else (meld["session_uid"] if meld is not None else None)
                ),
                source_review_digest=(
                    grounding["change_set_digest"]
                    if grounding is not None
                    else (meld["change_set_digest"] if meld is not None else None)
                ),
                source_analysis_uid=(
                    grounding["source_analysis_uid"] if grounding is not None else None
                ),
            )
        )

    occurrences = (
        _source_occurrences(
            args=args,
            after=after,
            added_uids=added,
        )
        if command == "add"
        else {}
    )
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
        added_in_context_order = [uid for uid in after.order if uid in added]
        if (
            isinstance(declared_uids, list)
            and set(uid for uid in declared_uids if isinstance(uid, str)) == added
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
        meld = meld_changes.get(uid)
        event_kind: EventKind = (
            "MERGED_IN"
            if command == "merge"
            else ("MELDED" if meld is not None else "CREATED")
        )
        evidence: Evidence
        if grounding is not None:
            evidence = "RECORDED"
        elif meld is not None:
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
                        meld["reason"]
                        if meld is not None
                        else (
                            "Copied into this Context's source-based initial "
                            f"frame from '{source_context['name']}'."
                            if recorded_init_copy
                            else None
                        )
                    )
                ),
                reason_codes=(
                    ("ATOMIZE_GROUNDING",)
                    if grounding is not None
                    else (
                        (
                            "MELD",
                            "ADD",
                            meld["disposition"],
                        )
                        if meld is not None and meld["mode"] == "DIRECTIONAL"
                        else ("MELD", meld["disposition"]) if meld is not None else ()
                    )
                ),
                source_occurrence=occurrence,
                operation_id=(
                    grounding["session_uid"]
                    if grounding is not None
                    else (meld["session_uid"] if meld is not None else None)
                ),
                declared_frame=(
                    grounding["declared_frame"]
                    if grounding is not None
                    else (meld["declared_frame"] if meld is not None else None)
                ),
                declared_frame_digest=(
                    hashlib.sha256(
                        grounding["declared_frame"].encode("utf-8")
                    ).hexdigest()
                    if grounding is not None
                    else (
                        hashlib.sha256(
                            meld["declared_frame"].encode("utf-8")
                        ).hexdigest()
                        if meld is not None
                        else None
                    )
                ),
                uncertainty_reason=(
                    "Created after a multi-turn atomize grounding dialogue."
                    if grounding is not None
                    else (
                        (
                            "Added by an accepted directional Context meld."
                            if meld["mode"] == "DIRECTIONAL"
                            else ("Created by an accepted symmetric Context meld.")
                        )
                        if meld is not None
                        else None
                    )
                ),
                source_review_uid=(
                    grounding["session_uid"]
                    if grounding is not None
                    else (meld["session_uid"] if meld is not None else None)
                ),
                source_review_digest=(
                    grounding["change_set_digest"]
                    if grounding is not None
                    else (meld["change_set_digest"] if meld is not None else None)
                ),
                source_analysis_uid=(
                    grounding["source_analysis_uid"] if grounding is not None else None
                ),
            )
        )

    for uid in sorted(removed, key=lambda item: before.memories[item].position):
        events.append(
            TraceEvent(
                kind="REMOVED",
                evidence=(
                    "RECORDED" if command in {"remove", "clear"} else "RECONSTRUCTED"
                ),
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=(before.memories[uid],),
            )
        )
    if set(before.memories) == set(after.memories) and before.order != after.order:
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
    if command_operation is not None:
        events = [
            replace(
                event,
                operation_id=event.operation_id or command_operation.uid,
                command_operation=command_operation,
            )
            for event in events
        ]
    return events, warnings


@dataclass(frozen=True)
class _RecordedBranchTransition:
    """Validated Context movement retained by one automatic Branch checkpoint."""

    operation_uid: str
    source: TraceCommandContext
    target: TraceCommandContext
    command_operation: TraceCommandOperation
    memory_edges: tuple[MemoryLineageEdge, ...]


@dataclass(frozen=True)
class _RecordedMergeEdge:
    """One disposition-complete Source/Target occurrence mapping."""

    edge: MemoryLineageEdge
    disposition: Literal[
        "NEW",
        "ALREADY_PRESENT",
        "TAKE_SOURCE",
        "KEEP_TARGET",
    ]


@dataclass(frozen=True)
class _RecordedMergeTransition:
    """Validated same-Store Merge evidence anchored by its target checkpoint."""

    checkpoint_uid: str
    timestamp: str
    description: str
    operation_uid: str
    source: TraceCommandContext
    target: TraceCommandContext
    command_operation: TraceCommandOperation
    before: _Frame
    after: _Frame
    edges: tuple[_RecordedMergeEdge, ...]


def _recorded_branch_transition(
    *,
    entry: dict,
    frame: _Frame,
) -> tuple[_RecordedBranchTransition | None, str | None]:
    """Validate the Branch receipt that owns ``frame`` without guessing lineage."""

    checkpoint_uid, _timestamp, command, _description, args = _checkpoint_fields(entry)
    if command != "branch" or "branch_tree" not in args:
        return None, None
    try:
        receipt = branch_tree_receipt(args)
    except CommandHistoryError:
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch creation "
            "metadata; inherited lineage could not be connected to its target.",
        )
    mapping = next(
        (
            item
            for item in receipt.contexts
            if item.target_uid == frame.context_uid
            and item.target_name == frame.context_name
        ),
        None,
    )
    if mapping is None or entry.get("auto") is not True:
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch creation "
            "ownership; inherited lineage could not be connected to its target.",
        )
    try:
        memory_edges = parse_memory_lineage_receipt(args)
    except (TypeError, ValueError):
        return (
            None,
            f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch Memory "
            "lineage metadata; inherited lineage could not be connected to "
            "its target.",
        )
    target_memory_edges = tuple(
        edge
        for edge in memory_edges
        if edge.source_context_uid == mapping.source_uid
        and edge.target_context_uid == mapping.target_uid
    )
    for edge in target_memory_edges:
        target_state = frame.memories.get(edge.target_memory_uid)
        if (
            target_state is None
            or target_state.content_digest != edge.target_content_sha256
        ):
            return (
                None,
                f"Checkpoint [{checkpoint_uid[:8]}] has invalid Branch Memory "
                "lineage evidence; inherited lineage could not be connected "
                "to its target.",
            )
    operation_uid = f"branch:{receipt.operation_uid}"
    return (
        _RecordedBranchTransition(
            operation_uid=operation_uid,
            source=TraceCommandContext(
                uid=mapping.source_uid,
                name=mapping.source_name,
            ),
            target=TraceCommandContext(
                uid=mapping.target_uid,
                name=mapping.target_name,
            ),
            command_operation=TraceCommandOperation(
                uid=operation_uid,
                command="branch",
                contexts=tuple(
                    TraceCommandContext(uid=item.target_uid, name=item.target_name)
                    for item in receipt.contexts
                ),
            ),
            memory_edges=target_memory_edges,
        ),
        None,
    )


def _branch_transition_events(
    *,
    transition: _RecordedBranchTransition,
    before: _Frame,
    after: _Frame,
    entry: dict,
) -> list[TraceEvent]:
    """Project stable direct Memories across one recorded Context Branch."""

    checkpoint_uid, timestamp, command, description, _args = _checkpoint_fields(entry)
    source_is_preceding_frame = (
        before.context_uid == transition.source.uid
        and before.context_name == transition.source.name
    )
    context_transition = TraceContextTransition(
        source=transition.source,
        target=transition.target,
    )
    events: list[TraceEvent] = []
    edge_by_target_uid = {
        edge.target_memory_uid: edge for edge in transition.memory_edges
    }
    for uid in after.order:
        target_state = after.memories[uid]
        edge = edge_by_target_uid.get(uid)
        source_uid = edge.source_memory_uid if edge is not None else uid
        source_state = (
            before.memories.get(source_uid) if source_is_preceding_frame else None
        )
        # Branch preserves content across distinct occurrence identities. If
        # the copied Source had uncheckpointed changes, the target snapshot
        # proves the copied result but the older inherited frame must not be
        # presented as its exact input.
        if source_state is not None and source_state.content == target_state.content:
            retained_source = (source_state,)
        elif (
            edge is not None
            and edge.source_content_sha256
            == memory_content_sha256(target_state.content)
        ):
            # The Branch receipt is written while the Source record is locked.
            # It therefore proves the copied Source value even when that value
            # had not received its own earlier checkpoint.
            retained_source = (
                MemoryState(
                    uid=edge.source_memory_uid,
                    content=target_state.content,
                    position=target_state.position,
                ),
            )
        else:
            retained_source = ()
        events.append(
            TraceEvent(
                kind="BRANCHED",
                evidence="RECORDED",
                timestamp=timestamp,
                checkpoint_uid=checkpoint_uid,
                command=command,
                description=description,
                before=retained_source,
                after=(target_state,),
                operation_id=transition.operation_uid,
                command_operation=transition.command_operation,
                context_transition=context_transition,
            )
        )
    return events


def _merge_decisions(
    args: dict[str, Any],
) -> dict[tuple[str, str], Literal["TAKE_SOURCE", "KEEP_TARGET"]]:
    """Validate the reviewed per-occurrence Merge dispositions."""

    record = args.get("merge_decisions")
    if not isinstance(record, dict) or set(record) != {"version", "decisions"}:
        raise ValueError("Merge decision metadata is invalid.")
    raw_decisions = record.get("decisions")
    if record.get("version") != 1 or not isinstance(raw_decisions, list):
        raise ValueError("Merge decision metadata is invalid.")
    result: dict[tuple[str, str], Literal["TAKE_SOURCE", "KEEP_TARGET"]] = {}
    expected = {
        "conflict_uid",
        "kind",
        "decision",
        "source_name",
        "target_name",
        "source_uid",
        "target_uids",
    }
    for raw in raw_decisions:
        if not isinstance(raw, dict) or set(raw) != expected:
            raise ValueError("Merge decision metadata is invalid.")
        decision = raw.get("decision")
        source_uid = raw.get("source_uid")
        target_uids = raw.get("target_uids")
        if (
            decision not in {"TAKE_SOURCE", "KEEP_TARGET"}
            or not isinstance(source_uid, str)
            or not source_uid
            or not isinstance(target_uids, list)
            or not target_uids
            or any(not isinstance(uid, str) or not uid for uid in target_uids)
            or len(target_uids) != len(set(target_uids))
        ):
            raise ValueError("Merge decision metadata is invalid.")
        for target_uid in target_uids:
            key = (source_uid, target_uid)
            if key in result:
                raise ValueError("Merge decision metadata repeats an occurrence.")
            result[key] = decision
    return result


def _recorded_merge_transition(
    entry: dict,
) -> tuple[_RecordedMergeTransition | None, str | None]:
    """Validate one Merge checkpoint before it can join two Trace owners."""

    checkpoint_uid, timestamp, command, description, args = _checkpoint_fields(entry)
    if command != "merge" or "memory_lineage" not in args:
        return None, None
    warning = (
        f"Checkpoint [{checkpoint_uid[:8]}] has invalid Merge Memory lineage "
        "metadata; Source and Target histories were not connected."
    )
    tree = args.get("merge_tree")
    source_name = args.get("source")
    contexts = args.get("command_contexts")
    try:
        after = _frame_from_snapshot(
            entry.get("snapshot"),
            label=f"Checkpoint [{checkpoint_uid[:8]}]",
        )
        command_before = entry.get("command_before")
        before = (
            _frame_from_snapshot(
                command_before,
                label=f"Checkpoint [{checkpoint_uid[:8]}] command pre-image",
            )
            if isinstance(command_before, dict)
            else _empty_frame(after.context_uid, after.context_name)
        )
        memory_edges = parse_memory_lineage_receipt(args)
        decisions = _merge_decisions(args)
    except (ProvenanceError, TypeError, ValueError):
        return None, warning
    target_created = tree.get("target_created") if isinstance(tree, dict) else None
    has_command_preimage = isinstance(command_before, dict)
    if (
        entry.get("auto") is not True
        or not isinstance(tree, dict)
        or tree.get("version") != 2
        or type(target_created) is not bool
        # Creation has no Target pre-image; an existing Target must retain one.
        or target_created == has_command_preimage
        or not isinstance(tree.get("operation_uid"), str)
        or not isinstance(source_name, str)
        or not source_name
        or not isinstance(contexts, list)
        or not any(
            isinstance(item, dict)
            and item.get("uid") == after.context_uid
            and item.get("name") == after.context_name
            for item in contexts
        )
        or before.context_uid != after.context_uid
    ):
        return None, warning
    anchored = tuple(
        edge for edge in memory_edges if edge.target_context_uid == after.context_uid
    )
    source_context_uids = {edge.source_context_uid for edge in anchored}
    if not anchored or len(source_context_uids) != 1:
        return None, warning

    recorded_edges: list[_RecordedMergeEdge] = []
    for edge in anchored:
        target_after = after.memories.get(edge.target_memory_uid)
        if (
            target_after is None
            or target_after.content_digest != edge.target_content_sha256
        ):
            return None, warning
        target_before = before.memories.get(edge.target_memory_uid)
        decision = decisions.get((edge.source_memory_uid, edge.target_memory_uid))
        if target_before is None:
            if decision is not None or (
                edge.source_content_sha256 != edge.target_content_sha256
            ):
                return None, warning
            disposition: Literal[
                "NEW", "ALREADY_PRESENT", "TAKE_SOURCE", "KEEP_TARGET"
            ] = "NEW"
        elif decision == "TAKE_SOURCE":
            if edge.source_content_sha256 != edge.target_content_sha256:
                return None, warning
            disposition = "TAKE_SOURCE"
        elif decision == "KEEP_TARGET":
            if target_before.content_digest != edge.target_content_sha256:
                return None, warning
            disposition = "KEEP_TARGET"
        elif (
            decision is None
            and target_before.content_digest == edge.target_content_sha256
            and edge.source_content_sha256 == edge.target_content_sha256
        ):
            disposition = "ALREADY_PRESENT"
        else:
            return None, warning
        recorded_edges.append(_RecordedMergeEdge(edge=edge, disposition=disposition))

    operation_uid = f"merge:{tree['operation_uid']}"
    context_records: list[TraceCommandContext] = []
    for item in contexts:
        if not isinstance(item, dict):
            return None, warning
        uid = item.get("uid")
        name = item.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None, warning
        context_records.append(TraceCommandContext(uid=uid, name=name))
    source_context_uid = next(iter(source_context_uids))
    return (
        _RecordedMergeTransition(
            checkpoint_uid=checkpoint_uid,
            timestamp=timestamp,
            description=description,
            operation_uid=operation_uid,
            source=TraceCommandContext(uid=source_context_uid, name=source_name),
            target=TraceCommandContext(
                uid=after.context_uid,
                name=after.context_name,
            ),
            command_operation=TraceCommandOperation(
                uid=operation_uid,
                command="merge",
                contexts=tuple(context_records),
            ),
            before=before,
            after=after,
            edges=tuple(recorded_edges),
        ),
        None,
    )


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

    recorded_branches: dict[str, _RecordedBranchTransition] = {}
    branch_warnings: list[str] = []
    branch_sources_by_target: dict[str, set[str]] = {}
    for entry in entries:
        frame = frames_by_checkpoint[entry["uid"]]
        transition, warning = _recorded_branch_transition(entry=entry, frame=frame)
        if warning is not None:
            branch_warnings.append(warning)
        if transition is None:
            continue
        recorded_branches[entry["uid"]] = transition
        branch_sources_by_target.setdefault(
            transition.target.uid,
            set(),
        ).add(transition.source.uid)

    # A target can inherit a Source that was itself branched. Walk the complete
    # recorded chain so earlier Source checkpoints remain lineage rather than
    # being misreported as separate missing creation events.
    explained_owner_uids = {ctx.uid}
    pending_owner_uids = [ctx.uid]
    while pending_owner_uids:
        target_uid = pending_owner_uids.pop()
        for source_uid in branch_sources_by_target.get(target_uid, ()):
            if source_uid in explained_owner_uids:
                continue
            explained_owner_uids.add(source_uid)
            pending_owner_uids.append(source_uid)

    events: list[TraceEvent] = []
    warnings: list[str] = list(branch_warnings)
    frames: list[_Frame] = []
    previous: _Frame | None = None
    warned_inherited_owners: set[tuple[str, str]] = set()
    for entry in entries:
        frame = frames_by_checkpoint[entry["uid"]]
        frame_owner = (frame.context_uid, frame.context_name)
        if frame.context_uid not in explained_owner_uids and (
            frame_owner not in warned_inherited_owners
        ):
            warnings.append(
                f"Checkpoint [{entry['uid'][:8]}] was inherited from "
                f"'{frame.context_name}'; the branch creation event was not "
                "recorded."
            )
            warned_inherited_owners.add(frame_owner)
        if previous is None:
            command_before = entry.get("command_before")
            if isinstance(command_before, dict):
                # The first retained command may replace a Context that was
                # initially saved without its own checkpoint. Its exact
                # command pre-image is still sufficient to validate lineage;
                # treating the frame as empty would erase every removed Source.
                previous = _frame_from_snapshot(
                    command_before,
                    label=f"Checkpoint [{entry['uid'][:8]}] command pre-image",
                )
            else:
                previous = _empty_frame(frame.context_uid, frame.context_name)

        recorded_branch = recorded_branches.get(entry["uid"])
        if recorded_branch is not None:
            events.extend(
                _branch_transition_events(
                    transition=recorded_branch,
                    before=previous,
                    after=frame,
                    entry=entry,
                )
            )
            frames.append(frame)
            previous = frame
            continue

        _, _, command, _, args = _checkpoint_fields(entry)
        command_operation = _command_restore_operation(
            command=command,
            args=args,
            context_uid=frame.context_uid,
            context_name=frame.context_name,
        )
        if (
            command in {"undo", "redo"}
            and args.get("command_restore") is not None
            and command_operation is None
        ):
            warnings.append(
                f"Checkpoint [{entry['uid'][:8]}] has invalid command "
                "restoration metadata; snapshot differences were used instead."
            )
        transition, transition_warnings = _transition_events(
            before=previous,
            after=frame,
            entry=entry,
            restoration=command_operation or False,
        )
        events.extend(transition)
        warnings.extend(transition_warnings)
        frames.append(frame)
        previous = frame

        if command == "revert":
            target_uid = args.get("target_uid")
            recorded_restoration = entry.get("restored_snapshot")
            target = (
                _frame_from_snapshot(
                    recorded_restoration,
                    label=f"Checkpoint [{entry['uid'][:8]}] restored post-image",
                )
                if isinstance(recorded_restoration, dict)
                else (
                    frames_by_checkpoint.get(target_uid)
                    if isinstance(target_uid, str)
                    else None
                )
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
        affected_before = tuple(state for event in gap_events for state in event.before)
        affected_after = tuple(state for event in gap_events for state in event.after)
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


def _known_historical_uids(
    events: Iterable[TraceEvent],
    frames: Iterable[_Frame],
) -> set[str]:
    """Return the exact UID domain accepted by trace/rationale selectors."""
    known = {uid for frame in frames for uid in frame.memories}
    known.update(
        state.uid for event in events for state in (*event.before, *event.after)
    )
    return known


def _resolve_historical_uid(
    selector: str,
    events: Iterable[TraceEvent],
    frames: Iterable[_Frame],
) -> str:
    if not isinstance(selector, str) or not selector:
        raise ProvenanceError("Memory selector must be non-empty.")
    known = _known_historical_uids(events, frames)
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
        if event.kind not in {
            "SPLIT",
            "ABSORBED",
            "TRANSLATED",
            "BRANCHED",
            "MERGED_IN",
        }:
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
        if event.kind in {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED", "MERGED_IN"}
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
        if not (isinstance(trace, dict) and trace.get("operation_id") == session.uid):
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
        frame.memory_uid: frame for frame in session.declared_frames
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
                declared_frame_by_memory_uid[item.memory_uid].uncertainty_reason
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
            source_review_uid=session.source_review_uid,
            source_review_digest=session.source_review_digest,
            source_review_analysis_uid=(
                declared_frame_by_memory_uid[item.memory_uid].source_analysis_uid
                if item.memory_uid in declared_frame_by_memory_uid
                else None
            ),
        )
        for item in session.items
        if item.memory_uid in component
    )
    return analyses, []


def _lineage_operation_counts(
    selected_uids: Iterable[str],
    events: Sequence[TraceEvent],
) -> dict[str, int]:
    """Count recorded temporal operations for every candidate in one pass."""

    candidates = tuple(dict.fromkeys(selected_uids))
    operations_by_uid: dict[str, set[tuple[str, str]]] = {
        uid: set() for uid in candidates
    }
    adjacency: dict[str, set[str]] = {uid: set() for uid in candidates}
    for event_index, event in enumerate(events):
        if event.kind == "HISTORY_GAP":
            # A gap proves that the current state is not reconstructable from
            # retained history. It is a visible Trace row, but not evidence of
            # one recorded creation or modification. Excluding it directly
            # keeps the count naturally nonnegative instead of subtracting a
            # synthetic row after aggregation.
            continue
        if event.command_operation is not None:
            key = ("command", event.command_operation.uid)
        elif event.operation_id is not None:
            key = ("operation", event.operation_id)
        elif event.checkpoint_uid is not None:
            key = ("checkpoint", event.checkpoint_uid)
        else:
            # Unidentified reconstructed events remain independently visible
            # in the Trace workbench, so they must not collapse by text/time.
            key = ("event", str(event_index))
        event_uids = event.uids
        for uid in event_uids:
            operations_by_uid.setdefault(uid, set()).add(key)
            adjacency.setdefault(uid, set())
        if event.kind in {"SPLIT", "ABSORBED", "TRANSLATED", "BRANCHED"}:
            related = tuple(event_uids)
            for uid in related:
                adjacency[uid].update(
                    candidate for candidate in related if candidate != uid
                )

    counts: dict[str, int] = {}
    visited: set[str] = set()
    for selected_uid in candidates:
        if selected_uid in visited:
            continue
        component = {selected_uid}
        pending = [selected_uid]
        while pending:
            uid = pending.pop()
            for neighbor in adjacency.get(uid, ()):
                if neighbor in component:
                    continue
                component.add(neighbor)
                pending.append(neighbor)
        visited.update(component)
        count = len(
            set().union(*(operations_by_uid.get(uid, set()) for uid in component))
        )
        for uid in component:
            if uid in operations_by_uid:
                counts[uid] = count
    return counts


def collect_trace_candidates(
    store: MemoryStore,
    ctx: Context,
) -> tuple[TraceCandidate, ...]:
    """List each selectable current or historical direct Memory once.

    Current Memories retain canonical Context order. Historical-only Memories
    use their last retained state, with the most recently observed frame first.
    The UID set intentionally shares the resolver's exact provenance domain so
    opening the picker cannot narrow what an explicit selector can trace.
    """
    events, _, frames = _history(store, ctx)
    current_frame = frames[-1]
    current_uids = set(current_frame.memories)
    known_uids = _known_historical_uids(events, frames)
    change_counts = _lineage_operation_counts(known_uids, events)
    current = tuple(
        TraceCandidate(
            uid=uid,
            content=current_frame.memories[uid].content,
            position=current_frame.memories[uid].position,
            status="CURRENT",
            change_count=change_counts[uid],
        )
        for uid in current_frame.order
    )

    last_frame_state: dict[str, tuple[int, MemoryState]] = {}
    for frame_index, frame in enumerate(frames):
        for uid in frame.order:
            last_frame_state[uid] = (frame_index, frame.memories[uid])

    # Valid explicit metadata normally names states also present in a retained
    # frame. Keep an event fallback so the picker and explicit selector still
    # share one domain when only an event retains the selected UID.
    last_event_state: dict[str, tuple[int, MemoryState]] = {}
    for event_index, event in enumerate(events):
        for state in (*event.before, *event.after):
            last_event_state[state.uid] = (event_index, state)

    historical: list[tuple[int, int, TraceCandidate]] = []
    for uid in known_uids - current_uids:
        frame_observation = last_frame_state.get(uid)
        if frame_observation is not None:
            rank, state = frame_observation
            frame_backed = 1
        else:
            # Event-only choices sort after frame-backed history. The event
            # index is retained only as a deterministic tie breaker.
            rank, state = last_event_state[uid]
            frame_backed = 0
        historical.append(
            (
                frame_backed,
                rank,
                TraceCandidate(
                    uid=uid,
                    content=state.content,
                    position=state.position,
                    status="HISTORICAL",
                    change_count=change_counts[uid],
                ),
            )
        )
    historical.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].position,
            item[2].uid,
        )
    )
    return (*current, *(candidate for _, _, candidate in historical))


def _build_local_trace(
    store: MemoryStore,
    ctx: Context,
    selector: str,
) -> TraceReport:
    """Reconstruct lineage retained by one exact owner Context."""
    events, warnings, frames = _history(store, ctx)
    selected_uid = _resolve_historical_uid(selector, events, frames)
    component = _lineage_component(selected_uid, events)
    relevant_events = tuple(event for event in events if event.uids & component)
    current_frame = frames[-1]
    current = tuple(
        current_frame.memories[uid] for uid in current_frame.order if uid in component
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


def _merge_transition_catalog(
    store: MemoryStore,
) -> tuple[
    tuple[_RecordedMergeTransition, ...],
    dict[tuple[str, str], tuple[str, ...]],
]:
    """Freeze validated local Merge receipts without opening sibling content."""

    transitions: list[_RecordedMergeTransition] = []
    warnings_by_node: dict[tuple[str, str], list[str]] = {}
    seen_checkpoints: set[str] = set()
    for context_name in store.list_context_names():
        try:
            entries = _checkpoint_entries(store, context_name)
        except ProvenanceError:
            # An unrelated broken history must not make an exact Trace fail.
            continue
        for entry in entries:
            checkpoint_uid = entry.get("uid")
            if (
                not isinstance(checkpoint_uid, str)
                or checkpoint_uid in seen_checkpoints
            ):
                continue
            seen_checkpoints.add(checkpoint_uid)
            transition, warning = _recorded_merge_transition(entry)
            if transition is not None:
                transitions.append(transition)
                continue
            if warning is None:
                continue
            snapshot = entry.get("snapshot")
            context_uid = snapshot.get("uid") if isinstance(snapshot, dict) else None
            after_memories = (
                snapshot.get("memories") if isinstance(snapshot, dict) else None
            )
            command_before = entry.get("command_before")
            before_memories = (
                command_before.get("memories")
                if isinstance(command_before, dict)
                else {}
            )
            if (
                isinstance(context_uid, str)
                and context_uid
                and isinstance(after_memories, dict)
                and isinstance(before_memories, dict)
            ):
                changed_uids = {
                    uid
                    for uid in set(after_memories) | set(before_memories)
                    if isinstance(uid, str)
                    and after_memories.get(uid) != before_memories.get(uid)
                }
                for uid in changed_uids:
                    warnings_by_node.setdefault((context_uid, uid), []).append(warning)
    return (
        tuple(transitions),
        {node: tuple(dict.fromkeys(items)) for node, items in warnings_by_node.items()},
    )


def _context_for_uid(
    store: MemoryStore,
    context_uid: str,
    *,
    hints: Iterable[str],
    cache: dict[str, Context],
) -> Context | None:
    """Resolve a current local owner by identity, tolerating a later rename."""

    cached = cache.get(context_uid)
    if cached is not None:
        return cached
    names = tuple(dict.fromkeys((*hints, *store.list_context_names())))
    for name in names:
        try:
            context = store.load_direct(name)
        except (FileNotFoundError, ValueError):
            continue
        cache.setdefault(context.uid, context)
        if context.uid == context_uid:
            return context
    return None


def _matching_state(
    report: TraceReport | None,
    *,
    uid: str,
    content_digest: str,
) -> MemoryState | None:
    if report is None:
        return None
    candidates = (
        *report.current,
        *(
            state
            for event in reversed(report.events)
            for state in (*event.after, *event.before)
        ),
        *report.originals,
    )
    return next(
        (
            state
            for state in candidates
            if state.uid == uid and state.content_digest == content_digest
        ),
        None,
    )


def _merge_transition_event(
    transition: _RecordedMergeTransition,
    mapping: _RecordedMergeEdge,
    *,
    source_report: TraceReport | None,
) -> TraceEvent | None:
    """Project one exact Merge mapping into the existing Trace event grammar."""

    edge = mapping.edge
    target_after = transition.after.memories[edge.target_memory_uid]
    source_state = _matching_state(
        source_report,
        uid=edge.source_memory_uid,
        content_digest=edge.source_content_sha256,
    )
    if source_state is None and (
        edge.source_content_sha256 == edge.target_content_sha256
    ):
        # A same-value Merge receipt is written while Source and Target are
        # locked, so the target post-image also proves the copied Source value.
        source_state = MemoryState(
            uid=edge.source_memory_uid,
            content=target_after.content,
            position=target_after.position,
        )
    if source_state is None:
        return None
    target_before = transition.before.memories.get(edge.target_memory_uid)
    before = (source_state,) + ((target_before,) if target_before is not None else ())
    return TraceEvent(
        kind="MERGED_IN",
        evidence="RECORDED",
        timestamp=transition.timestamp,
        checkpoint_uid=transition.checkpoint_uid,
        command="merge",
        description=transition.description,
        before=before,
        after=(target_after,),
        reason_codes=("MERGE", mapping.disposition),
        context_transition=TraceContextTransition(
            source=transition.source,
            target=transition.target,
        ),
    )


def _deduplicated_events(events: Iterable[TraceEvent]) -> tuple[TraceEvent, ...]:
    distinct: list[TraceEvent] = []
    seen: set[str] = set()
    for event in events:
        identity = json.dumps(
            event.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        distinct.append(event)
    indexed = tuple(enumerate(distinct))
    return tuple(
        event
        for _index, event in sorted(
            indexed,
            key=lambda item: (
                item[1].timestamp is None,
                item[1].timestamp or "",
                item[0],
            ),
        )
    )


def build_trace(
    store: MemoryStore,
    ctx: Context,
    selector: str,
) -> TraceReport:
    """Reconstruct one Memory's local history and recorded Merge uses."""

    selected = _build_local_trace(store, ctx, selector)
    transitions, merge_warnings = _merge_transition_catalog(store)
    start_warning_key = (ctx.uid, selected.selected_uid)
    if not transitions and start_warning_key not in merge_warnings:
        return selected

    adjacency: dict[
        tuple[str, str],
        set[tuple[str, str]],
    ] = {}
    recorded_mappings: list[
        tuple[
            tuple[str, str],
            tuple[str, str],
            _RecordedMergeTransition,
            _RecordedMergeEdge,
        ]
    ] = []
    for transition in transitions:
        for mapping in transition.edges:
            source_node = mapping.edge.source_node
            target_node = mapping.edge.target_node
            adjacency.setdefault(source_node, set()).add(target_node)
            adjacency.setdefault(target_node, set()).add(source_node)
            recorded_mappings.append((source_node, target_node, transition, mapping))

    start = (ctx.uid, selected.selected_uid)
    nodes = {start}
    pending = [start]
    while pending:
        node = pending.pop()
        for neighbor in adjacency.get(node, ()):
            if neighbor in nodes:
                continue
            nodes.add(neighbor)
            pending.append(neighbor)
    if len(nodes) == 1:
        extra_warnings = merge_warnings.get(start, ())
        return replace(
            selected,
            warnings=tuple(dict.fromkeys((*selected.warnings, *extra_warnings))),
        )

    hints_by_uid: dict[str, list[str]] = {}
    for transition in transitions:
        hints_by_uid.setdefault(transition.source.uid, []).append(
            transition.source.name
        )
        hints_by_uid.setdefault(transition.target.uid, []).append(
            transition.target.name
        )
    context_cache = {ctx.uid: ctx}
    reports: dict[tuple[str, str], TraceReport] = {start: selected}
    for context_uid, memory_uid in sorted(nodes):
        node = (context_uid, memory_uid)
        if node in reports:
            continue
        owner = _context_for_uid(
            store,
            context_uid,
            hints=hints_by_uid.get(context_uid, ()),
            cache=context_cache,
        )
        if owner is None:
            continue
        try:
            reports[node] = _build_local_trace(store, owner, memory_uid)
        except ProvenanceError:
            # The receipt still proves the immediate copied value. Older
            # Source history remains absent rather than being guessed.
            continue

    merge_events: list[TraceEvent] = []
    replacement_targets: set[tuple[str, str]] = set()
    for source_node, target_node, transition, mapping in recorded_mappings:
        if source_node not in nodes or target_node not in nodes:
            continue
        event = _merge_transition_event(
            transition,
            mapping,
            source_report=reports.get(source_node),
        )
        if event is None:
            continue
        merge_events.append(event)
        replacement_targets.add(
            (transition.checkpoint_uid, mapping.edge.target_memory_uid)
        )

    local_events = [
        event
        for report in reports.values()
        for event in report.events
        if not (
            event.command == "merge"
            and event.checkpoint_uid is not None
            and any(
                (event.checkpoint_uid, state.uid) in replacement_targets
                for state in (*event.before, *event.after)
            )
        )
    ]
    events = _deduplicated_events((*local_events, *merge_events))
    component = {uid for report in reports.values() for uid in report.component_uids}
    component.update(memory_uid for _context_uid, memory_uid in nodes)
    current_by_uid: dict[str, MemoryState] = {}
    for report in reports.values():
        for state in report.current:
            current_by_uid[state.uid] = state
    current = tuple(
        sorted(current_by_uid.values(), key=lambda state: (state.position, state.uid))
    )
    originals = _original_states(component, events, ())

    analyses: list[TraceAnalysis] = []
    analysis_ids: set[tuple[str, str]] = set()
    for report in reports.values():
        for analysis in report.analyses:
            identity = (analysis.kind, analysis.analysis_uid)
            if identity in analysis_ids:
                continue
            analysis_ids.add(identity)
            analyses.append(analysis)
    warnings = tuple(
        dict.fromkeys(
            (
                *(
                    warning
                    for report in reports.values()
                    for warning in report.warnings
                ),
                *(
                    warning
                    for node in nodes
                    for warning in merge_warnings.get(node, ())
                ),
            )
        )
    )
    return TraceReport(
        context_uid=selected.context_uid,
        context_name=selected.context_name,
        selected_uid=selected.selected_uid,
        component_uids=tuple(sorted(component)),
        originals=originals,
        current=current,
        events=events,
        analyses=tuple(analyses),
        warnings=warnings,
    )
