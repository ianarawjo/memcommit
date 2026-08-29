"""Save Location input and parent-tree key bindings."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prompt_toolkit.filters import has_focus
from prompt_toolkit.keys import Keys

from memcommit.adapters.console.terminal.components.save_location import (
    SaveLocationEditorState,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_destination_keys(
    state: ResolutionKeyBindingState,
) -> Callable[[Any], None]:
    """Bind destination submission, tree browsing, and cancellation."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    destination_input = controls.destination_input
    destination_tree_control = controls.destination_tree_control
    destination_action = controller.destination_action
    destination_editor_state = controller.destination_editor_state
    set_status = controller.set_status
    use_destination_parent = state.editors.use_destination_parent
    destination_editing = controller.destination_editing
    destination = state.options.destination
    destination_frame = controls.destination_frame
    session_navigation = controller.session_navigation
    destination_control = controls.destination_control

    @bindings.add("enter", filter=has_focus(destination_input), eager=True)
    def _submit_destination(event) -> None:
        action = destination_action(destination_input.text.strip())
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("up", filter=has_focus(destination_input), eager=True)
    def _browse_destination_parents(event) -> None:
        if destination_editor_state["value"] is None:
            set_status("No parent Context catalog is available here.")
        else:
            event.app.layout.focus(destination_tree_control)
            set_status("Choose a parent Context with arrows, then press Enter.")
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(destination_tree_control), eager=True)
    @bindings.add("up", filter=has_focus(destination_tree_control), eager=True)
    def _move_destination_parent(event) -> None:
        state = destination_editor_state["value"]
        if state is not None:
            delta = -1 if event.key_sequence[0].key == Keys.Up else 1
            state.tree.move(delta)
            set_status("")
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(destination_tree_control), eager=True)
    def _use_destination_parent(event) -> None:
        use_destination_parent()
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(destination_input), eager=True)
    def _reject_destination_newline(event) -> None:
        set_status("A Context name must stay on one line.")
        event.app.invalidate()

    @bindings.add("escape", filter=has_focus(destination_input), eager=True)
    def _cancel_destination_edit(event) -> None:
        destination_editing["value"] = False
        destination_editor_state["value"] = (
            SaveLocationEditorState.create(destination)
            if destination is not None
            else None
        )
        if destination is not None:
            destination_frame.title = safe_terminal_text(destination.label)
        session_navigation.focus("save_location")
        event.app.layout.focus(destination_control)
        set_status("")
        event.app.invalidate()

    return _cancel_destination_edit
