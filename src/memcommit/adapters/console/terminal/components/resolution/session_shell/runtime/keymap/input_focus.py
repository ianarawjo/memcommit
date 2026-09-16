"""Tab focus transitions for writable Resolution Session controls."""

from __future__ import annotations

from prompt_toolkit.filters import has_focus

from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_input_focus(state: ResolutionKeyBindingState) -> None:
    """Bind Tab transitions between inputs and their owning read-only Surface."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    input_area = controls.input_area
    destination_input = controls.destination_input
    destination_tree_control = controls.destination_tree_control
    destination_editor_state = controller.destination_editor_state
    set_status = controller.set_status
    destination_tree_is_focused = controls.destination_tree_is_focused
    global_comment = controller.global_comment
    response_validator = options.response_validator
    global_response_draft = controller.global_response_draft
    save_draft = state.editors.save_draft
    other_direction_editor = controller.other_direction_editor
    response_state = controller.response_state
    split_viewer_items = options.split_viewer_items
    session_navigation = controller.session_navigation
    responses_control = controls.responses_control
    body_control = controls.body_control

    editor_tab_focused = (
        has_focus(input_area)
        | has_focus(destination_input)
        | has_focus(destination_tree_control)
    )

    @bindings.add("tab", filter=editor_tab_focused, eager=True)
    @bindings.add("s-tab", filter=editor_tab_focused, eager=True)
    def _focus_input(event) -> None:
        if event.app.layout.has_focus(destination_input):
            if destination_editor_state["value"] is not None:
                event.app.layout.focus(destination_tree_control)
                set_status("Choose a parent Context with arrows, then press Enter.")
            else:
                set_status("Press Enter to save this location or Escape to cancel.")
            event.app.invalidate()
            return
        if destination_tree_is_focused():
            event.app.layout.focus(destination_input)
            set_status("Edit the exact Context name, then press Enter to save.")
            event.app.invalidate()
            return
        if event.app.layout.has_focus(input_area):
            if global_comment["value"]:
                if response_validator is not None:
                    try:
                        response_validator(input_area.text)
                    except (TypeError, ValueError) as error:
                        set_status(str(error))
                        event.app.invalidate()
                        return
                global_response_draft["value"] = ResponseDraft(None, input_area.text)
            else:
                if not save_draft():
                    event.app.invalidate()
                    return
            other_direction_editor["open"] = False
            response_state.editing = False
            if split_viewer_items:
                session_navigation.focus("responses")
                event.app.layout.focus(responses_control)
            else:
                event.app.layout.focus(body_control)
            event.app.invalidate()
            return
