"""Enter-key activation semantics for Resolution Session Surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
)
from memcommit.persistence.command_ledger.study_actions import record_study_action

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    session_todo_view,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


def build_surface_activation(
    state: ResolutionKeyBindingState,
) -> Callable[[Any], None]:
    """Build the Enter action shared by focus-Surface and legacy bindings."""

    controller = state.controller
    controls = state.controls
    editors = state.editors
    review_flow = state.review_flow
    options = state.options
    current_navigation = controller.navigation
    session_navigation = controller.session_navigation
    current_view = controller.current_view
    current_item_handoff = controller.current_item_handoff
    sync_response_state = controller.sync_response_state
    set_status = controller.set_status
    viewer_content = controller.viewer_content
    impact_reason_expanded = controller.impact_reason_expanded
    other_direction = controller.other_direction
    other_direction_editor = controller.other_direction_editor
    response_state = controller.response_state
    expanded_memory_section_uid = controller.expanded_memory_section_uid
    local_drafts = controller.local_drafts
    split_viewer_items = options.split_viewer_items
    read_only = options.read_only
    read_only_handoff = options.read_only_handoff
    global_strategies = options.global_strategies
    review_and_apply = options.review_and_apply
    report_apply = controller.report_apply
    draft_saver = options.draft_saver
    split_kind = controls.split_kind
    active_viewer_sections = controls.active_viewer_sections
    report_sections = controls.report_sections
    viewer_section_index = controls.viewer_section_index
    set_viewer_content = controls.set_viewer_content
    reset_viewer_section = controls.reset_viewer_section
    destination_tree_is_focused = controls.destination_tree_is_focused
    body_control = controls.body_control
    todo_control = controls.todo_control
    viewer_controller = state.viewer_controller
    save_draft = editors.save_draft
    open_item_input = editors.open_item_input
    open_global_input = editors.open_global_input
    open_destination_input = editors.open_destination_input
    use_destination_parent = editors.use_destination_parent
    current_response_heading = editors.current_response_heading
    open_split_item = review_flow.open_split_item
    close_final_review = review_flow.close_final_review
    open_final_review = review_flow.open_final_review
    approved_final_review_action = review_flow.approved_final_review_action

    def _open_or_choose(event) -> None:
        active_view = current_view()
        if split_viewer_items:
            kind = split_kind()
            if kind == "RESPONSES":
                target = sync_response_state()
                item = current_navigation.current_item(active_view)
                if target is not None and target.item_uid == "WHOLE_SET":
                    if not target.editable:
                        set_status("Whole-set guidance is read-only.")
                    else:
                        open_global_input()
                elif target is None or item is None or target.item_uid != item.uid:
                    set_status("No item response is available here.")
                elif response_state.option_navigation_active and not target.editable:
                    set_status("This response is read-only.")
                elif response_state.option_navigation_active:
                    draft = response_state.toggle_current_choice(target)
                    local_drafts[item.uid] = draft
                    current_navigation.selected_option_uid = draft.selected_choice_uid
                    if draft_saver is not None:
                        draft_saver(
                            item.uid,
                            draft.selected_choice_uid,
                            draft.text,
                        )
                    if draft.selected_choice_uid is None:
                        set_status("Selection cleared.")
                    else:
                        set_status(
                            "Selected · ✓ "
                            + target.choice(draft.selected_choice_uid).label
                        )
                elif response_state.section == "DECISION":
                    # A choice-bearing Decision is always directly focusable.
                    # This fallback is only reachable for a prompt-only target.
                    response_state.focus_response()
                    set_status("Move to Response and press Enter to answer.")
                elif not target.editable:
                    set_status("This response is read-only.")
                else:
                    open_item_input(title=current_response_heading())
                event.app.invalidate()
                return
            if kind == "REPORT":
                if (
                    session_navigation.pane == "viewer"
                    and viewer_content["kind"] == "REPORT"
                ):
                    sections = active_viewer_sections()
                    section = sections[viewer_section_index()]
                    if section.kind == "IMPACT_GROUP":
                        controller.unchanged_effects_expanded = (
                            not controller.unchanged_effects_expanded
                        )
                        set_status("")
                        event.app.invalidate()
                        return
                    if section.kind == "IMPACT_ENTRY":
                        impact_reason_expanded["uid"] = (
                            None
                            if impact_reason_expanded["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "" if controls.config.effect_report is not None else (
                                "Impact rationale hidden."
                                if impact_reason_expanded["uid"] is None
                                else "Impact rationale shown."
                            )
                        )
                        event.app.invalidate()
                        return
                    if controls.config.effect_report is not None:
                        # The instruction is a reading stop, never an implicit
                        # approval or a route to the hidden legacy Items frame.
                        event.app.invalidate()
                        return
                    if section.kind == "REPORT_APPLY":
                        session_navigation.focus("todo")
                        event.app.layout.focus(todo_control)
                        set_status("")
                        event.app.invalidate()
                        return
                    if section.kind in {"REVIEW_AND_APPLY", "RESOLVE_ALL"}:
                        open_final_review()
                        event.app.invalidate()
                        return
                other_direction_editor["open"] = False
                set_viewer_content("REPORT")
                reset_viewer_section()
                session_navigation.open_selected(report_sections())
                event.app.layout.focus(body_control)
                set_status("")
            elif kind == "SAVE_LOCATION":
                if destination_tree_is_focused():
                    use_destination_parent()
                else:
                    open_destination_input()
            elif kind == "ITEM":
                if (
                    session_navigation.pane != "viewer"
                    or viewer_content["kind"] != "ITEM"
                    or session_navigation.viewer_row_index
                    != session_navigation.row_index
                ):
                    item = active_view.items[session_navigation.row_index - 1]
                    open_split_item(item.uid)
                elif (
                    session_navigation.pane == "viewer"
                    and active_viewer_sections()[viewer_section_index()].kind
                    == "SOURCE_MEMORY"
                ):
                    section = active_viewer_sections()[viewer_section_index()]
                    if viewer_controller.nested_uid == section.uid:
                        viewer_controller.close_nested()
                        set_status("Memory reading closed.")
                    else:
                        viewer_controller.open_nested(section.uid)
                        set_status(
                            "Reading this Memory · ↑/↓ scroll · Enter/Escape back."
                        )
                    event.app.invalidate()
                    return
                elif read_only:
                    set_status("Applied Melds are read-only.")
                else:
                    section = active_viewer_sections()[viewer_section_index()]
                    item = current_navigation.current_item(active_view)
                    if section.kind == "MEMORY_ROW":
                        expanded_memory_section_uid["uid"] = (
                            None
                            if expanded_memory_section_uid["uid"] == section.uid
                            else section.uid
                        )
                        set_status(
                            "Evidence hidden."
                            if expanded_memory_section_uid["uid"] is None
                            else "Evidence shown."
                        )
                        event.app.invalidate()
                        return
                    set_status(
                        "This Viewer section is read-only; use the Responses frame "
                        "to answer."
                    )
            elif kind == "RESOLVE_ALL" and viewer_content["kind"] == "REVIEW":
                section = active_viewer_sections()[viewer_section_index()]
                if section.kind == "SUMMARY":
                    close_final_review()
                elif section.kind != "ACTION":
                    set_status("Move to the final action and press Enter.")
                else:
                    action = approved_final_review_action(active_view)
                    if action is not None:
                        record_study_action(
                            "APPROVAL_ACCEPTED",
                            surface="resolution",
                            action=action.kind,
                        )
                        event.app.exit(result=action)
                        return
            elif kind == "TODO" and report_apply:
                action = controller.report_apply_action()
                if action is not None:
                    record_study_action(
                        "APPLICATION_ACCEPTED",
                        surface="resolution",
                        action=action.kind,
                    )
                    event.app.exit(result=action)
                    return
            elif kind == "TODO" and viewer_content["kind"] == "REVIEW":
                action = approved_final_review_action(active_view)
                if action is not None:
                    record_study_action(
                        "APPROVAL_ACCEPTED",
                        surface="resolution",
                        action=action.kind,
                    )
                    event.app.exit(result=action)
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).unresolved_item_uids
            ):
                todo = session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                )
                open_split_item(todo.unresolved_item_uids[0])
            elif kind == "TODO" and current_item_handoff() is not None:
                item = current_navigation.current_item(active_view)
                if item is None:
                    set_status("There is no finding to hand off.")
                else:
                    # The operation receives the exact item identity and owns
                    # conversion, authority, provider use, and any Apply step.
                    event.app.exit(
                        result=ResolutionWorkbenchAction(
                            kind="HANDOFF",
                            item_uid=item.uid,
                        )
                    )
                    return
            elif kind == "TODO" and read_only:
                if read_only_handoff is None:
                    set_status("This saved session can only be inspected.")
                else:
                    # A standalone result remains immutable here. The handoff
                    # opens the owning operation, which must independently
                    # revalidate and obtain its normal Apply confirmation.
                    event.app.exit(result=ResolutionWorkbenchAction(kind="HANDOFF"))
                    return
            elif (
                kind == "TODO"
                and session_todo_view(
                    active_view,
                    local_drafts,
                    review_and_apply=review_and_apply,
                    read_only=read_only,
                    whole_set_available=bool(global_strategies),
                    read_only_handoff=read_only_handoff,
                    item_handoff=current_item_handoff(),
                ).kind
                == "COMPLETE"
            ):
                set_status(
                    "Required review is complete; close or revisit an optional review."
                )
            elif kind == "TODO" and review_and_apply:
                open_final_review()
            elif kind == "TODO" and not global_strategies:
                set_status("No whole-set strategies are available.")
            elif kind == "TODO":
                open_final_review()
            event.app.invalidate()
            return
        item = current_navigation.current_item(active_view)
        if item is None:
            set_status("There is no item to inspect.")
        elif current_navigation.expanded_item_uid != item.uid:
            current_navigation.toggle_detail(active_view)
            other_direction["focused"] = False
            set_status("")
        elif item.options:
            if item.issue_presentation is not None and other_direction["focused"]:
                current_navigation.selected_option_uid = None
                other_direction_editor["open"] = True
                open_item_input(
                    title=current_response_heading(),
                    clear=True,
                )
            else:
                current_navigation.toggle_option(active_view)
                if not save_draft():
                    event.app.invalidate()
                    return
                set_status("")
        else:
            current_navigation.toggle_detail(active_view)
            set_status("")
        event.app.invalidate()

    return _open_or_choose
