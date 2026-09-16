"""Layered back navigation and terminal-session closing bindings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_back_navigation(
    state: ResolutionKeyBindingState,
    cancel_destination_edit: Callable[[Any], None],
) -> Callable[[Any], None]:
    """Bind layered Escape/Backspace retreat and explicit session close keys."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    input_area = controls.input_area
    split_viewer_items = options.split_viewer_items
    session_navigation = controller.session_navigation
    response_state = controller.response_state
    set_status = controller.set_status
    viewer_controller = state.viewer_controller
    expanded_memory_section_uid = controller.expanded_memory_section_uid
    current_navigation = controller.navigation
    save_draft_on_close = options.save_draft_on_close
    save_draft = state.editors.save_draft
    writable_input_focused = controls.writable_input_focused
    destination_tree_is_focused = controls.destination_tree_is_focused
    _cancel_destination_edit = cancel_destination_edit
    viewer_content = controller.viewer_content
    close_final_review = state.review_flow.close_final_review
    set_viewer_content = controls.set_viewer_content
    reset_viewer_section = controls.reset_viewer_section
    items_control = controls.items_control

    def _collapse_detail(event) -> bool:
        if event.app.layout.has_focus(input_area):
            return False
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            return True
        if viewer_controller.close_nested():
            set_status("")
            return True
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            return True
        if current_navigation.expanded_item_uid is None:
            return False
        current_navigation.close_detail()
        return True

    def _close(event) -> None:
        if (
            save_draft_on_close
            and not event.app.layout.has_focus(input_area)
            and not save_draft()
        ):
            event.app.invalidate()
            return
        event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

    @bindings.add("escape", filter=~writable_input_focused, eager=True)
    @bindings.add("backspace", filter=~writable_input_focused, eager=True)
    def _back_or_close(event) -> None:
        if destination_tree_is_focused():
            _cancel_destination_edit(event)
            return
        if (
            split_viewer_items
            and session_navigation.pane == "responses"
            and response_state.close_nested()
        ):
            set_status("")
            event.app.invalidate()
            return
        if viewer_controller.close_nested():
            set_status("")
            event.app.invalidate()
            return
        if expanded_memory_section_uid["uid"] is not None:
            expanded_memory_section_uid["uid"] = None
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items and viewer_content["kind"] == "REVIEW":
            close_final_review()
            event.app.invalidate()
            return
        if (
            split_viewer_items
            and not event.app.layout.has_focus(input_area)
            and session_navigation.row_index != 0
        ):
            session_navigation.row_index = 0
            set_viewer_content("REPORT")
            reset_viewer_section()
            current_navigation.close_detail()
            session_navigation.focus("items")
            event.app.layout.focus(items_control)
            event.app.invalidate()
            return
        # Keep the shared shell independent of operation-specific back
        # dispatchers: its only presentation layer is the expanded detail.
        if _collapse_detail(event):
            event.app.invalidate()
            return
        _close(event)

    @bind_case_insensitive_key(
        bindings, "q", filter=~writable_input_focused, eager=True
    )
    @bindings.add("c-c", eager=True)
    def _quit(event) -> None:
        _close(event)

    return _close
