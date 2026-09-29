"""Ordered direct-item transitions shared by saved revisions and previews."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class ContextItemChange:
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


def context_item_changes(
    before_snapshot: object,
    after_snapshot: object,
) -> tuple[tuple[ContextItemChange, ...], int, bool]:
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
            ContextItemChange(uid, before.get(uid), after[uid]) for uid in after_order
        )
        removed_items = tuple(
            ContextItemChange(uid, before[uid], None)
            for uid in before_order
            if uid not in after
        )
        return (*result_items, *removed_items), len(after_order), True

    items: list[ContextItemChange] = []
    before_index = 0
    after_index = 0
    while before_index < len(before_order) or after_index < len(after_order):
        before_uid = (
            before_order[before_index] if before_index < len(before_order) else None
        )
        after_uid = after_order[after_index] if after_index < len(after_order) else None
        if before_uid is not None and before_uid == after_uid:
            items.append(
                ContextItemChange(
                    before_uid,
                    before[before_uid],
                    after[before_uid],
                )
            )
            before_index += 1
            after_index += 1
        elif before_uid is not None and before_uid not in after:
            items.append(ContextItemChange(before_uid, before[before_uid], None))
            before_index += 1
        elif after_uid is not None and after_uid not in before:
            items.append(ContextItemChange(after_uid, None, after[after_uid]))
            after_index += 1
        else:  # pragma: no cover - reordered common items take the branch above.
            raise AssertionError("Ordered Context diff could not advance.")
    return tuple(items), len(after_order), False


def context_item_text(item: Mapping[str, Any] | None) -> str | None:
    if item is None:
        return None
    if item.get("type") == "memory":
        content = item.get("content")
        return content if isinstance(content, str) else ""
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
