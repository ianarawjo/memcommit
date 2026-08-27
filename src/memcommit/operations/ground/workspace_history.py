"""Root-scoped command history for physical Ground workspaces.

Ground-local history deliberately does not reuse the Profile-global Undo
stack.  It reads only checkpoints carrying the exact workspace UID and writes
one new receipt checkpoint per affected Context when restoring a command.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from memcommit.context import AutoCheckpoint, Checkpoint, Context
from memcommit.operations.ground.workspace_model import GroundWorkspaceError
from memcommit.operations.ground.workspace_runtime import load_ground_workspace
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    canonical_context_record,
    context_record_digest,
)


_GROUND_COMMAND_KEY = "ground_workspace_command"


class GroundWorkspaceHistoryError(RuntimeError):
    """Ground checkpoints do not describe one safe root-scoped stack."""


@dataclass(frozen=True)
class GroundWorkspaceContextChange:
    context_uid: str
    context_name: str
    before: dict[str, object]
    after: dict[str, object]
    checkpoint_uid: str


@dataclass(frozen=True)
class GroundWorkspaceCommandUnit:
    uid: str
    workspace_uid: str
    workspace_name: str
    action: str
    revision: int
    timestamp: str
    changes: tuple[GroundWorkspaceContextChange, ...]


@dataclass(frozen=True)
class GroundWorkspaceCommandStack:
    undo: tuple[GroundWorkspaceCommandUnit, ...]


@dataclass(frozen=True)
class GroundWorkspaceUndoResult:
    source_unit: GroundWorkspaceCommandUnit
    receipt_uid: str
    revision: int
    checkpoints: tuple[Checkpoint, ...]


@dataclass(frozen=True)
class _EditPart:
    unit_uid: str
    workspace_uid: str
    workspace_name: str
    action: str
    revision: int
    timestamp: str
    expected_contexts: tuple[tuple[str, str], ...]
    change: GroundWorkspaceContextChange


@dataclass(frozen=True)
class _UndoPart:
    receipt_uid: str
    source_unit_uid: str
    workspace_uid: str
    workspace_name: str
    timestamp: str
    expected_contexts: tuple[tuple[str, str], ...]
    context_uid: str
    context_name: str


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GroundWorkspaceHistoryError(f"Ground {label} is invalid.")
    return value


def _required_revision(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GroundWorkspaceHistoryError("Ground command revision is invalid.")
    return value


def _command_contexts(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise GroundWorkspaceHistoryError(
            "Ground command Context membership is invalid."
        )
    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"uid", "name"}:
            raise GroundWorkspaceHistoryError(
                "Ground command Context membership is invalid."
            )
        result.append(
            (
                _required_text(item.get("uid"), "Context UID"),
                _required_text(item.get("name"), "Context name"),
            )
        )
    if len(result) != len(set(result)):
        raise GroundWorkspaceHistoryError(
            "Ground command Context membership contains duplicates."
        )
    return tuple(result)


def _owned_record(
    value: object,
    *,
    context_uid: str,
    context_name: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GroundWorkspaceHistoryError(
            "Ground checkpoint is missing a Context record."
        )
    if value.get("uid") != context_uid or value.get("name") != context_name:
        raise GroundWorkspaceHistoryError(
            "Ground checkpoint Context identity is inconsistent."
        )
    try:
        return canonical_context_record(value)
    except (KeyError, TypeError, ValueError) as error:
        raise GroundWorkspaceHistoryError(
            "Ground checkpoint Context record is invalid."
        ) from error


def _parts_for_context(
    store: MemoryStore,
    *,
    workspace_uid: str,
    workspace_name: str,
    context: Context,
) -> tuple[list[_EditPart], list[_UndoPart]]:
    edits: list[_EditPart] = []
    undos: list[_UndoPart] = []
    for entry in sorted(
        store.list_checkpoints(context.name),
        key=lambda item: item.get("timestamp", ""),
    ):
        command = entry.get("command")
        if command not in {"ground", "ground-undo"}:
            continue
        args = entry.get("args")
        metadata = args.get(_GROUND_COMMAND_KEY) if isinstance(args, dict) else None
        if not isinstance(metadata, dict) or metadata.get("version") != 1:
            raise GroundWorkspaceHistoryError(
                "Ground command checkpoint metadata is invalid."
            )
        if (
            metadata.get("workspace_uid") != workspace_uid
            or metadata.get("workspace_name") != workspace_name
        ):
            # A checkpoint under a workspace-owned physical lane may never be
            # silently attributed to another root.
            raise GroundWorkspaceHistoryError(
                "Ground command checkpoint belongs to a different workspace."
            )
        timestamp = _required_text(entry.get("timestamp"), "timestamp")
        expected_contexts = _command_contexts(args.get("command_contexts"))
        if (context.uid, context.name) not in expected_contexts:
            raise GroundWorkspaceHistoryError(
                "Ground command omits its checkpoint Context from membership."
            )
        if command == "ground":
            if metadata.get("kind") != "edit":
                raise GroundWorkspaceHistoryError("Ground edit kind is invalid.")
            before = _owned_record(
                entry.get("command_before"),
                context_uid=context.uid,
                context_name=context.name,
            )
            after = _owned_record(
                entry.get("snapshot"),
                context_uid=context.uid,
                context_name=context.name,
            )
            edits.append(
                _EditPart(
                    unit_uid=_required_text(
                        metadata.get("command_uid"), "command UID"
                    ),
                    workspace_uid=workspace_uid,
                    workspace_name=workspace_name,
                    action=_required_text(metadata.get("action"), "action"),
                    revision=_required_revision(metadata.get("revision")),
                    timestamp=timestamp,
                    expected_contexts=expected_contexts,
                    change=GroundWorkspaceContextChange(
                        context_uid=context.uid,
                        context_name=context.name,
                        before=before,
                        after=after,
                        checkpoint_uid=_required_text(
                            entry.get("uid"), "checkpoint UID"
                        ),
                    ),
                )
            )
            continue
        if metadata.get("kind") != "undo":
            raise GroundWorkspaceHistoryError("Ground Undo kind is invalid.")
        undos.append(
            _UndoPart(
                receipt_uid=_required_text(
                    metadata.get("command_uid"), "Undo receipt UID"
                ),
                source_unit_uid=_required_text(
                    metadata.get("source_command_uid"), "Undo source UID"
                ),
                workspace_uid=workspace_uid,
                workspace_name=workspace_name,
                timestamp=timestamp,
                expected_contexts=expected_contexts,
                context_uid=context.uid,
                context_name=context.name,
            )
        )
    return edits, undos


def build_ground_workspace_command_stack(
    store: MemoryStore,
    workspace_name: str,
) -> GroundWorkspaceCommandStack:
    """Reconstruct one workspace's applied edit stack from exact lanes only."""

    workspace = load_ground_workspace(store, workspace_name)
    edit_parts: list[_EditPart] = []
    undo_parts: list[_UndoPart] = []
    for context in workspace.all_contexts:
        edits, undos = _parts_for_context(
            store,
            workspace_uid=workspace.uid,
            workspace_name=workspace.name,
            context=context,
        )
        edit_parts.extend(edits)
        undo_parts.extend(undos)

    grouped_edits: dict[str, list[_EditPart]] = {}
    for part in edit_parts:
        grouped_edits.setdefault(part.unit_uid, []).append(part)
    units: dict[str, GroundWorkspaceCommandUnit] = {}
    for uid, members in grouped_edits.items():
        expected_sets = {member.expected_contexts for member in members}
        identities = {
            (member.change.context_uid, member.change.context_name)
            for member in members
        }
        if (
            len({member.action for member in members}) != 1
            or len({member.revision for member in members}) != 1
            or len(expected_sets) != 1
            or identities != set(next(iter(expected_sets)))
            or len(identities) != len(members)
        ):
            raise GroundWorkspaceHistoryError(
                f"Ground command unit '{uid}' is incomplete."
            )
        ordered = sorted(
            members,
            key=lambda member: member.change.context_name,
        )
        units[uid] = GroundWorkspaceCommandUnit(
            uid=uid,
            workspace_uid=workspace.uid,
            workspace_name=workspace.name,
            action=members[0].action,
            revision=members[0].revision,
            timestamp=max(member.timestamp for member in members),
            changes=tuple(member.change for member in ordered),
        )

    grouped_undos: dict[str, list[_UndoPart]] = {}
    for part in undo_parts:
        grouped_undos.setdefault(part.receipt_uid, []).append(part)
    undo_events: list[tuple[str, str, str]] = []
    for receipt_uid, members in grouped_undos.items():
        expected_sets = {member.expected_contexts for member in members}
        actual = {(member.context_uid, member.context_name) for member in members}
        sources = {member.source_unit_uid for member in members}
        if (
            len(expected_sets) != 1
            or len(sources) != 1
            or actual != set(next(iter(expected_sets)))
            or len(actual) != len(members)
        ):
            raise GroundWorkspaceHistoryError(
                f"Ground Undo receipt '{receipt_uid}' is incomplete."
            )
        source_uid = next(iter(sources))
        if source_uid not in units:
            raise GroundWorkspaceHistoryError(
                "Ground Undo receipt lost its source command."
            )
        undo_events.append(
            (max(member.timestamp for member in members), receipt_uid, source_uid)
        )

    events: list[tuple[str, int, str, str]] = [
        (unit.timestamp, 0, unit.uid, unit.uid) for unit in units.values()
    ]
    events.extend(
        (timestamp, 1, receipt_uid, source_uid)
        for timestamp, receipt_uid, source_uid in undo_events
    )
    events.sort()
    stack: list[GroundWorkspaceCommandUnit] = []
    for _, kind, event_uid, source_uid in events:
        if kind == 0:
            stack.append(units[source_uid])
            continue
        if not stack or stack[-1].uid != source_uid:
            raise GroundWorkspaceHistoryError(
                f"Ground Undo receipt '{event_uid}' is not LIFO."
            )
        stack.pop()
    return GroundWorkspaceCommandStack(undo=tuple(stack))


