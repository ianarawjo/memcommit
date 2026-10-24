"""Action- and impact-oriented receipts for Context restoration commands."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import typer

from memcommit.application.capabilities.command_recovery import (
    CommandRestoreResult,
    ContextCommandUnit,
)
from memcommit.core.uid_prefixes import (
    extend_uid_prefixes_until_unique,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    memory_object_color_rgb,
    semantic_action_role,
    semantic_color_rgb,
)
from memcommit.models.checkpoint import Checkpoint
from memcommit.source_projection.console import (
    styled_source_object_label,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    source_object_label,
)


_MAX_ITEM_LINES = 12
_MAX_CONTENT_CODEPOINTS = 240
_MAX_DESCRIPTION_CODEPOINTS = 240

_MEMORY_KIND = source_object_label(SourceForm.MEMORY, title=True)
_CHANGE_COLOR_ROLES = {
    "added": SemanticColorRole.ADD,
    "edited": SemanticColorRole.EDIT,
    "removed": SemanticColorRole.REMOVE,
}


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
        [uid for uid in raw_order if isinstance(uid, str) and uid in items]
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
            changes.append(_ItemChange("edited", uid, before[uid], after[uid]))
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
    return '"' + escaped.replace('"', r"\"") + '"'


def _item_kind(item):
    return (
        _MEMORY_KIND
        if item is not None and item.get("type") == "memory"
        else "direct item"
    )


def _styled_item_identity_label(item):
    return (
        styled_source_object_label(SourceForm.MEMORY)
        if _item_kind(item) == _MEMORY_KIND
        else "direct item"
    )


def _item_description(item):
    return _quoted_content(item.get("content", ""))


def _styled_item_description(
    item: Mapping[str, Any],
    *,
    effect_role: SemanticColorRole | None = None,
) -> str:
    description = _item_description(
        item,
    )
    if effect_role is not None:
        return typer.style(description, fg=semantic_color_rgb(effect_role))
    if item.get("type") == "memory":
        return typer.style(description, fg=memory_object_color_rgb())
    return description


def _styled_change_line(
    change: _ItemChange,
) -> str:
    """Compose Revert's effect, object, and before/after color axes."""

    marker = typer.style(
        {"added": "+", "edited": "~", "removed": "-"}[change.kind],
        fg=semantic_color_rgb(_CHANGE_COLOR_ROLES[change.kind]),
        bold=True,
    )
    uid = _short(change.uid, limit=64)[:8]
    if change.kind == "removed" and change.before is not None:
        return (
            f"  {marker} [{_styled_item_identity_label(change.before)} {uid}] "
            + _styled_item_description(
                change.before,
                effect_role=SemanticColorRole.REMOVE,
            )
        )
    if change.kind == "added" and change.after is not None:
        return (
            f"  {marker} [{_styled_item_identity_label(change.after)} {uid}] "
            + _styled_item_description(
                change.after,
            )
        )
    assert change.before is not None and change.after is not None
    before_kind = _item_kind(change.before)
    after_kind = _item_kind(change.after)
    label = (
        _styled_item_identity_label(change.after)
        if before_kind == after_kind
        else "direct item"
    )
    return (
        f"  {marker} [{label} {uid}] "
        + _styled_item_description(
            change.before,
            effect_role=SemanticColorRole.REMOVE,
        )
        + " → "
        + _styled_item_description(
            change.after,
            effect_role=SemanticColorRole.EDIT,
        )
    )


def _styled_action_name(command: str | None, *, fallback: str) -> str:
    action = _action_name(command, fallback=fallback)
    role = semantic_action_role(action)
    if role is None and command is None and action == fallback:
        role = SemanticColorRole.HISTORY
    if role is None:
        return action
    return typer.style(
        action,
        fg=semantic_color_rgb(role),
        bold=True,
    )


def _change_item_kind(change: _ItemChange) -> str:
    before_kind = _item_kind(change.before)
    after_kind = _item_kind(change.after)
    if before_kind == after_kind or change.after is None:
        return before_kind
    if change.before is None:
        return after_kind
    return "direct item"


