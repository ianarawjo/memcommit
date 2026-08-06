from __future__ import annotations

import asyncio
import shlex
from types import SimpleNamespace

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.output import DummyOutput

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
    render_exact_command_review,
)
from memcommit.commands.tui_primitives import (
    InFrameInputManager,
    InFrameInputSection,
    INLINE_AGENT_COMMENT_TITLE,
    INLINE_DIRECT_EDIT_TITLE,
    MEMCOMMIT_TUI_STYLE,
    NavigationAccelerator,
    TuiRegion,
    anchored_fragments,
    bind_focused_frame_style,
    build_framed_multiline_input,
    build_inline_direct_edit_input,
    build_scrollable_text_pane,
    build_tui_frame,
    classify_inline_edit_submission,
    dispatch_tui_back,
    display_escape_text,
    equal_pane_height,
    safe_terminal_text,
    set_scrollable_pane_text,
)


class _RecordingApp:
    def __init__(self) -> None:
        self.invalidations = 0

    def invalidate(self) -> None:
        self.invalidations += 1


def test_shared_navigation_accelerator_accelerates_only_after_hold_cadence():
    accelerator = NavigationAccelerator()

    held_input_times = [0.0, 0.35] + [0.35 + index * 0.08 for index in range(1, 15)]
    assert [accelerator.step(1, now=now) for now in held_input_times] == [
        1,
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
        2,
        5,
        5,
        5,
        5,
        5,
        10,
    ]
    assert accelerator.step(1, now=2.0) == 1
    assert accelerator.step(-1, now=2.1) == 1
    assert accelerator.step(-1, now=2.6) == 1


def test_shared_navigation_accelerator_never_accelerates_rapid_taps():
    accelerator = NavigationAccelerator()

    assert [accelerator.step(1, now=index * 0.08) for index in range(20)] == [
        1
    ] * 20


def test_shared_navigation_accelerator_resets_on_interrupted_repeat_bursts():
    accelerator = NavigationAccelerator()
    interrupted_times = (0.0, 0.35, 0.43, 0.51, 0.82, 0.90, 0.98, 1.35)

    assert [accelerator.step(1, now=now) for now in interrupted_times] == [
        1
    ] * len(interrupted_times)


class _SizedDummyOutput(DummyOutput):
    def __init__(self, *, rows: int, columns: int) -> None:
        super().__init__()
        self._size = Size(rows=rows, columns=columns)

    def get_size(self) -> Size:
        return self._size


def _render_pane_top_row(
    *,
    active: bool,
    columns: int,
    focused: bool = False,
) -> str:
    pane = build_scrollable_text_pane(
        "GOAL",
        "one Goal",
        height=3,
        notification=lambda: active,
    )
    if focused:
        bind_focused_frame_style(pane.frame, is_focused=lambda: True)
    captured: list[str] = []

    with create_pipe_input() as pipe_input:
        application = Application(
            layout=Layout(pane.container),
            full_screen=True,
            input=pipe_input,
            output=_SizedDummyOutput(rows=3, columns=columns),
            style=MEMCOMMIT_TUI_STYLE,
        )

        async def capture_after_render() -> None:
            for _attempt in range(100):
                await asyncio.sleep(0.01)
                screen = application.renderer.last_rendered_screen
                if screen is not None:
                    captured.append(
                        "".join(
                            screen.data_buffer[0][column].char or " "
                            for column in range(columns)
                        )
                    )
                    application.exit()
                    return
            application.exit(
                exception=AssertionError("pane was not rendered")
            )

        application.run(
            pre_run=lambda: application.create_background_task(
                capture_after_render()
            )
        )

    return captured[0]


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


def test_shared_back_dispatcher_unwinds_only_the_deepest_active_layer():
    app = _RecordingApp()
    event = SimpleNamespace(app=app)
    calls: list[str] = []

    dispatch_tui_back(
        event,
        lambda _event: calls.append("inner") or True,
        lambda _event: calls.append("outer") or True,
        close=lambda _event: calls.append("close"),
    )

    assert calls == ["inner"]
    assert app.invalidations == 1


