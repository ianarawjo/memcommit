"""Shared direct-item insertion-gap state and Context-tree projection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from prompt_toolkit.application.current import get_app
from prompt_toolkit.utils import get_cwidth

from memcommit.context_targeting.tui.picker import (
    ContextMemoryRow,
    context_memory_rows,
    render_context_options,
)
from memcommit.context import Context
from memcommit.context_targeting.tui.selector import ContextSelectorRowProjection
from memcommit.context_targeting.tui.tree import ContextTreeRow
from memcommit.selection.tui import tree_choice_marker, tree_choice_styles


@dataclass(frozen=True)
class DirectItemPlacementRow:
    """One direct Context item shown beside its neighboring insertion gaps."""

    uid: str
    preview: ContextMemoryRow

    def __post_init__(self) -> None:
        if not self.uid:
            raise ValueError("Direct-item placement rows require identity.")


@dataclass(frozen=True)
class DirectItemGap:
    """One exact gap in a frozen direct-item order."""

    position: int
    previous_uid: str | None
    next_uid: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise ValueError("A direct-item gap requires a nonnegative position.")
        if self.position == 0 and self.previous_uid is not None:
            raise ValueError("The first direct-item gap cannot have a previous item.")


def direct_item_placement_rows(context: Context) -> tuple[DirectItemPlacementRow, ...]:
    """Project every persisted direct-item slot without changing its order."""

    items = tuple(context.iter_items())
    previews = context_memory_rows(context)
    if len(items) != len(previews):
        raise RuntimeError("The shared picker omitted a direct Context item.")
    return tuple(
        DirectItemPlacementRow(uid=item.uid, preview=preview)
        for item, preview in zip(items, previews, strict=True)
    )


def direct_item_gap(
    rows: Sequence[DirectItemPlacementRow],
    position: int,
) -> DirectItemGap:
    """Freeze the exact neighbors around one insertion position."""

    values = tuple(rows)
    if (
        isinstance(position, bool)
        or not isinstance(position, int)
        or not 0 <= position <= len(values)
    ):
        raise ValueError(
            f"Direct-item insertion position must be between 0 and {len(values)}."
        )
    return DirectItemGap(
        position=position,
        previous_uid=values[position - 1].uid if position else None,
        next_uid=values[position].uid if position < len(values) else None,
    )


@dataclass
class DirectItemGapState:
    """Independent hover and retained selection for one ordered gap list."""

    rows: tuple[DirectItemPlacementRow, ...]
    cursor_position: int
    selected_position: int
    insertion_label: str = "INSERT HERE"

    @classmethod
    def create(
        cls,
        rows: Sequence[DirectItemPlacementRow],
        *,
        position: int | None = None,
        insertion_label: str = "INSERT HERE",
    ) -> "DirectItemGapState":
        values = tuple(rows)
        selected = len(values) if position is None else position
        direct_item_gap(values, selected)
        if not insertion_label.strip():
            raise ValueError("Insertion-gap controls require a visible action label.")
        return cls(values, selected, selected, insertion_label)

    @property
    def selected_gap(self) -> DirectItemGap:
        return direct_item_gap(self.rows, self.selected_position)

    def move(self, delta: int) -> bool:
        if delta not in {-1, 1}:
            raise ValueError("Insertion-gap movement must be -1 or 1.")
        candidate = max(0, min(self.cursor_position + delta, len(self.rows)))
        if candidate == self.cursor_position:
            return False
        self.cursor_position = candidate
        return True

    def choose_cursor(self) -> bool:
        changed = self.selected_position != self.cursor_position
        self.selected_position = self.cursor_position
        return changed

    def replace_rows(self, rows: Sequence[DirectItemPlacementRow]) -> None:
        """Reset a newly chosen Context to its explicit append gap."""

        self.rows = tuple(rows)
        self.cursor_position = len(self.rows)
        self.selected_position = len(self.rows)


def _gap_label(state: DirectItemGapState, position: int) -> str:
    gap_count = len(state.rows) + 1
    if not state.rows:
        return "FIRST = LAST · DEFAULT · 1/1"
    if position == 0:
        return f"FIRST · 1/{gap_count}"
    if position == len(state.rows):
        return f"LAST · DEFAULT · {gap_count}/{gap_count}"
    return f"POSITION · {position + 1}/{gap_count}"


def _render_position_line(
    state: DirectItemGapState,
    *,
    row: ContextTreeRow,
    editing: bool,
    focused: bool,
    width: int,
) -> list[tuple[str, str]]:
    position = state.cursor_position if editing else state.selected_position
    selected = position == state.selected_position
    cursor_style, value_style = tree_choice_styles(
        cursor=editing,
        selected=selected,
        focused=focused,
    )
    indent = "  " * (row.depth + 1)
    pointer = "›" if editing else " "
    marker = tree_choice_marker(selected=selected)
    prefix = f"{indent}{pointer} {marker} ───────── "
    label = _gap_label(state, position)
    fill = "─" * max(1, width - get_cwidth(prefix) - get_cwidth(label) - 1)
    fragments: list[tuple[str, str]] = [("", "\n")]
    if editing:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        (
            (cursor_style, prefix),
            (value_style, label),
            (cursor_style, " " + fill),
        )
    )
    return fragments


def _render_switch_item_preview(
    row: ContextTreeRow,
    preview: ContextMemoryRow,
    *,
    width: int,
) -> list[tuple[str, str]]:
    """Reuse Switch's complete row projector and retain its nested item tail."""

    fragments = render_context_options(
        (row,),
        selected=row.name,
        current=None,
        memories_by_context={row.name: (preview,)},
        visible_memory_contexts=frozenset((row.name,)),
        wrap_width=width,
        memory_anchor=None,
    )
    # The shared renderer emits the Context row first, then starts every direct
    # item with a newline. Embed already owns that Context row through the
    # common selector, so composing only this tail avoids redrawing it.
    try:
        start = next(
            index for index, (_style, text) in enumerate(fragments) if text == "\n"
        )
    except StopIteration as error:
        raise RuntimeError("Switch did not project the direct item.") from error
    return fragments[start:]


