from __future__ import annotations

from memcommit.responses.model import ResponseChoice, ResponseDraft, ResponseTarget
from memcommit.responses.state import ResponseFrameState
from memcommit.responses.tui import response_frame_fragments


def _target() -> ResponseTarget:
    return ResponseTarget(
        item_uid="finding-1",
        item_label="Campus access ambiguity",
        obligation="OPTIONAL",
        state="OPEN",
        mode="DECISION",
        prompt_heading="CLARIFICATION QUESTION",
        prompt="Which entrance does the rule describe?",
        choices_heading="PROPOSED READINGS",
        choices=(
            ResponseChoice("north", "North entrance", "Use the north entrance."),
            ResponseChoice("staff", "Staff entrance", "Use the staff entrance."),
        ),
    )


def test_response_state_moves_linearly_from_choices_to_response():
    target = _target()
    state = ResponseFrameState()
    state.sync(target, ResponseDraft("staff", "Keep the time window."))

    assert state.section == "DECISION"
    assert state.option_navigation_active is True
    assert state.option_cursor_uid == "staff"
    state.move_focus(target, 1)
    assert state.section == "RESPONSE"
    assert state.option_navigation_active is False
    state.move_focus(target, -1)
    assert state.section == "DECISION"
    assert state.option_cursor_uid == "staff"

    draft = state.toggle_current_choice(target)
    assert draft.selected_choice_uid is None
    assert draft.text == "Keep the time window."


def test_response_focus_restores_the_checked_choice_after_transient_hover():
    target = _target()
    draft = ResponseDraft("staff", "")
    state = ResponseFrameState()
    state.sync(target, draft, frame_focused=True)

    state.move_focus(target, -1)
    assert state.option_cursor_uid == "north"
    assert state.draft.selected_choice_uid == "staff"

    state.sync(target, draft, frame_focused=False)
    assert state.option_cursor_uid == "staff"

    state.move_focus(target, -1)
    state.focus_response()
    assert state.option_cursor_uid == "staff"
    state.move_focus(target, -1)
    assert state.option_cursor_uid == "staff"


def test_response_renderer_owns_question_and_real_options_only():
    target = _target()
    draft = ResponseDraft("staff", "Only during construction.")
    state = ResponseFrameState()
    state.sync(target, draft)

    fragments = response_frame_fragments(
        target,
        draft,
        state,
        focused=True,
        content_width=72,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "Campus access ambiguity" not in rendered
    assert "OPTIONAL · ANSWERED" not in rendered
    assert "CLARIFICATION QUESTION" in rendered
    assert "PROPOSED READINGS" in rendered
    assert "✓ 2. Staff entrance" in rendered
    assert not any(glyph in rendered for glyph in "┏┓┗┛┌┐└┘")
    assert (
        "class:memcommit.choice.active.focused",
        "✓ 2. Staff entrance\n",
    ) in fragments
    assert (
        "class:memcommit.choice.active",
        "  Use the staff entrance.\n",
    ) in fragments
    assert (
        "class:viewer-body",
        " Which entrance does the rule describe?\n",
    ) in fragments
    assert not any(
        style == "class:viewer-body.focused" for style, _text in fragments
    )
    assert "Different reading" not in rendered
    assert "RESPONSE" not in rendered
    assert "Only during construction." not in rendered


def test_response_choice_owns_the_first_effective_viewport_anchor():
    target = _target()
    draft = ResponseDraft("staff", "")
    state = ResponseFrameState()
    state.sync(target, draft)

    fragments = response_frame_fragments(
        target,
        draft,
        state,
        focused=True,
        content_width=72,
    )
    selected_label = next(
        index
        for index, (_style, text) in enumerate(fragments)
        if "✓ 2. Staff entrance" in text
    )
    anchor = next(
        index
        for index, (style, _text) in enumerate(fragments)
        if style == "[SetCursorPosition]"
    )

    assert selected_label < anchor
