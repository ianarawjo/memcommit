"""Provider invocation and response acceptance for the blank Ground workbench."""

from __future__ import annotations

import asyncio

from memcommit.adapters.console.commands.ground.shell.proposal import GroundInterpreter
from memcommit.adapters.console.commands.ground.shell.runtime.grounding_drafting import (
    freeze_grounding_response,
    interpret_from_background_thread,
)
from memcommit.adapters.console.commands.ground.shell.runtime.grounding_drafting.response import (
    GroundingDraftResponse,
)
from memcommit.adapters.console.commands.ground.shell.runtime.session.drafting import (
    DraftRequest,
    DraftThinking,
    GroundPane,
)
from memcommit.adapters.console.commands.ground.shell.runtime.session.state import (
    GroundShellState,
)
from memcommit.adapters.console.commands.ground.shell.runtime.terminal_interaction.workbench.workbench_view import (
    BlankGroundWorkbenchView,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


class BlankGroundGroundingCoordinator:
    """Connect one interpreter call to the draft lifecycle and workbench."""

    def __init__(
        self,
        state: GroundShellState,
        view: BlankGroundWorkbenchView,
        *,
        interpret: GroundInterpreter,
        context_catalog_count: int,
        background_interpretation: bool,
        thinking_interval_seconds: float,
    ) -> None:
        self.state = state
        self.view = view
        self.drafting = state.drafting
        self.interpret = interpret
        self.context_catalog_count = context_catalog_count
        self.background_interpretation = background_interpretation
        self.thinking_interval_seconds = thinking_interval_seconds

    def reset_to_input(self, *, restore: bool) -> None:
        self.drafting.return_to_input()
        self.state.review_view = "COMMAND"
        self.state.status_message = ""
        self.view.input_area.text = self.state.last_submission if restore else ""
        self.view.input_area.buffer.cursor_position = len(self.view.input_area.text)
        self.view.sync_input_host()
        self.view.sync_panes(dialogue_anchor="end")
        self.view.focus_message()
        self.view.invalidate()

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

    def validate_response(
        self, turn: DraftThinking, response: object
    ) -> GroundingDraftResponse:
        drafted = freeze_grounding_response(
            response,
            planned_ground_name=turn.request.planned_ground_name,
            context_catalog_count=self.context_catalog_count,
        )
        exact_goal = turn.request.required_direct_goal
        proposal = drafted.proposal
        if (
            exact_goal is not None
            and proposal is not None
            and proposal.goal != exact_goal
        ):
            raise ValueError(
                "The provider rewrote the directly edited Goal; no command was prepared."
            )
        return drafted

    def accept_response(
        self, turn: DraftThinking, drafted: GroundingDraftResponse
    ) -> None:
        if not self.drafting.is_current(turn):
            return
        proposal = drafted.proposal
        if proposal is not None:
            state = self.state
            if state.planned_ground_name is None:
                # A provider name remains visibly suggested until the person
                # chooses a location or approves the exact creation command.
                state.planned_ground_name = proposal.ground_name
                state.location_source = "SUGGESTED"
                state.mark_pane_updates("LOCATION", "CONTEXTS")
            if turn.request.required_direct_goal is None:
                state.pending_inline_goal = None
            state.editable_goal = proposal.goal
        self.drafting.complete(turn, drafted)

    async def interpret_in_background(self, turn: DraftThinking) -> None:
        try:
            response = await interpret_from_background_thread(
                self.interpret, turn.request.text
            )
            if not self.drafting.is_current(turn):
                return
            drafted = self.validate_response(turn, response)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.drafting.fail(turn, error)
        else:
            self.accept_response(turn, drafted)

    async def animate_thinking(self, turn: DraftThinking) -> None:
        while self.drafting.is_current(turn):
            await asyncio.sleep(self.thinking_interval_seconds)
            if not self.drafting.is_current(turn):
                return
            self.state.thinking_phase = (self.state.thinking_phase + 1) % len(
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
        if append_user:
            state.submitted_turns.append(text)
            if turn_target == "CHAT":
                state.conversation.append(
                    f"YOU\n  {safe_terminal_text(turn_display or text)}"
                )
        selection = self.drafting.selection
        turn = self.drafting.begin(
            DraftRequest(
                text=self.dialogue_payload(),
                target=turn_target,
                display=turn_display or text,
                append_user=append_user,
                initial=initial,
                planned_ground_name=state.planned_ground_name,
                required_direct_goal=state.required_direct_goal,
            ),
            new_context_name=(
                selection.new_context_name
                if preserve_local_new_context and selection
                else ""
            ),
        )
        if self.background_interpretation:
            application = self.view.require_application()
            application.create_background_task(self.animate_thinking(turn))
            application.create_background_task(self.interpret_in_background(turn))
            return
        try:
            drafted = self.validate_response(turn, self.interpret(turn.request.text))
        except Exception as error:
            self.drafting.fail(turn, error)
        else:
            self.accept_response(turn, drafted)