def _impact_summary(changes, reordered):
    counts = {
        kind: sum(change.kind == kind for change in changes)
        for kind in ("added", "edited", "removed")
    }
    parts = [
        f"{count} {'Memory' if count == 1 else 'Memories'} {kind}"
        for kind, count in counts.items()
        if count
    ]
    if reordered:
        parts.append("Memory order restored")
    return ", ".join(parts) or "no content changes"


def _action_name(command: str | None, *, fallback: str) -> str:
    if not isinstance(command, str) or not command.strip():
        return fallback
    name = command.strip()
    if name == "meld":
        return "mem merge"
    if name == "merge":
        return "mem merge --literal"
    return "mem " + _short(name, limit=80)


def _command_arg(value: object) -> str:
    """Return one display-safe shell argument without introducing new lines."""

    return shlex.quote(display_escape_text(str(value)))


def _sole_context(unit: ContextCommandUnit) -> str | None:
    names = {change.context_name for change in unit.changes}
    return next(iter(names)) if len(names) == 1 else None


def _with_context(command: str, context_name: str | None) -> str:
    if context_name is None:
        return command
    return f"{command} --context {_command_arg(context_name)}"


def _compact_direct_item_selector(
    unit: ContextCommandUnit,
    selector: str,
) -> str:
    """Project a retained selector against its frozen single-Context scope.

    Direct Memory mutation receipts can stay compact without consulting live
    state: their command unit retains the relevant pre/post images. Multi-owner
    commands and legacy records without that exact catalog keep the persisted
    operand in full because a guessed eight-character scope would be unsafe.
    """

    if len(unit.changes) != 1:
        return selector
    frozen_uids: list[str] = []
    change = unit.changes[0]
    for snapshot in (change.before, change.after):
        items, _order = _snapshot_items(snapshot)
        frozen_uids.extend(items)
    catalog = tuple(dict.fromkeys(frozen_uids))
    matches = [uid for uid in catalog if uid.startswith(selector)]
    if len(matches) != 1:
        return selector
    return extend_uid_prefixes_until_unique(catalog)[matches[0]]


def _meld_command(args: Mapping[str, object]) -> str | None:
    left = args.get("left")
    right = args.get("right")
    target = args.get("to")
    if all(isinstance(value, str) for value in (left, right, target)):
        return (
            f"mem merge {_command_arg(left)} {_command_arg(right)} "
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
        if isinstance(item, Mapping) and isinstance(item.get("context_name"), str)
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
            f"mem merge {_command_arg(incoming)} "
            f"--into {_command_arg(target_name)} --accept"
        )
    if len(source_names) >= 2:
        return (
            f"mem merge {_command_arg(source_names[0])} "
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
        else "--source-root-only"
    )
    criteria_scope = (
        "--criteria-descendants"
        if record.get("criteria_scope") == "INCLUDE_DESCENDANTS"
        else "--criteria-root-only"
    )
    command = f"mem sever {_command_arg(source)} {_command_arg(criteria)}"
    if output != source:
        command += f" {_command_arg(output)}"
    return f"{command} {source_scope} {criteria_scope} --accept"


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


def _branch_command(args: Mapping[str, object]) -> str | None:
    record = args.get("branch_tree")
    if not isinstance(record, Mapping):
        return None
    target = record.get("target_root")
    source = record.get("source_root")
    if not isinstance(target, str) or not isinstance(source, str):
        return None
    command = f"mem branch {_command_arg(target)}"
    command += f" --from {_command_arg(source)}"
    command += (
        " --recursive" if record.get("include_descendants") is True else " --direct"
    )
    return command


