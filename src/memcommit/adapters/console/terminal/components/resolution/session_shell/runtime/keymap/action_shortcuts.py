"""Direct semantic-action and sort shortcut bindings."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_action_shortcuts(state: ResolutionKeyBindingState) -> None:
    """Bind Preserve, Defer, Accept, and Sort shortcuts."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    writable_input_focused = controls.writable_input_focused
    semantic_action = controller.semantic_action
    split_viewer_items = options.split_viewer_items
    review_and_apply = options.review_and_apply
    open_final_review = state.review_flow.open_final_review
    toggle_sort = options.toggle_sort
    set_status = controller.set_status
    save_draft = state.editors.save_draft
    current_navigation = controller.navigation
    current_view = controller.current_view
    load_draft = state.editors.load_draft

    def exit_simple(event, kind: str) -> None:
        action = semantic_action(kind)
        if action is not None:
            event.app.exit(result=action)
        else:
            event.app.invalidate()

    @bindings.add("p", filter=~writable_input_focused)
    def _preserve(event) -> None:
        exit_simple(event, "PRESERVE_ALL")

    @bindings.add("d", filter=~writable_input_focused)
    def _defer(event) -> None:
        exit_simple(event, "DEFER")

    @bindings.add("a", filter=~writable_input_focused)
    def _accept(event) -> None:
        if split_viewer_items and review_and_apply:
            open_final_review()
            event.app.invalidate()
            return
        exit_simple(event, "ACCEPT")

    @bindings.add("s", filter=~writable_input_focused)
    def _sort(event) -> None:
        if toggle_sort is None:
            set_status("Sorting is unavailable here.")
        else:
            save_draft()
            toggle_sort()
            current_navigation.sync(current_view())
            load_draft()
            set_status("")
        event.app.invalidate()
