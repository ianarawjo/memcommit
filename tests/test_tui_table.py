from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.processors import TransformationInput

from memcommit.commands.tui_table import (
    SelectedTableCellProcessor,
    TuiTableColumn,
    TuiTableRow,
    clamp_table_position,
    render_tui_table,
)


def test_table_clamps_coordinates_without_wrapping_edges():
    assert clamp_table_position(
        row_count=3,
        column_count=4,
        row=-9,
        column=99,
    ) == (0, 3)
    assert clamp_table_position(
        row_count=0,
        column_count=4,
        row=2,
        column=2,
    ) == (0, 0)


def test_table_preserves_full_multilingual_selected_cell_below_grid():
    rendered = render_tui_table(
        columns=(
            TuiTableColumn("id", "ID", 4),
            TuiTableColumn("input", "INPUT", 8),
        ),
        rows=(
            TuiTableRow("c1", ("c1", "정문\n실물 카드만 사용")),
        ),
        selected_row=0,
        selected_column=1,
        noun="MEMORIES",
    )

    assert "TABLE · 1 MEMORIES · ROW 1/1 · COLUMN INPUT" in rendered.text
    assert "CELL · c1 · INPUT" in rendered.text
    assert "정문↵실물카드만사용" in "".join(rendered.text.split())
    assert rendered.selected_span is not None
    assert rendered.cursor_position > 0


def test_table_folds_windows_line_endings_without_replacement_characters():
    rendered = render_tui_table(
        columns=(TuiTableColumn("value", "VALUE", 12),),
        rows=(TuiTableRow("c1", ("first\r\nsecond\rthird",)),),
        noun="MEMORIES",
    )

    assert "first ↵" in rendered.text
    assert "first↵second↵third" in "".join(rendered.text.split())
    assert "�" not in rendered.text


def test_selected_cell_processor_styles_only_the_selected_span():
    rendered = render_tui_table(
        columns=(
            TuiTableColumn("id", "ID", 4),
            TuiTableColumn("value", "VALUE", 8),
        ),
        rows=(TuiTableRow("c1", ("c1", "AAPL")),),
        selected_row=0,
        selected_column=1,
    )
    span = rendered.selected_span
    assert span is not None
    line = rendered.text.splitlines()[span.line]
    processor = SelectedTableCellProcessor(lambda: span)
    transformed = processor.apply_transformation(
        TransformationInput(
            buffer_control=BufferControl(buffer=Buffer()),
            document=Document(rendered.text),
            lineno=span.line,
            source_to_display=lambda value: value,
            fragments=[("", line)],
            width=80,
            height=1,
        )
    )

    styles = [style for style, _text in transformed.fragments]
    assert all(
        "class:memcommit.table.selected" not in style
        for style in styles[: span.start]
    )
    assert all(
        "class:memcommit.table.selected" in style
        for style in styles[span.start : span.end]
    )