def _restored_command(unit: ContextCommandUnit) -> str:
    """Render a canonical effective command from retained checkpoint args."""

    context_name = _sole_context(unit)
    args = unit.checkpoint_command_details[0] if unit.checkpoint_command_details else {}
    operand_context = context_name
    if unit.command == "add":
        if isinstance(args.get("content"), str):
            return _with_context("mem add <CONTENT>", operand_context)
        # Historical checkpoints retain the exact retired source spelling so
        # restoration reports do not rewrite how the original mutation arose.
        if isinstance(args.get("input"), str):
            return _with_context(
                f"mem add --input {_command_arg(args['input'])}", operand_context
            )
        if args.get("mode") == "paste":
            return _with_context("mem add --paste", operand_context)
        contents = args.get("contents")
        if (
            isinstance(contents, list)
            and contents
            and all(isinstance(content, str) for content in contents)
        ):
            return "mem add <MEMORY>..."
    if unit.command == "edit":
        if isinstance(args.get("input"), str):
            return _with_context(
                f"mem edit --input {_command_arg(args['input'])}",
                operand_context,
            )
        if isinstance(args.get("uid"), str) and isinstance(args.get("content"), str):
            selector = _compact_direct_item_selector(unit, args["uid"])
            return _with_context(
                f"mem edit {_command_arg(selector)} <CONTENT>",
                operand_context,
            )
    if unit.command == "remove" and isinstance(args.get("uid"), str):
        selector = _compact_direct_item_selector(unit, args["uid"])
        return _with_context(f"mem remove {_command_arg(selector)}", operand_context)
    if unit.command == "chunk" and isinstance(args.get("uid"), str):
        selector = _compact_direct_item_selector(unit, args["uid"])
        command = f"mem chunk {_command_arg(selector)}"
        if isinstance(args.get("method"), str):
            command += f" --method {_command_arg(args['method'])}"
        if isinstance(args.get("break_on"), str):
            command += f" --break-on {_command_arg(args['break_on'])}"
        for option in ("min_chars", "max_chars"):
            value = args.get(option)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                command += f" --{option.replace('_', '-')} {value}"
        target = args.get("context") or operand_context or context_name
        return _with_context(command, target if isinstance(target, str) else None)
    if unit.command == "chunk" and isinstance(args.get("splits"), list):
        command = "mem chunk"
        if isinstance(args.get("method"), str):
            command += f" --method {_command_arg(args['method'])}"
        if isinstance(args.get("break_on"), str):
            command += f" --break-on {_command_arg(args['break_on'])}"
        for option in ("min_chars", "max_chars"):
            value = args.get(option)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                command += f" --{option.replace('_', '-')} {value}"
        target = args.get("context") or operand_context or context_name
        return _with_context(command, target if isinstance(target, str) else None)
    if unit.command == "clear":
        tree = args.get("clear_tree")
        if (
            isinstance(tree, Mapping)
            and tree.get("include_descendants") is True
            and isinstance(tree.get("root"), str)
        ):
            return f"mem clear {_command_arg(tree['root'])} --recursive"
        target = args.get("context") or context_name
        if isinstance(target, str):
            return f"mem clear {_command_arg(target)}"
    if unit.command == "dedup":
        tree = args.get("dedup_tree")
        if (
            isinstance(tree, Mapping)
            and tree.get("include_descendants") is True
            and isinstance(tree.get("root"), str)
        ):
            return f"mem dedup {_command_arg(tree['root'])} --recursive"
    if unit.command == "dedun":
        tree = args.get("dedun_tree")
        if (
            isinstance(tree, Mapping)
            and tree.get("include_descendants") is True
            and isinstance(tree.get("root"), str)
        ):
            return f"mem dedun {_command_arg(tree['root'])} --recursive"
    if unit.command == "branch":
        command = _branch_command(args)
        if command is not None:
            return command
    if unit.command == "merge" and isinstance(args.get("source"), str):
        return f"mem merge --literal {_command_arg(args['source'])}"
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
        # Legacy Revert receipts predate the keep-all default, so a missing
        # policy still describes the old explicit discard behavior faithfully.
        policy = "--keep" if args.get("keep_history") is True else "--discard-newer"
        revert_unit = args.get("revert_unit")
        if isinstance(revert_unit, Mapping) and isinstance(
            revert_unit.get("checkpoint_unit_uid"), str
        ):
            return (
                "mem revert "
                f"{_command_arg(revert_unit['checkpoint_unit_uid'])} {policy}"
            )
        return f"mem revert {_command_arg(args['target_uid'])} {policy}"
    if unit.command == "atomize":
        if context_name is not None:
            if unit.changes and unit.changes[0].before is None:
                return f"mem atomize --save-as {_command_arg(context_name)}"
            return f"mem atomize {_command_arg(context_name)}"
    if unit.command != "update":
        return _action_name(unit.command, fallback="recorded Context command")

    sources = {
        args.get("source_context_name")
        for args in unit.checkpoint_command_details
        if isinstance(args.get("source_context_name"), str)
    }
    targets = {
        args.get("target_context_name")
        for args in unit.checkpoint_command_details
        if isinstance(args.get("target_context_name"), str)
    }
    if not targets and len(unit.changes) == 1:
        targets = {unit.changes[0].context_name}
    instruction_records = [
        args
        for args in unit.checkpoint_command_details
        if args.get("instruction_kind") in {"TEXT", "MEMORY"}
    ]
    if instruction_records and len(targets) == 1:
        instruction = instruction_records[0]
        target = _command_arg(next(iter(targets)))
        memory_uid = instruction.get("source_memory_uid")
        if (
            instruction["instruction_kind"] == "MEMORY"
            and isinstance(memory_uid, str)
            and len(sources) == 1
        ):
            source = _command_arg(f"{next(iter(sources))}:{memory_uid}")
            return f"mem update -m {source} --to {target}"
        text = instruction.get("instruction_text")
        if isinstance(text, str):
            return f"mem update {_command_arg(text)} --to {target}"
        return f"mem update (instruction retained in initiating Profile) --to {target}"
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
        "Affected Context: " + _short(context_name, limit=_MAX_CONTENT_CODEPOINTS)
    )
    typer.echo("Affected content: " + _impact_summary(changes, reordered))
    for change in changes[:_MAX_ITEM_LINES]:
        typer.echo(
            _styled_change_line(
                change,
            )
        )
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
            "Action detail: " + _short(description, limit=_MAX_DESCRIPTION_CODEPOINTS)
        )


