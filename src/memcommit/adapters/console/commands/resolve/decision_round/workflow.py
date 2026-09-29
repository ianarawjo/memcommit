"""Prepare decision previews, run the screen and finalize Resolve decisions."""

from __future__ import annotations

from dataclasses import replace

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.resolve.receipt import render_resolve_status
from memcommit.adapters.console.commands.resolve.decision_round.impact_diff import (
    project_choice_previews,
    project_semantic_choice,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen.inputs import (
    CompactScreenPresentation,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen.screen import (
    run_compact_resolution_decisions,
)
from memcommit.adapters.console.commands.resolve.decision_round.answers import (
    DecisionRoundState,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen_content import (
    build_decision_view,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.application.operations.resolve.decisions import ResolveDecision
from memcommit.application.operations.resolve.model import ResolveAnalysis, ResolveError

RESOLVE_PRESENTATION = CompactScreenPresentation(
    response_title="YOUR INTENT",
    continue_label="Review changes",
    activation_hint="select/review",
    show_item_navigation=True,
    require_all_decisions=False,
)


def run_resolve_console(
    analysis: ResolveAnalysis,
    *,
    header_label: str = "RESOLVE",
    allow_bulk: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    prepare_choice=None,
) -> tuple[ResolveDecision, ...] | None:
    """Collect decisions for one analysis without applying changes."""

    if not isinstance(analysis, ResolveAnalysis):
        raise TypeError("Resolve requires a typed analysis.")

    if not analysis.issues:
        render_resolve_status(analysis)
        return None

    decision_state = prepare_decision_state(
        analysis,
        allow_bulk=allow_bulk,
        prepare_choice=prepare_choice,
    )
    action = run_compact_resolution_decisions(
        view=decision_state.view,
        decisions=decision_state,
        presentation=RESOLVE_PRESENTATION,
        header_label=header_label,
        app_input=app_input,
        app_output=app_output,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind != "ACCEPT":
        raise ResolveError("Resolve decisions returned an invalid action.")

    return decision_state.finalize_decisions()


def prepare_decision_state(
    analysis: ResolveAnalysis,
    *,
    allow_bulk: bool,
    prepare_choice,
) -> DecisionRoundState:
    """Prepare every initial suggestion preview before opening the screen."""
    view = build_decision_view(analysis)
    choice_previews = project_choice_previews(analysis)
    options_by_uid = {
        item.uid: {option.uid for option in item.options} for item in view.items
    }
    if prepare_choice is not None:
        for issue in analysis.issues:
            if (
                issue.item_kind == "MEMORY"
                and f"{issue.uid}:confirm" in options_by_uid[issue.uid]
            ):
                choice = run_command_wait(
                    "RESOLVE",
                    "preparing suggestion preview",
                    total=1,
                    work=lambda progress, issue=issue: prepare_choice(
                        ResolveDecision(issue.uid, "CONFIRM")
                    ),
                )
                choice_previews[f"{issue.uid}:confirm"] = project_semantic_choice(
                    analysis, choice
                )
        view = replace(
            view,
            items=tuple(
                replace(
                    item,
                    options=tuple(
                        replace(option, label="USE SUGGESTION")
                        if option.uid.endswith(":confirm")
                        and option.uid in choice_previews
                        and item.kind != "REDUNDANCY"
                        else option
                        for option in item.options
                    ),
                )
                for item in view.items
            ),
        )
    return DecisionRoundState(
        analysis,
        view,
        choice_previews,
        allow_bulk=allow_bulk,
        prepare_choice=prepare_choice,
    )


__all__ = ["run_resolve_console"]
