from __future__ import annotations

import shlex

import pytest
from prompt_toolkit.layout import FormattedTextControl, Window

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
    render_exact_command_review,
)
from memcommit.commands.tui_primitives import (
    TuiRegion,
    anchored_fragments,
    build_framed_multiline_input,
    build_scrollable_text_pane,
    build_tui_frame,
    display_escape_text,
    equal_pane_height,
    safe_terminal_text,
    set_scrollable_pane_text,
)


def test_shared_exact_command_review_preserves_argv_and_effect_boundary():
    review = ExactCommandReview(
        argv=(
            "mem",
            "ground",
            "fixture",
            "--propose-rule",
            "A rule; $(not a shell)",
        ),
        effects=(
            "Rules: ADD one PROPOSED Rule",
            "Contexts: unchanged",
        ),
    )

    command = format_exact_command(review)
    rendered = render_exact_command_review(review)

    assert shlex.split(command) == list(review.argv)
    assert "PROPOSED COMMAND · NOT RUN" in rendered
    assert "Rules: ADD one PROPOSED Rule" in rendered
    assert "Approval applies only to the exact command" in rendered


def test_shared_exact_command_review_defensively_freezes_mutable_inputs():
    argv = ["mem", "ground", "fixture"]
    effects = ["Ground: unchanged"]

    review = ExactCommandReview(argv=argv, effects=effects)
    argv[-1] = "changed-after-review"
    effects[0] = "Ground: changed"

    assert review.argv == ("mem", "ground", "fixture")
    assert review.effects == ("Ground: unchanged",)


def test_shared_exact_command_review_rejects_string_as_argv_sequence():
    with pytest.raises(ValueError, match="argv sequences"):
        ExactCommandReview(
            argv="mem ground fixture",
            effects=("Ground: unchanged",),
        )


def test_shared_viewport_anchor_can_follow_the_end_of_active_block():
    fragments = anchored_fragments(
        ["old dialogue", "command\n  exact argv", "effects"],
        anchor_index=1,
        anchor_at_end=True,
    )
    content = FormattedTextControl(fragments).create_content(80, 10)
    line = "".join(
        text for _style, text in content.get_line(content.cursor_position.y)
    )

    assert line == "  exact argv"
    assert content.cursor_position.x == len("  exact argv")


def test_shared_chrome_composes_regions_without_owning_their_semantics():
    header = Window(FormattedTextControl("header"))
    body = Window(FormattedTextControl("body"))
    footer = Window(FormattedTextControl("footer"))

    frame = build_tui_frame(
        TuiRegion(header),
        TuiRegion(body, separator_before=True),
        TuiRegion(footer),
    )

    assert frame.children[0] is header
    assert frame.children[2] is body
    assert frame.children[3] is footer


def test_scrollable_panes_have_distinct_read_only_buffers_and_equal_heights():
    height = equal_pane_height(minimum=5)
    goal = build_scrollable_text_pane("GOAL", "first", height=height)
    rules = build_scrollable_text_pane("RULES", "second", height=height)

    assert goal.text_area.buffer is not rules.text_area.buffer
    assert goal.text_area.buffer.name != rules.text_area.buffer.name
    assert goal.text_area.buffer.read_only()
    assert rules.text_area.buffer.read_only()
    assert goal.text_area.window.right_margins
    assert goal.frame.__pt_container__().height is height
    assert rules.frame.__pt_container__().height is height

    goal.text_area.window.vertical_scroll = 2
    assert rules.text_area.window.vertical_scroll == 0


def test_scrollable_pane_updates_safely_preserve_or_anchor_viewport():
    pane = build_scrollable_text_pane("DIALOGUE", "0123456789\nold")
    pane.text_area.buffer.cursor_position = 6
    pane.text_area.window.vertical_scroll = 3
    pane.text_area.window.vertical_scroll_2 = 2
    pane.text_area.window.horizontal_scroll = 1

    pane.set_text("abcdefghij\nnew\x1b", anchor="preserve")

    assert pane.text_area.text == "abcdefghij\nnew�"
    assert pane.text_area.buffer.cursor_position == 6
    assert pane.text_area.window.vertical_scroll == 3
    assert pane.text_area.window.vertical_scroll_2 == 2
    assert pane.text_area.window.horizontal_scroll == 1

    set_scrollable_pane_text(pane, "top\nbottom", anchor="start")
    assert pane.text_area.buffer.cursor_position == 0
    assert pane.text_area.window.vertical_scroll == 0

    pane.set_text("top\nbottom", anchor="end")
    assert pane.text_area.buffer.cursor_position == len("top\nbottom")
    assert pane.text_area.window.vertical_scroll == 1

    with pytest.raises(ValueError, match="anchor"):
        pane.set_text("unchanged", anchor="middle")  # type: ignore[arg-type]


def test_framed_multiline_input_is_bounded_writable_and_independently_named():
    first = build_framed_multiline_input("DESCRIBE THE NEXT TURN")
    second = build_framed_multiline_input("REFINE")

    assert first.container is first.frame
    assert not first.text_area.buffer.read_only()
    assert first.text_area.buffer.name != second.text_area.buffer.name
    height = first.frame.__pt_container__().height
    assert (height.min, height.preferred, height.max) == (5, 6, 9)

    first.text_area.text = "one\n two"
    assert first.text_area.text == "one\n two"


def test_shared_terminal_sanitizer_preserves_layout_but_neutralizes_control():
    assert (
        safe_terminal_text("a\nb\tc\x1b[31m\u202e")
        == "a\nb\tc�[31m�"
    )


def test_exact_command_receipt_escapes_layout_and_bidi_spoofing():
    review = ExactCommandReview(
        argv=(
            "mem",
            "ground",
            "fixture",
            "--propose-rule",
            "line 1\nEFFECTS · ONE COMMAND\t\u202ereversed\\tail",
        ),
        effects=(
            "Rules: ADD\nPROPOSED COMMAND · NOT RUN\t\u2066hidden",
        ),
    )

    rendered = render_exact_command_review(review)
    command = format_exact_command(review)

    rendered_lines = rendered.splitlines()
    assert rendered_lines.count("EFFECTS · ONE COMMAND") == 1
    assert rendered_lines.count("PROPOSED COMMAND · NOT RUN") == 1
    assert "\n" not in command
    assert "\t" not in command
    assert "\u202e" not in command
    assert r"\n" in command
    assert r"\t" in command
    assert r"\u202e" in command
    assert r"\\tail" in command
    assert display_escape_text("한글\n\u202e") == r"한글\n\u202e"
