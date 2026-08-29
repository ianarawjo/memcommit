"""Ground turn and exact-application controller for the named workbench."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.in_frame_input import (
    INLINE_AGENT_COMMENT_TITLE,
    classify_inline_edit_submission,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.ground.model import (
    GROUND_PROPOSITION_SCHEMA_VERSION,
    GroundSession,
    is_bound_ground_schema,
)
from memcommit.application.operations.ground.turn_dialogue import GroundTurnDraftBatch

from memcommit.adapters.console.commands.ground.named_shell.presentation import (
    _aliased_items,
    _initial_question,
    _memory_use_checkbox,
)
from memcommit.adapters.console.commands.ground.named_shell.proposal import (
    GroundCommandProposal,
    NamedGroundApplier,
    NamedGroundDirectEditPreparer,
    NamedGroundDraftPreparer,
    NamedGroundFitLookup,
    NamedGroundInterpreter,
    NamedGroundProposalRetargeter,
    NamedGroundReloader,
    NamedGroundUseTogglePreparer,
    _response_kind,
    _response_text,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.fit_coordinator import (
    NamedGroundFitCoordinator,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.state import (
    GroundInlineTarget,
    GroundPaneLayer,
    NamedGroundShellState,
)
from memcommit.adapters.console.commands.ground.named_shell.runtime.workbench_view import (
    NamedGroundWorkbenchView,
)


class NamedGroundTurnController:
    """Own dialogue, draft, proposal, approval, and reload transitions."""

    def __init__(
        self,
        state: NamedGroundShellState,
        view: NamedGroundWorkbenchView,
        fit: NamedGroundFitCoordinator,
        *,
        interpret: NamedGroundInterpreter,
        apply: NamedGroundApplier,
        prepare_rule_draft: NamedGroundDraftPreparer | None,
        prepare_direct_edit: NamedGroundDirectEditPreparer | None,
        prepare_use_toggle: NamedGroundUseTogglePreparer | None,
        retarget_proposal: NamedGroundProposalRetargeter | None,
        reload_session: NamedGroundReloader | None,
        lookup_fit: NamedGroundFitLookup | None,
    ) -> None:
        self.state = state
        self.view = view
        self.fit = fit
        self.interpret = interpret
        self.apply = apply
        self.prepare_rule_draft = prepare_rule_draft
        self.prepare_direct_edit = prepare_direct_edit
        self.prepare_use_toggle = prepare_use_toggle
        self.retarget_proposal = retarget_proposal
        self.reload_session = reload_session
        self.lookup_fit = lookup_fit

    def reset_to_input(self, *, restore: bool) -> None:
        state = self.state
        state.mode = "INPUT"
        state.pending = None
        state.pending_inline_edit = None
        state.pending_draft_index = None
        state.review_view = "COMMAND"
        state.error_message = ""
        state.status_message = ""
        if restore:
            self.view.input_area.text = state.last_submission
            self.view.input_area.buffer.cursor_position = len(self.view.input_area.text)
        else:
            self.view.input_area.text = ""
        self.view.sync_input_host()
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_message()
        self.view.invalidate()

    def refresh_current(self, *, announce: bool) -> bool:
        state = self.state
        if self.reload_session is None:
            return False
        previous = state.current
        refreshed = self.reload_session(previous.contract_name)
        if not isinstance(refreshed, GroundSession):
            raise ValueError("Named Ground reload returned invalid state.")
        if refreshed.contract_name != previous.contract_name:
            raise ValueError("Named Ground reload changed its storage key.")
        if refreshed == previous:
            return False
        state.mark_pane_updates(*state.changed_pane_layers(previous, refreshed))
        state.current = refreshed
        if self.lookup_fit is not None:
            state.fit_receipt = self.lookup_fit(refreshed)
        state.selected_rule_index = min(
            state.selected_rule_index,
            max(0, len(_aliased_items(refreshed, "RULE")) - 1),
        )
        state.selected_memory_index = min(
            state.selected_memory_index,
            max(0, len(_aliased_items(refreshed, "CASE")) - 1),
        )
        state.cycle_dialogue.clear()
        state.draft_queue = ()
        state.draft_index = 0
        state.draft_queue_stale = False
        state.draft_source_submission = ""
        state.pending_draft_index = None
        if announce:
            state.mark_pane_updates("CHAT")
            state.conversation.append(
                "\n".join(
                    [
                        "GROUND REFRESHED",
                        "  Another saved change was found before this turn.",
                        (
                            "  The five workbench panes and semantic turn now use "
                            "the latest Ground."
                        ),
                    ]
                )
            )
        self.view.sync_panes(dialogue_anchor="end")
        self.view.invalidate()
        return True

    def interpret_current(
        self,
        *,
        append_user: bool,
        text: str,
        focus: str = "",
    ) -> None:
        state = self.state
        # Provider work and exact review are read-only presentation states;
        # no writable field remains mounted while either is active.
        self.view.input_manager.clear()
        try:
            self.refresh_current(announce=True)
            if append_user or not state.cycle_dialogue:
                user_turn_number = (
                    sum(
                        block.startswith("USER TURN ") for block in state.cycle_dialogue
                    )
                    + 1
                )
                focus_line = f"\nFOCUS · {focus}" if focus else ""
                state.cycle_dialogue.append(
                    f"USER TURN {user_turn_number}{focus_line}\n{text}"
                )
            if append_user:
                state.all_submitted_turns.append(text)
                state.conversation.append(
                    (
                        f"YOU · COMMENT FOR {safe_terminal_text(focus)}\n"
                        if focus
                        else "YOU\n"
                    )
                    + f"  {safe_terminal_text(text)}"
                )
                if state.draft_queue:
                    # Corrections can invalidate an earlier READY judgment.
                    state.draft_queue_stale = True
            response = self.interpret(
                state.current,
                state.dialogue_text(),
                text,
            )
            kind = _response_kind(response)
            understanding = _response_text(response, "understanding")
            question = _response_text(response, "question")
            agent_turn_number = (
                sum(block.startswith("AGENT TURN ") for block in state.cycle_dialogue)
                + 1
            )
            state.cycle_dialogue.append(
                "\n".join(
                    [
                        f"AGENT TURN {agent_turn_number}",
                        f"UNDERSTANDING\n{understanding}",
                        f"QUESTION\n{question}",
                    ]
                )
            )
            state.conversation.append(
                "\n".join(
                    [
                        "AGENT UNDERSTANDING" if append_user else "AGENT RETRY",
                        f"  {safe_terminal_text(understanding)}",
                        "",
                        "AGENT QUESTION",
                        f"  {safe_terminal_text(question)}",
                    ]
                )
            )
            state.mark_pane_updates("CHAT")
            state.error_message = ""
            state.status_message = ""
            if kind == "ASK":
                self.reset_to_input(restore=False)
                return
            if isinstance(response, GroundTurnDraftBatch):
                state.draft_queue = response.drafts
                if response.drafts:
                    state.mark_pane_updates("RULES")
                state.draft_queue_stale = False
                state.draft_source_submission = response.raw_source
                state.draft_index = next(
                    (
                        index
                        for index, draft in enumerate(response.drafts)
                        if draft.kind == "RULE" and draft.status == "READY"
                    ),
                    0,
                )
                state.pending = None
                state.pending_draft_index = None
                state.review_view = "COMMAND"
                state.mode = "INPUT"
                self.view.input_area.text = ""
                self.view.sync_input_host()
                state.status_message = (
                    f"{len(response.drafts)} unsaved draft(s) classified. "
                    "Review them in Rules."
                )
                state.conversation.append(
                    "\n".join(
                        [
                            "DRAFTS · PENDING",
                            (
                                f"  {len(response.drafts)} independent "
                                "unit(s) classified from this turn."
                            ),
                            (
                                "  No Rule, Ground Memory, Context Memory, or "
                                "checkpoint changed."
                            ),
                        ]
                    )
                )
                self.view.sync_panes(dialogue_anchor="end")
                self.view.sync_rules_pane(align_draft=True)
                self.view.require_application().layout.focus(
                    self.view.rules_pane.text_area
                )
                self.view.invalidate()
                return
            if not isinstance(response, GroundCommandProposal):
                raise ValueError("Ground action was not reduced to an exact command.")
            layer = {
                "BIND": "CONTEXTS",
                "PROPOSE_RULE": "RULES",
                "PROPOSE_CASE": "MEMORIES",
            }.get(response.kind)
            if (
                layer is not None
                and state.placement_overridden[layer]
                and self.retarget_proposal is not None
            ):
                response = self.retarget_proposal(
                    state.current,
                    response,
                    state.placement_choice[layer],
                )
            state.pending = response
            state.pending_inline_edit = None
            state.review_view = "COMMAND"
            state.mode = "APPROVAL"
            self.view.input_area.text = ""
            self.view.sync_input_host()
            self.view.sync_panes(dialogue_anchor="end")
            self.view.focus_conversation()
            self.view.invalidate()
        except Exception as error:
            state.pending = None
            state.error_message = f"{type(error).__name__}: {error}"
            state.status_message = ""
            state.mark_pane_updates("CHAT")
            state.mode = "ERROR"
            self.view.sync_input_host()
            self.view.sync_panes(dialogue_anchor="end")
            self.view.focus_conversation()
            self.view.invalidate()

    def collapse_inline_editor(
        self,
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        state = self.state
        if state.inline_target is None:
            return False
        owner = self.view.inline_owner_area()
        state.inline_target = None
        state.inline_selector = ""
        state.inline_original = ""
        state.inline_direct_locked = False
        self.view.direct_edit_area.text = ""
        self.view.composer.frame.title = "MESSAGE"
        self.view.input_area.text = state.suspended_message
        state.suspended_message = ""
        self.view.sync_input_host()
        if focus_owner:
            self.view.require_application().layout.focus(owner)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            self.view.invalidate()
        return True

    def collapse_panel_comment(
        self,
        event: object | None = None,
        *,
        focus_owner: bool = True,
    ) -> bool:
        state = self.state
        if state.panel_comment_target is None:
            return False
        owner = self.view.panel_comment_owner_area()
        state.panel_comment_target = None
        state.panel_comment_focus = ""
        self.view.composer.frame.title = "MESSAGE"
        self.view.input_area.text = state.suspended_message
        state.suspended_message = ""
        self.view.sync_input_host()
        if focus_owner:
            self.view.require_application().layout.focus(owner)
        if event is not None:
            getattr(event, "app").invalidate()
        else:
            self.view.invalidate()
        return True

    def open_panel_comment(
        self,
        *,
        target: GroundPaneLayer,
        focus: str,
    ) -> None:
        state = self.state
        if state.mode != "INPUT":
            return
        state.acknowledge_pane(target)
        if target == "CHAT":
            self.view.focus_message()
            self.view.invalidate()
            return
        state.suspended_message = self.view.input_area.text
        self.view.input_area.text = ""
        state.panel_comment_target = target
        state.panel_comment_focus = focus
        self.view.composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.status_message = ""
        self.view.sync_input_host()
        self.view.focus_message()
        self.view.invalidate()

    def finish_panel_comment(self) -> None:
        state = self.state
        target = state.panel_comment_target
        if target is None:
            return
        comment = self.view.input_area.text.strip()
        if not comment:
            state.status_message = "Enter a nonblank agent comment first."
            self.view.invalidate()
            return
        focus = state.panel_comment_focus or target
        state.suspended_message = ""
        self.collapse_panel_comment(focus_owner=False)
        state.last_submission = comment
        self.interpret_current(append_user=True, text=comment, focus=focus)

    def open_inline_editor(
        self,
        *,
        target: GroundInlineTarget,
        selector: str,
        original: str,
    ) -> None:
        state = self.state
        if state.mode != "INPUT":
            return
        state.acknowledge_pane(
            {"GOAL": "GOAL", "RULE": "RULES", "MEMORY": "MEMORIES"}[target]
        )
        state.suspended_message = self.view.input_area.text
        self.view.input_area.text = ""
        state.inline_target = target
        state.inline_selector = selector
        state.inline_original = original
        state.inline_direct_locked = not is_bound_ground_schema(
            state.current.schema_version
        )
        self.view.direct_edit_area.text = original
        self.view.direct_edit_area.buffer.cursor_position = len(original)
        self.view.composer.frame.title = INLINE_AGENT_COMMENT_TITLE
        state.status_message = ""
        self.view.sync_input_host()
        self.view.require_application().layout.focus(
            self.view.input_area
            if state.inline_direct_locked
            else self.view.direct_edit_area
        )
        self.view.invalidate()

    def finish_inline_submission(self) -> None:
        state = self.state
        target = state.inline_target
        if target is None:
            return
        selector = state.inline_selector
        original = state.inline_original
        edited = self.view.direct_edit_area.text
        comment = self.view.input_area.text.strip()
        submission_kind = classify_inline_edit_submission(
            original=original,
            edited=edited,
            comment=comment,
        )
        focus_label = target if not selector else f"{target} {selector}"
        if submission_kind == "NOOP":
            self.collapse_inline_editor(focus_owner=True)
            state.status_message = "No edit or agent comment was submitted."
            self.view.invalidate()
            return
        if self.refresh_current(announce=True):
            self.collapse_inline_editor(focus_owner=False)
            self.view.input_area.text = comment
            state.status_message = (
                "The saved Ground changed. Reopen the pane before editing; "
                "your comment remains in Message."
            )
            self.view.focus_message()
            self.view.invalidate()
            return
        if submission_kind == "COMMENT":
            state.suspended_message = ""
            self.collapse_inline_editor(focus_owner=False)
            state.last_submission = comment
            self.interpret_current(
                append_user=True,
                text=comment,
                focus=focus_label,
            )
            return
        if self.prepare_direct_edit is None:
            state.status_message = "This shell cannot prepare a direct Ground edit."
            self.view.invalidate()
            return
        try:
            proposal = self.prepare_direct_edit(
                state.current,
                target,
                selector,
                edited,
                comment,
            )
        except Exception as error:
            state.status_message = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            self.view.invalidate()
            return

        turn_lines = [f"DIRECT EDIT · {focus_label}", safe_terminal_text(edited)]
        if comment:
            turn_lines.extend(
                ["", INLINE_AGENT_COMMENT_TITLE, safe_terminal_text(comment)]
            )
        submitted_text = "\n".join(turn_lines)
        state.all_submitted_turns.append(submitted_text)
        state.last_submission = comment or edited
        if state.draft_queue:
            state.draft_queue_stale = True
        state.conversation.append("YOU · " + submitted_text)
        state.conversation.append(
            "DIRECT EDIT READY\n"
            "  The edited text was not rewritten by the provider.\n"
            "  Review the command below, then press Enter to save it."
        )
        state.suspended_message = ""
        state.pending_inline_edit = (
            target,
            selector,
            original,
            edited,
            comment,
        )
        self.collapse_inline_editor(focus_owner=False)
        state.pending = proposal
        state.review_view = "COMMAND"
        state.mode = "APPROVAL"
        state.status_message = ""
        self.view.sync_input_host()
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_conversation()
        self.view.invalidate()

    def toggle_memory_use(self) -> None:
        state = self.state
        selected = state.selected_saved_item("CASE", state.selected_memory_index)
        if selected is None:
            return
        if self.prepare_use_toggle is None:
            state.status_message = "This Ground adapter cannot change Example USE."
            self.view.invalidate()
            return
        try:
            self.refresh_current(announce=True)
            selected = state.selected_saved_item("CASE", state.selected_memory_index)
            if selected is None:
                raise ValueError("The selected Ground Memory no longer exists.")
            alias, item = selected
            proposal = self.prepare_use_toggle(state.current, alias)
        except Exception as error:
            state.status_message = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            self.view.invalidate()
            return
        state.conversation.append(
            "USE TOGGLE · "
            f"{safe_terminal_text(alias)}\n"
            f"  {_memory_use_checkbox(item.disposition)} "
            f"{safe_terminal_text(item.disposition)} remains saved until "
            "the exact command is approved."
        )
        state.pending = proposal
        state.pending_inline_edit = None
        state.review_view = "COMMAND"
        state.mode = "APPROVAL"
        state.status_message = ""
        self.view.sync_input_host()
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_conversation()
        self.view.invalidate()

    def review_rule_draft(self) -> None:
        state = self.state
        if not state.draft_queue:
            return
        state.acknowledge_pane("RULES")
        if state.draft_queue_stale:
            state.status_message = (
                "The saved Ground changed. Press R to reclassify every "
                "remaining draft before command review."
            )
            self.view.invalidate()
            return
        selected_index = state.draft_index
        draft = state.draft_queue[selected_index]
        if draft.kind != "RULE" or draft.status != "READY":
            state.status_message = (
                f"d{selected_index + 1} is {draft.kind} · {draft.status}; "
                "add clarification in Message or choose a READY Rule."
            )
            self.view.focus_message()
            self.view.invalidate()
            return
        if self.prepare_rule_draft is None:
            state.status_message = "This shell has no Rule-draft command preparer."
            self.view.invalidate()
            return
        try:
            if self.refresh_current(announce=True):
                state.status_message = (
                    "The saved Ground changed; submit the comment again so "
                    "its drafts can be reclassified."
                )
                self.view.sync_panes(dialogue_anchor="end")
                self.view.focus_message()
                self.view.invalidate()
                return
            proposal = self.prepare_rule_draft(state.current, draft)
            if (
                state.placement_overridden["RULES"]
                and self.retarget_proposal is not None
            ):
                proposal = self.retarget_proposal(
                    state.current,
                    proposal,
                    state.placement_choice["RULES"],
                )
        except Exception as error:
            state.status_message = (
                f"{type(error).__name__}: {safe_terminal_text(str(error))}"
            )
            self.view.focus_message()
            self.view.invalidate()
            return
        state.pending = proposal
        state.pending_draft_index = selected_index
        state.review_view = "COMMAND"
        state.mode = "APPROVAL"
        self.view.sync_input_host()
        state.status_message = ""
        state.conversation.append(
            "\n".join(
                [
                    f"DRAFT SELECTED · d{selected_index + 1}",
                    "  One READY Rule was reduced to the exact command shown below.",
                    "  Press Enter to approve and save it.",
                ]
            )
        )
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_conversation()
        self.view.invalidate()

    def reclassify_rule_drafts(self) -> None:
        state = self.state
        if not state.draft_source_submission:
            state.status_message = (
                "The original submitted comment is no longer available."
            )
            self.view.invalidate()
            return
        state.status_message = "Reclassifying drafts against saved Ground…"
        state.last_submission = state.draft_source_submission
        self.interpret_current(
            append_user=False,
            text=state.draft_source_submission,
        )

    def edit_goal(self) -> None:
        self.open_inline_editor(
            target="GOAL",
            selector="",
            original=self.state.current.goal,
        )

    def edit_saved_rule(self) -> None:
        state = self.state
        selected = state.selected_saved_item("RULE", state.selected_rule_index)
        if selected is None:
            state.status_message = (
                "No saved Rule is available; describe a new one in Message."
            )
            self.view.invalidate()
            return
        alias, item = selected
        self.open_inline_editor(target="RULE", selector=alias, original=item.content)

    def edit_saved_memory(self) -> None:
        state = self.state
        selected = state.selected_saved_item("CASE", state.selected_memory_index)
        if selected is None:
            state.status_message = (
                "No saved Ground Memory is available; describe one in Message."
            )
            self.view.invalidate()
            return
        alias, item = selected
        self.open_inline_editor(
            target="MEMORY",
            selector=alias,
            original=(
                item.proposition
                if state.current.schema_version == GROUND_PROPOSITION_SCHEMA_VERSION
                else item.expected
            ),
        )

    def submit_message(self) -> None:
        state = self.state
        text = self.view.input_area.text.strip()
        if not text:
            state.status_message = "Enter a nonblank Ground turn first."
            self.view.invalidate()
            return
        state.acknowledge_pane("CHAT")
        state.last_submission = text
        self.view.input_area.text = ""
        self.interpret_current(append_user=True, text=text)

    def approve(self) -> None:
        state = self.state
        proposal = state.pending
        if state.mode != "APPROVAL" or proposal is None:
            return
        state.mode = "APPLYING"
        self.view.invalidate()
        previous = state.current
        try:
            updated, actual_output = self.apply(previous, proposal)
        except Exception as error:
            refresh_note = (
                "The saved Ground could not be reloaded; close and resume "
                "before proposing another command."
            )
            try:
                if self.refresh_current(announce=False):
                    refresh_note = (
                        "The five workbench panes were refreshed from the latest saved "
                        "Ground before further input."
                    )
                else:
                    refresh_note = "The five workbench panes already match the latest saved Ground."
            except Exception as refresh_error:
                refresh_note += (
                    " Reload error: "
                    f"{safe_terminal_text(type(refresh_error).__name__)}: "
                    f"{safe_terminal_text(str(refresh_error))}"
                )
            state.conversation.append(
                "\n".join(
                    [
                        "APPLY NOT CONFIRMED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                        refresh_note,
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
        state.current = updated
        if self.lookup_fit is not None:
            state.fit_receipt = self.lookup_fit(updated)
        placement_options = state.current_placement_options()
        placement_default = next(
            (
                frame.context_name
                for frame in updated.frames
                if frame.role == "PUBLICATION_TARGET"
            ),
            placement_options[0] if placement_options else "",
        )
        for placement_layer in state.placement_choice:
            if state.placement_choice[placement_layer] not in placement_options:
                state.placement_choice[placement_layer] = placement_default
                state.placement_overridden[placement_layer] = False
        state.mark_pane_updates(
            *state.changed_pane_layers(previous, updated),
            "CHAT",
        )
        state.applied_argvs.append(proposal.review.argv)
        applied_draft_index = state.pending_draft_index
        if applied_draft_index is not None and 0 <= applied_draft_index < len(
            state.draft_queue
        ):
            remaining = list(state.draft_queue)
            del remaining[applied_draft_index]
            state.draft_queue = tuple(remaining)
            state.draft_index = min(
                applied_draft_index,
                max(0, len(remaining) - 1),
            )
        state.pending_draft_index = None
        state.conversation.append(
            "\n".join(
                [
                    f"APPLIED · {safe_terminal_text(proposal.kind)}",
                    f"  {safe_terminal_text(actual_output)}",
                    "",
                    (
                        "The Goal, Contexts, Rules, Memories, and Chat panes "
                        "now reflect the saved Ground."
                    ),
                ]
            )
        )
        state.conversation.append(_initial_question(updated))
        state.cycle_dialogue.clear()
        if state.draft_queue:
            # Ground mutation can change duplicate/conflict judgments.
            state.draft_queue_stale = True
        else:
            state.draft_queue_stale = False
            state.draft_source_submission = ""
            state.last_submission = ""
        applied_kind = proposal.kind
        self.reset_to_input(restore=False)
        if applied_kind == "SET_EXAMPLE_USE":
            state.status_message = (
                "Example USE updated · future Fit and Distill inputs changed"
            )
            self.view.sync_memories_pane(align_selection=True)
            self.view.require_application().layout.focus(self.view.cases_pane.text_area)
            self.view.invalidate()
        if state.draft_queue:
            state.status_message = (
                "Ground changed; remaining drafts are pending and require "
                "R reclassification."
            )
            self.view.sync_rules_pane(align_draft=True)
            self.view.require_application().layout.focus(self.view.rules_pane.text_area)
            self.view.invalidate()
        self.fit.schedule_auto_fit(self.view.require_application())

    def show_review(self, view: str) -> None:
        if self.state.mode != "APPROVAL":
            return
        self.state.acknowledge_pane("CHAT")
        self.state.review_view = "EFFECTS" if view == "EFFECTS" else "COMMAND"
        self.view.sync_panes(dialogue_anchor="end")
        self.view.invalidate()

    def refine(self) -> None:
        state = self.state
        if state.mode not in {"APPROVAL", "ERROR", "APPLY_ERROR"}:
            return
        previous_mode = state.mode
        inline_draft = state.pending_inline_edit
        state.conversation.append(
            "REFINEMENT\n  The pending action returned for revision."
        )
        if inline_draft is not None and previous_mode == "APPROVAL":
            target, selector, original, edited, comment = inline_draft
            self.reset_to_input(restore=False)
            self.open_inline_editor(
                target=target,
                selector=selector,
                original=original,
            )
            self.view.direct_edit_area.text = edited
            self.view.direct_edit_area.buffer.cursor_position = len(edited)
            self.view.input_area.text = comment
            self.view.input_area.buffer.cursor_position = len(comment)
            self.view.invalidate()
            return
        if inline_draft is not None and previous_mode == "APPLY_ERROR":
            self.reset_to_input(restore=False)
            state.status_message = (
                "The direct edit was discarded after an unconfirmed apply; "
                "reopen the current pane before proposing it again."
            )
            self.view.invalidate()
            return
        self.reset_to_input(restore=True)

    def retry(self) -> None:
        state = self.state
        if state.mode != "ERROR":
            return
        state.mode = "INTERPRETING"
        state.error_message = ""
        self.interpret_current(append_user=False, text=state.last_submission)