def render_direct_item_tree_fragments(
    state: DirectItemGapState,
    *,
    row: ContextTreeRow,
    editing: bool,
    focused: bool,
    width: int,
) -> list[tuple[str, str]]:
    """Render common Switch previews with only one visible insertion line."""

    available_width = max(24, width)
    fragments: list[tuple[str, str]] = []
    visible_position = (
        state.cursor_position if editing else state.selected_position
    )
    for position in range(len(state.rows) + 1):
        if position == visible_position:
            fragments.extend(
                _render_position_line(
                    state,
                    row=row,
                    editing=editing,
                    focused=focused,
                    width=available_width,
                )
            )
        if position < len(state.rows):
            fragments.extend(
                _render_switch_item_preview(
                    row,
                    state.rows[position].preview,
                    width=available_width,
                )
            )
    return fragments


@dataclass
class DirectItemPlacementTreeProjection:
    """Compose one target's ordered items into the shared Context selector."""

    context_name: str
    state: DirectItemGapState
    editing: bool = False

    @classmethod
    def create(
        cls,
        context_name: str,
        rows: Sequence[DirectItemPlacementRow],
    ) -> "DirectItemPlacementTreeProjection":
        return cls(
            context_name,
            DirectItemGapState.create(
                rows,
                insertion_label="POSITION",
            ),
        )

    def begin(self) -> None:
        self.state.cursor_position = self.state.selected_position
        self.editing = True

    def end(self) -> None:
        self.editing = False

    def project(
        self,
        row: ContextTreeRow,
        focused: bool,
    ) -> ContextSelectorRowProjection:
        if row.name != self.context_name:
            return ContextSelectorRowProjection()
        return ContextSelectorRowProjection(
            branch="▾",
            nested_fragments=tuple(
                render_direct_item_tree_fragments(
                    self.state,
                    row=row,
                    editing=self.editing,
                    focused=focused,
                    width=max(24, get_app().output.get_size().columns - 2),
                )
            ),
            show_context_cursor=not self.editing,
        )

    def replace_context(
        self,
        context_name: str,
        rows: Sequence[DirectItemPlacementRow],
    ) -> None:
        self.context_name = context_name
        self.state.replace_rows(rows)
        self.editing = False
