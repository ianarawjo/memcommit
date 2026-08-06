"""Action- and impact-oriented receipts for Context restoration commands."""
from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import typer

from memcommit.command_history import CommandRestoreResult, ContextCommandUnit
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


def _change_item_kind(change: _ItemChange) -> str:
    before_kind = _item_kind(change.before)
    after_kind = _item_kind(change.after)
    if before_kind == after_kind or change.after is None:
        return before_kind
    if change.before is None:
        return after_kind
    return "direct item"


def _impact_summary(changes: list[_ItemChange], reordered: bool) -> str:
    counts: dict[tuple[str, str], int] = {}
    for change in changes:
        item_kind = _change_item_kind(change)
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


def _command_arg(value: object) -> str:
    """Return one display-safe shell argument without introducing new lines."""

    return shlex.quote(display_escape_text(str(value)))


def _sole_context(unit: ContextCommandUnit) -> str | None:
    names = {change.context_name for change in unit.changes}
    return next(iter(names)) if len(names) == 1 else None


def _operand_context(
    args: Mapping[str, object], fallback: str | None
) -> str | None:
    """Prefer the retained public Grant operand over its authority owner."""

    grant = args.get("authority_grant")
    if isinstance(grant, Mapping) and isinstance(
        grant.get("public_context"), str
    ):
        return grant["public_context"]
    return fallback


def _with_context(command: str, context_name: str | None) -> str:
    if context_name is None:
        return command
    return f"{command} --context {_command_arg(context_name)}"


def _meld_command(args: Mapping[str, object]) -> str | None:
    left = args.get("left")
    right = args.get("right")
    target = args.get("to")
    if all(isinstance(value, str) for value in (left, right, target)):
        return (
            f"mem meld {_command_arg(left)} {_command_arg(right)} "
            f"--to {_command_arg(target)}"
        )

    record = args.get("meld")
    if not isinstance(record, Mapping):
        return None
    sources = record.get("sources")
    baseline = record.get("target_baseline")
    if not isinstance(sources, list) or not isinstance(baseline, Mapping):
        return None
    source_names = [
        item.get("context_name")
        for item in sources
        if isinstance(item, Mapping)
        and isinstance(item.get("context_name"), str)
    ]
    target_name = baseline.get("context_name")
    if not isinstance(target_name, str):
        return None
    if record.get("mode") == "DIRECTIONAL" and source_names:
        incoming = next(
            (
                item.get("context_name")
                for item in sources
                if isinstance(item, Mapping)
                and item.get("role") == "INCOMING"
                and isinstance(item.get("context_name"), str)
            ),
            source_names[0],
        )
        return (
            f"mem meld {_command_arg(incoming)} "
            f"--into {_command_arg(target_name)} --accept"
        )
    if len(source_names) >= 2:
        return (
            f"mem meld {_command_arg(source_names[0])} "
            f"{_command_arg(source_names[1])} "
            f"--to {_command_arg(target_name)} --accept"
        )
    return None


def _sever_command(args: Mapping[str, object]) -> str | None:
    record = args.get("sever")
    if not isinstance(record, Mapping):
        return None
    source = record.get("source")
    criteria = record.get("criteria")
    output = record.get("output")
    if not all(isinstance(value, str) for value in (source, criteria, output)):
        return None
    source_scope = (
        "--source-descendants"
        if record.get("source_scope") == "INCLUDE_DESCENDANTS"
        else "--source-only"
    )
    criteria_scope = (
        "--criteria-descendants"
        if record.get("criteria_scope") == "INCLUDE_DESCENDANTS"
        else "--criteria-only"
    )
    return (
        f"mem sever --source {_command_arg(source)} "
        f"--criteria {_command_arg(criteria)} --save-as {_command_arg(output)} "
        f"{source_scope} {criteria_scope} --accept"
    )


def _translate_command(args: Mapping[str, object]) -> str | None:
    language = args.get("target_language")
    source = args.get("source_context")
    scope = args.get("scope")
    if not isinstance(language, str) or not isinstance(source, Mapping):
        return None
    source_name = source.get("name")
    if not isinstance(source_name, str):
        return None
    selector = None
    if isinstance(scope, Mapping) and scope.get("kind") == "memory":
        selector = scope.get("memory_uid")
        if not isinstance(selector, str):
            return None
    command = "mem translate"
    if selector is not None:
        command += f" {_command_arg(selector)}"
    command += f" --to {_command_arg(language)}"
    destination = args.get("destination_context")
    if isinstance(destination, Mapping) and isinstance(destination.get("name"), str):
        command += f" --save-as {_command_arg(destination['name'])}"
    else:
        command += " --in-place"
    return command


