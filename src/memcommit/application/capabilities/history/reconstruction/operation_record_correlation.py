"""Correlate checkpoint receipts that belong to one logical operation."""

from __future__ import annotations

from typing import Any
import uuid


class OperationRecordCorrelationError(RuntimeError):
    """A retained receipt cannot prove a safe logical operation identity."""


def _recursive_tree_identity(
    args: dict[str, Any],
    *,
    command: str,
    key: str,
    label: str,
) -> str | None:
    if key not in args:
        return None
    record = args.get(key)
    expected_fields = {"version", "operation_uid", "root", "include_descendants"}
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise OperationRecordCorrelationError(f"Recursive {label} receipt is invalid.")
    operation_uid = record.get("operation_uid")
    root = record.get("root")
    try:
        canonical_uid = str(uuid.UUID(operation_uid))
    except (AttributeError, TypeError, ValueError) as error:
        raise OperationRecordCorrelationError(
            f"Recursive {label} operation identity is invalid."
        ) from error
    if (
        record.get("version") != 1
        or operation_uid != canonical_uid
        or not isinstance(root, str)
        or not root
        or record.get("include_descendants") is not True
    ):
        raise OperationRecordCorrelationError(f"Recursive {label} receipt is invalid.")
    return f"{command}:{operation_uid}"


def operation_record_identity(
    *,
    checkpoint_uid: str,
    command: str,
    args: dict[str, Any],
) -> str:
    """Return the proven logical operation identity for one checkpoint record.

    A plain checkpoint falls back to its physical UID. Multi-Context commands
    collapse only when their explicit receipt fields prove shared identity.
    """

    if command == "checkpoint":
        record = args.get("checkpoint_set")
        if isinstance(record, dict):
            operation_uid = record.get("uid")
            try:
                canonical_uid = str(uuid.UUID(operation_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise OperationRecordCorrelationError(
                    "Recursive Checkpoint identity is invalid."
                ) from error
            if (
                record.get("version") not in {1, 2}
                or operation_uid != canonical_uid
                or record.get("include_descendants") is not True
            ):
                raise OperationRecordCorrelationError(
                    "Recursive Checkpoint identity is invalid."
                )
            return (
                f"checkpoint:{operation_uid}"
                if record.get("version") == 2
                else f"checkpoint-set:{operation_uid}"
            )
    if command == "update":
        session_uid = args.get("update_session_uid")
        operation_digest = args.get("operation_digest")
        if all(
            isinstance(value, str) and value
            for value in (session_uid, operation_digest)
        ):
            return f"update:{session_uid}:{operation_digest}"
    if command == "meld":
        record = args.get("meld")
        if isinstance(record, dict):
            session_uid = record.get("session_uid")
            change_set_digest = record.get("change_set_digest")
            if all(
                isinstance(value, str) and value
                for value in (session_uid, change_set_digest)
            ):
                return f"meld:{session_uid}:{change_set_digest}"
    if command == "sever":
        record = args.get("sever")
        if isinstance(record, dict) and isinstance(args.get("command_contexts"), list):
            session_uid = record.get("session_uid")
            session_digest = record.get("session_digest")
            if all(
                isinstance(value, str) and value
                for value in (session_uid, session_digest)
            ):
                # Every selected Source owner has its own physical checkpoint,
                # but this retained session identity proves that they belong to
                # one reviewed, atomic in-place Sever command.
                return f"sever:{session_uid}:{session_digest}"
    if command == "merge":
        record = args.get("merge_tree")
        if isinstance(record, dict):
            operation_uid = record.get("operation_uid")
            if (
                record.get("version") in {1, 2}
                and isinstance(operation_uid, str)
                and operation_uid
            ):
                return f"merge:{operation_uid}"
    if command == "replace":
        record = args.get("replace")
        if isinstance(record, dict):
            operation_uid = record.get("operation_uid")
            if (
                record.get("version") == 1
                and isinstance(operation_uid, str)
                and operation_uid
            ):
                return f"replace:{operation_uid}"
    if command in {"copy", "move"}:
        record = args.get("memory_transfer")
        if isinstance(record, dict):
            operation_uid = record.get("operation_uid")
            if (
                record.get("version") == 1
                and record.get("kind") == command.upper()
                and isinstance(operation_uid, str)
                and operation_uid
            ):
                return f"{command}:{operation_uid}"
    if command == "branch":
        record = args.get("branch_tree")
        if isinstance(record, dict):
            operation_uid = record.get("operation_uid")
            if (
                record.get("version") == 1
                and isinstance(operation_uid, str)
                and operation_uid
            ):
                return f"branch:{operation_uid}"
    if command == "clear":
        identity = _recursive_tree_identity(
            args,
            command=command,
            key="clear_tree",
            label="clear",
        )
        if identity is not None:
            return identity
    if command == "dedup":
        identity = _recursive_tree_identity(
            args,
            command=command,
            key="dedup_tree",
            label="exact Dedup",
        )
        if identity is not None:
            return identity
    if command == "dedun":
        identity = _recursive_tree_identity(
            args,
            command=command,
            key="dedun_tree",
            label="Dedun",
        )
        if identity is not None:
            return identity
    return f"checkpoint:{checkpoint_uid}"


__all__ = ["OperationRecordCorrelationError", "operation_record_identity"]