def test_shared_back_dispatcher_delegates_terminal_close_to_operation():
    app = _RecordingApp()
    event = SimpleNamespace(app=app)
    calls: list[str] = []

    dispatch_tui_back(
        event,
        lambda _event: calls.append("inner") or False,
        close=lambda _event: calls.append("close"),
    )

    assert calls == ["inner", "close"]
    assert app.invalidations == 0


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


def test_scrollable_pane_notification_is_optional_and_right_anchored():
    inactive = _render_pane_top_row(active=False, columns=30)
    active = _render_pane_top_row(active=True, columns=30)
    resized = _render_pane_top_row(active=True, columns=40)

    assert "●" not in inactive
    assert active.index("●") == 27
    assert resized.index("●") == 37
    assert active.endswith("●─┐")
    assert resized.endswith("●─┐")
    assert "| GOAL |" in active


def test_focused_frame_renders_heavy_box_glyphs():
    focused = _render_pane_top_row(active=False, columns=30, focused=True)

    assert focused.startswith("┏")
    assert focused.endswith("┓")
    assert "━┃ GOAL ┃━" in focused


def test_focus_style_highlights_only_frame_chrome_and_keeps_base_style():
    pane = build_scrollable_text_pane(
        "RULES",
        "one Rule",
        frame_style="class:custom-frame",
        notification=lambda: True,
    )
    focused = {"value": False}
    bind_focused_frame_style(
        pane.frame,
        is_focused=lambda: focused["value"],
    )

    def border_chars(container) -> str:
        values: list[str] = []
        char = getattr(container, "char", None)
        if char is not None:
            values.append(char() if callable(char) else char)
        content = getattr(container, "content", None)
        if content is not None and type(container).__name__ == "ConditionalContainer":
            values.append(border_chars(content))
        for child in getattr(container, "children", ()):
            values.append(border_chars(child))
        return "".join(values)

    assert pane.frame.container.style() == (
        "class:frame class:custom-frame"
    )
    assert set(border_chars(pane.frame.container)) == set("┌─|┐│└┘")
    assert pane.container is not pane.frame
    focused["value"] = True
    assert pane.frame.container.style() == (
        "class:frame class:custom-frame class:memcommit.focused"
    )
    assert set(border_chars(pane.frame.container)) == set("┏━┓┃┗┛")

    border = MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
        "class:memcommit.focused class:frame.border"
    )
    label = MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
        "class:memcommit.focused class:frame.label"
    )
    body = MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
        "class:memcommit.focused class:text-area"
    )
    assert border.color == "8bd5ff"
    assert border.bold
    assert label.color == "8bd5ff"
    assert label.bold
    assert body.color == ""
    assert not body.bold


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


def test_in_frame_inputs_share_the_pane_frame_and_restore_base_layout():
    base_height = equal_pane_height(minimum=4, preferred=5, maximum=8)
    expanded_height = equal_pane_height(
        minimum=8,
        preferred=10,
        maximum=12,
    )
    pane = build_scrollable_text_pane(
        "RULES",
        "read-only Rules",
        height=base_height,
        notification=lambda: True,
    )
    presentation_container = pane.container
    original_body = pane.frame.body
    message = build_framed_multiline_input("MESSAGE")
    editor = build_framed_multiline_input("EDIT")
    manager = InFrameInputManager(pane)

    manager.show(
        pane,
        InFrameInputSection(
            "EDIT (DIRECTLY)",
            editor.text_area,
            height=2,
        ),
        InFrameInputSection(
            "COMMENT (FOR THE AGENT)",
            message.text_area,
            height=3,
        ),
        height=expanded_height,
    )

    assert manager.active_pane is pane
    assert [section.text_area for section in manager.active_sections] == [
        editor.text_area,
        message.text_area,
    ]
    assert pane.frame.body is not original_body
    assert pane.frame.body.children[0] is pane.text_area.window
    assert pane.frame.body.children[2].children[0] is editor.text_area.window
    assert pane.frame.body.children[4].children[0] is message.text_area.window
    assert pane.frame.container.height is expanded_height
    assert pane.container is presentation_container

    manager.clear()

    assert manager.active_pane is None
    assert manager.active_sections == ()
    assert pane.frame.body is original_body
    assert pane.frame.container.height is base_height
    assert pane.container is presentation_container