def _compact_restore_effect(
    result: CommandRestoreResult,
) -> tuple[tuple[str, str | tuple[int, int, int] | None], ...]:
    """Summarize one restoration as semantic, independently styled parts."""

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
        change for change in changes if _change_item_kind(change) == _MEMORY_KIND
    ]
    parts: list[tuple[str, str | tuple[int, int, int] | None]] = [
        (f"Affected Memories: {len(memory_changes)}", None)
    ]
    markers = {"added": "+", "edited": "~", "removed": "-"}
    for kind in ("added", "edited", "removed"):
        count = sum(change.kind == kind for change in memory_changes)
        if count:
            parts.append(
                (
                    f"{markers[kind]} {count} {kind}",
                    semantic_color_rgb(_CHANGE_COLOR_ROLES[kind]),
                )
            )

    other_changes = [change for change in changes if change not in memory_changes]
    if other_changes:
        parts.append(("Other: " + _impact_summary(other_changes, False), None))
    if reordered_contexts:
        parts.append(
            (
                f"~ order restored in {reordered_contexts} "
                f"{'Context' if reordered_contexts == 1 else 'Contexts'}",
                semantic_color_rgb(SemanticColorRole.HISTORY),
            )
        )
    return tuple(parts)


def render_command_restore_receipt(result: CommandRestoreResult) -> None:
    """Report one global Undo or Redo as a compact one-line receipt."""
    direction = result.direction
    past = "Undid" if direction == "undo" else "Redid"
    direction_role = (
        SemanticColorRole.UNDO if direction == "undo" else SemanticColorRole.REDO
    )
    fragments = [
        typer.style(
            f"{past} command: ",
            fg=semantic_color_rgb(direction_role),
            bold=True,
        ),
        _restored_command(result.unit),
        f" · Affected Contexts: {len(result.unit.changes)}",
    ]
    for text, color in _compact_restore_effect(result):
        fragments.append(" · ")
        fragments.append(typer.style(text, fg=color) if color else text)
    typer.echo("".join(fragments))


