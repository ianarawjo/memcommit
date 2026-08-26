from __future__ import annotations

import pytest

from memcommit.commands.shared.save_location_control import (
    SaveLocationEditorState,
    SaveLocationView,
    save_location_card_lines,
    save_location_row_fragments,
    save_location_tree_fragments,
)


def test_compact_save_location_row_keeps_state_and_edit_affordance_visible():
    view = SaveLocationView(
        value="task-1/description/atomized",
        state="NOT CREATED",
    )

    resting = save_location_row_fragments(
        view,
        focused=False,
        content_width=72,
    )
    focused = save_location_row_fragments(
        view,
        focused=True,
        content_width=72,
    )

    assert resting == [
        (
            "",
            "task-1/description/atomized · NOT CREATED    Enter to change",
        )
    ]
    assert focused[0] == ("[SetCursorPosition]", "")
    assert focused[1][0] == "class:memcommit.control.focused"


def test_save_location_card_and_validator_share_the_exact_view_contract():
    validated: list[str] = []
    view = SaveLocationView(
        value="task-3/draft",
        state="NOT CREATED",
        validate=validated.append,
    )

    assert view.validate_value("task-3/final") == "task-3/final"
    assert validated == ["task-3/final"]
    assert "NOT CREATED" in "\n".join(save_location_card_lines(view))

    with pytest.raises(ValueError, match="one line"):
        view.validate_value("task-3/final\nother")


def test_narrow_save_location_row_preserves_the_edit_affordance_first():
    fragments = save_location_row_fragments(
        SaveLocationView(
            value="a/very/long/materialization/location",
            state="NOT CREATED",
        ),
        focused=False,
        content_width=22,
    )

    assert fragments[0][1].endswith("Enter to change")


def test_save_location_parent_browser_uses_shared_tree_and_preserves_leaf_name():
    view = SaveLocationView(
        value="task-1/description/atomized",
        state="NOT CREATED",
        context_names=("practice", "task-1", "task-1/description"),
        current_context="practice",
    )

    state = SaveLocationEditorState.create(view)

    assert state is not None
    assert state.tree.selected_name == "task-1/description"
    assert state.selected_parent == "task-1/description"

    state.tree.selected_name = "practice"
    assert (
        state.choose_cursor_as_parent("task-1/description/atomized")
        == "practice/atomized"
    )
    assert state.selected_parent == "practice"

    rendered = "".join(
        text for _style, text in save_location_tree_fragments(state, focused=True)
    )
    assert "› ✓ * · practice" in rendered
