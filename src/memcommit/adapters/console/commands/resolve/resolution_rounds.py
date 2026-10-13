"""Repeat decision collection and reinspection until Resolve results are ready."""

from memcommit.adapters.console.commands.resolve.decision_round.workflow import (
    run_resolve_console,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from typing import Callable
from memcommit.application.operations.resolve.review_round.build_change_plans_for_choices import (
    prepare_resolve_choice,
)
from memcommit.application.operations.resolve.review_round.finalize_review_decisions import (
    ResolveDecision,
)
from memcommit.adapters.console.commands.resolve.in_round_change_review.review_selected_changes import (
    review_selected_changes,
)
from memcommit.application.operations.resolve.review_round.review_session import (
    ResolveReviewSession,
)
from memcommit.application.operations.resolve.analysis.analyze_next_review_round import (
    analyze_next_review_round,
)
from memcommit.application.operations.resolve.resolve_finalization.proposal import (
    ResolveProposal,
)


def run_resolution_rounds(
    inputs: tuple[ResolveReviewSession, ...],
    *,
    revalidate_target: Callable[[], None] | None = None,
    provider_factory=None,
    preview_choices=False,
    initial_decisions: tuple[ResolveDecision, ...] | None = None,
    header_label="RESOLVE",
    allow_bulk=False,
    require_tty=True,
    **terminal_options,
) -> tuple[ResolveProposal, ...] | None:
    """Review one Context and repeat only for new or changed semantic findings."""
    if not inputs or any(not isinstance(item, ResolveReviewSession) for item in inputs):
        raise ValueError("Issue review requires prepared Resolve inputs.")
    if len(inputs) != 1 or provider_factory is None:
        raise ValueError("Issue review requires one Context and a provider.")

    reviewed_choices = {}

    def check_live_target():
        if revalidate_target is not None:
            revalidate_target()

    def prepare_choice(current, decision):
        check_live_target()
        key = (current.frame.revision, decision)
        if key not in reviewed_choices:
            reviewed_choices[key] = prepare_resolve_choice(
                current, decision, provider_factory=provider_factory
            )
        check_live_target()
        return reviewed_choices[key]

    def current_reviewed_choices(current):
        return {
            decision: value
            for (revision, decision), value in reviewed_choices.items()
            if revision == current.frame.revision
        }

    def prepare_results(current_inputs, decisions, previous, chosen_candidate_uids):
        known = {issue.uid for item in current_inputs for issue in item.analysis.issues}
        if any(decision.issue_uid not in known for decision in decisions):
            raise ValueError("Issue review received a decision outside its inputs.")
        check_live_target()
        results = []
        for item in current_inputs:
            current = item.analysis
            issue_uids = {issue.uid for issue in current.issues}
            results.append(
                item.prepare_result(
                    tuple(d for d in decisions if d.issue_uid in issue_uids),
                    provider_factory=provider_factory,
                    previous=previous,
                    # An empty cache must not silently generate an unseen replacement.
                    reviewed_choices=current_reviewed_choices(current)
                    if preview_choices
                    else None,
                    chosen_candidate_uids=chosen_candidate_uids,
                )
            )
        check_live_target()
        return tuple(results)

    original_inputs = inputs
    previous = None
    number = 1
    while True:
        check_live_target()
        analysis = inputs[0].analysis
        revisit_decisions = ()
        while True:
            if number == 1 and initial_decisions is not None and not revisit_decisions:
                decisions = initial_decisions
            elif analysis.issues:
                if require_tty:
                    require_interactive_terminal("Interactive issue review")
                decisions = run_resolve_console(
                    analysis,
                    header_label=f"{header_label} · ROUND {number}",
                    allow_bulk=allow_bulk,
                    prepare_choice=(lambda decision: prepare_choice(analysis, decision))
                    if preview_choices
                    else None,
                    initial_decisions=revisit_decisions,
                    **terminal_options,
                )
                if decisions is None:
                    return None
            else:
                decisions = ()
            chosen_candidate_uids = {}
            if preview_choices and decisions:
                check_live_target()
                chosen = review_selected_changes(
                    analysis,
                    decisions,
                    target=analysis.frame.source.context(),
                    reviewed_choices=current_reviewed_choices(analysis),
                    header_label=f"{header_label} · ROUND {number}",
                    **terminal_options,
                )
                if chosen is None:
                    revisit_decisions = decisions
                    continue
                chosen_candidate_uids = chosen
            break
        results = run_command_wait(
            header_label.split(" · ")[0],
            "preparing and checking decisions",
            total=1,
            work=lambda progress: prepare_results(
                inputs, decisions, previous, chosen_candidate_uids
            ),
        )
        for original, current, result in zip(
            original_inputs, inputs, results, strict=True
        ):
            original.accept_reviewed_result(current, result)
        if not results[0].blocking_audit_keys:
            return results
        previous = results[0]
        following = run_command_wait(
            header_label.split(" · ")[0],
            "preparing the next issues",
            total=1,
            work=lambda progress: analyze_next_review_round(
                previous,
                direction_provider_factory=provider_factory,
            ),
        )
        inputs = (ResolveReviewSession(following),)
        number += 1
