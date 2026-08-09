"""Read-only table presentation shared by terminal workbenches.

The table owns display geometry only. Operation-specific row meaning,
persistence, commands, and provider inputs remain with the calling shell.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from prompt_toolkit.formatted_text.utils import to_formatted_text
from prompt_toolkit.layout.processors import (
    Processor,
    Transformation,
    TransformationInput,
)
from prompt_toolkit.layout.utils import explode_text_fragments
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.commands.tui_text_layout import (
    elide_terminal_text,
    pad_terminal_text,
)


@dataclass(frozen=True)
class TuiTableColumn:
    """One stable logical table column and its display width."""

    key: str
    heading: str
    width: int


@dataclass(frozen=True)
class TuiTableRow:
    """One row whose cell order matches the table column order."""

    row_id: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class TuiTableCellSpan:
    """One selected source-text span inside a rendered table document."""

    line: int
    start: int
    end: int


@dataclass(frozen=True)
class RenderedTuiTable:
    """Rendered text plus the selected cell's navigation coordinates."""

    text: str
    selected_row: int
    selected_column: int
    selected_span: TuiTableCellSpan | None
    cursor_position: int


def clamp_table_position(
    *,
    row_count: int,
    column_count: int,
    row: int,
    column: int,
) -> tuple[int, int]:
    """Clamp one process-local cell coordinate without wrapping edges."""
    if row_count <= 0 or column_count <= 0:
        return 0, 0
    return (
        max(0, min(row, row_count - 1)),
        max(0, min(column, column_count - 1)),
    )


def _single_line(value: str) -> str:
    # Normalize platform line endings before the terminal-safety boundary;
    # otherwise a carriage return becomes � and LIST/TABLE disagree.
    normalized = safe_terminal_text(
        value.replace("\r\n", "\n").replace("\r", "\n")
    )
    return (
        normalized.replace("\n", " ↵ ")
        .replace("\t", " ⇥ ")
    )


def _fit_display(value: str, width: int) -> str:
    if width < 2:
        raise ValueError("table column width must be at least two")
    value = _single_line(value)
    return pad_terminal_text(elide_terminal_text(value, width), width)


def _wrap_display(value: str, width: int) -> tuple[str, ...]:
    value = _single_line(value)
    if not value:
        return ("(empty)",)
    lines: list[str] = []
    current: list[str] = []
    used = 0
    for character in value:
        character_width = get_cwidth(character)
        if current and used + character_width > width:
            lines.append("".join(current))
            current = []
            used = 0
        current.append(character)
        used += character_width
    if current:
        lines.append("".join(current))
    return tuple(lines)


def render_tui_table(
    *,
    columns: Sequence[TuiTableColumn],
    rows: Sequence[TuiTableRow],
    selected_row: int = 0,
    selected_column: int = 0,
    noun: str = "ROWS",
) -> RenderedTuiTable:
    """Render one horizontally scrollable grid and full selected-cell value."""
    if not columns:
        raise ValueError("table requires at least one column")
    if any(len(row.cells) != len(columns) for row in rows):
        raise ValueError("table row does not match its columns")
    selected_row, selected_column = clamp_table_position(
        row_count=len(rows),
        column_count=len(columns),
        row=selected_row,
        column=selected_column,
    )
    if not rows:
        text = f"TABLE · 0 {noun}\n(none yet)"
        return RenderedTuiTable(
            text=text,
            selected_row=0,
            selected_column=0,
            selected_span=None,
            cursor_position=0,
        )

    selected = rows[selected_row]
    selected_key = columns[selected_column].heading
    lines = [
        (
            f"TABLE · {len(rows)} {noun} · ROW {selected_row + 1}/"
            f"{len(rows)} · COLUMN {selected_key}"
        )
    ]
    lines.append(
        " │ ".join(
            _fit_display(column.heading, column.width)
            for column in columns
        )
    )
    lines.append(
        "─┼─".join("─" * column.width for column in columns)
    )

    selected_span: TuiTableCellSpan | None = None
    cursor_position = 0
    selected_cell_start = 0
    for row_index, row in enumerate(rows):
        fragments: list[str] = []
        character_offset = 0
        for column_index, (column, value) in enumerate(
            zip(columns, row.cells, strict=True)
        ):
            fitted = _fit_display(value, column.width)
            if row_index == selected_row and column_index == selected_column:
                selected_span = TuiTableCellSpan(
                    line=len(lines),
                    start=character_offset,
                    end=character_offset + len(fitted),
                )
                selected_cell_start = character_offset
                cursor_position = sum(len(line) + 1 for line in lines) + character_offset
            fragments.append(fitted)
            character_offset += len(fitted)
            if column_index < len(columns) - 1:
                character_offset += len(" │ ")
        lines.append(" │ ".join(fragments))

    full_value = selected.cells[selected_column]
    indent = " " * selected_cell_start
    lines.extend(
        [
            "",
            f"{indent}CELL · {selected.row_id} · {selected_key}",
            *(
                f"{indent}{line}"
                for line in _wrap_display(
                    full_value,
                    columns[selected_column].width,
                )
            ),
        ]
    )
    return RenderedTuiTable(
        text="\n".join(lines),
        selected_row=selected_row,
        selected_column=selected_column,
        selected_span=selected_span,
        cursor_position=cursor_position,
    )


class SelectedTableCellProcessor(Processor):
    """Apply a dynamic style to the selected cell in the existing TextArea."""

    def __init__(
        self,
        selected_span: Callable[[], TuiTableCellSpan | None],
    ) -> None:
        self._selected_span = selected_span

    def apply_transformation(
        self,
        transformation_input: TransformationInput,
    ) -> Transformation:
        span = self._selected_span()
        if span is None or span.line != transformation_input.lineno:
            return Transformation(transformation_input.fragments)
        fragments = explode_text_fragments(
            to_formatted_text(transformation_input.fragments)
        )
        start = transformation_input.source_to_display(span.start)
        end = transformation_input.source_to_display(span.end)
        for index in range(max(0, start), min(end, len(fragments))):
            style, text, *rest = fragments[index]
            fragments[index] = (
                f"{style} class:memcommit.table.selected",
                text,
                *rest,
            )
        return Transformation(fragments)
