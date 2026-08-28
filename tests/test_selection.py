from __future__ import annotations

from memcommit.adapters.console.terminal.components.selection.model import SelectionOption
from memcommit.adapters.console.terminal.components.selection.state import FlatSelectionState
from memcommit.adapters.console.terminal.components.selection import (
    render_vertical_choice_cards,
    render_vertical_choice_rows,
    tree_choice_styles,
)


def test_flat_selection_keeps_cursor_and_checked_value_independent():
    state = FlatSelectionState(
        (
            SelectionOption("one", "First"),
            SelectionOption("two", "Second"),
        ),
        cursor_uid="one",
        selected_uid="two",
    )

    assert state.move(1) is True
    assert state.cursor_uid == "two"
    assert state.selected_uid == "two"
    assert state.select_cursor(toggle=True) is None
    assert state.cursor_uid == "two"


def test_vertical_choices_use_meld_rectangles_without_radio_markers():
    state = FlatSelectionState(
        (
            SelectionOption("one", "First", "Use the first form."),
            SelectionOption("two", "Second", "Use the second form."),
        ),
        cursor_uid="one",
        selected_uid="one",
    )

    fragments = render_vertical_choice_cards(
        state,
        focused=True,
        content_width=36,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "┏" in rendered
    assert "✓ 1. First" in rendered
    assert "┌" in rendered
    assert not any(marker in rendered for marker in ("○", "●", "◇"))
    assert any(
        style == "class:memcommit.choice.border.focused" and "┏" in text
        for style, text in fragments
    )
    focused_bottom = next(
        index
        for index, (style, text) in enumerate(fragments)
        if style == "class:memcommit.choice.border.focused" and "┗" in text
    )
    cursor_anchor = next(
        index
        for index, (style, _text) in enumerate(fragments)
        if style == "[SetCursorPosition]"
    )
    assert cursor_anchor > focused_bottom


def test_vertical_choice_rows_highlight_content_without_boxing_description_bold():
    state = FlatSelectionState(
        (SelectionOption("one", "[SINGLE] First", "Use the first form."),),
        cursor_uid="one",
    )

    fragments = render_vertical_choice_rows(
        state,
        focused=True,
        content_width=36,
    )
    rendered = "".join(text for _style, text in fragments)

    assert not any(glyph in rendered for glyph in "┏┓┗┛┌┐└┘")
    assert (
        "class:memcommit.choice.active.focused",
        "  1. [SINGLE] First\n",
    ) in fragments
    assert (
        "class:memcommit.choice.active",
        "  Use the first form.\n",
    ) in fragments


def test_tree_variant_shares_checked_color_without_losing_tree_cursor():
    assert tree_choice_styles(
        cursor=True,
        selected=True,
        focused=True,
    ) == (
        "class:memcommit.table.selected",
        "class:memcommit.choice.active.focused",
    )
