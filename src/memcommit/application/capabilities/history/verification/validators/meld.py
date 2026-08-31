"""Validate retained Meld applications across supported receipt schemas."""

from __future__ import annotations

import hashlib
from typing import Any

from memcommit.core.context import Context
from memcommit.persistence.store import context_record_digest

from ..frame import _Frame


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
        from memcommit.application.operations.meld.model import (
            MeldChangeSet,
            meld_canonical_digest,
        )

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
