"""Contracts for the operation-neutral exact Context-name control."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    ContextParentLocatorControl,
    ContextParentLocatorState,
    ContextNameView,
    choose_context_name,
    suggest_fresh_context_name,
)
from memcommit.core.context_targeting.tui.name_draft import ContextNameDraftState


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


def test_name_editor_preserves_a_directly_edited_path_after_parent_choice() -> None:
    with create_pipe_input() as pipe_input:
        # Replace the complete exact path, open the parent locator, move from
        # beta to alpha, and choose it. The edited field remains authoritative.
        pipe_input.send_text("\x15aaa/bbb\x1b[A\x1b[A\r\r")
        result = choose_context_name(
            ContextNameView(
                value="new-context",
                context_names=("alpha", "beta"),
                current_context="beta",
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == "aaa/bbb"


def test_context_name_draft_shares_suggestion_and_parent_inheritance() -> None:
    draft = ContextNameDraftState("alpha/branch", parent_name="alpha")

    assert draft.inherit_suggestion("beta/branch", parent_name="beta") == (
        "beta/branch"
    )
    assert draft.choose_parent("project") == "project/branch"

    draft.record_direct_edit("custom/aaa/bbb")

    assert draft.inherit_suggestion("alpha/branch", parent_name="alpha") == (
        "custom/aaa/bbb"
    )
    assert draft.parent_name == "project"
    assert draft.choose_parent("practice") == "custom/aaa/bbb"
    assert draft.parent_name == "practice"


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
