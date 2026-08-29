"""Paging, directional movement, and Viewer-copy key bindings."""

from __future__ import annotations

from prompt_toolkit.filters import has_focus

from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    copy_plain_text,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    _impact_arrow_expansion,
    _stacked_horizontal_key_message,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def bind_navigation_keys(state: ResolutionKeyBindingState) -> None:
    """Bind keys that move through or copy the active semantic surface."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    navigation_accelerator = state.navigation_accelerator
    move = state.review_flow.move
    writable_input_focused = controls.writable_input_focused
    current_viewer_plain_text = controls.current_viewer_plain_text
    set_status = controller.set_status
    body_control = controls.body_control
    split_kind = controls.split_kind
    destination_editor_state = controller.destination_editor_state
    destination_tree_is_focused = controls.destination_tree_is_focused
    impact_reason_expanded = controller.impact_reason_expanded
    focused_impact_entry_uid = controls.focused_impact_entry_uid
    global_strategies = options.global_strategies
    strategy = controller.strategy
    split_viewer_items = options.split_viewer_items
    save_draft = state.editors.save_draft
    current_navigation = controller.navigation
    current_view = controller.current_view
    load_draft = state.editors.load_draft

    @bindings.add("pagedown", filter=~writable_input_focused)
    def _page_down(event) -> None:
        # Once results are independent sections, a page step advances several
        # short result blocks instead of trying to display one 234-result
        # monolith. Down still advances one block at a time.
        navigation_accelerator.reset()
        move(8)
        event.app.invalidate()

    @bindings.add("pageup", filter=~writable_input_focused)
    def _page_up(event) -> None:
        navigation_accelerator.reset()
        move(-8)
        event.app.invalidate()

    @bindings.add("end", filter=~writable_input_focused)
    def _end(event) -> None:
        navigation_accelerator.reset()
        move(1_000_000)
        event.app.invalidate()

    @bindings.add("home", filter=~writable_input_focused)
    def _home(event) -> None:
        navigation_accelerator.reset()
        move(-1_000_000)
        event.app.invalidate()

    def copy_current_viewer(event, *, whole_document: bool) -> None:
        copied = copy_plain_text(
            current_viewer_plain_text(whole_document=whole_document),
            success_message=(
                "complete current document"
                if whole_document
                else "focused semantic unit"
            ),
        )
        set_status(copied.message)
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(body_control), eager=True)
    def _copy_focused_viewer(event) -> None:
        copy_current_viewer(event, whole_document=False)

    @bindings.add("Y", filter=has_focus(body_control), eager=True)
    def _copy_complete_viewer(event) -> None:
        copy_current_viewer(event, whole_document=True)

    def explain_unused_split_horizontal_key() -> None:
        """Make stacked-frame horizontal no-ops explicit instead of silent."""

        set_status(_stacked_horizontal_key_message(split_kind()))

    @bindings.add("right", filter=~writable_input_focused)
    def _right(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.expand_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                impact_reason_expanded["uid"] = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=True,
                )
                set_status("Impact rationale shown.")
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = min(
                    strategy["index"] + 1,
                    len(global_strategies) - 1,
                )
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), 1)
        load_draft()
        event.app.invalidate()

    @bindings.add("left", filter=~writable_input_focused)
    def _left(event) -> None:
        state = destination_editor_state["value"]
        if destination_tree_is_focused() and state is not None:
            state.tree.collapse_selected()
            set_status("")
            event.app.invalidate()
            return
        if split_viewer_items:
            impact_uid = focused_impact_entry_uid()
            if impact_uid is not None:
                collapsed = _impact_arrow_expansion(
                    impact_reason_expanded["uid"],
                    impact_uid,
                    expand=False,
                )
                if collapsed != impact_reason_expanded["uid"]:
                    set_status("Impact rationale hidden.")
                impact_reason_expanded["uid"] = collapsed
            elif split_kind() == "RESOLVE_ALL" and global_strategies:
                strategy["index"] = max(strategy["index"] - 1, 0)
            else:
                explain_unused_split_horizontal_key()
            event.app.invalidate()
            return
        save_draft()
        current_navigation.move_item(current_view(), -1)
        load_draft()
        event.app.invalidate()
