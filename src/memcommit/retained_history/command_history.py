"""Reconstruct global Context-command undo and redo stacks from checkpoints.

Ordinary checkpoints remain owned by one Context.  This module adds the small
amount of host-side interpretation needed to recover command boundaries across
Contexts: semantic Update and deterministic batch Move checkpoints share their
operation identity, while explicit Undo/Redo receipts share a restoration
identity. No referenced Context or Memory content is opened while building the
stacks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from memcommit.context import Checkpoint, Context
from memcommit.retained_history.reconstruction import HistoryError, flatten_checkpoint_entries
from memcommit.persistence.store import MemoryStore, canonical_context_record


RestoreDirection = Literal["undo", "redo"]
_RESTORE_METADATA_KEY = "command_restore"


class CommandHistoryError(RuntimeError):
    """Retained checkpoints do not describe a safe command stack."""


@dataclass(frozen=True)
class CommandContextChange:
    """One direct Context's pre/post image in an entered command."""

    context_uid: str
    context_name: str
    before: dict[str, object] | None
    after: dict[str, object] | None
    checkpoint_uid: str


@dataclass(frozen=True)
class ContextCommandUnit:
    """One recoverable entered command, possibly spanning Contexts."""

    uid: str
    command: str
    description: str
    started_at: str
    completed_at: str
    changes: tuple[CommandContextChange, ...]
    checkpoint_args: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class CommandStacks:
    undo: tuple[ContextCommandUnit, ...]
    redo: tuple[ContextCommandUnit, ...]


@dataclass(frozen=True)
class CommandRestoreResult:
    unit: ContextCommandUnit
    direction: RestoreDirection
    receipt_uid: str
    checkpoints: tuple[Checkpoint, ...]


@dataclass(frozen=True)
class BranchTreeContext:
    """One Source-to-target identity mapping in a Branch command receipt."""

    source_uid: str
    source_name: str
    target_uid: str
    target_name: str


@dataclass(frozen=True)
class BranchTreeReceipt:
    """Frozen lifecycle identity for one exact or recursive Branch."""

    operation_uid: str
    source_root: str
    target_root: str
    include_descendants: bool
    current_before: str | None
    contexts: tuple[BranchTreeContext, ...]


@dataclass(frozen=True)
class _OriginalPart:
    unit_uid: str
    command: str
    description: str
    timestamp: str
    expected_contexts: tuple[tuple[str, str], ...] | None
    args: dict[str, object]
    change: CommandContextChange


@dataclass(frozen=True)
class _RestorePart:
    receipt_uid: str
    direction: RestoreDirection
    source_unit_uid: str
    source_command: str
    timestamp: str
    expected_contexts: tuple[tuple[str, str], ...]
    context_uid: str
    context_name: str


@dataclass(frozen=True)
class _StackEvent:
    started_at: str
    completed_at: str
    kind: Literal["original", "undo", "redo"]
    uid: str
    unit: ContextCommandUnit


def command_restore_metadata(
    *,
    receipt_uid: str,
    direction: RestoreDirection,
    unit: ContextCommandUnit,
) -> dict[str, object]:
    """Return the checkpoint metadata shared by one restoration receipt."""
    return {
        "version": 1,
        "receipt_uid": receipt_uid,
        "direction": direction,
        "source_unit_uid": unit.uid,
        "source_command": unit.command,
        "contexts": [
            {
                "uid": change.context_uid,
                "name": change.context_name,
            }
            for change in unit.changes
        ],
    }


