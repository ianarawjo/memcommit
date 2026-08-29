"""Prompt-toolkit key bindings for the named Ground workbench."""

from __future__ import annotations

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import Output

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
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.core.context_targeting.tui.picker import choose_context
from memcommit.adapters.console.commands.ground.named_shell.presentation import (
    _aliased_items,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.fit_coordinator import (
    NamedGroundFitCoordinator,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.state import (
    GroundShellExitStatus,
    NamedGroundShellState,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.turn_controller import (
    NamedGroundTurnController,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.workbench_view import (
    NamedGroundWorkbenchView,
)


def install_named_ground_keybindings(
    bindings: KeyBindings,
    *,
    state: NamedGroundShellState,
    view: NamedGroundWorkbenchView,
    controller: NamedGroundTurnController,
    fit: NamedGroundFitCoordinator,
    app_input: Input | None,
    app_output: Output | None,
    require_tty: bool,
) -> None:
    """Bind keys to the narrow view, turn, and Fit owners."""

    input_mode = Condition(lambda: state.mode == "INPUT")
    inline_editor_mode = Condition(
        lambda: state.mode == "INPUT" and state.inline_target is not None
    )
    panel_comment_mode = Condition(
        lambda: state.mode == "INPUT" and state.panel_comment_target is not None
    )
    normal_input_mode = input_mode & ~inline_editor_mode & ~panel_comment_mode
    approval_mode = Condition(lambda: state.mode == "APPROVAL")
    approval_dialogue_focus = approval_mode & has_focus(view.dialogue_pane.text_area)
    error_mode = Condition(lambda: state.mode == "ERROR")
    action_mode = Condition(lambda: state.mode in {"APPROVAL", "ERROR", "APPLY_ERROR"})
    read_pane_focus = (
        has_focus(view.goal_pane.text_area)
        | has_focus(view.contexts_pane.text_area)
        | has_focus(view.rules_pane.text_area)
        | has_focus(view.cases_pane.text_area)
        | has_focus(view.dialogue_pane.text_area)
    )
    memory_pane_focus = (
        has_focus(view.cases_pane.text_area)
        & ~inline_editor_mode
        & Condition(lambda: bool(_aliased_items(state.current, "CASE")))
    )
    fit_pane_focus = (
        has_focus(view.goal_pane.text_area)
        | has_focus(view.contexts_pane.text_area)
        | has_focus(view.rules_pane.text_area)
        | has_focus(view.cases_pane.text_area)
    ) & ~inline_editor_mode
    memory_detail_focus = memory_pane_focus & Condition(
        lambda: state.memory_detail_open
    )
    rule_draft_focus = (
        input_mode
        & has_focus(view.rules_pane.text_area)
        & Condition(lambda: bool(state.draft_queue))
    )
    stale_rule_draft_focus = rule_draft_focus & Condition(
        lambda: state.draft_queue_stale
    )
    saved_rule_focus = (
        normal_input_mode
        & has_focus(view.rules_pane.text_area)
        & Condition(lambda: not state.draft_queue)
    )
    saved_memory_focus = normal_input_mode & has_focus(view.cases_pane.text_area)
    saved_memory_list_focus = saved_memory_focus & Condition(
        lambda: not state.memory_detail_open
    )
    inline_field_focus = inline_editor_mode & (
        has_focus(view.direct_edit_area) | has_focus(view.input_area)
    )
    placement_pane_focus = normal_input_mode & Condition(
        lambda: view.focused_placement_layer() is not None
    )

    @bindings.add("p", filter=placement_pane_focus, eager=True)
    @bindings.add("P", filter=placement_pane_focus, eager=True)
    def _choose_placement_target(event) -> None:
        layer = view.focused_placement_layer()
        if layer is None:
            return
        options = state.current_placement_options()
        if not options:
            state.status_message = (
                "No ordinary Context names are available for placement."
            )
            event.app.invalidate()
            return

        async def choose() -> None:
            result = await run_in_terminal(
                lambda: choose_context(
                    options,
                    current=(
                        state.placement_choice[layer]
                        if state.placement_choice[layer] in options
                        else options[0]
                    ),
                    app_input=app_input,
                    app_output=app_output,
                    require_tty=require_tty,
                ),
                # Placement opens a synchronous nested picker while the named
                # Ground event loop is active.
                in_executor=True,
            )
            if result is None:
                state.status_message = "Placement selection cancelled."
            else:
                state.placement_choice[layer] = result
                state.placement_overridden[layer] = True
                state.status_message = (
                    f"{layer} placement · {safe_terminal_text(result)} · "
                    "LOCAL UNTIL EXACT COMMAND APPROVAL"
                )
                view.sync_panes(dialogue_anchor="end")
            view.invalidate()

        event.app.create_background_task(choose())

    @bindings.add("tab", filter=normal_input_mode, eager=True)
    def _focus_next(_event) -> None:
        view.cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=normal_input_mode, eager=True)
    def _focus_previous(_event) -> None:
        view.cycle_focus(-1)

    @bindings.add("tab", filter=inline_editor_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=inline_editor_mode, eager=True)
    def _cycle_inline_fields(event) -> None:
        target = (
            view.input_area
            if event.app.layout.has_focus(view.direct_edit_area)
            else view.direct_edit_area
        )
        event.app.layout.focus(target)
        event.app.invalidate()

    @bindings.add("tab", filter=~input_mode, eager=True)
    def _focus_next_modal_pane(_event) -> None:
        view.cycle_read_focus(1)

    @bindings.add(Keys.BackTab, filter=~input_mode, eager=True)
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

    @bindings.add("c", filter=normal_input_mode & read_pane_focus, eager=True)
    def _open_focused_comment(_event) -> None:
        selected = view.focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        controller.open_panel_comment(target=target, focus=focus)

    @bindings.add("enter", filter=saved_memory_list_focus, eager=True)
    def _open_memory_detail(_event) -> None:
        view.open_memory_detail()

    @bindings.add(" ", filter=saved_memory_focus, eager=True)
    def _toggle_memory_use(_event) -> None:
        controller.toggle_memory_use()

    @bindings.add("f", filter=normal_input_mode & fit_pane_focus, eager=True)
    def _run_fit(_event) -> None:
        fit.start(view.require_application(), automatic=False)

    @bindings.add("down", filter=saved_rule_focus, eager=True)
    def _next_saved_rule(_event) -> None:
        view.move_saved_item(kind="RULE", step=1)

    @bindings.add("up", filter=saved_rule_focus, eager=True)
    def _previous_saved_rule(_event) -> None:
        view.move_saved_item(kind="RULE", step=-1)

    @bindings.add("down", filter=saved_memory_list_focus, eager=True)
    def _next_saved_memory(_event) -> None:
        view.move_saved_item(kind="CASE", step=1)

    @bindings.add("up", filter=saved_memory_list_focus, eager=True)
    def _previous_saved_memory(_event) -> None:
        view.move_saved_item(kind="CASE", step=-1)

    @bindings.add("down", filter=rule_draft_focus, eager=True)
    def _next_rule_draft(_event) -> None:
        view.move_rule_draft(1)

    @bindings.add("up", filter=rule_draft_focus, eager=True)
    def _previous_rule_draft(_event) -> None:
        view.move_rule_draft(-1)

    @bindings.add(
        "r",
        filter=rule_draft_focus & ~stale_rule_draft_focus,
        eager=True,
    )
    def _review_rule_draft(_event) -> None:
        controller.review_rule_draft()

    @bindings.add("r", filter=stale_rule_draft_focus, eager=True)
    def _reclassify_rule_drafts(_event) -> None:
        controller.reclassify_rule_drafts()

    @bindings.add(
        "e",
        filter=normal_input_mode & has_focus(view.goal_pane.text_area),
        eager=True,
    )
    def _edit_goal(_event) -> None:
        controller.edit_goal()

    @bindings.add("e", filter=saved_rule_focus, eager=True)
    def _edit_saved_rule(_event) -> None:
        controller.edit_saved_rule()

    @bindings.add("e", filter=saved_memory_focus, eager=True)
    def _edit_saved_memory(_event) -> None:
        controller.edit_saved_memory()

    @bindings.add(
        "enter",
        filter=(
            normal_input_mode & read_pane_focus & ~has_focus(view.cases_pane.text_area)
        ),
        eager=True,
    )
    def _talk_in_focused_pane(_event) -> None:
        selected = view.focused_comment_target()
        if selected is None:
            return
        target, focus = selected
        controller.open_panel_comment(target=target, focus=focus)

    @bindings.add("enter", filter=inline_field_focus, eager=True)
    def _submit_inline(_event) -> None:
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
        filter=(has_focus(view.input_area) & ~inline_editor_mode & ~panel_comment_mode),
        eager=True,
    )
    def _submit(_event) -> None:
        controller.submit_message()

    @bindings.add(
        "c-j",
        filter=(
            (has_focus(view.input_area) & ~inline_editor_mode) | inline_field_focus
        ),
        eager=True,
    )
    def _insert_newline(event) -> None:
        event.app.current_buffer.insert_text("\n")
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

    def exit_view(event, *, status: GroundShellExitStatus) -> None:
        state.deferred_exit_status = status
        if state.fit_turn.request_close():
            state.status_message = (
                "FIT RUNNING · close requested after the receipt boundary"
            )
            event.app.invalidate()
            return
        event.app.exit(result=state.result(status))

    @bindings.add("b", filter=read_pane_focus, eager=True)
    def _back_to_picker(event) -> None:
        # Navigation discards pending review and can never imply approval.
        exit_view(event, status="BACK_TO_PICKER")

    @bind_case_insensitive_key(bindings, "q", filter=read_pane_focus, eager=True)
    def _quit_ground(event) -> None:
        exit_view(event, status="CLOSED")

    bind_session_help(
        bindings,
        filter=read_pane_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="ground-named",
    )

    @bindings.add("escape", eager=True)
    def _close_on_escape(event) -> None:
        dispatch_tui_back(
            event,
            view.collapse_memory_detail,
            controller.collapse_panel_comment,
            controller.collapse_inline_editor,
            close=lambda current_event: exit_view(
                current_event,
                status="CLOSED",
            ),
        )

    @bindings.add("backspace", filter=memory_detail_focus, eager=True)
    def _back_from_memory_detail(event) -> None:
        view.collapse_memory_detail(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _close_anywhere(event) -> None:
        exit_view(event, status="CLOSED")
