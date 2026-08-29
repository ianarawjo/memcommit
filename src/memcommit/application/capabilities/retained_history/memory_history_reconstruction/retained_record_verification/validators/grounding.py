"""Validate retained conversational Grounding applications."""

from __future__ import annotations

import hashlib
from typing import Any
import uuid

from ..frame import _Frame


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
