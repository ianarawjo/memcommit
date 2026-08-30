"""Item preview, final review, and submission flow for a Resolution Session."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from prompt_toolkit.application.current import get_app

from memcommit.adapters.console.terminal.components.command_editor.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerController,
)
from memcommit.adapters.console.terminal.core.keybindings import NavigationAccelerator
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchPane,
)
from memcommit.persistence.command_ledger.study_actions import record_study_action

from memcommit.adapters.console.terminal.components.resolution.session_shell.controller import (
    FinalReviewOrigin,
    ResolutionSessionController,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    ResolutionGlobalStrategy,
    SessionTodoView,
    _source_memory_lines,
    session_todo_view,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.controls import (
    ResolutionShellControls,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.editors import (
    ResolutionEditors,
)


class ResolutionReviewFlow:
    """Own item preview, review transitions, and returned semantic actions."""

    def __init__(
        self,
        controller: ResolutionSessionController,
        controls: ResolutionShellControls,
        editors: ResolutionEditors,
        viewer_controller: SemanticViewerController,
        navigation_accelerator: NavigationAccelerator,
        *,
        split_viewer_items: bool,
        global_strategies: tuple[ResolutionGlobalStrategy, ...],
        review_and_apply: bool,
        read_only: bool,
        read_only_handoff: SessionTodoView | None,
        destination_available: bool,
        draft_saver_available: bool,
        turn_command_review: (
            Callable[[ResolutionWorkbenchAction], CommandReview | None] | None
        ),
    ) -> None:
        self.controller = controller
        self.controls = controls
        self.editors = editors
        self.viewer_controller = viewer_controller
        self.navigation_accelerator = navigation_accelerator
        self.split_viewer_items = split_viewer_items
        self.global_strategies = global_strategies
        self.review_and_apply = review_and_apply
        self.read_only = read_only
        self.read_only_handoff = read_only_handoff
        self.destination_available = destination_available
        self.draft_saver_available = draft_saver_available
        self.turn_command_review = turn_command_review

    def project_previewed_items_row(
        self,
        active_view: ResolutionWorkbenchView,
    ) -> None:
        """Project the already-aligned shared Items row into operation state."""

        controller = self.controller
        controller.other_direction["focused"] = False
        controller.other_direction_editor["open"] = False
        controller.response_state.editing = False
        controller.expanded_memory_section_uid["uid"] = None
        self.viewer_controller.close_nested()
        if controller.session_navigation.row_index == 0:
            self.controls.set_viewer_content("REPORT")
            controller.navigation.close_detail()
            self.controls.reset_viewer_section()
            return
        item = active_view.items[controller.session_navigation.row_index - 1]
        self.controls.set_viewer_content("ITEM")
        controller.navigation.selected_item_uid = item.uid
        controller.navigation.sync(active_view)
        controller.navigation.close_detail()
        controller.navigation.toggle_detail(active_view)
        self.controls.reset_viewer_section()
        self.editors.load_draft()
        controller.sync_response_state()

    def preview_items_row(self, active_view: ResolutionWorkbenchView) -> None:
        """Align and project one explicitly selected Items row."""

        self.controller.session_navigation.preview_selected_row()
        self.project_previewed_items_row(active_view)

    def move(self, delta: int) -> None:
        controller = self.controller
        active_view = controller.current_view()
        if self.split_viewer_items:
            pane = controller.session_navigation.pane
            if pane == "responses":
                target = controller.sync_response_state()
                if target is None:
                    controller.set_status("No response target is open.")
                    return
                controller.response_state.move_focus(target, delta)
                controller.set_status("")
                return
            if pane == "viewer":
                if self.viewer_controller.nested_uid is not None:
                    source = self.controls.focused_source_memory()
                    if source is not None:
                        self.viewer_controller.move_nested(
                            len(
                                _source_memory_lines(
                                    source.content,
                                    self.controls.pane_content_width(),
                                )
                            ),
                            delta,
                        )
                    controller.set_status("")
                    return
                section = self.viewer_controller.move(
                    self.controls.active_viewer_sections(),
                    delta,
                )
                if controller.viewer_content["kind"] == "REPORT" and section:
                    controller.session_navigation.row_index = section.row_index or 0
                    if section.kind == "ITEM" and section.row_index is not None:
                        item = active_view.items[section.row_index - 1]
                        controller.navigation.selected_item_uid = item.uid
                controller.set_status("")
                return
            if pane == "todo":
                controller.set_status("")
                return
            if pane == "save_location":
                state = controller.destination_editor_state["value"]
                if self.controls.destination_tree_is_focused() and state is not None:
                    state.tree.move(delta)
                controller.set_status("")
                return
            total_rows = len(active_view.items) + 1
            controller.session_navigation.move_and_preview_row(total_rows, delta)
            self.project_previewed_items_row(active_view)
            controller.set_status("")
            return

        item = controller.navigation.current_item(active_view)
        if (
            item is not None
            and controller.navigation.expanded_item_uid == item.uid
            and item.options
        ):
            controller.navigation.move_option(active_view, delta)
        else:
            if not self.editors.save_draft():
                return
            controller.navigation.move_item(active_view, delta)
            self.editors.load_draft()
        controller.global_comment["value"] = False
        self.controls.composer.frame.title = "MESSAGE"
        controller.set_status("")

    def open_split_item(self, item_uid: str) -> None:
        """Open one selected item from Items or the state-derived To Do."""

        active_view = self.controller.current_view()
        item_index = next(
            index
            for index, item in enumerate(active_view.items)
            if item.uid == item_uid
        )
        self.controller.session_navigation.row_index = item_index + 1
        self.preview_items_row(active_view)
        self.controller.session_navigation.open_selected(self.controls.item_sections())
        get_app().layout.focus(self.controls.body_control)
        self.controller.set_status("")

    def focus_surface_pane(self, pane: WorkbenchPane) -> None:
        """Keep semantic frame state aligned with prompt-toolkit focus."""

        controller = self.controller
        if pane != "viewer":
            self.navigation_accelerator.reset()
            self.viewer_controller.close_nested()
        if pane == "items" and controller.viewer_content["kind"] == "REVIEW":
            # Final review is not an Items row. Both Tab and vertical entry
            # expose the ordinary Report selection while leaving the reviewed
            # confirmation visible until the person moves or activates it.
            controller.session_navigation.row_index = 0
        controller.session_navigation.focus(pane)
        controller.set_status("")

    def close_final_review(self) -> None:
        """Return from final review to the exact process-local entry surface."""

        controller = self.controller
        origin = controller.final_review_origin["value"]
        controller.final_review_origin["value"] = None
        controller.final_command_review["value"] = None
        if origin is None:
            # Compatibility fallback for navigation state created before this
            # shell began tracking review entry. The report action is the
            # closest stable semantic parent of the confirmation surface.
            controller.session_navigation.row_index = 0
            controller.session_navigation.viewer_row_index = 0
            self.controls.set_viewer_content("REPORT")
            sections = self.controls.report_sections()
            action_section = next(
                (section for section in sections if section.uid == "REPORT:ACTION"),
                sections[0] if sections else None,
            )
            controller.session_navigation.section_uid = (
                action_section.uid if action_section is not None else None
            )
            pane: WorkbenchPane = "viewer"
        else:
            controller.session_navigation.row_index = origin.row_index
            controller.session_navigation.viewer_row_index = origin.viewer_row_index
            self.controls.set_viewer_content(origin.viewer_kind)
            controller.session_navigation.section_uid = origin.section_uid
            self.viewer_controller.index(self.controls.active_viewer_sections())
            pane = origin.pane

        if pane == "responses" and not self.controls.response_visible():
            pane = "viewer"
        if pane == "save_location" and not self.destination_available:
            pane = "viewer"
        if pane == "composer":
            pane = "viewer"
        prompt_controls = {
            "viewer": self.controls.body_control,
            "responses": self.controls.responses_control,
            "items": self.controls.items_control,
            "save_location": self.controls.destination_control,
            "todo": self.controls.todo_control,
        }
        self.focus_surface_pane(pane)
        get_app().layout.focus(prompt_controls[pane])
        controller.set_status("")

    def open_final_review(self) -> None:
        """Open the non-mutating review before a whole-set or apply action."""

        controller = self.controller
        # A split report has no open response editor. Saving there would copy
        # the navigation sentinel over an already-staged durable choice.
        if not self.split_viewer_items or self.controls.response_visible():
            self.editors.save_draft()
        active_view = controller.current_view()
        todo = session_todo_view(
            active_view,
            controller.local_drafts,
            review_and_apply=self.review_and_apply,
            read_only=self.read_only,
            whole_set_available=bool(self.global_strategies),
            read_only_handoff=self.read_only_handoff,
            item_handoff=controller.current_item_handoff(),
        )
        if todo.kind not in {"REVIEW AND APPLY", "RESOLVE ALL"}:
            if todo.unresolved_item_uids:
                self.open_split_item(todo.unresolved_item_uids[0])
            else:
                controller.set_status(todo.detail)
            return
        controller.final_review_title["value"] = (
            "APPLY CONFIRMATION" if todo.kind == "REVIEW AND APPLY" else todo.kind
        )
        proposed_action = self.final_review_action(active_view, open_custom=False)
        controller.final_command_review["value"] = (
            self.turn_command_review(proposed_action)
            if self.turn_command_review is not None and proposed_action is not None
            else None
        )
        if controller.viewer_content["kind"] != "REVIEW":
            controller.final_review_origin["value"] = FinalReviewOrigin(
                viewer_kind=controller.viewer_content["kind"],
                pane=controller.session_navigation.pane,
                row_index=controller.session_navigation.row_index,
                viewer_row_index=controller.session_navigation.viewer_row_index,
                section_uid=controller.session_navigation.section_uid,
            )
        controller.session_navigation.row_index = len(active_view.items) + 1
        controller.session_navigation.viewer_row_index = (
            controller.session_navigation.row_index
        )
        self.controls.set_viewer_content("REVIEW")
        controller.session_navigation.focus_section(
            self.controls.active_viewer_sections(),
            kind="SUMMARY",
        )
        controller.session_navigation.focus("viewer")
        get_app().layout.focus(self.controls.body_control)
        controller.set_status("")
        record_study_action(
            "APPROVAL_PRESENTED",
            surface="resolution",
            action=todo.kind,
        )

    def final_review_action(
        self,
        active_view: ResolutionWorkbenchView,
        *,
        open_custom: bool = True,
    ) -> ResolutionWorkbenchAction | None:
        controller = self.controller
        final_action = controller.review_action()
        if final_action.kind in {"APPLY", "APPLY AS IS"}:
            return controller.semantic_action("ACCEPT")
        if final_action.kind == "INCORPORATE AND APPLY":
            return controller.incorporate_responses_action(
                active_view,
                action_kind="INCORPORATE_AND_APPLY",
            )
        if final_action.kind == "INCORPORATE RESPONSES":
            return controller.incorporate_responses_action(active_view)
        if final_action.kind == "RESOLVE ALL":
            selected_strategy = self.global_strategies[controller.strategy["index"]]
            if selected_strategy.action_kind == "CUSTOM":
                if open_custom:
                    self.editors.open_global_input(clear=True)
                return None
            return controller.semantic_action(
                selected_strategy.action_kind,
                comment=selected_strategy.comment,
            )
        controller.set_status("No final action is available.")
        return None

    def approved_final_review_action(
        self,
        active_view: ResolutionWorkbenchView,
    ) -> ResolutionWorkbenchAction | None:
        """Rebuild the final action and its command before returning either."""

        action = self.final_review_action(active_view)
        if action is None or self.turn_command_review is None:
            return action
        rebuilt = self.turn_command_review(action)
        if rebuilt != self.controller.final_command_review["value"]:
            self.controller.set_status(
                "The semantic turn changed after review. Reopen the final review."
            )
            return None
        return action

    def submit(self, event: Any) -> None:
        controller = self.controller
        active_view = controller.current_view()
        comment = self.controls.input_area.text.strip()
        if (self.review_and_apply or self.draft_saver_available) and not (
            controller.global_comment["value"]
        ):
            item = controller.navigation.current_item(active_view)
            if not self.editors.save_draft():
                event.app.invalidate()
                return
            controller.other_direction_editor["open"] = False
            controller.response_state.editing = False
            if self.split_viewer_items:
                controller.session_navigation.focus("responses")
                event.app.layout.focus(self.controls.responses_control)
            else:
                controller.session_navigation.focus("viewer")
                event.app.layout.focus(self.controls.body_control)
            if item is not None:
                draft = controller.local_drafts.get(item.uid, ResponseDraft())
                if draft.selected_choice_uid is not None:
                    label = item.option(draft.selected_choice_uid).label
                    controller.set_status(f"Selected · {label}")
                elif draft.text.strip():
                    controller.set_status("Saved · Response")
            event.app.invalidate()
            return
        if controller.global_comment["value"]:
            action = controller.semantic_action("SUBMIT_ALL", comment=comment)
        else:
            item = controller.navigation.current_item(active_view)
            action = controller.semantic_action(
                "SUBMIT_ITEM",
                item_uid=item.uid if item is not None else None,
                option_uid=controller.navigation.selected_option_uid,
                comment=comment,
            )
        if action is not None:
            event.app.exit(result=action)