def test_in_frame_input_moves_one_shared_composer_between_live_panes():
    goal_height = equal_pane_height(minimum=3)
    rules_height = equal_pane_height(minimum=5)
    goal = build_scrollable_text_pane("GOAL", "goal", height=goal_height)
    rules = build_scrollable_text_pane(
        "RULES",
        "rules",
        height=rules_height,
    )
    goal_body = goal.frame.body
    rules_body = rules.frame.body
    composer = build_framed_multiline_input("MESSAGE")
    manager = InFrameInputManager(goal, rules)
    section = InFrameInputSection("MESSAGE", composer.text_area, height=2)

    manager.show(goal, section, height=9)
    goal_embedded_body = goal.frame.body
    assert (
        goal_embedded_body.children[2].children[0]
        is composer.text_area.window
    )

    manager.show(rules, section, height=11)

    assert goal.frame.body is goal_body
    assert goal.frame.container.height is goal_height
    assert rules.frame.body is not rules_body
    assert (
        rules.frame.body.children[2].children[0]
        is composer.text_area.window
    )
    assert rules.frame.container.height == 11
    assert manager.active_pane is rules

    manager.show(rules)
    assert rules.frame.body is rules_body
    assert rules.frame.container.height is rules_height


def test_in_frame_input_allows_an_explicitly_locked_direct_field_only():
    pane = build_scrollable_text_pane("GOAL", "saved Goal")
    locked = build_framed_multiline_input("EDIT")
    locked.text_area.buffer.read_only = lambda: True
    manager = InFrameInputManager(pane)

    with pytest.raises(ValueError, match="must be writable"):
        manager.show(pane, InFrameInputSection("EDIT", locked.text_area))

    manager.show(
        pane,
        InFrameInputSection(
            "EDIT (DIRECTLY)",
            locked.text_area,
            allow_read_only=True,
        ),
    )

    assert manager.active_sections[0].allow_read_only


def test_in_frame_input_rejects_invalid_or_duplicate_layout_members():
    pane = build_scrollable_text_pane("CHAT", "history")
    other = build_scrollable_text_pane("RULES", "rules")
    composer = build_framed_multiline_input("MESSAGE")
    manager = InFrameInputManager(pane)
    section = InFrameInputSection("MESSAGE", composer.text_area)

    with pytest.raises(ValueError, match="not registered"):
        manager.show(other, section)
    with pytest.raises(ValueError, match="distinct"):
        manager.show(pane, section, section)
    with pytest.raises(ValueError, match="writable"):
        manager.show(
            pane,
            InFrameInputSection("READ ONLY", other.text_area),
        )

    assert pane.frame.body is pane.text_area


def test_inline_edit_uses_exact_labels_and_distinguishes_comment_from_change():
    editor = build_inline_direct_edit_input()

    assert editor.frame.title == INLINE_DIRECT_EDIT_TITLE
    assert INLINE_DIRECT_EDIT_TITLE == "EDIT (DIRECTLY)"
    assert INLINE_AGENT_COMMENT_TITLE == "COMMENT (FOR THE AGENT)"
    assert "OPTIONAL" not in editor.frame.title.upper()
    height = editor.frame.__pt_container__().height
    assert (height.min, height.preferred, height.max) == (3, 3, 4)
    assert classify_inline_edit_submission(
        original="Goal",
        edited="Goal",
        comment="",
    ) == "NOOP"
    assert classify_inline_edit_submission(
        original="Goal",
        edited="Revised Goal",
        comment="",
    ) == "DIRECT"
    assert classify_inline_edit_submission(
        original="Goal",
        edited="Goal",
        comment="Explain this",
    ) == "COMMENT"
    assert classify_inline_edit_submission(
        original="Goal",
        edited="Revised Goal",
        comment="This is why",
    ) == "BOTH"


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
