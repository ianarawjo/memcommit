"""Reconstruct global Context-command undo and redo stacks from checkpoints.

Ordinary checkpoints remain owned by one Context.  This module adds the small
amount of host-side interpretation needed to recover command boundaries across
Contexts: semantic Update checkpoints share an Update identity, while explicit
Undo/Redo receipts share a restoration identity.  No referenced Context or
Memory content is opened while building the stacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from memcommit.context import Checkpoint, Context
from memcommit.history import HistoryError, flatten_checkpoint_entries
from memcommit.store import MemoryStore, canonical_context_record


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
        raw_command
        if isinstance(raw_command, str) and raw_command
        else "checkpoint"
    )
    raw_description = entry.get("description") or entry.get("message")
    description = (
        raw_description if isinstance(raw_description, str) else ""
    )
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
            target = records.get(target_uid) if isinstance(target_uid, str) else None
            if target is None:
                raise CommandHistoryError(
                    f"Revert checkpoint [{uid[:8]}] does not retain its target."
                )
            before = snapshot
            if owned and before != target:
                originals.append(
                    _OriginalPart(
                        unit_uid=f"revert:{uid}",
                        command="revert",
                        description=f"Reverted to checkpoint [{target_uid[:8]}]",
                        timestamp=timestamp,
                        expected_contexts=None,
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
                expected_contexts=_command_contexts(
                    args.get("command_contexts")
                ),
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
            or (
                expected_sets
                and set(next(iter(expected_sets))) != set(identities)
            )
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
            description=(
                next(iter(descriptions)) if len(descriptions) == 1 else ""
            ),
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
        actual = {
            (member.context_uid, member.context_name)
            for member in members
        }
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