def _restored_command(unit: ContextCommandUnit) -> str:
    """Render a canonical effective command from retained checkpoint args."""

    context_name = _sole_context(unit)
    args = unit.checkpoint_args[0] if unit.checkpoint_args else {}
    operand_context = _operand_context(args, context_name)
    if unit.command == "add":
        if isinstance(args.get("content"), str):
            return _with_context(
                "mem add <CONTENT>", operand_context
            )
        if isinstance(args.get("input"), str):
            return _with_context(
                f"mem add --input {_command_arg(args['input'])}", operand_context
            )
        if args.get("mode") == "paste":
            return _with_context("mem add --paste", operand_context)
    if unit.command == "edit":
        if isinstance(args.get("input"), str):
            return _with_context(
                f"mem edit --input {_command_arg(args['input'])}",
                operand_context,
            )
        if isinstance(args.get("uid"), str) and isinstance(
            args.get("content"), str
        ):
            return _with_context(
                f"mem edit {_command_arg(args['uid'])} "
                "<CONTENT>",
                operand_context,
            )
    if unit.command == "remove" and isinstance(args.get("uid"), str):
        return _with_context(
            f"mem remove {_command_arg(args['uid'])}", operand_context
        )
    if unit.command == "chunk" and isinstance(args.get("uid"), str):
        command = f"mem chunk {_command_arg(args['uid'])}"
        if isinstance(args.get("method"), str):
            command += f" --method {_command_arg(args['method'])}"
        return command
    if unit.command == "clear":
        target = args.get("context") or context_name
        if isinstance(target, str):
            return f"mem clear {_command_arg(target)} --force"
    if unit.command == "embed" and isinstance(args.get("child"), str) and isinstance(
        args.get("into"), str
    ):
        return (
            f"mem embed {_command_arg(args['child'])} "
            f"--into {_command_arg(args['into'])}"
        )
    if unit.command == "reference" and all(
        isinstance(args.get(key), str)
        for key in ("memory_uid", "source", "into")
    ):
        return (
            f"mem reference {_command_arg(args['memory_uid'])} "
            f"--from {_command_arg(args['source'])} "
            f"--into {_command_arg(args['into'])}"
        )
    if unit.command == "merge" and isinstance(args.get("source"), str):
        return f"mem merge {_command_arg(args['source'])}"
    if unit.command == "forget" and isinstance(args.get("query"), str):
        return "mem forget <INSTRUCTION>"
    if unit.command == "integrate" and isinstance(args.get("info"), str):
        return "mem integrate <INFO>"
    if unit.command == "meld":
        command = _meld_command(args)
        if command is not None:
            return command
    if unit.command == "sever":
        command = _sever_command(args)
        if command is not None:
            return command
    if unit.command == "translate":
        command = _translate_command(args)
        if command is not None:
            return command
    if unit.command == "revert" and isinstance(args.get("target_uid"), str):
        return f"mem revert {_command_arg(args['target_uid'])}"
    if unit.command == "atomize":
        if context_name is not None:
            if unit.changes and unit.changes[0].before is None:
                return f"mem atomize --save-as {_command_arg(context_name)}"
            return f"mem atomize --save --context {_command_arg(context_name)}"
    if unit.command == "atomize-grounding" and context_name is not None:
        return (
            "mem atomize --accept-grounding --context "
            + _command_arg(context_name)
        )
    if unit.command == "dev query-source install" and all(
        isinstance(args.get(key), str) for key in ("name", "into")
    ):
        command = (
            f"mem dev query-source install {_command_arg(args['name'])} "
        )
        source_file = args.get("source_file")
        if isinstance(source_file, str):
            command += f"--from {_command_arg(source_file)} "
        # Legacy checkpoints omit the concealed source path. Keep their exact
        # retained operands and do not fabricate a --from value.
        return command + f"--into {_command_arg(args['into'])}"
    if unit.command != "update":
        return _action_name(unit.command, fallback="recorded Context command")

    sources = {
        args.get("source_context_name")
        for args in unit.checkpoint_args
        if isinstance(args.get("source_context_name"), str)
    }
    targets = {
        args.get("target_context_name")
        for args in unit.checkpoint_args
        if isinstance(args.get("target_context_name"), str)
    }
    if not targets and len(unit.changes) == 1:
        targets = {unit.changes[0].context_name}
    if len(sources) == 1 and len(targets) == 1:
        source = _command_arg(next(iter(sources)))
        target = _command_arg(next(iter(targets)))
        return f"mem update --from {source} --to {target}"
    return "mem update"


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


def _compact_restore_effect(result: CommandRestoreResult) -> str:
    """Summarize one restoration without repeating restored Memory content."""

    changes: list[_ItemChange] = []
    reordered_contexts = 0
    for context_change in result.unit.changes:
        before_snapshot = (
            context_change.after
            if result.direction == "undo"
            else context_change.before
        )
        after_snapshot = (
            context_change.before
            if result.direction == "undo"
            else context_change.after
        )
        context_changes, reordered = _changes(before_snapshot, after_snapshot)
        changes.extend(context_changes)
        reordered_contexts += int(reordered)

    memory_changes = [
        change
        for change in changes
        if _change_item_kind(change) == "Memory"
    ]
    parts = [f"Affected Memories: {len(memory_changes)}"]
    markers = {"added": "+", "edited": "~", "removed": "-"}
    for kind in ("added", "edited", "removed"):
        count = sum(change.kind == kind for change in memory_changes)
        if count:
            parts.append(f"{markers[kind]} {count} {kind}")

    other_changes = [change for change in changes if change not in memory_changes]
    if other_changes:
        parts.append("Other: " + _impact_summary(other_changes, False))
    if reordered_contexts:
        parts.append(
            f"~ order restored in {reordered_contexts} "
            f"{'Context' if reordered_contexts == 1 else 'Contexts'}"
        )
    return " · ".join(parts)


def render_command_restore_receipt(result: CommandRestoreResult) -> None:
    """Report one global Undo or Redo as a compact one-line receipt."""
    direction = result.direction
    past = "Undid" if direction == "undo" else "Redid"
    typer.echo(
        f"{past} command: "
        + _restored_command(result.unit)
        + f" · Affected Contexts: {len(result.unit.changes)}"
        + " · "
        + _compact_restore_effect(result)
    )


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
