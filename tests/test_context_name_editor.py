"""Contracts for the operation-neutral exact Context-name control."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.context_targeting.tui.name_editor import (
    ContextParentLocatorControl,
    ContextParentLocatorState,
    ContextNameView,
    choose_context_name,
    suggest_fresh_context_name,
)


def test_generic_name_view_has_no_save_location_semantics() -> None:
    view = ContextNameView(value="draft")

    assert view.label == "CONTEXT NAME"
    assert "Save" not in view.detail
    assert view.validate_value("final") == "final"


def test_name_editor_submits_a_prefilled_validated_name() -> None:
    validated: list[str] = []
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("-pilot\r")
        result = choose_context_name(
            ContextNameView(
                value="new-context",
                label="NEW CONTEXT NAME",
                state="NOT CREATED",
                validate=validated.append,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == "new-context-pilot"
    assert validated == ["new-context-pilot"]


def test_name_editor_reuses_parent_locator_and_preserves_leaf() -> None:
    with create_pipe_input() as pipe_input:
        # Direct input starts focused. Up enters the parent locator, Up moves
        # to practice, Enter reparents, and the final Enter submits the name.
        pipe_input.send_text("\x1b[A\x1b[A\r\r")
        result = choose_context_name(
            ContextNameView(
                value="task-1/description/atomized",
                context_names=("practice", "task-1/description"),
                current_context="practice",
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == "practice/atomized"


def test_parent_locator_can_reparent_without_owning_a_name_field() -> None:
    view = ContextNameView(
        value="task-1/description/atomized",
        context_names=("practice", "task-1/description"),
        current_context="practice",
    )
    state = ContextParentLocatorState.create(view)
    assert state is not None
    locator = ContextParentLocatorControl.create(state)

    locator.move(-1)

    assert locator.choose_parent(view.value) == "practice/atomized"
    assert not hasattr(locator, "input")


def test_fresh_name_suggestion_is_case_insensitive_and_editable() -> None:
    assert (
        suggest_fresh_context_name(
            "new-context",
            ["New-Context", "new-context-2"],
        )
        == "new-context-3"
    )