def undo_ground_workspace_command(
    store: MemoryStore,
    workspace_name: str,
) -> GroundWorkspaceUndoResult:
    """Undo the latest command inside one Ground root and retain a receipt."""

    workspace = load_ground_workspace(store, workspace_name)
    stack = build_ground_workspace_command_stack(store, workspace_name)
    if not stack.undo:
        raise GroundWorkspaceHistoryError(
            "There is no Ground-local command to undo."
        )
    source = stack.undo[-1]
    current_by_name = {
        context.name: context for context in workspace.all_contexts
    }
    root_change = next(
        (
            change
            for change in source.changes
            if change.context_name == workspace.name
        ),
        None,
    )
    if root_change is None:
        raise GroundWorkspaceHistoryError(
            "Ground command does not include its workspace root."
        )

    targets: list[Context] = []
    for change in source.changes:
        current = current_by_name.get(change.context_name)
        if current is None or current.uid != change.context_uid:
            raise ConcurrentContextUpdateError(
                "A Ground command Context no longer has its recorded identity."
            )
        if change.context_name == workspace.name:
            continue
        if context_record_digest(current) != context_record_digest(change.after):
            raise ConcurrentContextUpdateError(
                f"Ground Context '{change.context_name}' changed after the "
                "command selected for Undo."
            )
        restored = Context.from_dict(change.before)
        restored._store_digest = context_record_digest(current)
        targets.append(restored)

    # Revision is causal history, not a content checksum.  Undo restores lane
    # state but advances the root manifest so prior semantic receipts become
    # visibly stale instead of making the workspace appear to travel backward.
    revised = workspace.advance_revision()
    targets.insert(0, revised.root)
    receipt_uid = str(uuid.uuid4())
    membership = [
        {"uid": context.uid, "name": context.name}
        for context in targets
    ]
    metadata: dict[str, Any] = {
        "version": 1,
        "kind": "undo",
        "workspace_uid": workspace.uid,
        "workspace_name": workspace.name,
        "command_uid": receipt_uid,
        "source_command_uid": source.uid,
        "action": "undo",
        "revision": revised.manifest.revision,
    }
    entries = []
    for context in targets:
        expected_digest = getattr(context, "_store_digest", None)
        if not isinstance(expected_digest, str):
            raise GroundWorkspaceError(
                "Ground Undo is missing its Context CAS base."
            )
        entries.append(
            (
                context,
                AutoCheckpoint(
                    command="ground-undo",
                    args={
                        _GROUND_COMMAND_KEY: metadata,
                        "command_contexts": membership,
                    },
                    description=(
                        f"Undid Ground command '{source.action}' "
                        f"[{source.uid[:8]}] in '{workspace.name}'."
                    ),
                ),
                expected_digest,
            )
        )
    checkpoints = store.save_context_command_batch(entries)
    return GroundWorkspaceUndoResult(
        source_unit=source,
        receipt_uid=receipt_uid,
        revision=revised.manifest.revision,
        checkpoints=checkpoints,
    )


__all__ = [
    "GroundWorkspaceCommandStack",
    "GroundWorkspaceCommandUnit",
    "GroundWorkspaceContextChange",
    "GroundWorkspaceHistoryError",
    "GroundWorkspaceUndoResult",
    "build_ground_workspace_command_stack",
    "undo_ground_workspace_command",
]
