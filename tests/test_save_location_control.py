from __future__ import annotations

import pytest

from memcommit.commands.save_location_control import (
    SaveLocationView,
    save_location_card_lines,
    save_location_row_fragments,
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
