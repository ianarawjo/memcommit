"""Validate retained records used to reconstruct per-Memory history.

This stage reads checkpoints, snapshots, and command receipts, then accepts
only claims whose identities, digests, and before/after states agree.  It does
not decide which verified changes belong to a requested Memory history.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Literal
import uuid

from memcommit.application.operations.chunk.domain import chunk_content
from memcommit.application.capabilities.retained_history.command_history import (
    CommandHistoryError,
    branch_tree_receipt,
)
from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.retained_history.reconstruction import (
    HistoryError,
    flatten_checkpoint_entries,
)
from memcommit.application.capabilities.retained_history.memory_lineage import (
    MemoryLineageEdge,
    parse_memory_lineage_receipt,
)
from memcommit.persistence.store import (
    MemoryStore,
    canonical_context_record,
    context_record_digest,
)


MemoryHistoryEvidence = Literal["RECORDED", "RECONSTRUCTED", "INFERRED", "UNRECORDED"]

TRACE_METADATA_SCHEMA_VERSION = 3
TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION = 4
TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION = 2
TRACE_METADATA_LEGACY_SCHEMA_VERSION = 1


class MemoryHistoryReconstructionError(RuntimeError):
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
class MemoryHistoryChildEvidence:
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
class MemoryHistoryCommandContext:
    """One Context named by a retained command-unit receipt."""

    uid: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "name": self.name}


@dataclass(frozen=True)
class MemoryHistoryCommandOperation:
    """The command boundary shared by one or more Context checkpoints."""

    uid: str
    command: str
    contexts: tuple[MemoryHistoryCommandContext, ...]
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
class MemoryHistoryContextTransition:
    """One recorded ancestry transition between Context-bound occurrences."""

    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
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
        raise MemoryHistoryReconstructionError(
            f"{label} is not a valid Context snapshot."
        )
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
        raise MemoryHistoryReconstructionError(
            f"{label} is not a valid Context snapshot."
        )

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
            raise MemoryHistoryReconstructionError(
                f"{label} contains an invalid direct item."
            )
        if item.get("type") != "memory":
            continue
        item_uid = item.get("uid")
        content = item.get("content")
        if item_uid != uid or not isinstance(content, str):
            raise MemoryHistoryReconstructionError(
                f"{label} contains an invalid Memory."
            )
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
        raise MemoryHistoryReconstructionError(str(error)) from error
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
) -> dict[str, tuple[SourceOccurrence, MemoryHistoryEvidence]]:
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

    result: dict[str, tuple[SourceOccurrence, MemoryHistoryEvidence]] = {}
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

    from memcommit.application.operations.atomize.grounding import (
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
        from memcommit.application.operations.meld.model import (
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
        from memcommit.application.operations.meld.model import MeldChangeSet, meld_canonical_digest

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


def _history_change_matches_snapshot(
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
) -> tuple[tuple[MemoryHistoryChildEvidence, ...], dict[str, str] | None] | None:
    """Validate optional reviewed evidence without weakening lineage checks."""
    expected_record_keys = {
        "kind",
        "classification",
        "source_uids",
        "result_uids",
        "reason",
        "reason_codes",
        "child_evidence",
        "review_evidence",
    }
    if schema_version == TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION:
        expected_record_keys.add("result_contents")
    if set(record) != expected_record_keys:
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
        TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
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
    parsed_children: list[MemoryHistoryChildEvidence] = []
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
            MemoryHistoryChildEvidence(
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
        from memcommit.application.operations.atomize.domain import atomize_declared_frame_digest

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


@dataclass(frozen=True)
class _RecordedBranchTransition:
    """Validated Context movement retained by one automatic Branch checkpoint."""

    operation_uid: str
    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext
    command_operation: MemoryHistoryCommandOperation
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
    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext
    command_operation: MemoryHistoryCommandOperation
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
            source=MemoryHistoryCommandContext(
                uid=mapping.source_uid,
                name=mapping.source_name,
            ),
            target=MemoryHistoryCommandContext(
                uid=mapping.target_uid,
                name=mapping.target_name,
            ),
            command_operation=MemoryHistoryCommandOperation(
                uid=operation_uid,
                command="branch",
                contexts=tuple(
                    MemoryHistoryCommandContext(
                        uid=item.target_uid, name=item.target_name
                    )
                    for item in receipt.contexts
                ),
            ),
            memory_edges=target_memory_edges,
        ),
        None,
    )


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
    except (MemoryHistoryReconstructionError, TypeError, ValueError):
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
    context_records: list[MemoryHistoryCommandContext] = []
    for item in contexts:
        if not isinstance(item, dict):
            return None, warning
        uid = item.get("uid")
        name = item.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None, warning
        context_records.append(MemoryHistoryCommandContext(uid=uid, name=name))
    source_context_uid = next(iter(source_context_uids))
    return (
        _RecordedMergeTransition(
            checkpoint_uid=checkpoint_uid,
            timestamp=timestamp,
            description=description,
            operation_uid=operation_uid,
            source=MemoryHistoryCommandContext(
                uid=source_context_uid, name=source_name
            ),
            target=MemoryHistoryCommandContext(
                uid=after.context_uid,
                name=after.context_name,
            ),
            command_operation=MemoryHistoryCommandOperation(
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
