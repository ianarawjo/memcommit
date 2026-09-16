"""Validate retained cross-Context command membership without creating events."""

from __future__ import annotations

from typing import Any

from ..model import MemoryHistoryCommandContext, MemoryHistoryCommandOperation


def _command_restore_operation(
    *,
    command: str,
    args: dict[str, Any],
    context_uid: str,
    context_name: str,
) -> MemoryHistoryCommandOperation | None:
    """Validate the operation boundary retained by one Undo/Redo checkpoint.

    History is reconstructed one Context at a time, but the receipt deliberately
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
    contexts: list[MemoryHistoryCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(MemoryHistoryCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return MemoryHistoryCommandOperation(
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
) -> MemoryHistoryCommandOperation | None:
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
    contexts: list[MemoryHistoryCommandContext] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {"uid", "name"}:
            return None
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            return None
        contexts.append(MemoryHistoryCommandContext(uid=uid, name=name))
    identities = [(context.uid, context.name) for context in contexts]
    if (
        len(identities) != len(set(identities))
        or (context_uid, context_name) not in identities
    ):
        return None
    return MemoryHistoryCommandOperation(
        uid=f"update:{session_uid}:{operation_digest}",
        command=command,
        contexts=tuple(contexts),
    )
