"""Exact, provider-free checkpoint transition presentation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.commands.history_picker import HistoryDetailView, HistoryPickerItem
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.core.theme import semantic_action_style
from memcommit.memory_diff import MemoryChange, memory_diff_lines


@dataclass(frozen=True)
class _CheckpointItemChange:
    uid: str
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None

    @property
    def treatment(self) -> str:
        if self.before is None:
            return "ADD"
        if self.after is None:
            return "REMOVE"
        if self.before != self.after:
            return "EDIT"
        return "KEEP"


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


def _checkpoint_revision_items(
    before_snapshot: object,
    after_snapshot: object,
) -> tuple[tuple[_CheckpointItemChange, ...], int, bool]:
    """Project one compact unified stream without losing the complete result.

    When retained items keep their relative order, a two-cursor merge places
    removals and additions at the transition where they occurred.  This keeps
    every direct item in one scan path while stable UIDs continue to prove
    KEEP or EDIT.  A reorder falls back to authoritative result order and an
    explicit note instead of misrepresenting a move as REMOVE plus ADD.
    """

    before, before_order = _snapshot_items(before_snapshot)
    after, after_order = _snapshot_items(after_snapshot)
    common = set(before) & set(after)
    reordered = [uid for uid in before_order if uid in common] != [
        uid for uid in after_order if uid in common
    ]
    if reordered:
        result_items = tuple(
            _CheckpointItemChange(uid, before.get(uid), after[uid])
            for uid in after_order
        )
        removed_items = tuple(
            _CheckpointItemChange(uid, before[uid], None)
            for uid in before_order
            if uid not in after
        )
        return (*result_items, *removed_items), len(after_order), True

    items: list[_CheckpointItemChange] = []
    before_index = 0
    after_index = 0
    while before_index < len(before_order) or after_index < len(after_order):
        before_uid = (
            before_order[before_index]
            if before_index < len(before_order)
            else None
        )
        after_uid = (
            after_order[after_index]
            if after_index < len(after_order)
            else None
        )
        if before_uid is not None and before_uid == after_uid:
            items.append(
                _CheckpointItemChange(
                    before_uid,
                    before[before_uid],
                    after[before_uid],
                )
            )
            before_index += 1
            after_index += 1
        elif before_uid is not None and before_uid not in after:
            items.append(_CheckpointItemChange(before_uid, before[before_uid], None))
            before_index += 1
        elif after_uid is not None and after_uid not in before:
            items.append(_CheckpointItemChange(after_uid, None, after[after_uid]))
            after_index += 1
        else:  # pragma: no cover - reordered common items take the branch above.
            raise AssertionError("Ordered checkpoint merge could not advance.")
    return tuple(items), len(after_order), False


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
        result[uid] = (
            command_before if isinstance(command_before, Mapping) else previous
        )
        previous = checkpoint.get("snapshot")
    return result


def _item_text(item: Mapping[str, Any] | None) -> str | None:
    if item is None:
        return None
    if item.get("type") == "memory":
        content = item.get("content")
        return content if isinstance(content, str) else ""
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _direct_item_count(count: int) -> str:
    return f"{count} DIRECT ITEM{'S' if count != 1 else ''}"


def _render_revision_item(
    change: _CheckpointItemChange,
    *,
    location: str,
) -> StyleAndTextTuples:
    """Render a dense diff row while keeping its disposition text-visible."""

    treatment = change.treatment
    fragments: StyleAndTextTuples = []
    memory_change = MemoryChange(
        marker={"KEEP": "=", "ADD": "+", "REMOVE": "−", "EDIT": "~"}[
            treatment
        ],
        treatment=treatment,
        location=location,
        memory_uid=change.uid,
        before=_item_text(change.before),
        after=_item_text(change.after),
    )
    for line in memory_diff_lines(memory_change):
        style_key = {
            "-": "remove",
            "+": "add",
            "=": "equal",
            " ": "equal",
        }[line.marker]
        visible_marker = line.marker if line.marker in {"-", "+"} else " "
        marker_style = {
            "-": "class:memory-diff.before-marker",
            "+": "class:memory-diff.after-marker",
        }.get(line.marker, "class:memory-diff.equal")
        label = f"[{treatment}]"
        fragments.append((marker_style, f" {visible_marker} "))
        fragments.append(("class:report-neutral", "["))
        fragments.append(
            (
                semantic_action_style(treatment, fallback="class:report-neutral"),
                treatment,
            )
        )
        fragments.append(
            (
                "class:report-neutral",
                "]" + " " * (9 - len(label))
                + f"[{display_escape_text(change.uid[:8])}] ",
            )
        )
        fragments.extend(
            (
                (
                    f"class:memory-diff.{style_key}"
                    + (".changed" if span.changed else "")
                ),
                display_escape_text(span.text),
            )
            for span in line.spans
        )
        fragments.append(("", "\n"))
    return fragments


def checkpoint_revision_detail_renderer(
    checkpoints: Sequence[Mapping[str, Any]],
):
    """Render one revision diff together with its complete resulting state."""
    records = {
        checkpoint["uid"]: checkpoint
        for checkpoint in checkpoints
        if isinstance(checkpoint.get("uid"), str)
    }
    before_by_uid = _before_snapshots(checkpoints)

    def render(entry: HistoryPickerItem) -> StyleAndTextTuples | HistoryDetailView:
        checkpoint = records[entry.uid]
        revision_items, result_count, reordered = _checkpoint_revision_items(
            before_by_uid[entry.uid],
            checkpoint.get("snapshot"),
        )
        command = checkpoint.get("command")
        action = command if isinstance(command, str) and command else "checkpoint"
        fragments: StyleAndTextTuples = [
            ("class:report-label", " CHECKPOINT  "),
            ("class:report-neutral", display_escape_text(entry.uid) + "\n"),
            ("class:report-label", " ACTION      "),
            (
                semantic_action_style(action, fallback="class:report-label"),
                display_escape_text(action) + "\n",
            ),
            ("class:report-label", " DESCRIPTION "),
            (
                "class:report-neutral",
                display_escape_text(entry.description or "(none)") + "\n\n",
            ),
            ("class:report-label", " REVISION DIFF"),
            (
                "class:report-neutral",
                f" · RESULT {_direct_item_count(result_count)}\n",
            ),
        ]
        counts = {
            treatment: sum(
                change.treatment == treatment
                for change in revision_items
            )
            for treatment in ("KEEP", "ADD", "EDIT", "REMOVE")
        }
        fragments.append(
            (
                "class:report-neutral",
                " SUMMARY · "
                f"{counts['KEEP']} kept · {counts['ADD']} added · "
                f"{counts['EDIT']} edited · {counts['REMOVE']} removed\n\n",
            )
        )
        unit_start_lines: list[int] = []
        if not revision_items:
            fragments.append(("class:report-neutral", " (empty direct Context)\n"))
        for change in revision_items:
            unit_start_lines.append(
                sum(text.count("\n") for _style, text in fragments)
            )
            fragments.extend(
                _render_revision_item(
                    change,
                    location=entry.uid,
                )
            )
        if reordered:
            fragments.append(
                (
                    "class:report-neutral",
                    "\n ORDER · retained direct items changed position; result "
                    "rows remain authoritative.\n",
                )
            )
        return HistoryDetailView(
            content=fragments,
            unit_start_lines=tuple(unit_start_lines),
            unit_label="ITEM",
        )

    return render


def checkpoint_diff_detail_renderer(
    checkpoints: Sequence[Mapping[str, Any]],
):
    """Compatibility name for the shared complete revision renderer."""

    return checkpoint_revision_detail_renderer(checkpoints)


def checkpoint_restore_detail_renderer(
    current_snapshot: Mapping[str, Any],
    checkpoints: Sequence[Mapping[str, Any]],
):
    """Compatibility adapter; Revert now reviews the checkpoint revision."""

    del current_snapshot
    return checkpoint_revision_detail_renderer(checkpoints)
