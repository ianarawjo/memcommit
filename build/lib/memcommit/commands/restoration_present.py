"""Action- and impact-oriented receipts for Context restoration commands."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import typer

from memcommit.command_history import CommandRestoreResult
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.context import Checkpoint


_MAX_ITEM_LINES = 12
_MAX_CONTENT_CODEPOINTS = 240
_MAX_DESCRIPTION_CODEPOINTS = 240


@dataclass(frozen=True)
class _ItemChange:
    """One direct-item change in restoration direction (before -> after)."""

    kind: str
    uid: str
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None


def _snapshot_items(
    snapshot: object,
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    if not isinstance(snapshot, Mapping):
        return {}, []
    raw_items = snapshot.get("memories")
    items = (
        {
            uid: item
            for uid, item in raw_items.items()
            if isinstance(uid, str) and isinstance(item, Mapping)
        }
        if isinstance(raw_items, Mapping)
        else {}
    )
    raw_order = snapshot.get("order")
    order = (
        [
            uid
            for uid in raw_order
            if isinstance(uid, str) and uid in items
        ]
        if isinstance(raw_order, list)
        else list(items)
    )
    for uid in items:
        if uid not in order:
            order.append(uid)
    return items, order


def _changes(
    before_snapshot: object,
    after_snapshot: object,
) -> tuple[list[_ItemChange], bool]:
    before, before_order = _snapshot_items(before_snapshot)
    after, after_order = _snapshot_items(after_snapshot)
    changes: list[_ItemChange] = []
    for uid in before_order:
        if uid not in after:
            changes.append(_ItemChange("removed", uid, before[uid], None))
        elif before[uid] != after[uid]:
            changes.append(
                _ItemChange("edited", uid, before[uid], after[uid])
            )
    for uid in after_order:
        if uid not in before:
            changes.append(_ItemChange("added", uid, None, after[uid]))

    # Insertions and removals shift numeric positions without reordering the
    # surviving items. Compare only their relative sequence so the receipt
    # does not report those mechanical shifts as another change.
    common = set(before) & set(after)
    before_common = [uid for uid in before_order if uid in common]
    after_common = [uid for uid in after_order if uid in common]
    return changes, before_common != after_common


def _short(value: object, *, limit: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return display_escape_text(text)


def _quoted_content(value: object) -> str:
    escaped = _short(value, limit=_MAX_CONTENT_CODEPOINTS)
    # display_escape_text escapes original backslashes first. Escaping quotes
    # here keeps the enclosing quotation marks unambiguous as well.
    return '"' + escaped.replace('"', r'\"') + '"'


def _item_kind(item: Mapping[str, Any] | None) -> str:
    raw = item.get("type") if item is not None else None
    return {
        "memory": "Memory",
        "memory_ref": "MemoryRef",
        "query_context_ref": "query-only Context",
        "context_ref": "embedded Context",
    }.get(raw, "direct item")


def _item_description(item: Mapping[str, Any]) -> str:
    kind = item.get("type")
    if kind == "memory":
        return _quoted_content(item.get("content", ""))
    if kind == "memory_ref":
        target_context = item.get("target_context")
        target_name = (
            target_context.get("name")
            if isinstance(target_context, Mapping)
            else None
        )
        target_uid = item.get("target_memory_uid")
        return (
            "to Context "
            + _quoted_content(target_name or "(unknown)")
            + (
                f" Memory [{_short(target_uid, limit=64)[:8]}]"
                if isinstance(target_uid, str) and target_uid
                else ""
            )
        )
    if kind in {"query_context_ref", "context_ref"}:
        return _quoted_content(item.get("name", "(unknown)"))
    return _quoted_content(item)


def _change_line(change: _ItemChange) -> str:
    before_kind = _item_kind(change.before)
    after_kind = _item_kind(change.after)
    uid = _short(change.uid, limit=64)[:8]
    if change.kind == "removed" and change.before is not None:
        return f"  - [{uid}] {before_kind}: {_item_description(change.before)}"
    if change.kind == "added" and change.after is not None:
        return f"  + [{uid}] {after_kind}: {_item_description(change.after)}"
    assert change.before is not None and change.after is not None
    label = before_kind if before_kind == after_kind else "direct item"
    return (
        f"  ~ [{uid}] {label}: {_item_description(change.before)}"
        f" → {_item_description(change.after)}"
    )


def _impact_summary(changes: list[_ItemChange], reordered: bool) -> str:
    counts: dict[tuple[str, str], int] = {}
    for change in changes:
        before_kind = _item_kind(change.before)
        after_kind = _item_kind(change.after)
        item_kind = (
            before_kind
            if before_kind == after_kind or change.after is None
            else after_kind if change.before is None else "direct item"
        )
        key = (item_kind, change.kind)
        counts[key] = counts.get(key, 0) + 1

    plural = {
        "Memory": "Memories",
        "MemoryRef": "MemoryRefs",
        "query-only Context": "query-only Contexts",
        "embedded Context": "embedded Contexts",
        "direct item": "direct items",
    }
    parts: list[str] = []
    for change_kind in ("added", "edited", "removed"):
        for item_kind in (
            "Memory",
            "MemoryRef",
            "query-only Context",
            "embedded Context",
            "direct item",
        ):
            count = counts.get((item_kind, change_kind), 0)
            if count:
                label = item_kind if count == 1 else plural[item_kind]
                parts.append(f"{count} {label} {change_kind}")
    if reordered:
        parts.append("direct-item order changed")
    return ", ".join(parts) if parts else "no direct Context changes"


def _action_name(command: str | None, *, fallback: str) -> str:
    if not isinstance(command, str) or not command.strip():
        return fallback
    return "mem " + _short(command.strip(), limit=80)


def _render_impact(
    *,
    context_name: str,
    before_snapshot: object,
    after_snapshot: object,
) -> None:
    changes, reordered = _changes(before_snapshot, after_snapshot)
    typer.echo(
        "Affected Context: "
        + _short(context_name, limit=_MAX_CONTENT_CODEPOINTS)
    )
    typer.echo(f"Affected content: {_impact_summary(changes, reordered)}")
    for change in changes[:_MAX_ITEM_LINES]:
        typer.echo(_change_line(change))
    omitted = len(changes) - _MAX_ITEM_LINES
    if omitted > 0:
        typer.echo(
            f"  ... {omitted} more affected direct "
            f"{'item' if omitted == 1 else 'items'} not shown"
        )
    if reordered:
        typer.echo("  ~ Direct-item order was restored.")


def _render_action_detail(description: str | None) -> None:
    if isinstance(description, str) and description:
        typer.echo(
            "Action detail: "
            + _short(description, limit=_MAX_DESCRIPTION_CODEPOINTS)
        )


def render_command_restore_receipt(result: CommandRestoreResult) -> None:
    """Report one global command-unit Undo or Redo and every affected Context."""
    direction = result.direction
    past = "Undid" if direction == "undo" else "Redid"
    inverse = "redo" if direction == "undo" else "undo"
    typer.secho(
        f"{past} command: "
        + _action_name(result.unit.command, fallback="recorded Context command"),
        fg=typer.colors.GREEN,
        bold=True,
    )
    _render_action_detail(result.unit.description)
    count = len(result.unit.changes)
    typer.echo(f"Affected Contexts: {count}")
    for change in result.unit.changes:
        before_snapshot = (
            change.after if direction == "undo" else change.before
        )
        after_snapshot = (
            change.before if direction == "undo" else change.after
        )
        _render_impact(
            context_name=change.context_name,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
    typer.secho(
        f"Restoration receipt: [{result.receipt_uid[:8]}]",
        dim=True,
    )
    typer.secho(f"{inverse.title()} command: mem {inverse}", dim=True)


def render_revert_receipt(
    *,
    context_name: str,
    before_snapshot: object,
    target: Checkpoint,
    recovery: Checkpoint,
) -> None:
    """Report Revert's Context impact and the action that made its target."""
    typer.secho(
        "Reverted Context: "
        + _short(context_name, limit=_MAX_CONTENT_CODEPOINTS),
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(
        "Restored state recorded by: "
        + _action_name(target.command, fallback="manual checkpoint")
    )
    _render_action_detail(target.description or target.message)
    _render_impact(
        context_name=context_name,
        before_snapshot=before_snapshot,
        after_snapshot=target.snapshot,
    )
    target_ts = target.timestamp.strftime("%Y-%m-%d %H:%M")
    typer.secho(
        f"Restored checkpoint: [{target.uid[:8]}] ({target_ts})",
        dim=True,
    )
    typer.secho(
        "Undo command: mem undo",
        dim=True,
    )
    typer.secho(
        f"Exact recovery checkpoint: mem revert {recovery.uid[:8]}",
        dim=True,
    )
