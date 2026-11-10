"""Prepare decision previews, run the screen and finalize Conflict decisions."""

from __future__ import annotations

from dataclasses import replace

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.conflict.receipt import (
    render_conflict_resolution_status,
)
from memcommit.adapters.console.commands.conflict.decision_round.impact_diff import (
    project_choice_previews,
    project_semantic_choice,
)
from memcommit.adapters.console.commands.conflict.decision_round.screen.inputs import (
    CompactScreenPresentation,
)
from memcommit.adapters.console.commands.conflict.decision_round.screen.screen import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.commands.conflict.decision_round.answers import (
    DecisionRoundState,
)
from memcommit.adapters.console.commands.conflict.decision_round.screen_content import (
    build_decision_view,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.application.operations.conflict.review_round.finalize_review_decisions import (
    ConflictResolutionDecision,
)
from memcommit.application.operations.conflict.model import (
    ConflictResolutionAnalysis,
    ConflictResolutionError,
)

CONFLICT_RESOLUTION_PRESENTATION = CompactScreenPresentation(
    response_title="YOUR INTENT",
    continue_label="Review changes",
    activation_hint="select/continue",
    show_item_navigation=True,
    require_all_decisions=False,
)


def collect_conflict_resolution_decisions(
    analysis: ConflictResolutionAnalysis,
    *,
    header_label: str = "CONFLICT",
    allow_bulk: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    prepare_choice=None,
    initial_decisions: tuple[ConflictResolutionDecision, ...] = (),
) -> tuple[ConflictResolutionDecision, ...] | None:
    """Collect decisions for one analysis without applying changes."""

    if not isinstance(analysis, ConflictResolutionAnalysis):
        raise TypeError("Conflict requires a typed analysis.")

    if not analysis.issues:
        render_conflict_resolution_status(analysis)
        return None

    decision_state = prepare_decision_state(
        analysis,
        allow_bulk=allow_bulk,
        prepare_choice=prepare_choice,
        initial_decisions=initial_decisions,
    )
    action = run_compact_resolution_decisions(
        view=decision_state.view,
        decisions=decision_state,
        presentation=CONFLICT_RESOLUTION_PRESENTATION,
        header_label=header_label,
        app_input=app_input,
        app_output=app_output,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind != "ACCEPT":
        raise ConflictResolutionError("Conflict decisions returned an invalid action.")

    return decision_state.finalize_decisions()


def prepare_decision_state(
    analysis: ConflictResolutionAnalysis,
    *,
    allow_bulk: bool,
    prepare_choice,
    initial_decisions: tuple[ConflictResolutionDecision, ...] = (),
) -> DecisionRoundState:
    """Prepare every initial suggestion preview before opening the screen."""
    view = build_decision_view(analysis)
    choice_previews = project_choice_previews(analysis)
    options_by_uid = {
        item.uid: {option.uid for option in item.options} for item in view.items
    }
    if prepare_choice is not None:
        for issue in analysis.issues:
            if f"{issue.uid}:confirm" in options_by_uid[issue.uid]:
                choice = run_command_wait(
                    "CONFLICT",
                    "preparing suggestion preview",
                    total=1,
                    work=lambda progress, issue=issue: prepare_choice(
                        ConflictResolutionDecision(issue.uid, "CONFIRM")
                    ),
                )
                choice_previews[f"{issue.uid}:confirm"] = project_semantic_choice(
                    analysis, choice
                )
        view = replace(
            view,
            items=tuple(
                (
                    replace(
                        item,
                        options=tuple(
                            (
                                replace(option, label="USE THIS SUGGESTION")
                                if option.uid.endswith(":confirm")
                                and option.uid in choice_previews
                                else option
                                for option in item.options
                            )
                        ),
                    )
                    for item in view.items
                )
            ),
        )
    state = DecisionRoundState(
        analysis,
        view,
        choice_previews,
        allow_bulk=allow_bulk,
        prepare_choice=prepare_choice,
    )
    for decision in initial_decisions:
        if decision.kind == "INTENT":
            state.submit_intent(decision.issue_uid, decision.intent)
            if prepare_choice is not None:
                choice = prepare_choice(decision)
                choice_previews[f"{decision.issue_uid}:intent"] = (
                    project_semantic_choice(analysis, choice, include_explanation=False)
                )
        else:
            state.select_choice(
                decision.issue_uid, f"{decision.issue_uid}:{decision.kind.lower()}"
            )
    return state


__all__ = ["collect_conflict_resolution_decisions"]
