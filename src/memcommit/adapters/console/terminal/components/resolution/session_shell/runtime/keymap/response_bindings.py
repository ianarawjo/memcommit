"""Response-selection, comment, and writable-response key bindings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prompt_toolkit.filters import has_focus

from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_response_keys(
    state: ResolutionKeyBindingState,
    close_session: Callable[[Any], None],
) -> None:
    """Bind response entry, submission, and comment shortcuts."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    writable_input_focused = controls.writable_input_focused
    split_viewer_items = options.split_viewer_items
    current_view = controller.current_view
    focused_impact_comment_item = controls.focused_impact_comment_item
    set_status = controller.set_status
    current_navigation = controller.navigation
    open_split_item = state.review_flow.open_split_item
    open_item_input = state.editors.open_item_input
    split_kind = controls.split_kind
    viewer_content = controller.viewer_content
    other_direction_editor = controller.other_direction_editor
    current_response_heading = state.editors.current_response_heading
    open_global_input = state.editors.open_global_input
    global_comment = controller.global_comment
    composer = controls.composer
    input_heading = controller.input_heading
    input_area = controls.input_area
    submit = state.review_flow.submit
    load_draft = state.editors.load_draft
    global_response_draft = controller.global_response_draft
    response_state = controller.response_state
    response_visible = controls.response_visible
    session_navigation = controller.session_navigation
    responses_control = controls.responses_control
    body_control = controls.body_control
    _close = close_session

    @bindings.add("escape", filter=has_focus(input_area), eager=True)
    def _cancel_response_edit(event) -> None:
        if not split_viewer_items:
            _close(event)
            return
        if global_comment["value"]:
            input_area.text = global_response_draft["value"].text
        else:
            load_draft()
        response_state.editing = False
        other_direction_editor["open"] = False
        if split_viewer_items and response_visible():
            session_navigation.focus("responses")
            event.app.layout.focus(responses_control)
        else:
            session_navigation.focus("viewer")
            event.app.layout.focus(body_control)
        set_status("Response edit cancelled.")
        event.app.invalidate()

    @bindings.add("c", filter=~writable_input_focused)
    def _comment_item(event) -> None:
        if not split_viewer_items:
            return
        active_view = current_view()
        impact_item = focused_impact_comment_item()
        if impact_item is not None:
            if (
                active_view.input_locked
                or "SUBMIT_ITEM" not in active_view.capabilities
            ):
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            current_navigation.selected_item_uid = impact_item.uid
            current_navigation.sync(active_view)
            open_split_item(impact_item.uid)
            open_item_input(title="COMMENT ON THIS CHANGE")
            event.app.invalidate()
            return
        if split_kind() == "RESOLVE_ALL":
            if active_view.input_locked or "SUBMIT_ALL" not in active_view.capabilities:
                set_status("Whole-set guidance is unavailable here.")
                event.app.invalidate()
                return
            open_global_input(clear=True)
            return
        if split_kind() != "ITEM":
            set_status("Choose one review item or RESOLVE ALL first.")
            event.app.invalidate()
            return
        if viewer_content["kind"] != "ITEM":
            set_status("Press Enter to open the selected review item first.")
            event.app.invalidate()
            return
        if active_view.input_locked or "SUBMIT_ITEM" not in active_view.capabilities:
            set_status("Item comments are unavailable here.")
            event.app.invalidate()
            return
        other_direction_editor["open"] = True
        open_item_input(title=current_response_heading())

    @bindings.add("g", filter=~writable_input_focused)
    def _global_comment(event) -> None:
        active_view = current_view()
        if "SUBMIT_ALL" not in active_view.capabilities:
            set_status("Whole-set comments are unavailable here.")
            event.app.invalidate()
            return
        if active_view.input_locked:
            set_status("Resolution input is locked while analysis is pending.")
            event.app.invalidate()
            return
        if split_viewer_items:
            open_global_input(clear=True)
        else:
            global_comment["value"] = True
            other_direction_editor["open"] = False
            composer.frame.title = "WHOLE-SET COMMENT"
            input_heading["value"] = "WHOLE-SET GUIDANCE"
            input_area.text = ""
            event.app.layout.focus(input_area)

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    @bindings.add("c-s", filter=has_focus(input_area), eager=True)
    @bindings.add("f2", filter=has_focus(input_area), eager=True)
    def _submit_input(event) -> None:
        submit(event)

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()
