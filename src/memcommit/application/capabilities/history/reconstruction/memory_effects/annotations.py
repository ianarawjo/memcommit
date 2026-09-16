"""Read operation-owned explanations without changing the direct effect grammar."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from ...history_evidence_source import HistoryEvidenceSource
from ...model.memory_event import MemoryHistoryRelation, MemoryHistorySource
from ...verification.frame import _Frame


def relation_annotations(
    relations: list[MemoryHistoryRelation],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    excluded = {
        "kind",
        "before",
        "after",
        "timestamp",
        "checkpoint_uid",
        "command",
        "description",
        "context_transition",
        "operation_id",
        "command_operation",
    }
    for relation in relations:
        annotation = {
            field.name: getattr(relation, field.name)
            for field in fields(relation)
            if field.name not in excluded
        }
        for uid in relation.uids:
            result[uid] = annotation.copy()
    return result


def update_annotations(
    *,
    source: HistoryEvidenceSource,
    before: _Frame,
    after: _Frame,
    args: dict,
    checkpoint_uid: str,
) -> dict[str, dict[str, Any]]:
    """Bind retained reasons to the exact checkpoint, operation set and states."""
    from memcommit.application.operations.update.model import operation_digest

    session_uid = args.get("update_session_uid")
    if not isinstance(session_uid, str):
        return {}
    receipt = source.load_update_receipt(session_uid)
    application = receipt.application
    if (
        receipt.uid != session_uid
        or application is None
        or args.get("owner_context_uid") != after.context_uid
        or operation_digest(receipt.operations) != args.get("operation_digest")
        or not any(
            cp.checkpoint_uid == checkpoint_uid and cp.context_uid == after.context_uid
            for cp in application.checkpoints
        )
    ):
        raise ValueError("Update application record does not match this checkpoint.")
    operations = tuple(
        op for op in receipt.operations if op.owner_context_uid == after.context_uid
    )
    if {op.memory_uid for op in operations} != set(
        args.get("operation_memory_uids", ())
    ):
        raise ValueError("Update operation membership does not match this checkpoint.")
    expected = {uid: state.content for uid, state in before.memories.items()}
    result = {}
    for operation in operations:
        uid = operation.memory_uid
        if operation.operation == "add":
            if uid in expected:
                raise ValueError("Update Add already exists in the command pre-image.")
            expected[uid] = operation.new_content
        else:
            if expected.get(uid) != operation.old_content:
                raise ValueError(
                    "Update pre-image does not match the applied operation."
                )
            if operation.operation == "remove":
                del expected[uid]
            else:
                expected[uid] = operation.new_content
        result[uid] = {
            "reason": operation.reason,
            "sources": tuple(
                MemoryHistorySource(**ref.to_dict()) for ref in operation.source_refs
            ),
        }
    if expected != {uid: state.content for uid, state in after.memories.items()}:
        raise ValueError("Update result does not match the applied operation set.")
    return result


def duplicate_relations(
    *, before: _Frame, after: _Frame, entry: dict
) -> list[MemoryHistoryRelation]:
    """Validate exact/semantic duplicate selections against their retained states."""
    args = entry.get("args") or {}
    command = entry.get("command")
    if command not in {"dedup", "dedun"}:
        return []
    groups = (
        args.get("groups", [])
        if command == "dedup"
        else args.get("exact_item_groups", [])
    )
    pairs: list[tuple[str, str, str]] = []
    for group in groups:
        if group.get("item_kind") != "MEMORY":
            continue
        survivor = group["survivor_uid"]
        for uid in group["absorbed_uids"]:
            if before.memories[uid].content != before.memories[survivor].content:
                raise ValueError("Exact duplicate record names unequal Memories.")
            pairs.append(
                (uid, survivor, f"Exact duplicate of retained Memory [{survivor}].")
            )
    if command == "dedun":
        for component in args.get("components", []):
            survivor = component["survivor_uid"]
            reasons = tuple(
                dict.fromkeys(
                    item["reason"]
                    for item in component["evidence"]
                    if item.get("reason")
                )
            )
            for member in component["members"]:
                uid = member["uid"]
                if before.memories[uid].content != member["content"]:
                    raise ValueError(
                        "Dedun member does not match its command pre-image."
                    )
                if uid != survivor:
                    pairs.append((uid, survivor, "\n".join(reasons)))
    relations = []
    for uid, survivor, reason in pairs:
        if (
            uid in after.memories
            or after.memories[survivor].content != before.memories[survivor].content
        ):
            raise ValueError("Duplicate disposition does not match the command result.")
        relations.append(
            MemoryHistoryRelation(
                command=command,
                checkpoint_uid=entry["uid"],
                timestamp=entry["timestamp"],
                description=entry.get("description") or "",
                before=(before.memories[uid],),
                after=(after.memories[survivor],),
                reason=reason or None,
            )
        )
    return relations
