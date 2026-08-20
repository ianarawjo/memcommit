"""Typed presentation projection for retained Context checkpoint history."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from memcommit.command_history import command_unit_uid


HistoryBadgeStyle = Literal[
    "report-neutral",
    "memory-object",
    "history-receipt",
    "history-source",
]

HistoryRowSegmentStyle = Literal[
    "semantic-action",
    "report-neutral",
    "memory-object",
    "history-receipt",
    "history-source",
]


def history_action_style(command: str) -> str:
    """Return the shared semantic TUI class without its ``class:`` prefix.

    Older History surfaces still accept this narrow string adapter.  Keeping
    it here avoids forcing the Trace row refactor to migrate Diff and Revert in
    the same change, while the color decision remains owned by the common
    semantic palette.
    """

    from memcommit.interfaces.tui.core.theme import semantic_action_style

    return semantic_action_style(command, fallback="class:report-neutral").removeprefix(
        "class:"
    )


@dataclass(frozen=True)
class HistoryDisplayBadge:
    """One explicitly named identity in a compact History row."""

    text: str
    style: HistoryBadgeStyle = "report-neutral"


@dataclass(frozen=True)
class HistoryDisplayDetail:
    """One exact field shown when a compact History row is focused."""

    label: str
    value: str
    style: HistoryBadgeStyle = "report-neutral"


@dataclass(frozen=True)
class HistoryDisplayRow:
    """One retained checkpoint with typed identities and ownership role."""

    command: str
    timestamp: str
    checkpoint_uid: str
    command_identity: str | None
    summary: str
    badges: tuple[HistoryDisplayBadge, ...]
    details: tuple[HistoryDisplayDetail, ...]
    inherited_from: str | None = None
    is_creation: bool = False

    @property
    def section_label(self) -> str:
        return (
            f"INHERITED HISTORY · source {self.inherited_from}"
            if self.inherited_from is not None
            else "DIRECT COMMANDS"
        )


@dataclass(frozen=True)
class HistoryRowSegment:
    """One adapter-neutral segment of the shared compact History row."""

    text: str
    style: HistoryRowSegmentStyle = "report-neutral"
    action: str | None = None


def history_display_row_segments(
    row: HistoryDisplayRow,
    *,
    action: str | None = None,
) -> tuple[HistoryRowSegment, ...]:
    """Project the Log row grammar once for static and formatted adapters."""

    command = row.command if action is None else action
    segments: list[HistoryRowSegment] = [
        HistoryRowSegment(f"[{command}]", "semantic-action", action=command)
    ]
    for badge in row.badges:
        segments.extend(
            (
                HistoryRowSegment(" "),
                HistoryRowSegment(f"[{badge.text}]", badge.style),
            )
        )
    segments.extend(
        (
            HistoryRowSegment("  "),
            HistoryRowSegment(row.timestamp),
        )
    )
    if row.summary:
        segments.extend(
            (
                HistoryRowSegment(" · "),
                HistoryRowSegment(row.summary),
            )
        )
    return tuple(segments)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _one_line(value: object, *, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return " ".join(value.split())


def checkpoint_command_identity(checkpoint: Mapping[str, object]) -> str | None:
    """Return the shared command or restoration identity for one checkpoint."""

    command = checkpoint.get("command")
    if command == "init":
        return None
    uid = checkpoint.get("uid")
    if not isinstance(uid, str) or not uid:
        return None
    args = _mapping(checkpoint.get("args"))
    if command in {"undo", "redo"}:
        restore = _mapping(args.get("command_restore"))
        receipt_uid = restore.get("receipt_uid")
        if isinstance(receipt_uid, str) and receipt_uid:
            return f"restore:{receipt_uid}"
    return command_unit_uid(
        checkpoint_uid=uid,
        command=command if isinstance(command, str) and command else "checkpoint",
        args=dict(args),
    )


def checkpoint_inherited_from(
    checkpoint: Mapping[str, object],
    *,
    context_name: str,
    context_uid: str,
) -> str | None:
    """Name an inherited checkpoint owner; missing legacy headers stay direct."""

    snapshot = _mapping(checkpoint.get("snapshot"))
    snapshot_name = snapshot.get("name")
    snapshot_uid = snapshot.get("uid")
    if not isinstance(snapshot_name, str) or not isinstance(snapshot_uid, str):
        return None
    if snapshot_name == context_name and snapshot_uid == context_uid:
        return None
    # Branch intentionally preserves the Source checkpoint identity. Keeping
    # that lineage must not make the copied command look directly executed
    # against the independently editable target Context.
    return snapshot_name


def _command_identity_badge(identity: str | None) -> HistoryDisplayBadge | None:
    if (
        identity is None
        or identity.startswith("checkpoint:")
        or identity.startswith("restore:")
    ):
        # A restore receipt is already projected with the more precise RECEIPT
        # label below. Showing the same UID as COMMAND would recreate the exact
        # namespace ambiguity this presentation is intended to remove.
        return None
    parts = identity.split(":")
    if len(parts) < 2 or not parts[1]:
        return None
    return HistoryDisplayBadge(f"COMMAND {parts[1][:8]}", "history-source")


def _memory_badges_and_details(
    command: str,
    args: Mapping[str, Any],
) -> tuple[tuple[HistoryDisplayBadge, ...], tuple[HistoryDisplayDetail, ...]]:
    raw_uids: Sequence[object]
    if command == "add":
        value = args.get("memory_uids")
        raw_uids = value if isinstance(value, list) else ()
    elif command in {"edit", "remove"}:
        raw_uids = (args.get("uid"),)
    else:
        raw_uids = ()
    uids = tuple(value for value in raw_uids if isinstance(value, str) and value)
    if not uids:
        return (), ()
    badges = (
        (HistoryDisplayBadge(f"MEMORY {uids[0][:8]}", "memory-object"),)
        if len(uids) == 1
        else (HistoryDisplayBadge(f"MEMORIES {len(uids)}", "memory-object"),)
    )
    detail_label = "Memory" if len(uids) == 1 else "Memories"
    return badges, (
        HistoryDisplayDetail(detail_label, ", ".join(uids), "memory-object"),
    )


def _restore_badges_and_details(
    command: str,
    args: Mapping[str, Any],
) -> tuple[tuple[HistoryDisplayBadge, ...], tuple[HistoryDisplayDetail, ...]]:
    if command not in {"undo", "redo"}:
        return (), ()
    restore = _mapping(args.get("command_restore"))
    receipt_uid = restore.get("receipt_uid")
    source_command = restore.get("source_command")
    source_unit_uid = restore.get("source_unit_uid")
    badges: list[HistoryDisplayBadge] = []
    details: list[HistoryDisplayDetail] = []
    if isinstance(receipt_uid, str) and receipt_uid:
        badges.append(
            HistoryDisplayBadge(f"RECEIPT {receipt_uid[:8]}", "history-receipt")
        )
        details.append(
            HistoryDisplayDetail("Receipt", receipt_uid, "history-receipt")
        )
    if isinstance(source_unit_uid, str) and source_unit_uid:
        source_short = source_unit_uid.split(":", 1)[-1][:8]
        source_label = (
            f"SOURCE {source_command} {source_short}"
            if isinstance(source_command, str) and source_command
            else f"SOURCE {source_short}"
        )
        badges.append(HistoryDisplayBadge(source_label, "history-source"))
        if isinstance(source_command, str) and source_command:
            details.append(HistoryDisplayDetail("Source command", source_command))
        details.append(
            HistoryDisplayDetail(
                "Source command unit",
                source_unit_uid,
                "history-source",
            )
        )
    return tuple(badges), tuple(details)


def _placement_badges_and_details(
    command: str,
    args: Mapping[str, Any],
) -> tuple[tuple[HistoryDisplayBadge, ...], tuple[HistoryDisplayDetail, ...]]:
    if command != "embed":
        return (), ()
    badges: list[HistoryDisplayBadge] = []
    details: list[HistoryDisplayDetail] = []
    for key, label in (("after_uid", "AFTER MEMORY"), ("before_uid", "BEFORE MEMORY")):
        uid = args.get(key)
        if isinstance(uid, str) and uid:
            badges.append(HistoryDisplayBadge(f"{label} {uid[:8]}", "memory-object"))
            details.append(HistoryDisplayDetail(label.title(), uid, "memory-object"))
    child = args.get("child")
    if isinstance(child, str) and child:
        details.append(HistoryDisplayDetail("Child Context", child))
    into = args.get("into")
    if isinstance(into, str) and into:
        details.append(HistoryDisplayDetail("Into Context", into))
    return tuple(badges), tuple(details)


def _summary(
    command: str,
    checkpoint: Mapping[str, object],
    args: Mapping[str, Any],
) -> str:
    if command == "init":
        snapshot = _mapping(checkpoint.get("snapshot"))
        name = snapshot.get("name") or args.get("name") or "unknown"
        return f"baseline for CONTEXT {name} · not counted as a command"
    if command == "add":
        content = _one_line(args.get("content"))
        if content:
            return f'created "{content}"'
    if command == "edit":
        return "content changed · Memory identity preserved"
    if command == "remove":
        description = _one_line(checkpoint.get("description"))
        marker = "]: "
        if marker in description:
            return "removed " + description.split(marker, 1)[1]
        return "removed one direct Memory"
    if command == "embed":
        child = args.get("child")
        into = args.get("into")
        if isinstance(child, str) and isinstance(into, str):
            return f"child {child} · into {into}"
    if command in {"undo", "redo"}:
        restore = _mapping(args.get("command_restore"))
        source = restore.get("source_command")
        if isinstance(source, str) and source:
            effect = "restored" if command == "undo" else "reapplied"
            return f"{effect} mem {source}"
    return _one_line(
        checkpoint.get("description") or checkpoint.get("message"),
        fallback="(no description)",
    )


def project_history_display_rows(
    checkpoints: Sequence[Mapping[str, object]],
    *,
    context_name: str,
    context_uid: str,
    deduplicate_commands: bool = True,
) -> tuple[HistoryDisplayRow, ...]:
    """Project direct commands first, followed by explicitly inherited lineage."""

    direct: list[HistoryDisplayRow] = []
    inherited: list[HistoryDisplayRow] = []
    seen: set[tuple[str | None, str]] = set()
    for checkpoint in checkpoints:
        checkpoint_uid = checkpoint.get("uid")
        if not isinstance(checkpoint_uid, str) or not checkpoint_uid:
            continue
        raw_command = checkpoint.get("command")
        command = (
            raw_command
            if isinstance(raw_command, str) and raw_command
            else "checkpoint"
        )
        identity = checkpoint_command_identity(checkpoint)
        inherited_from = checkpoint_inherited_from(
            checkpoint,
            context_name=context_name,
            context_uid=context_uid,
        )
        if command != "init" and identity is not None and deduplicate_commands:
            seen_key = (inherited_from, identity)
            if seen_key in seen:
                continue
            seen.add(seen_key)
        args = _mapping(checkpoint.get("args"))
        badges: list[HistoryDisplayBadge] = [
            HistoryDisplayBadge(f"CHECKPOINT {checkpoint_uid[:8]}")
        ]
        details: list[HistoryDisplayDetail] = [
            HistoryDisplayDetail("Checkpoint", checkpoint_uid),
            HistoryDisplayDetail(
                "History role",
                (
                    f"inherited from {inherited_from}"
                    if inherited_from is not None
                    else f"direct · {context_name}"
                ),
            ),
        ]
        command_badge = _command_identity_badge(identity)
        if command_badge is not None:
            badges.append(command_badge)
            details.append(
                HistoryDisplayDetail(
                    "Command unit",
                    identity or "",
                    "history-source",
                )
            )
        for projected_badges, projected_details in (
            _memory_badges_and_details(command, args),
            _restore_badges_and_details(command, args),
            _placement_badges_and_details(command, args),
        ):
            badges.extend(projected_badges)
            details.extend(projected_details)
        if command == "init":
            snapshot = _mapping(checkpoint.get("snapshot"))
            snapshot_uid = snapshot.get("uid")
            if isinstance(snapshot_uid, str) and snapshot_uid:
                badges.append(
                    HistoryDisplayBadge(f"CONTEXT {snapshot_uid[:8]}")
                )
                details.append(HistoryDisplayDetail("Context", snapshot_uid))
        row = HistoryDisplayRow(
            command="created" if command == "init" else command,
            timestamp=_one_line(checkpoint.get("timestamp"))[:16].replace("T", " "),
            checkpoint_uid=checkpoint_uid,
            command_identity=identity,
            summary=_summary(command, checkpoint, args),
            badges=tuple(badges),
            details=tuple(details),
            inherited_from=inherited_from,
            is_creation=command == "init",
        )
        (inherited if inherited_from is not None else direct).append(row)
    return (*direct, *inherited)
