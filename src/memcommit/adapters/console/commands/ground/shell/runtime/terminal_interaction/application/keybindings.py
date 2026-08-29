"""Prompt-toolkit key bindings for the blank Ground workbench."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.ground.shell.runtime.session import (
    GroundShellState,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.turn_controller import (
    BlankGroundTurnController,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.workbench_view import (
    BlankGroundWorkbenchView,
)
from memcommit.adapters.console.terminal.components.context_picker import choose_context
from memcommit.adapters.console.terminal.components.exact_command_review import (
    bind_exact_command_approval,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    scroll_wrapped_page,
)
from memcommit.adapters.console.terminal.components.session_help import (
    bind_session_help,
)
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)


def install_blank_ground_keybindings(
    bindings: KeyBindings,
    *,
    state: GroundShellState,
    view: BlankGroundWorkbenchView,
    controller: BlankGroundTurnController,
    choose_save_location: Callable[[str | None], str | None] | None,
    app_input: Input | None,
    app_output: Output | None,
    require_tty: bool,
) -> None:
    """Bind keys to the narrow view and turn/coordinator owners."""

    input_mode = Condition(lambda: state.mode == "INPUT")
    context_selection_mode = Condition(lambda: state.mode == "CONTEXT_SELECTION")
    inline_goal_mode = Condition(
        lambda: state.mode == "INPUT" and state.inline_goal_open
    )
    inline_context_mode = Condition(
        lambda: state.mode in {"INPUT", "CONTEXT_SELECTION"}
        and state.inline_context_open
    )
    inline_edit_mode = inline_goal_mode | inline_context_mode
    panel_comment_mode = Condition(
        lambda: state.mode in {"INPUT", "CONTEXT_SELECTION"}
        and state.panel_comment_target is not None
    )
    normal_input_mode = input_mode & ~inline_edit_mode & ~panel_comment_mode
    navigation_mode = (
        (normal_input_mode | context_selection_mode)
        & ~inline_edit_mode
        & ~panel_comment_mode
    )
    approval_mode = Condition(lambda: state.mode == "APPROVAL")
    approval_dialogue_focus = approval_mode & has_focus(view.dialogue_pane.text_area)
    error_mode = Condition(lambda: state.mode == "ERROR")
    action_mode = Condition(lambda: state.mode in {"APPROVAL", "ERROR", "APPLY_ERROR"})
    read_pane_focus = (
        has_focus(view.location_pane.text_area)
        | has_focus(view.goal_pane.text_area)
        | has_focus(view.contexts_pane.text_area)
        | has_focus(view.rules_pane.text_area)
        | has_focus(view.cases_pane.text_area)
        | has_focus(view.dialogue_pane.text_area)
    )
    memory_pane_focus = (
        has_focus(view.cases_pane.text_area)
        & ~inline_edit_mode
        & Condition(lambda: bool(state.memory_drafts))
    )
    memory_table_focus = memory_pane_focus & Condition(
        lambda: state.memory_view == "TABLE"
    )
    inline_field_focus = inline_edit_mode & (
        has_focus(view.direct_edit_area) | has_focus(view.input_area)
    )
    context_candidate_focus = (
        navigation_mode
        & has_focus(view.contexts_pane.text_area)
        & Condition(lambda: bool(view.ordered_context_rows()))
        & Condition(lambda: not state.context_selection_finished)
    )
    finished_context_focus = (
        (input_mode | approval_mode)
        & has_focus(view.contexts_pane.text_area)
        & Condition(
            lambda: bool(view.ordered_context_rows())
            or bool(state.local_new_context_name)
        )
        & Condition(lambda: state.context_selection_finished)
    )
    approval_context_add_focus = (
        approval_mode
        & has_focus(view.contexts_pane.text_area)
        & Condition(lambda: not state.context_selection_finished)
        & Condition(
            lambda: (
                view.context_cursor_row() is not None
                and view.context_cursor_row().kind == "ADD_NEW"
            )
        )
    )
    location_focus = has_focus(view.location_pane.text_area)
    location_edit_available = (
        (input_mode | approval_mode)
        & read_pane_focus
        & ~inline_edit_mode
        & ~panel_comment_mode
    )

    def choose_or_change_save_location(event) -> None:
        state.acknowledge_pane("LOCATION")
        if choose_save_location is None:
            state.status_message = (
                "Save Location editing is unavailable in this adapter."
            )
            event.app.invalidate()
            return

        async def choose() -> None:
            result = await run_in_terminal(
                lambda: choose_save_location(state.planned_ground_name),
                in_executor=True,
            )
            controller.select_save_location(result)

        event.app.create_background_task(choose())

    @bindings.add("l", filter=location_edit_available, eager=True)
    @bindings.add("L", filter=location_edit_available, eager=True)
    def _choose_or_change_save_location(event) -> None:
        choose_or_change_save_location(event)

    @bindings.add(
        "enter",
        filter=location_edit_available & location_focus,
        eager=True,
    )
    def _expand_focused_save_location(event) -> None:
        choose_or_change_save_location(event)

    @bindings.add("tab", filter=navigation_mode, eager=True)
    def _focus_next(_event) -> None:
        view.cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=navigation_mode, eager=True)
    def _focus_previous(_event) -> None:
        view.cycle_focus(-1)

    @bindings.add("tab", filter=inline_edit_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=inline_edit_mode, eager=True)
    def _cycle_inline_edit_fields(event) -> None:
        target = (
            view.input_area
            if event.app.layout.has_focus(view.direct_edit_area)
            else view.direct_edit_area
        )
        event.app.layout.focus(target)
        event.app.invalidate()

    @bindings.add(
        "tab",
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_next_modal_pane(_event) -> None:
        view.cycle_read_focus(1)

    @bindings.add(
        Keys.BackTab,
        filter=~navigation_mode & ~inline_edit_mode & ~panel_comment_mode,
        eager=True,
    )
    def _focus_previous_modal_pane(_event) -> None:
        view.cycle_read_focus(-1)

    @bindings.add(Keys.PageDown, filter=read_pane_focus, eager=True)
    def _page_down(event) -> None:
        view.acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=1)

    @bindings.add(Keys.PageUp, filter=read_pane_focus, eager=True)
    def _page_up(event) -> None:
        view.acknowledge_focused_read_pane()
        scroll_wrapped_page(event, direction=-1)

    @bindings.add("c", filter=navigation_mode & read_pane_focus, eager=True)
    def _open_focused_comment(_event) -> None:
        selected = view.focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        controller.open_panel_comment(target=target, focus=focus)

    @bindings.add("v", filter=memory_pane_focus, eager=True)
    def _toggle_memory_view(_event) -> None:
        view.toggle_memory_view()

    @bindings.add("down", filter=memory_table_focus, eager=True)
    def _next_memory_table_row(_event) -> None:
        view.move_memory_table_cell(row_step=1)

    @bindings.add("up", filter=memory_table_focus, eager=True)
    def _previous_memory_table_row(_event) -> None:
        view.move_memory_table_cell(row_step=-1)

    @bindings.add("right", filter=memory_table_focus, eager=True)
    def _next_memory_table_column(_event) -> None:
        view.move_memory_table_cell(column_step=1)

    @bindings.add("left", filter=memory_table_focus, eager=True)
    def _previous_memory_table_column(_event) -> None:
        view.move_memory_table_cell(column_step=-1)

    @bindings.add("down", filter=context_candidate_focus, eager=True)
    def _next_context_candidate(_event) -> None:
        view.move_context_candidate(1)

    @bindings.add("up", filter=context_candidate_focus, eager=True)
    def _previous_context_candidate(_event) -> None:
        view.move_context_candidate(-1)

    @bindings.add(" ", filter=context_candidate_focus, eager=True)
    def _toggle_context_candidate(_event) -> None:
        controller.toggle_context_candidate()

    @bindings.add("p", filter=context_candidate_focus, eager=True)
    @bindings.add("P", filter=context_candidate_focus, eager=True)
    def _direct_context_picker(event) -> None:
        if not view.context_catalog_names:
            state.status_message = "No ordinary Context names are available."
            event.app.invalidate()
            return

        async def choose() -> None:
            selected = state.selected_context_names
            result = await run_in_terminal(
                lambda: choose_context(
                    view.context_catalog_names,
                    current=(
                        selected[-1]
                        if selected and selected[-1] in view.context_catalog_names
                        else view.current_context_name
                    ),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=require_tty,
                ),
                # The nested synchronous prompt-toolkit Application must not
                # call asyncio.run() on the outer Ground event loop.
                in_executor=True,
            )
            controller.accept_direct_context_selection(result)

        event.app.create_background_task(choose())

    @bindings.add("n", filter=context_candidate_focus, eager=True)
    def _edit_context_name_plan(_event) -> None:
        controller.edit_context_name_plan()

    @bindings.add("f", filter=context_candidate_focus, eager=True)
    def _finish_context_selection(_event) -> None:
        controller.finish_context_selection()

    @bindings.add("f", filter=finished_context_focus, eager=True)
    def _reopen_context_selection(_event) -> None:
        controller.reopen_context_selection()

    @bindings.add("n", filter=approval_context_add_focus, eager=True)
    def _open_add_context_from_approval(_event) -> None:
        controller.open_add_context_from_approval()

    @bindings.add(
        "enter",
        filter=(
            navigation_mode & read_pane_focus & ~has_focus(view.location_pane.text_area)
        ),
        eager=True,
    )
    def _talk_in_focused_pane(_event) -> None:
        selected = view.focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        controller.open_panel_comment(target=target, focus=focus)

    @bindings.add(
        "e",
        filter=normal_input_mode & has_focus(view.goal_pane.text_area),
        eager=True,
    )
    def _open_goal_editor(_event) -> None:
        controller.open_inline_goal()

    @bindings.add("enter", filter=inline_field_focus, eager=True)
    def _submit_inline_edit(_event) -> None:
        controller.finish_inline_submission()

    @bindings.add(
        "enter",
        filter=panel_comment_mode & has_focus(view.input_area),
        eager=True,
    )
    def _submit_panel_comment(_event) -> None:
        controller.finish_panel_comment()

    @bindings.add(
        "enter",
        filter=(has_focus(view.input_area) & ~inline_edit_mode & ~panel_comment_mode),
        eager=True,
    )
    def _submit(_event) -> None:
        controller.submit_message()

    @bindings.add(
        "c-j",
        filter=(
            (has_focus(view.input_area) & ~inline_edit_mode)
            | (inline_goal_mode & inline_field_focus)
            | (inline_context_mode & has_focus(view.input_area))
        ),
        eager=True,
    )
    def _insert_newline(event) -> None:
        event.app.current_buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add(
        "c-j",
        filter=inline_context_mode & has_focus(view.direct_edit_area),
        eager=True,
    )
    def _reject_newline_in_context_name(event) -> None:
        state.status_message = (
            "Context names are one line; press Tab to add a multiline comment."
        )
        event.app.invalidate()

    @bind_exact_command_approval(
        bindings,
        filter=approval_dialogue_focus,
        legacy_a_filter=approval_mode,
        eager=True,
    )
    def _approve(_event) -> None:
        controller.approve()

    @bindings.add("up", filter=approval_dialogue_focus, eager=True)
    @bindings.add("left", filter=approval_dialogue_focus, eager=True)
    def _show_command(_event) -> None:
        controller.show_review("COMMAND")

    @bindings.add("down", filter=approval_dialogue_focus, eager=True)
    @bindings.add("right", filter=approval_dialogue_focus, eager=True)
    def _show_effects(_event) -> None:
        controller.show_review("EFFECTS")

    @bindings.add("e", filter=action_mode, eager=True)
    def _refine(_event) -> None:
        controller.refine()

    @bindings.add("r", filter=error_mode, eager=True)
    def _retry(_event) -> None:
        controller.retry()

    @bindings.add("b", filter=read_pane_focus, eager=True)
    def _back_to_picker(event) -> None:
        controller.back_to_picker(event)

    @bind_case_insensitive_key(bindings, "q", filter=read_pane_focus, eager=True)
    def _quit_ground(event) -> None:
        controller.cancel(event)

    bind_session_help(
        bindings,
        filter=read_pane_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="ground",
    )

    @bindings.add("escape", eager=True)
    def _cancel_on_escape(event) -> None:
        dispatch_tui_back(
            event,
            controller.collapse_panel_comment,
            controller.collapse_inline_context,
            controller.collapse_inline_goal,
            controller.restore_suspended_context_approval,
            close=controller.cancel,
        )

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _cancel_anywhere(event) -> None:
        controller.cancel(event)
