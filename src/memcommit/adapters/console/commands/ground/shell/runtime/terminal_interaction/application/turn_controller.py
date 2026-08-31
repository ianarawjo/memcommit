"""Ground turn and exact-application controller for the blank workbench."""

from __future__ import annotations

from dataclasses import replace

from memcommit.adapters.console.commands.ground.shell.proposal import GroundApplier
from memcommit.adapters.console.commands.ground.shell.runtime.context_selection import (
    toggle_selected_context,
)
from memcommit.adapters.console.commands.ground.shell.runtime.session import (
    GroundPane,
    GroundShellState,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.activity import (
    pane_turn_label,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.grounding_coordinator import (
    BlankGroundGroundingCoordinator,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.application.workbench_view import (
    BlankGroundWorkbenchView,
)
from memcommit.adapters.console.terminal.components.in_frame_input import (
    INLINE_AGENT_COMMENT_TITLE,
    classify_inline_edit_submission,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.contracts import (
    GroundError,
    validate_ground_goal,
)
from memcommit.core.context_targeting.naming import validate_portable_context_name


class BlankGroundTurnController:
    """Own dialogue, local planning, review, approval, and exit transitions."""

    def __init__(
        self,
        state: GroundShellState,
        view: BlankGroundWorkbenchView,
        grounding: BlankGroundGroundingCoordinator,
        *,
        apply: GroundApplier,
        validate_new_context,
    ) -> None:
        self.state = state
        self.view = view
        self.grounding = grounding
        self.apply = apply
        self.validate_new_context = validate_new_context

    def collapse_inline_goal(
        self,
        event: object | None = None,
        *,
        focus_goal: bool = True,
    ) -> bool:
        state = self.state
        view = self.view
        if not state.inline_goal_open:
            return False
        state.inline_goal_open = False
        state.inline_goal_original = ""
        view.direct_edit_area.text = ""
        view.composer.frame.title = "MESSAGE"
        view.input_area.text = state.suspended_message
        state.suspended_message = ""
        view.sync_input_host()
        if focus_goal:
            view.require_application().layout.focus(view.goal_pane.text_area)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            view.invalidate()
        return True

    def collapse_inline_context(
        self,
        event: object | None = None,
        *,
        focus_contexts_after: bool = True,
    ) -> bool:
        state = self.state
        view = self.view
        if not state.inline_context_open:
            return False
        state.inline_context_open = False
        state.inline_context_original = ""
        view.direct_edit_area.text = ""
        view.composer.frame.title = "MESSAGE"
        view.input_area.text = state.suspended_message
        state.suspended_message = ""
        view.sync_input_host()
        if focus_contexts_after:
            view.focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            view.invalidate()
        return True

    def collapse_panel_comment(
        self,
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        state = self.state
        view = self.view
        if state.panel_comment_target is None:
            return False
        owner = view.panel_comment_owner_area()
        state.panel_comment_target = None
        state.panel_comment_focus = ""
        view.composer.frame.title = "MESSAGE"
        view.input_area.text = state.suspended_message
        state.suspended_message = ""
        view.sync_input_host()
        if focus_owner:
            view.require_application().layout.focus(owner)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            view.invalidate()
        return True

    def open_panel_comment(self, *, target: GroundPane, focus: str) -> None:
        state = self.state
        view = self.view
        if state.mode not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        state.acknowledge_pane(target)
        if target == "CHAT":
            view.focus_message()
            view.invalidate()
            return
        state.suspended_message = view.input_area.text
        view.input_area.text = ""
        state.panel_comment_target = target
        state.panel_comment_focus = focus
        view.composer.frame.title = pane_turn_label(target)
        state.status_message = ""
        view.sync_input_host()
        view.focus_message()
        view.invalidate()

    def finish_panel_comment(self) -> None:
        state = self.state
        view = self.view
        target = state.panel_comment_target
        if target is None:
            return
        comment = view.input_area.text.strip()
        if not comment:
            state.status_message = "Enter a nonblank agent comment first."
            view.invalidate()
            return
        focus = state.panel_comment_focus or target
        payload = "\n".join(
            [
                f"FOCUS · {focus}",
                INLINE_AGENT_COMMENT_TITLE,
                comment,
            ]
        )
        state.suspended_message = ""
        self.collapse_panel_comment(focus_owner=False)
        state.last_submission = payload
        state.last_submission_target = target
        state.last_submission_display = comment
        self.grounding.begin_interpretation(
            payload,
            append_user=True,
            turn_target=target,
            turn_display=comment,
        )

    def restore_suspended_context_approval(
        self,
        event: object | None = None,
    ) -> bool:
        state = self.state
        proposal = state.suspended_context_proposal
        if (
            proposal is None
            or state.inline_context_open
            or state.mode != "CONTEXT_SELECTION"
        ):
            return False
        state.pending = proposal
        state.suspended_context_proposal = None
        state.mode = "APPROVAL"
        self.view.sync_input_host()
        state.status_message = (
            "Local Context edit cancelled; exact Ground approval restored."
        )
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_contexts()
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            self.view.invalidate()
        return True

    def complete_context_plan(self, *, allow_empty: bool = False) -> bool:
        state = self.state
        view = self.view
        selected = state.selected_context_names
        new_name = state.local_new_context_name
        if not selected and not new_name and not allow_empty:
            state.status_message = (
                "Select an existing Context with Space or enter a new "
                "Context name first."
            )
            view.invalidate()
            return False
        state.context_selection_finished = True
        view.sync_contexts_pane()
        parts = []
        if selected:
            parts.append(f"{len(selected)} existing")
        if new_name:
            parts.append("1 new local name")
        summary = " + ".join(parts) or "No Context plan"
        suspended = state.suspended_context_proposal
        if suspended is not None:
            state.pending = suspended
            state.suspended_context_proposal = None
            state.mode = "APPROVAL"
            view.sync_input_host()
            state.status_message = (
                f"{summary}. The Ground command is ready for a fresh Enter."
            )
            view.sync_panes(dialogue_anchor="end")
            view.focus_conversation()
            view.invalidate()
            return True
        if state.mode == "CONTEXT_SELECTION" and state.pending is not None:
            # Context planning is a process-local hint and cannot expand the
            # frozen Ground creation command into hidden Context mutations.
            state.mode = "APPROVAL"
            view.sync_input_host()
            state.status_message = (
                f"{summary}. Enter approves only the Ground name and Goal."
            )
            view.focus_conversation()
        else:
            state.status_message = f"{summary}. Continue in Message."
            view.focus_message()
        view.invalidate()
        return True

    def open_inline_context(self, *, prefill: str) -> None:
        state = self.state
        view = self.view
        if state.mode not in {"INPUT", "CONTEXT_SELECTION"}:
            return
        state.acknowledge_pane("CONTEXTS")
        state.inline_context_original = prefill
        state.suspended_message = view.input_area.text
        view.input_area.text = ""
        view.direct_edit_area.text = prefill
        view.direct_edit_area.buffer.cursor_position = len(prefill)
        view.composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.inline_context_open = True
        state.status_message = ""
        view.sync_input_host()
        view.require_application().layout.focus(view.direct_edit_area)
        view.invalidate()

    def finish_inline_context(self) -> None:
        state = self.state
        view = self.view
        original = state.inline_context_original
        edited = view.direct_edit_area.text
        comment = view.input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP" and original:
            submission_kind = "DIRECT"
        if submission_kind == "NOOP":
            self.collapse_inline_context(focus_contexts_after=True)
            state.status_message = "No Context name or agent comment was submitted."
            view.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_name = self.validate_new_context(edited)
            except (OSError, ValueError) as error:
                state.status_message = safe_terminal_text(str(error))
                view.invalidate()
                return
            if not isinstance(exact_name, str) or not exact_name:
                state.status_message = (
                    "The new Context validator returned no exact name."
                )
                view.invalidate()
                return
            state.local_new_context_name = exact_name
            state.conversation.append(
                "\n".join(
                    [
                        "YOU · NEW CONTEXT NAME (DIRECTLY)",
                        f"  {safe_terminal_text(exact_name)}",
                        "  PLANNED CONTEXT · NOT CREATED",
                    ]
                )
            )
        else:
            exact_name = ""

        state.suspended_message = ""
        self.collapse_inline_context(focus_contexts_after=False)
        if comment:
            payload = "\n".join(
                [
                    "FOCUS · NEW CONTEXT PLANNING",
                    INLINE_AGENT_COMMENT_TITLE,
                    comment,
                ]
            )
            state.last_submission = payload
            state.last_submission_target = "CONTEXTS"
            state.last_submission_display = comment
            self.grounding.begin_interpretation(
                payload,
                append_user=True,
                preserve_local_new_context=bool(exact_name),
                turn_target="CONTEXTS",
                turn_display=comment,
            )
            return
        view.sync_panes(dialogue_anchor="end")
        self.complete_context_plan()

    def open_inline_goal(self) -> None:
        state = self.state
        view = self.view
        if state.mode != "INPUT":
            return
        state.acknowledge_pane("GOAL")
        original = state.editable_goal
        state.inline_goal_original = original
        state.suspended_message = view.input_area.text
        view.input_area.text = ""
        view.direct_edit_area.text = original
        view.direct_edit_area.buffer.cursor_position = len(original)
        view.composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.inline_goal_open = True
        state.status_message = ""
        view.sync_input_host()
        view.require_application().layout.focus(view.direct_edit_area)
        view.invalidate()

    def finish_inline_goal(self) -> None:
        state = self.state
        view = self.view
        original = state.inline_goal_original
        edited = view.direct_edit_area.text
        comment = view.input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        if submission_kind == "NOOP":
            self.collapse_inline_goal(focus_goal=True)
            state.status_message = "No edit or agent comment was submitted."
            view.invalidate()
            return
        if submission_kind in {"DIRECT", "BOTH"}:
            try:
                exact_goal = validate_ground_goal(
                    edited,
                    label="directly edited Ground goal",
                )
            except GroundError as error:
                state.status_message = safe_terminal_text(str(error))
                view.invalidate()
                return
            state.editable_goal = exact_goal
            state.required_direct_goal = exact_goal
            state.pending_inline_goal = (original, exact_goal, comment)
            blocks = [
                "FOCUS · GOAL",
                "EDIT (DIRECTLY) · PRESERVE EXACTLY",
                exact_goal,
            ]
            if comment:
                blocks.extend(["", INLINE_AGENT_COMMENT_TITLE, comment])
            payload = "\n".join(blocks)
            turn_display = (
                f"DIRECT GOAL\n{exact_goal}\n\n{comment}"
                if comment
                else f"DIRECT GOAL\n{exact_goal}"
            )
        else:
            state.pending_inline_goal = None
            blocks = ["FOCUS · GOAL"]
            if state.editable_goal:
                blocks.extend(["CURRENT GOAL · DRAFT", state.editable_goal])
            blocks.extend([INLINE_AGENT_COMMENT_TITLE, comment])
            payload = "\n".join(blocks)
            turn_display = comment
        state.suspended_message = ""
        self.collapse_inline_goal(focus_goal=False)
        state.last_submission = payload
        state.last_submission_target = "GOAL"
        state.last_submission_display = turn_display
        self.grounding.begin_interpretation(
            payload,
            append_user=True,
            turn_target="GOAL",
            turn_display=turn_display,
        )

    def finish_inline_submission(self) -> None:
        if self.state.inline_context_open:
            self.finish_inline_context()
        else:
            self.finish_inline_goal()

    def toggle_context_candidate(self) -> None:
        state = self.state
        view = self.view
        state.acknowledge_pane("CONTEXTS")
        row = view.context_cursor_row()
        if row is None:
            return
        if row.kind != "EXISTING":
            state.status_message = (
                "Press F to continue without a Context plan."
                if row.kind == "CONTINUE_EMPTY"
                else (
                    "Press P to open the direct ordinary Context tree."
                    if row.kind == "DIRECT_PICK"
                    else (
                        "Press N to edit this new Context name; Space "
                        "selects existing Contexts only."
                    )
                )
            )
            view.invalidate()
            return
        state.selected_context_names = toggle_selected_context(
            state.selected_context_names,
            row.context_name,
        )
        view.sync_contexts_pane(align_candidate=True)
        state.status_message = (
            f"{len(state.selected_context_names)} Context(s) selected for this draft."
        )
        view.invalidate()

    def accept_direct_context_selection(self, result: str | None) -> None:
        state = self.state
        if result is None:
            state.status_message = "Direct Context selection cancelled."
        else:
            names = list(state.selected_context_names)
            if result not in names:
                names.append(result)
            state.selected_context_names = tuple(names)
            state.status_message = f"{len(names)} Context(s) selected for this draft."
            self.view.sync_contexts_pane(align_candidate=True)
        self.view.invalidate()

    def edit_context_name_plan(self) -> None:
        row = self.view.context_cursor_row()
        if row is None:
            return
        if row.kind == "NEW_SUGGESTION":
            self.open_inline_context(prefill=row.context_name)
            return
        if row.kind == "ADD_NEW":
            self.open_inline_context(prefill=self.state.local_new_context_name)
            return
        self.state.status_message = (
            "N edits NEW? or ADD NEW CONTEXT; Space selects existing Contexts."
        )
        self.view.invalidate()

    def finish_context_selection(self) -> None:
        self.state.acknowledge_pane("CONTEXTS")
        row = self.view.context_cursor_row()
        if row is not None and row.kind == "CONTINUE_EMPTY":
            self.state.local_new_context_name = ""
            self.complete_context_plan(allow_empty=True)
            return
        self.complete_context_plan()

    def reopen_context_selection(self) -> None:
        state = self.state
        state.context_selection_finished = False
        state.mode = "CONTEXT_SELECTION"
        self.view.sync_input_host()
        state.status_message = (
            "Context plan reopened · Space selects existing · F finishes · "
            "N edits a new name."
        )
        self.view.sync_contexts_pane(align_candidate=True)
        self.view.focus_contexts()
        self.view.invalidate()

    def open_add_context_from_approval(self) -> None:
        state = self.state
        proposal = state.pending
        if proposal is None:
            return
        state.suspended_context_proposal = proposal
        state.pending = None
        state.mode = "CONTEXT_SELECTION"
        state.review_view = "COMMAND"
        state.status_message = (
            "Ground approval suspended while editing a local Context name."
        )
        self.view.sync_panes(dialogue_anchor="end")
        self.open_inline_context(prefill=state.local_new_context_name)
        self.view.invalidate()

    def select_save_location(self, result: str | None) -> None:
        state = self.state
        if result is None:
            state.status_message = "Save Location change cancelled."
            self.view.invalidate()
            return
        # Location selection and a proposed new Context have different
        # adapter contracts. Keep the former on the canonical portable-name
        # validator even when a caller injects the latter's focused validator.
        exact_name = validate_portable_context_name(result)
        state.planned_ground_name = exact_name
        state.location_source = "SELECTED"
        if state.pending is not None:
            state.pending = replace(state.pending, ground_name=exact_name)
        if state.suspended_context_proposal is not None:
            state.suspended_context_proposal = replace(
                state.suspended_context_proposal,
                ground_name=exact_name,
            )
        state.mark_pane_updates("LOCATION", "CONTEXTS", "CHAT")
        state.status_message = (
            f"Save Location selected · {safe_terminal_text(exact_name)} · NOT CREATED."
        )
        self.view.sync_panes(dialogue_anchor="end")
        self.view.invalidate()

    def submit_message(self) -> None:
        state = self.state
        view = self.view
        text = view.input_area.text.strip()
        if not text:
            state.status_message = "Enter a nonblank description first."
            view.invalidate()
            return
        state.status_message = ""
        state.acknowledge_pane("CHAT")
        state.last_submission = text
        state.last_submission_target = "CHAT"
        state.last_submission_display = text
        view.input_area.text = ""
        self.grounding.begin_interpretation(
            text,
            append_user=True,
            turn_target="CHAT",
            turn_display=text,
        )

    def approve(self) -> None:
        state = self.state
        if state.mode != "APPROVAL" or state.pending is None:
            return
        proposal = state.pending
        state.mode = "APPLYING"
        self.view.invalidate()
        try:
            actual_output = self.apply(proposal)
        except Exception as error:
            state.conversation.append(
                "\n".join(
                    [
                        "APPLY FAILED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                    ]
                )
            )
            state.error_message = ""
            state.mark_pane_updates("CHAT")
            state.mode = "APPLY_ERROR"
            self.view.sync_panes(dialogue_anchor="end")
            self.view.focus_conversation()
            self.view.invalidate()
            return
        self.view.require_application().exit(
            result=state.result(
                "APPLIED",
                proposal=proposal,
                actual_output=actual_output,
            )
        )

    def show_review(self, review_view: str) -> None:
        if self.state.mode != "APPROVAL":
            return
        self.state.acknowledge_pane("CHAT")
        self.state.review_view = "EFFECTS" if review_view == "EFFECTS" else "COMMAND"
        self.view.sync_panes(dialogue_anchor="end")
        self.view.invalidate()

    def refine(self) -> None:
        state = self.state
        if state.mode not in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
            "APPLY_ERROR",
        }:
            return
        previous_mode = state.mode
        inline_draft = state.pending_inline_goal
        if state.pending is not None:
            state.editable_goal = state.pending.goal
        state.conversation.append(
            "REFINEMENT\n  Previous proposal or interpretation returned for revision."
        )
        if inline_draft is not None and previous_mode in {
            "CONTEXT_SELECTION",
            "APPROVAL",
            "ERROR",
        }:
            original, edited, comment = inline_draft
            self.grounding.reset_to_input(restore=False)
            self.open_inline_goal()
            state.inline_goal_original = original
            self.view.direct_edit_area.text = edited
            self.view.direct_edit_area.buffer.cursor_position = len(edited)
            self.view.input_area.text = comment
            self.view.input_area.buffer.cursor_position = len(comment)
            self.view.invalidate()
            return
        if inline_draft is not None and previous_mode == "APPLY_ERROR":
            # The external command may have reached its mutation boundary.
            # Never recreate the same direct proposal from an uncertain result.
            state.pending_inline_goal = None
            state.required_direct_goal = None
            self.grounding.reset_to_input(restore=False)
            state.status_message = (
                "The direct Goal edit was discarded after an unconfirmed "
                "apply; reopen Goal before proposing it again."
            )
            self.view.invalidate()
            return
        self.grounding.reset_to_input(restore=True)

    def retry(self) -> None:
        state = self.state
        if state.mode != "ERROR":
            return
        state.error_message = ""
        self.grounding.begin_interpretation(
            state.last_submission,
            append_user=False,
            turn_target=state.last_submission_target,
            turn_display=state.last_submission_display,
        )

    def cancel(self, event) -> None:
        # Executor-backed provider work may finish after Escape. The closed
        # flag makes the late result observationally inert.
        self.state.shell_closed = True
        event.app.exit(result=self.state.result("CANCELLED"))

    def back_to_picker(self, event) -> None:
        self.state.shell_closed = True
        event.app.exit(result=self.state.result("BACK_TO_PICKER"))

    def start_initial_turn(self, working_goal: str) -> None:
        self.grounding.begin_interpretation(
            working_goal,
            append_user=False,
            initial=True,
            turn_target="GOAL",
            turn_display=working_goal,
        )