def render_revert_receipt(
    *,
    context_name: str,
    before_snapshot: object,
    target: Checkpoint,
    recovery: Checkpoint,
) -> None:
    """Report Revert's Context impact and the action that made its target."""
    typer.secho(
        "Reverted Context: " + _short(context_name, limit=_MAX_CONTENT_CODEPOINTS),
        fg=semantic_color_rgb(SemanticColorRole.UNDO),
        bold=True,
    )
    typer.echo(
        "Restored state recorded by: "
        + _styled_action_name(target.command, fallback="manual checkpoint")
    )
    _render_action_detail(target.checkpoint_message)
    _render_impact(
        context_name=context_name,
        before_snapshot=before_snapshot,
        after_snapshot=target.snapshot,
    )
    target_ts = target.timestamp.strftime("%Y-%m-%d %H:%M")
    typer.echo(
        typer.style("Restored checkpoint: ", dim=True)
        + typer.style(
            f"[{target.uid[:8]}]",
            fg=semantic_color_rgb(SemanticColorRole.HISTORY),
            bold=True,
        )
        + typer.style(f" ({target_ts})", dim=True)
    )
    typer.echo(
        typer.style("Undo command: ", dim=True)
        + typer.style(
            "mem undo",
            fg=semantic_color_rgb(SemanticColorRole.UNDO),
            bold=True,
        )
    )
    typer.echo(
        # Recovery checkpoints carry the displaced log snapshot. Explicit
        # discard mode materializes that snapshot again; the keep-all default
        # would restore content without rebuilding removed active files.
        typer.style("Exact recovery checkpoint: ", dim=True)
        + typer.style(
            "mem revert",
            fg=semantic_color_rgb(SemanticColorRole.UNDO),
            bold=True,
        )
        + typer.style(f" {recovery.uid[:8]} --discard-newer", dim=True)
    )


def render_checkpoint_unit_revert_receipt(
    result,
) -> None:
    """Report one atomic recursive Checkpoint recovery unit."""

    typer.secho(
        f"Reverted checkpoint unit: [{result.unit.canonical_uid[:8]}] · "
        f"Affected Contexts: {len(result.members)}",
        fg=semantic_color_rgb(SemanticColorRole.UNDO),
        bold=True,
    )
    for index, member in enumerate(result.members):
        if index:
            typer.echo()
        typer.echo(
            "Context: " + _short(member.context_name, limit=_MAX_CONTENT_CODEPOINTS)
        )
        typer.echo(
            "Restored state recorded by: "
            + _styled_action_name(member.target.command, fallback="manual checkpoint")
        )
        _render_action_detail(member.target.checkpoint_message)
        _render_impact(
            context_name=member.context_name,
            before_snapshot=member.recovery.snapshot,
            after_snapshot=member.target.snapshot,
        )
        target_ts = member.target.timestamp.strftime("%Y-%m-%d %H:%M")
        typer.echo(
            typer.style("Restored checkpoint: ", dim=True)
            + typer.style(
                f"[{member.target.uid[:8]}]",
                fg=semantic_color_rgb(SemanticColorRole.HISTORY),
                bold=True,
            )
            + typer.style(f" ({target_ts})", dim=True)
        )
    typer.echo()
    typer.echo(
        typer.style("Undo complete unit: ", dim=True)
        + typer.style(
            "mem undo",
            fg=semantic_color_rgb(SemanticColorRole.UNDO),
            bold=True,
        )
    )
    typer.echo("Exact member recovery checkpoints:")
    for member in result.members:
        command = (
            f"mem revert {member.recovery.uid} --context "
            f"{_command_arg(member.context_name)} --discard-newer"
        )
        typer.echo("  " + command)
