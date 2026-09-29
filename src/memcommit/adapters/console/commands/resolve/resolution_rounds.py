"""Repeat decision collection and reinspection until Resolve results are ready."""

from memcommit.adapters.console.commands.resolve.decision_round.workflow import (
    run_resolve_console,
)
from memcommit.adapters.console.terminal.components.command_wait import run_command_wait
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.application.operations.resolve.application import ResolveFramePort
from memcommit.application.operations.resolve.choice_plans import prepare_resolve_choice
from memcommit.application.operations.resolve.decisions import ResolveDecision
from memcommit.application.operations.resolve.detached import DetachedResolvePort
from memcommit.application.operations.resolve.issue_review import (
    ResolveReviewInput,
    next_issue_analysis,
)
from memcommit.application.operations.resolve.proposal import ResolveProposal


def run_resolution_rounds(
    inputs: tuple[ResolveReviewInput, ...],
    *,
    frame_port: ResolveFramePort | None = None,
    provider_factory=None,
    preview_choices=False,
    initial_decisions: tuple[ResolveDecision, ...] | None = None,
    header_label="RESOLVE",
    allow_bulk=False,
    require_tty=True,
    **terminal_options,
) -> tuple[ResolveProposal, ...] | None:
    """Review one Context and repeat only for new or changed semantic findings."""
    if not inputs or any(not isinstance(item, ResolveReviewInput) for item in inputs):
        raise ValueError("Issue review requires prepared Resolve inputs.")
    if len(inputs) != 1 or provider_factory is None:
        raise ValueError("Issue review requires one Context and a provider.")

    initial_frame = inputs[0].analysis.frame
    if frame_port is None:
        frame_port = DetachedResolvePort(
            inputs[0].analysis.audit.source, revision=initial_frame.revision
        )
    reviewed_choices = {}

    def current_port(current, previous):
        # Reinspection uses detached post-images but retains original live authority.
        frame_port.revalidate(initial_frame)
        return (
            frame_port
            if previous is None
            else DetachedResolvePort(
                current.audit.source, revision=current.frame.revision
            )
        )

    def prepare_choice(current, decision, previous):
        port = current_port(current, previous)
        key = (current.frame.revision, decision)
        if key not in reviewed_choices:
            reviewed_choices[key] = prepare_resolve_choice(
                current, decision, frame_port=port, provider_factory=provider_factory
            )
        return reviewed_choices[key]

    def prepare_results(current_inputs, decisions, previous):
        known = {issue.uid for item in current_inputs for issue in item.analysis.issues}
        if any(decision.issue_uid not in known for decision in decisions):
            raise ValueError("Issue review received a decision outside its inputs.")
        results = []
        for item in current_inputs:
            current = item.analysis
            issue_uids = {issue.uid for issue in current.issues}
            results.append(
                item.prepare_result(
                    tuple(d for d in decisions if d.issue_uid in issue_uids),
                    provider_factory=provider_factory,
                    frame_port=current_port(current, previous),
                    previous=previous,
                    # An empty cache must not silently generate an unseen replacement.
                    reviewed_choices={
                        decision: value
                        for (revision, decision), value in reviewed_choices.items()
                        if revision == current.frame.revision
                    }
                    if preview_choices
                    else None,
                )
            )
        return tuple(results)

    original_inputs = inputs
    previous = None
    number = 1
    while True:
        analysis = inputs[0].analysis
        if number == 1 and initial_decisions is not None:
            decisions = initial_decisions
        elif analysis.issues:
            if require_tty:
                require_interactive_terminal("Interactive issue review")
            decisions = run_resolve_console(
                analysis,
                header_label=f"{header_label} · ROUND {number}",
                allow_bulk=allow_bulk,
                prepare_choice=(
                    lambda decision: prepare_choice(analysis, decision, previous)
                )
                if preview_choices
                else None,
                **terminal_options,
            )
            if decisions is None:
                return None
        else:
            decisions = ()
        results = run_command_wait(
            header_label.split(" · ")[0],
            "preparing and checking decisions",
            total=1,
            work=lambda progress: prepare_results(inputs, decisions, previous),
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
            work=lambda progress: next_issue_analysis(
                previous,
                direction_provider_factory=provider_factory,
            ),
        )
        inputs = (ResolveReviewInput(following),)
        number += 1
