"""Mutable process-local state for one blank-Ground terminal session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from memcommit.adapters.console.terminal.core.text import safe_terminal_text

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellProposal,
    GroundShellResult,
)

from memcommit.adapters.console.commands.ground.shell.runtime.session.drafting import (
    DraftRequest,
    GroundDraftLifecycle,
    GroundPane,
)

GroundPaneActivityPhase = Literal[
    "IDLE",
    "THINKING",
    "PROPOSED",
    "NEEDS_CLARIFICATION",
    "FAILED",
]
GroundLocationSource = Literal["UNSET", "SUGGESTED", "SELECTED", "RESUMED"]


@dataclass
class GroundPaneActivity:
    """One target-owned semantic turn projected in its originating pane."""

    phase: GroundPaneActivityPhase = "IDLE"
    request: str = ""
    detail: str = ""


@dataclass
class GroundShellState:
    """Own every mutable value that lives only for one terminal Application.

    Durable Ground mutation remains behind the injected Apply callback. Keeping
    these values together gives the four runtime responsibilities one explicit
    session object instead of sharing dozens of closure-owned dictionaries.
    """

    planned_ground_name: str | None
    location_source: GroundLocationSource
    editable_goal: str
    drafting: GroundDraftLifecycle
    last_submission: str
    last_submission_target: GroundPane
    last_submission_display: str
    submitted_turns: list[str]
    conversation: list[str]

    required_direct_goal: str | None = None
    inline_goal_open: bool = False
    inline_goal_original: str = ""
    inline_context_open: bool = False
    inline_context_original: str = ""
    panel_comment_target: GroundPane | None = None
    panel_comment_focus: str = ""
    pending_inline_goal: tuple[str, str, str] | None = None
    suspended_message: str = ""
    review_view: Literal["COMMAND", "EFFECTS"] = "COMMAND"
    memory_view: Literal["LIST", "TABLE"] = "LIST"
    thinking_phase: int = 0
    active_turn_target: GroundPane = "CHAT"
    pane_activities: dict[GroundPane, GroundPaneActivity] = field(default_factory=dict)
    pane_notifications: dict[GroundPane, bool] = field(default_factory=dict)
    status_message: str = ""

    @classmethod
    def create(
        cls,
        *,
        fixed_ground_name: str | None,
        initial_proposal: GroundShellProposal | None,
        initial_turns: tuple[str, ...],
        working_goal: str,
        context_catalog_count: int,
        initial_question: str,
    ) -> GroundShellState:
        """Construct the process-local state and its initial conversation."""

        pane_activities = {
            pane: GroundPaneActivity()
            for pane in (
                "LOCATION",
                "GOAL",
                "CONTEXTS",
                "RULES",
                "MEMORIES",
                "CHAT",
            )
        }
        if initial_proposal is not None:
            pane_activities["GOAL"] = GroundPaneActivity(
                phase="PROPOSED",
                request=(initial_turns[-1] if initial_turns else ""),
            )
        conversation = (
            [
                "\n".join(
                    [
                        "RESUMED DRAFT · NOT CREATED",
                        "  The saved proposal is ready for exact command review.",
                        "  No Context, manifest, or checkpoint exists yet.",
                    ]
                )
            ]
            if initial_proposal is not None
            else [
                "\n".join(
                    [
                        "YOU · STARTING REQUEST",
                        f"  {safe_terminal_text(working_goal)}",
                        "",
                        "AGENT · CONTEXT DISCOVERY",
                        (
                            f"  Checking {context_catalog_count} ordinary Context "
                            "locator names."
                            if context_catalog_count
                            else "  No ordinary Context locator names were found."
                        ),
                        "  No Context Memory content will be opened.",
                    ]
                )
            ]
            if working_goal
            else [
                "\n".join(
                    [
                        "OPEN QUESTION · GOAL",
                        f"  {initial_question}",
                        "",
                        "Start in your own words; a rough outcome, case, or",
                        "uncertainty is enough.",
                    ]
                )
            ]
        )
        return cls(
            planned_ground_name=fixed_ground_name,
            location_source=(
                "RESUMED"
                if initial_proposal is not None
                else "SELECTED"
                if fixed_ground_name is not None
                else "UNSET"
            ),
            editable_goal=working_goal,
            drafting=(
                GroundDraftLifecycle.resumed(
                    initial_proposal,
                    DraftRequest(
                        text=initial_turns[-1] if initial_turns else "",
                        target="GOAL",
                        display=working_goal,
                    ),
                )
                if initial_proposal is not None
                else GroundDraftLifecycle()
            ),
            last_submission=(initial_turns[-1] if initial_turns else working_goal),
            last_submission_target="GOAL" if working_goal else "CHAT",
            last_submission_display=working_goal,
            submitted_turns=list(initial_turns),
            conversation=conversation,
            active_turn_target="GOAL" if initial_proposal is not None else "CHAT",
            pane_activities=pane_activities,
            pane_notifications={pane: False for pane in pane_activities},
            status_message=(
                "Draft resumed · NOT CREATED · review and approve the exact command."
                if initial_proposal is not None
                else ""
            ),
        )

    def mark_pane_updates(self, *layers: GroundPane) -> None:
        for layer in layers:
            self.pane_notifications[layer] = True

    def acknowledge_pane(self, layer: GroundPane) -> None:
        self.pane_notifications[layer] = False

    def result(
        self,
        status: Literal["APPLIED", "CANCELLED", "BACK_TO_PICKER"],
        *,
        proposal: GroundShellProposal | None = None,
        actual_output: object | None = None,
    ) -> GroundShellResult:
        """Project one terminal outcome without adding another mutation path."""

        selection = self.drafting.selection
        return GroundShellResult(
            status=status,
            proposal=(
                proposal
                if proposal is not None
                else self.drafting.pending or self.drafting.suspended_context_proposal
            ),
            actual_output=(str(actual_output) if actual_output is not None else None),
            submitted_turns=tuple(self.submitted_turns),
            selected_context_names=selection.context_names if selection else (),
            new_context_name_hint=self.drafting.new_context_name or None,
        )
