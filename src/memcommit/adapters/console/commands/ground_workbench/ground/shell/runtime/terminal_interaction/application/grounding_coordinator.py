"""Background grounding-draft coordination for the blank Ground workbench."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from memcommit.adapters.console.commands.ground_workbench.ground.shell.presentation import _agent_block
from memcommit.adapters.console.commands.ground_workbench.ground.shell.proposal import GroundInterpreter
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.grounding_drafting import (
    freeze_grounding_response,
    interpret_from_background_thread,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.session import (
    GroundPane,
    GroundShellState,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.runtime.terminal_interaction.application.workbench_view import (
    BlankGroundWorkbenchView,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


class BlankGroundGroundingCoordinator:
    """Own one provider-backed drafting turn and its liveness boundary."""

    def __init__(
        self,
        state: GroundShellState,
        view: BlankGroundWorkbenchView,
        *,
        interpret: GroundInterpreter,
        fixed_ground_name: str | None,
        context_catalog_count: int,
        background_interpretation: bool,
        thinking_interval_seconds: float,
    ) -> None:
        self.state = state
        self.view = view
        self.interpret = interpret
        self.fixed_ground_name = fixed_ground_name
        self.context_catalog_count = context_catalog_count
        self.background_interpretation = background_interpretation
        self.thinking_interval_seconds = thinking_interval_seconds

    def reset_to_input(self, *, restore: bool) -> None:
        state = self.state
        view = self.view
        state.mode = "INPUT"
        state.pending = None
        state.suspended_context_proposal = None
        state.review_view = "COMMAND"
        state.error_message = ""
        state.status_message = ""
        if restore:
            view.input_area.text = state.last_submission
            view.input_area.buffer.cursor_position = len(view.input_area.text)
        else:
            view.input_area.text = ""
        view.sync_input_host()
        view.sync_panes(dialogue_anchor="end")
        view.focus_message()
        view.invalidate()

    def dialogue_payload(self) -> str:
        turns = self.state.submitted_turns
        return (
            turns[0]
            if len(turns) == 1
            else "\n\n".join(
                f"USER TURN {index}\n{turn}"
                for index, turn in enumerate(turns, start=1)
            )
        )

    def finish_interpretation(
        self,
        response: object,
        *,
        append_user: bool,
        initial: bool,
        turn_target: GroundPane,
    ) -> None:
        state = self.state
        view = self.view
        drafted = freeze_grounding_response(
            response,
            planned_ground_name=state.planned_ground_name,
            context_catalog_count=self.context_catalog_count,
        )
        kind = drafted.kind
        understanding = drafted.understanding
        question = drafted.question
        frozen_contexts = drafted.context_suggestions
        frozen_new_contexts = drafted.new_context_suggestions
        frozen_rule_drafts = drafted.rule_drafts
        frozen_memory_drafts = drafted.memory_drafts
        state.context_suggestions = frozen_contexts
        state.new_context_suggestions = frozen_new_contexts
        state.rule_drafts = frozen_rule_drafts
        state.memory_drafts = frozen_memory_drafts
        # Results belong to their originating pane. Other panes receive a
        # badge only when the response actually changed their semantic data.
        state.mark_pane_updates(turn_target)
        if self.fixed_ground_name is None:
            state.mark_pane_updates("CONTEXTS")
        if frozen_rule_drafts:
            state.mark_pane_updates("RULES")
        if frozen_memory_drafts:
            state.mark_pane_updates("MEMORIES")
        if kind != "ASK":
            state.mark_pane_updates("GOAL")
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        view.reset_context_candidate_cursor()
        state.selected_context_names = ()
        state.context_selection_finished = False
        state.context_discovery_in_progress = False
        state.context_discovery_complete = True
        activity = state.pane_activities[turn_target]
        activity.phase = "NEEDS_CLARIFICATION" if kind == "ASK" else "PROPOSED"
        activity.detail = question if kind == "ASK" else ""
        if turn_target == "CHAT" and (append_user or initial):
            state.conversation.append(
                _agent_block(
                    understanding=understanding,
                    question=question,
                )
            )
        elif turn_target == "CHAT":
            state.conversation.append(
                "\n".join(
                    [
                        "AGENT RETRY",
                        f"  {safe_terminal_text(understanding)}",
                        "",
                        "AGENT QUESTION",
                        f"  {safe_terminal_text(question)}",
                    ]
                )
            )
        state.error_message = ""
        state.status_message = ""
        if kind == "ASK":
            self.reset_to_input(restore=False)
            if frozen_contexts or frozen_new_contexts:
                view.sync_contexts_pane(align_candidate=True)
                view.focus_contexts()
                view.invalidate()
            elif turn_target != "CHAT":
                state.status_message = (
                    f"{turn_target.title()} revision needs clarification · "
                    "Enter to continue in this pane."
                )
                view.sync_panes(dialogue_anchor="preserve")
                view.focus_turn_target(turn_target)
                view.invalidate()
            return

        frozen = drafted.proposal
        if frozen is None:
            raise AssertionError("A PROPOSE turn must freeze one Ground proposal.")
        if state.planned_ground_name is None:
            # Provider naming stays visibly unapproved in LOCATION; the exact
            # command is rebuilt after any person-owned replacement.
            state.planned_ground_name = frozen.ground_name
            state.location_source = "SUGGESTED"
            state.mark_pane_updates("LOCATION", "CONTEXTS")
        else:
            frozen = replace(frozen, ground_name=state.planned_ground_name)
        exact_goal = state.required_direct_goal
        if exact_goal is not None and frozen.goal != exact_goal:
            raise ValueError(
                "The provider rewrote the directly edited Goal; no command "
                "was prepared."
            )
        if exact_goal is None:
            state.pending_inline_goal = None
        state.editable_goal = frozen.goal
        state.pending = frozen
        state.review_view = "COMMAND"
        state.mode = (
            "CONTEXT_SELECTION"
            if frozen_contexts or frozen_new_contexts
            else "APPROVAL"
        )
        view.input_area.text = ""
        view.sync_input_host()
        view.sync_panes(dialogue_anchor="end")
        if frozen_contexts or frozen_new_contexts:
            view.sync_contexts_pane(align_candidate=True)
            view.focus_contexts()
        elif turn_target != "CHAT":
            state.status_message = (
                f"{turn_target.title()} revision proposed · inspect this pane; "
                "Tab to CHAT for the exact command review."
            )
            view.focus_turn_target(turn_target)
        else:
            view.focus_conversation()
        view.invalidate()

    def fail_interpretation(
        self,
        error: Exception,
        *,
        turn_target: GroundPane,
    ) -> None:
        state = self.state
        state.pending = None
        state.suspended_context_proposal = None
        state.context_suggestions = ()
        state.new_context_suggestions = ()
        state.rule_drafts = ()
        state.memory_drafts = ()
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        state.memory_table_render = None
        state.context_candidate_index = 0
        state.selected_context_names = ()
        state.local_new_context_name = ""
        state.context_selection_finished = False
        state.context_discovery_in_progress = False
        state.context_discovery_complete = False
        state.error_message = f"{type(error).__name__}: {error}"
        activity = state.pane_activities[turn_target]
        activity.phase = "FAILED"
        activity.detail = state.error_message
        state.status_message = ""
        state.mark_pane_updates(turn_target)
        if self.fixed_ground_name is None:
            state.mark_pane_updates("CONTEXTS")
        state.mode = "ERROR"
        self.view.sync_input_host()
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_turn_target(turn_target)
        self.view.invalidate()

    async def interpret_in_background(
        self,
        text: str,
        *,
        append_user: bool,
        initial: bool,
        turn_target: GroundPane,
    ) -> None:
        try:
            response = await interpret_from_background_thread(self.interpret, text)
            if self.state.shell_closed:
                return
            self.finish_interpretation(
                response,
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if not self.state.shell_closed:
                self.fail_interpretation(error, turn_target=turn_target)

    async def animate_thinking(self, generation: int) -> None:
        state = self.state
        while (
            not state.shell_closed
            and state.context_discovery_in_progress
            and state.interpretation_generation == generation
        ):
            await asyncio.sleep(self.thinking_interval_seconds)
            if (
                state.shell_closed
                or not state.context_discovery_in_progress
                or state.interpretation_generation != generation
            ):
                return
            state.thinking_phase = (state.thinking_phase + 1) % len(
                self.view.thinking_suffixes
            )
            self.view.sync_pane_titles()
            self.view.invalidate()

    def begin_interpretation(
        self,
        text: str,
        *,
        append_user: bool,
        initial: bool = False,
        preserve_local_new_context: bool = False,
        turn_target: GroundPane = "CHAT",
        turn_display: str | None = None,
    ) -> None:
        state = self.state
        view = self.view
        if append_user:
            state.submitted_turns.append(text)
            if turn_target == "CHAT":
                state.conversation.append(
                    f"YOU\n  {safe_terminal_text(turn_display or text)}"
                )
        state.active_turn_target = turn_target
        activity = state.pane_activities[turn_target]
        activity.phase = "THINKING"
        activity.request = (turn_display or text).strip()
        activity.detail = ""
        payload = self.dialogue_payload()
        state.pending = None
        state.suspended_context_proposal = None
        state.context_suggestions = ()
        state.new_context_suggestions = ()
        state.rule_drafts = ()
        state.memory_drafts = ()
        state.selected_memory_index = 0
        state.selected_memory_column = 0
        state.memory_table_render = None
        state.context_candidate_index = 0
        state.selected_context_names = ()
        if not preserve_local_new_context:
            state.local_new_context_name = ""
        state.context_selection_finished = False
        state.context_discovery_complete = False
        state.context_discovery_in_progress = True
        state.thinking_phase = 0
        state.interpretation_generation += 1
        generation = state.interpretation_generation
        state.error_message = ""
        state.status_message = ""
        state.mode = "INTERPRETING"
        view.sync_input_host()
        view.sync_panes(dialogue_anchor="end")
        view.focus_turn_target(turn_target)
        view.invalidate()
        application = view.require_application()
        if self.background_interpretation:
            application.create_background_task(self.animate_thinking(generation))
            application.create_background_task(
                self.interpret_in_background(
                    payload,
                    append_user=append_user,
                    initial=initial,
                    turn_target=turn_target,
                )
            )
            return
        try:
            self.finish_interpretation(
                self.interpret(payload),
                append_user=append_user,
                initial=initial,
                turn_target=turn_target,
            )
        except Exception as error:
            self.fail_interpretation(error, turn_target=turn_target)