def _normalized_record(
    snapshot: object,
    *,
    context_uid: str,
    context_name: str,
) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        raise CommandHistoryError(
            "Checkpoint history contains an invalid Context snapshot."
        )
    try:
        return canonical_context_record(
            {
                **snapshot,
                "uid": context_uid,
                "name": context_name,
            }
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CommandHistoryError(
            "Checkpoint history contains an invalid Context snapshot."
        ) from error


def _owned_snapshot(
    snapshot: object,
    *,
    context_uid: str,
    context_name: str,
) -> bool:
    return (
        isinstance(snapshot, dict)
        and snapshot.get("uid") == context_uid
        and snapshot.get("name") == context_name
    )


def _entry_fields(
    entry: dict[str, Any],
) -> tuple[str, str, str, str, dict[str, Any], bool]:
    uid = entry.get("uid")
    timestamp = entry.get("timestamp")
    if not isinstance(uid, str) or not uid:
        raise CommandHistoryError("Checkpoint history contains an invalid UID.")
    if not isinstance(timestamp, str) or not timestamp:
        raise CommandHistoryError(
            f"Checkpoint [{uid[:8]}] contains an invalid timestamp."
        )
    raw_command = entry.get("command")
    command = (
        raw_command if isinstance(raw_command, str) and raw_command else "checkpoint"
    )
    raw_description = entry.get("description") or entry.get("message")
    description = raw_description if isinstance(raw_description, str) else ""
    raw_args = entry.get("args")
    args = raw_args if isinstance(raw_args, dict) else {}
    return uid, timestamp, command, description, args, bool(entry.get("auto"))


def _restore_part(
    entry: dict[str, Any],
    *,
    context_uid: str,
    context_name: str,
) -> _RestorePart | None:
    _, timestamp, command, _, args, _ = _entry_fields(entry)
    if command not in {"undo", "redo"}:
        return None
    value = args.get(_RESTORE_METADATA_KEY)
    if not isinstance(value, dict) or set(value) != {
        "version",
        "receipt_uid",
        "direction",
        "source_unit_uid",
        "source_command",
        "contexts",
    }:
        raise CommandHistoryError("Command restoration receipt is invalid.")
    if value.get("version") != 1:
        raise CommandHistoryError("Command restoration receipt version is invalid.")
    receipt_uid = value.get("receipt_uid")
    direction = value.get("direction")
    source_unit_uid = value.get("source_unit_uid")
    source_command = value.get("source_command")
    raw_contexts = value.get("contexts")
    if (
        not isinstance(receipt_uid, str)
        or not receipt_uid
        or direction not in {"undo", "redo"}
        or direction != command
        or not isinstance(source_unit_uid, str)
        or not source_unit_uid
        or not isinstance(source_command, str)
        or not source_command
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        raise CommandHistoryError("Command restoration receipt is invalid.")
    expected_contexts: list[tuple[str, str]] = []
    for raw_context in raw_contexts:
        if not isinstance(raw_context, dict) or set(raw_context) != {
            "uid",
            "name",
        }:
            raise CommandHistoryError("Command restoration Context is invalid.")
        uid = raw_context.get("uid")
        name = raw_context.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            raise CommandHistoryError("Command restoration Context is invalid.")
        expected_contexts.append((uid, name))
    if len(expected_contexts) != len(set(expected_contexts)):
        raise CommandHistoryError(
            "Command restoration receipt repeats an affected Context."
        )
    return _RestorePart(
        receipt_uid=receipt_uid,
        direction=direction,
        source_unit_uid=source_unit_uid,
        source_command=source_command,
        timestamp=timestamp,
        expected_contexts=tuple(expected_contexts),
        context_uid=context_uid,
        context_name=context_name,
    )


def command_unit_uid(
    *,
    checkpoint_uid: str,
    command: str,
    args: dict[str, Any],
) -> str:
    if command == "checkpoint":
        record = args.get("checkpoint_set")
        if isinstance(record, dict):
            operation_uid = record.get("uid")
            try:
                canonical_uid = str(uuid.UUID(operation_uid))
            except (AttributeError, TypeError, ValueError) as error:
                raise CommandHistoryError(
                    "Recursive Checkpoint identity is invalid."
                ) from error
            if (
                record.get("version") not in {1, 2}
                or operation_uid != canonical_uid
                or record.get("include_descendants") is not True
            ):
                raise CommandHistoryError("Recursive Checkpoint identity is invalid.")
            # Version 2 deliberately uses the root's real checkpoint UID as
            # the complete recovery-unit handle. Legacy version 1 retains its
            # receipt-only set UID as a catalog alias.
            return (
                f"checkpoint:{operation_uid}"
                if record.get("version") == 2
                else f"checkpoint-set:{operation_uid}"
            )
    if command == "update":
        session_uid = args.get("update_session_uid")
        operation_digest = args.get("operation_digest")
        if (
            isinstance(session_uid, str)
            and session_uid
            and isinstance(operation_digest, str)
            and operation_digest
        ):
            return f"update:{session_uid}:{operation_digest}"
    if command == "meld":
        record = args.get("meld")
        if isinstance(record, dict):
            session_uid = record.get("session_uid")
            change_set_digest = record.get("change_set_digest")
            if (
                isinstance(session_uid, str)
                and session_uid
                and isinstance(change_set_digest, str)
                and change_set_digest
            ):
                return f"meld:{session_uid}:{change_set_digest}"
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
    if command == "clear" and "clear_tree" in args:
        record = args.get("clear_tree")
        expected_fields = {
            "version",
            "operation_uid",
            "root",
            "include_descendants",
        }
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise CommandHistoryError("Recursive clear receipt is invalid.")
        operation_uid = record.get("operation_uid")
        root = record.get("root")
        try:
            canonical_uid = str(uuid.UUID(operation_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise CommandHistoryError(
                "Recursive clear operation identity is invalid."
            ) from error
        if (
            record.get("version") != 1
            or operation_uid != canonical_uid
            or not isinstance(root, str)
            or not root
            or record.get("include_descendants") is not True
        ):
            raise CommandHistoryError("Recursive clear receipt is invalid.")
        return f"clear:{operation_uid}"
    if command == "dedup" and "dedup_tree" in args:
        record = args.get("dedup_tree")
        expected_fields = {
            "version",
            "operation_uid",
            "root",
            "include_descendants",
        }
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise CommandHistoryError("Recursive exact Dedup receipt is invalid.")
        operation_uid = record.get("operation_uid")
        root = record.get("root")
        try:
            canonical_uid = str(uuid.UUID(operation_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise CommandHistoryError(
                "Recursive exact Dedup operation identity is invalid."
            ) from error
        if (
            record.get("version") != 1
            or operation_uid != canonical_uid
            or not isinstance(root, str)
            or not root
            or record.get("include_descendants") is not True
        ):
            raise CommandHistoryError("Recursive exact Dedup receipt is invalid.")
        return f"dedup:{operation_uid}"
    if command == "dedun" and "dedun_tree" in args:
        record = args.get("dedun_tree")
        expected_fields = {
            "version",
            "operation_uid",
            "root",
            "include_descendants",
        }
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise CommandHistoryError("Recursive Dedun receipt is invalid.")
        operation_uid = record.get("operation_uid")
        root = record.get("root")
        try:
            canonical_uid = str(uuid.UUID(operation_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise CommandHistoryError(
                "Recursive Dedun operation identity is invalid."
            ) from error
        if (
            record.get("version") != 1
            or operation_uid != canonical_uid
            or not isinstance(root, str)
            or not root
            or record.get("include_descendants") is not True
        ):
            raise CommandHistoryError("Recursive Dedun receipt is invalid.")
        return f"dedun:{operation_uid}"
    return f"checkpoint:{checkpoint_uid}"


def _command_contexts(
    value: object,
) -> tuple[tuple[str, str], ...] | None:
    """Validate an optional complete multi-Context command membership list."""
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise CommandHistoryError("Command Context membership is invalid.")
    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"uid", "name"}:
            raise CommandHistoryError("Command Context membership is invalid.")
        uid = item.get("uid")
        name = item.get("name")
        if not isinstance(uid, str) or not uid or not isinstance(name, str) or not name:
            raise CommandHistoryError("Command Context membership is invalid.")
        result.append((uid, name))
    if len(result) != len(set(result)):
        raise CommandHistoryError("Command Context membership contains duplicates.")
    return tuple(result)


def _revert_unit(
    args: dict[str, Any],
) -> tuple[str, str, tuple[tuple[str, str], ...]] | None:
    """Validate one shared multi-Context Revert command receipt."""

    record = args.get("revert_unit")
    if record is None:
        return None
    expected_fields = {
        "version",
        "receipt_uid",
        "checkpoint_unit_uid",
        "checkpoint_set_uid",
        "root_context_uid",
        "root_context_name",
        "contexts",
    }
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise CommandHistoryError("Recursive Revert receipt is invalid.")
    receipt_uid = record.get("receipt_uid")
    checkpoint_unit_uid = record.get("checkpoint_unit_uid")
    checkpoint_set_uid = record.get("checkpoint_set_uid")
    try:
        canonical_receipt_uid = str(uuid.UUID(receipt_uid))
        canonical_checkpoint_uid = str(uuid.UUID(checkpoint_unit_uid))
        canonical_set_uid = str(uuid.UUID(checkpoint_set_uid))
    except (AttributeError, TypeError, ValueError) as error:
        raise CommandHistoryError("Recursive Revert receipt is invalid.") from error
    root_context_uid = record.get("root_context_uid")
    root_context_name = record.get("root_context_name")
    contexts = _command_contexts(record.get("contexts"))
    command_contexts = _command_contexts(args.get("command_contexts"))
    if (
        record.get("version") != 1
        or receipt_uid != canonical_receipt_uid
        or checkpoint_unit_uid != canonical_checkpoint_uid
        or checkpoint_set_uid != canonical_set_uid
        or not isinstance(root_context_uid, str)
        or not root_context_uid
        or not isinstance(root_context_name, str)
        or not root_context_name
        or contexts is None
        or command_contexts != contexts
        or (root_context_uid, root_context_name) not in contexts
    ):
        raise CommandHistoryError("Recursive Revert receipt is invalid.")
    return canonical_receipt_uid, canonical_checkpoint_uid, contexts


def branch_tree_receipt(args: dict[str, Any]) -> BranchTreeReceipt:
    """Validate and normalize one complete Branch creation receipt.

    Branch copies Source history into independently owned target Contexts, so
    inherited checkpoints cannot prove where the target lifecycle began. This
    explicit receipt is the sole boundary that lets command history treat the
    target pre-image as absent without mistaking inherited Source state for a
    prior target state.
    """

    record = args.get("branch_tree")
    expected_fields = {
        "version",
        "operation_uid",
        "source_root",
        "target_root",
        "include_descendants",
        "current_before",
        "contexts",
    }
    if not isinstance(record, dict) or set(record) != expected_fields:
        raise CommandHistoryError("Branch creation receipt is invalid.")
    operation_uid = record.get("operation_uid")
    try:
        canonical_operation_uid = str(uuid.UUID(operation_uid))
    except (AttributeError, TypeError, ValueError) as error:
        raise CommandHistoryError("Branch operation uid is invalid.") from error
    source_root = record.get("source_root")
    target_root = record.get("target_root")
    include_descendants = record.get("include_descendants")
    current_before = record.get("current_before")
    raw_contexts = record.get("contexts")
    if (
        record.get("version") != 1
        or operation_uid != canonical_operation_uid
        or not isinstance(source_root, str)
        or not source_root
        or not isinstance(target_root, str)
        or not target_root
        or source_root == target_root
        or type(include_descendants) is not bool
        or (current_before is not None and not isinstance(current_before, str))
        or not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        raise CommandHistoryError("Branch creation receipt is invalid.")

    contexts: list[BranchTreeContext] = []
    for raw in raw_contexts:
        if not isinstance(raw, dict) or set(raw) != {
            "source_uid",
            "source_name",
            "target_uid",
            "target_name",
        }:
            raise CommandHistoryError("Branch Context receipt is invalid.")
        values = tuple(
            raw.get(key)
            for key in (
                "source_uid",
                "source_name",
                "target_uid",
                "target_name",
            )
        )
        if not all(isinstance(value, str) and value for value in values):
            raise CommandHistoryError("Branch Context receipt is invalid.")
        source_uid, source_name, target_uid, target_name = values
        assert isinstance(source_uid, str)
        assert isinstance(source_name, str)
        assert isinstance(target_uid, str)
        assert isinstance(target_name, str)
        if source_name != source_root and not source_name.startswith(source_root + "/"):
            raise CommandHistoryError(
                "Branch Context receipt escapes its Source subtree."
            )
        expected_target = target_root + source_name[len(source_root) :]
        if target_name != expected_target:
            raise CommandHistoryError(
                "Branch Context receipt does not preserve subtree suffixes."
            )
        contexts.append(
            BranchTreeContext(
                source_uid=source_uid,
                source_name=source_name,
                target_uid=target_uid,
                target_name=target_name,
            )
        )

    source_identities = [(item.source_uid, item.source_name) for item in contexts]
    target_identities = [(item.target_uid, item.target_name) for item in contexts]
    command_contexts = _command_contexts(args.get("command_contexts"))
    if (
        len(source_identities) != len(set(source_identities))
        or len(target_identities) != len(set(target_identities))
        or not any(item.source_name == source_root for item in contexts)
        or not any(item.target_name == target_root for item in contexts)
        or (not include_descendants and len(contexts) != 1)
        or command_contexts is None
        or set(command_contexts) != set(target_identities)
    ):
        raise CommandHistoryError("Branch creation membership is invalid.")
    return BranchTreeReceipt(
        operation_uid=canonical_operation_uid,
        source_root=source_root,
        target_root=target_root,
        include_descendants=include_descendants,
        current_before=current_before,
        contexts=tuple(contexts),
    )


def _context_parts(
    store: MemoryStore,
    context_name: str,
    *,
    archived: tuple[Context, list[dict[str, Any]]] | None = None,
) -> tuple[list[_OriginalPart], list[_RestorePart]]:
    if archived is None:
        context = store.load_direct(context_name)
        raw_entries = store.list_checkpoints(context_name)
    else:
        context, raw_entries = archived
    try:
        entries, _ = flatten_checkpoint_entries(raw_entries)
    except HistoryError as error:
        raise CommandHistoryError(str(error)) from error
    records = {
        entry["uid"]: _normalized_record(
            entry["snapshot"],
            context_uid=context.uid,
            context_name=context.name,
        )
        for entry in entries
    }
    originals: list[_OriginalPart] = []
    restorations: list[_RestorePart] = []
    effective: dict[str, object] | None = None
    for entry in entries:
        uid, timestamp, command, description, args, auto = _entry_fields(entry)
        snapshot = records[uid]
        owned = _owned_snapshot(
            entry.get("snapshot"),
            context_uid=context.uid,
            context_name=context.name,
        )

        restore = _restore_part(
            entry,
            context_uid=context.uid,
            context_name=context.name,
        )
        if restore is not None:
            recorded_before = entry.get("command_before")
            normalized_before = (
                _normalized_record(
                    recorded_before,
                    context_uid=context.uid,
                    context_name=context.name,
                )
                if isinstance(recorded_before, dict)
                else None
            )
            if (
                effective is not None
                and normalized_before is not None
                and effective != normalized_before
            ):
                raise CommandHistoryError(
                    "Command restoration pre-image conflicts with retained history."
                )
            if effective is None and normalized_before is None:
                raise CommandHistoryError(
                    "Command restoration has no preceding Context state."
                )
            if owned:
                restorations.append(restore)
            effective = snapshot
            continue

        if command in {"ground", "ground-undo"}:
            # Ground owns a root-scoped command stack over its physical lane
            # Contexts.  Letting these checkpoints enter the Profile-global
            # stack would make ``mem undo`` consume an in-workspace action and
            # would couple unrelated Ground roots by timestamp.
            effective = snapshot
            continue

        if command == "revert":
            target_uid = args.get("target_uid")
            revert_unit = _revert_unit(args)
            recorded_restoration = entry.get("restored_snapshot")
            target = (
                _normalized_record(
                    recorded_restoration,
                    context_uid=context.uid,
                    context_name=context.name,
                )
                if isinstance(recorded_restoration, dict)
                else (records.get(target_uid) if isinstance(target_uid, str) else None)
            )
            if target is None:
                raise CommandHistoryError(
                    f"Revert checkpoint [{uid[:8]}] does not retain its target."
                )
            before = snapshot
            if owned and before != target:
                unit_uid = (
                    f"revert:{revert_unit[0]}"
                    if revert_unit is not None
                    else f"revert:{uid}"
                )
                originals.append(
                    _OriginalPart(
                        unit_uid=unit_uid,
                        command="revert",
                        description=(
                            f"Reverted checkpoint unit [{revert_unit[1][:8]}]"
                            if revert_unit is not None
                            else f"Reverted to checkpoint [{target_uid[:8]}]"
                        ),
                        timestamp=timestamp,
                        expected_contexts=(
                            revert_unit[2] if revert_unit is not None else None
                        ),
                        args=args,
                        change=CommandContextChange(
                            context_uid=context.uid,
                            context_name=context.name,
                            before=before,
                            after=target,
                            checkpoint_uid=uid,
                        ),
                    )
                )
            effective = target
            continue

        recorded_before = entry.get("command_before")
        normalized_before = (
            _normalized_record(
                recorded_before,
                context_uid=context.uid,
                context_name=context.name,
            )
            if isinstance(recorded_before, dict)
            else None
        )
        branch_receipt = (
            branch_tree_receipt(args)
            if command == "branch" and "branch_tree" in args
            else None
        )
        is_branch_creation = branch_receipt is not None and any(
            item.target_uid == context.uid and item.target_name == context.name
            for item in branch_receipt.contexts
        )
        if branch_receipt is not None and not is_branch_creation:
            raise CommandHistoryError(
                "Branch checkpoint owner is outside its creation membership."
            )
        if is_branch_creation and (not owned or not auto):
            raise CommandHistoryError(
                "Branch creation checkpoint does not own its automatic snapshot."
            )
        if is_branch_creation:
            originals.append(
                _OriginalPart(
                    unit_uid=command_unit_uid(
                        checkpoint_uid=uid,
                        command=command,
                        args=args,
                    ),
                    command=command,
                    description=description,
                    timestamp=timestamp,
                    expected_contexts=_command_contexts(args.get("command_contexts")),
                    args=args,
                    change=CommandContextChange(
                        context_uid=context.uid,
                        context_name=context.name,
                        # Inherited Source checkpoints describe lineage, not a
                        # pre-existing target. Branch therefore has an absent
                        # target pre-image even when ``effective`` is nonempty.
                        before=None,
                        after=snapshot,
                        checkpoint_uid=uid,
                    ),
                )
            )
            effective = snapshot
            continue
        merge_tree = args.get("merge_tree")
        is_legacy_recursive_merge = (
            command == "merge"
            and isinstance(merge_tree, dict)
            and merge_tree.get("version") == 1
            and isinstance(merge_tree.get("operation_uid"), str)
        )
        if is_legacy_recursive_merge:
            # A recursive Merge can both update and create Contexts. The
            # current lifecycle restoration archive supports one exact Sever
            # creation only; exposing a partial tree Undo would be worse than
            # keeping this checkpoint out of the command stack. Diff/history
            # still retain every per-Context checkpoint until generic
            # multi-Context creation restoration is implemented.
            effective = snapshot
            continue
        creation = args.get("context_creation")
        is_exact_sever_creation = (
            command == "sever"
            and isinstance(creation, dict)
            and set(creation) == {"version", "context_uid", "context_name"}
            and creation.get("version") == 1
            and creation.get("context_uid") == context.uid
            and creation.get("context_name") == context.name
        )
        is_merge_creation = (
            command == "merge"
            and isinstance(merge_tree, dict)
            and merge_tree.get("version") == 2
            and merge_tree.get("target_created") is True
            and isinstance(merge_tree.get("operation_uid"), str)
            and bool(merge_tree.get("operation_uid"))
        )
        save_as = args.get("atomize_save_as")
        is_exact_atomize_creation = (
            command == "atomize"
            and isinstance(creation, dict)
            and set(creation) == {"version", "context_uid", "context_name"}
            and creation.get("version") == 1
            and creation.get("context_uid") == context.uid
            and creation.get("context_name") == context.name
            and isinstance(save_as, dict)
            and save_as.get("version") == 1
        )
        # A created result has no pre-image only when neither the
        # checkpoint nor the retained history supplies one.  Test those
        # sources directly: ``before`` is assigned below for ordinary edits.
        if (
            normalized_before is None
            and effective is None
            and (
                is_exact_sever_creation
                or is_merge_creation
                or is_exact_atomize_creation
            )
            and owned
            and auto
        ):
            originals.append(
                _OriginalPart(
                    unit_uid=command_unit_uid(
                        checkpoint_uid=uid,
                        command=command,
                        args=args,
                    ),
                    command=command,
                    description=description,
                    timestamp=timestamp,
                    expected_contexts=None,
                    args=args,
                    change=CommandContextChange(
                        context_uid=context.uid,
                        context_name=context.name,
                        before=None,
                        after=snapshot,
                        checkpoint_uid=uid,
                    ),
                )
            )
            continue
        if (
            effective is not None
            and normalized_before is not None
            and effective != normalized_before
        ):
            raise CommandHistoryError(
                f"Checkpoint [{uid[:8]}] pre-image conflicts with retained history."
            )
        before = normalized_before if normalized_before is not None else effective
        effective = snapshot
        if (
            not auto
            or command in {"checkpoint", "init"}
            or not owned
            or before is None
            # A zero-change Meld still changes its durable session from READY
            # to APPLIED. Keep that checkpoint in the command stack so Undo
            # and Redo restore the complete operation rather than only visible
            # Context bytes.
            or (before == snapshot and command not in {"meld", "merge"})
        ):
            continue
        originals.append(
            _OriginalPart(
                unit_uid=command_unit_uid(
                    checkpoint_uid=uid,
                    command=command,
                    args=args,
                ),
                command=command,
                description=description,
                timestamp=timestamp,
                expected_contexts=_command_contexts(args.get("command_contexts")),
                args=args,
                change=CommandContextChange(
                    context_uid=context.uid,
                    context_name=context.name,
                    before=before,
                    after=snapshot,
                    checkpoint_uid=uid,
                ),
            )
        )
    return originals, restorations


def _group_originals(parts: list[_OriginalPart]) -> dict[str, ContextCommandUnit]:
    grouped: dict[str, list[_OriginalPart]] = {}
    for part in parts:
        grouped.setdefault(part.unit_uid, []).append(part)
    units: dict[str, ContextCommandUnit] = {}
    for uid, members in grouped.items():
        commands = {member.command for member in members}
        descriptions = {member.description for member in members}
        expected_sets = {
            member.expected_contexts
            for member in members
            if member.expected_contexts is not None
        }
        identities = [
            (member.change.context_uid, member.change.context_name)
            for member in members
        ]
        if (
            len(commands) != 1
            or len(identities) != len(set(identities))
            or len(expected_sets) > 1
            or (expected_sets and set(next(iter(expected_sets))) != set(identities))
        ):
            raise CommandHistoryError(
                f"Command unit '{uid}' has inconsistent checkpoint metadata."
            )
        ordered = sorted(
            members,
            key=lambda member: (
                member.change.context_name,
                member.change.context_uid,
            ),
        )
        units[uid] = ContextCommandUnit(
            uid=uid,
            command=next(iter(commands)),
            description=(next(iter(descriptions)) if len(descriptions) == 1 else ""),
            started_at=min(member.timestamp for member in members),
            completed_at=max(member.timestamp for member in members),
            changes=tuple(member.change for member in ordered),
            checkpoint_args=tuple(member.args for member in ordered),
        )
    return units


def _restore_events(
    parts: list[_RestorePart],
    units: dict[str, ContextCommandUnit],
) -> list[_StackEvent]:
    grouped: dict[str, list[_RestorePart]] = {}
    for part in parts:
        grouped.setdefault(part.receipt_uid, []).append(part)
    events: list[_StackEvent] = []
    for receipt_uid, members in grouped.items():
        directions = {member.direction for member in members}
        sources = {member.source_unit_uid for member in members}
        source_commands = {member.source_command for member in members}
        expected_sets = {member.expected_contexts for member in members}
        actual = {(member.context_uid, member.context_name) for member in members}
        if (
            len(directions) != 1
            or len(sources) != 1
            or len(source_commands) != 1
            or len(expected_sets) != 1
            or actual != set(next(iter(expected_sets)))
        ):
            raise CommandHistoryError(
                f"Command restoration [{receipt_uid[:8]}] is incomplete."
            )
        source_uid = next(iter(sources))
        unit = units.get(source_uid)
        if unit is None or unit.command != next(iter(source_commands)):
            raise CommandHistoryError(
                f"Command restoration [{receipt_uid[:8]}] lost its source command."
            )
        direction = next(iter(directions))
        events.append(
            _StackEvent(
                started_at=min(member.timestamp for member in members),
                completed_at=max(member.timestamp for member in members),
                kind=direction,
                uid=receipt_uid,
                unit=unit,
            )
        )
    return events


def build_command_stacks(store: MemoryStore) -> CommandStacks:
    """Reconstruct global LIFO stacks from retained direct checkpoints."""
    original_parts: list[_OriginalPart] = []
    restore_parts: list[_RestorePart] = []
    try:
        names = store.list_context_names()
    except (OSError, ValueError) as error:
        raise CommandHistoryError(str(error)) from error
    for name in names:
        try:
            originals, restorations = _context_parts(store, name)
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            raise CommandHistoryError(str(error)) from error
        original_parts.extend(originals)
        restore_parts.extend(restorations)

    try:
        archives = store.list_command_context_archives()
    except (OSError, RuntimeError, ValueError) as error:
        raise CommandHistoryError(str(error)) from error
    for context, entries in archives:
        try:
            originals, restorations = _context_parts(
                store,
                context.name,
                archived=(context, entries),
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise CommandHistoryError(str(error)) from error
        original_parts.extend(originals)
        restore_parts.extend(restorations)

    units = _group_originals(original_parts)
    events = [
        _StackEvent(
            started_at=unit.started_at,
            completed_at=unit.completed_at,
            kind="original",
            uid=unit.uid,
            unit=unit,
        )
        for unit in units.values()
    ]
    events.extend(_restore_events(restore_parts, units))
    events.sort(
        key=lambda event: (
            event.completed_at,
            event.started_at,
            0 if event.kind == "original" else 1,
            event.uid,
        )
    )
    for previous, current in zip(events, events[1:]):
        if previous.completed_at > current.started_at:
            raise CommandHistoryError(
                "Concurrent Context commands have no safe global undo order."
            )

    undo: list[ContextCommandUnit] = []
    redo: list[ContextCommandUnit] = []
    for event in events:
        if event.kind == "original":
            undo.append(event.unit)
            redo.clear()
            continue
        if event.kind == "undo":
            if not undo or undo[-1].uid != event.unit.uid:
                raise CommandHistoryError(
                    "Undo receipt does not match the latest applied command."
                )
            redo.append(undo.pop())
            continue
        if not redo or redo[-1].uid != event.unit.uid:
            raise CommandHistoryError(
                "Redo receipt does not match the latest undone command."
            )
        undo.append(redo.pop())
    return CommandStacks(undo=tuple(undo), redo=tuple(redo))
