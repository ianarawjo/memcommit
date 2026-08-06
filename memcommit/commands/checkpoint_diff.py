"""Exact, provider-free checkpoint transition presentation."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.history_picker import HistoryPickerItem
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.memory_diff import MemoryChange, memory_diff_lines


@dataclass(frozen=True)
class _CheckpointItemChange:
    uid: str
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None


def _snapshot_items(snapshot: object) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
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
    order.extend(uid for uid in items if uid not in order)
    return items, order


def _checkpoint_changes(
    before_snapshot: object,
    after_snapshot: object,
) -> tuple[tuple[_CheckpointItemChange, ...], bool]:
    before, before_order = _snapshot_items(before_snapshot)
    after, after_order = _snapshot_items(after_snapshot)
    changes: list[_CheckpointItemChange] = []
    for uid in before_order:
        if uid not in after:
            changes.append(_CheckpointItemChange(uid, before[uid], None))
        elif before[uid] != after[uid]:
            changes.append(_CheckpointItemChange(uid, before[uid], after[uid]))
    changes.extend(
        _CheckpointItemChange(uid, None, after[uid])
        for uid in after_order
        if uid not in before
    )
    common = set(before) & set(after)
    reordered = (
        [uid for uid in before_order if uid in common]
        != [uid for uid in after_order if uid in common]
    )
    return tuple(changes), reordered


def _before_snapshots(
    checkpoints: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    ordered = sorted(
        checkpoints,
        key=lambda value: (str(value.get("timestamp", "")), str(value.get("uid", ""))),
    )
    previous: object = {"memories": {}, "order": []}
    result: dict[str, object] = {}
    for checkpoint in ordered:
        uid = checkpoint.get("uid")
        if not isinstance(uid, str):
            continue
        command_before = checkpoint.get("command_before")
        result[uid] = command_before if isinstance(command_before, Mapping) else previous
        previous = checkpoint.get("snapshot")
    return result


def _item_text(item: Mapping[str, Any] | None) -> str | None:
    if item is None:
        return None
    if item.get("type") == "memory":
        content = item.get("content")
        return content if isinstance(content, str) else ""
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checkpoint_diff_detail_renderer(
    checkpoints: Sequence[Mapping[str, Any]],
):
    """Return a rich History detail renderer for exact checkpoint changes."""
    records = {
        checkpoint["uid"]: checkpoint
        for checkpoint in checkpoints
        if isinstance(checkpoint.get("uid"), str)
    }
    before_by_uid = _before_snapshots(checkpoints)

    def render(entry: HistoryPickerItem) -> StyleAndTextTuples:
        checkpoint = records[entry.uid]
        changes, reordered = _checkpoint_changes(
            before_by_uid[entry.uid],
            checkpoint.get("snapshot"),
        )
        command = checkpoint.get("command")
        action = command if isinstance(command, str) and command else "checkpoint"
        fragments: StyleAndTextTuples = [
            ("class:report-label", " CHECKPOINT  "),
            ("class:report-neutral", display_escape_text(entry.uid) + "\n"),
            ("class:report-label", " ACTION      "),
            ("class:report-label", display_escape_text(action) + "\n"),
            ("class:report-label", " DESCRIPTION "),
            (
                "class:report-neutral",
                display_escape_text(entry.description or "(none)") + "\n\n",
            ),
        ]
        if not changes and not reordered:
            fragments.append(
                ("class:report-neutral", " (no direct Context changes)\n")
            )
            return fragments
        for index, change in enumerate(changes, start=1):
            before = _item_text(change.before)
            after = _item_text(change.after)
            treatment = "ADD" if before is None else "REMOVE" if after is None else "EDIT"
            fragments.append(
                (
                    "class:report-label",
                    f" {index}. {action.upper()} · {treatment} "
                    f"[{display_escape_text(change.uid[:8])}]\n",
                )
            )
            memory_change = MemoryChange(
                marker={"ADD": "+", "REMOVE": "−", "EDIT": "~"}[treatment],
                treatment=treatment,
                location=entry.uid,
                memory_uid=change.uid,
                before=before,
                after=after,
            )
            for line in memory_diff_lines(memory_change):
                style_key = {
                    "-": "remove",
                    "+": "add",
                    "=": "equal",
                    " ": "equal",
                }[line.marker]
                fragments.append(
                    (f"class:memory-diff.{style_key}", f" {line.marker} ")
                )
                fragments.extend(
                    (
                        f"class:memory-diff.{style_key}"
                        + (".changed" if span.changed else ""),
                        display_escape_text(span.text),
                    )
                    for span in line.spans
                )
                fragments.append(("", "\n"))
            fragments.append(("", "\n"))
        if reordered:
            fragments.append(
                ("class:report-neutral", " = Direct-item order changed.\n")
            )
        return fragments

    return render
