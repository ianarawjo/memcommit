"""Terminal workbench adapter for one saved Context Meld."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.application.capabilities.review_policy import (
    ownership_aware_application_review,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.text_layout import (
    elide_terminal_text,
    single_line_terminal_text,
)
from memcommit.adapters.console.terminal.components.peer_relations.presentation import (
    render_peer_relation_analysis,
)
from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import (
    MELD_INLINE_MEMORY_SCHEMA_VERSION,
    MeldSession,
    meld_canonical_digest,
)
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld import command_codec as meld_command_review
from memcommit.application.capabilities.resolution.workbench import ResolutionNavigation


@dataclass(frozen=True)
class MeldShellAction:
    kind: str
    issue_uid: str | None = None
    option_uid: str | None = None
    comment: str = ""
    destination: str | None = None


def _line(value: str, limit: int = 100) -> str:
    normalized = single_line_terminal_text(safe_terminal_text(value))
    return elide_terminal_text(normalized, limit)


def _relation_issue_resolution_badges(session: MeldSession) -> tuple[str, ...]:
    """Project durable relation-issue outcomes without inventing a selection."""
    if session.relation_analysis_seed is None or session.current_assessment is None:
        return ()
    assessment = session.current_assessment
    open_issue_uids = {issue.uid for issue in assessment.issues}
    proposals_by_relation = {
        relation_uid: tuple(
            proposal
            for proposal in assessment.proposals
            if relation_uid in proposal.relation_uids
        )
        for issue in session.relation_analysis_seed.analysis.issues
        for relation_uid in issue.relation_uids
    }
    badges: list[str] = []
    for issue in session.relation_analysis_seed.analysis.issues:
        if issue.uid in open_issue_uids:
            badges.append("")
            continue
        matched_label = ""
        for turn in reversed(session.user_turns):
            for option in issue.options:
                if option.text in turn.comment:
                    matched_label = f"CHOSEN · {option.label}"
                    break
            if matched_label:
                break
            marker = f"- {issue.title}: Other direction:"
            marked_line = next(
                (
                    line.partition(marker)[2].strip()
                    for line in turn.comment.splitlines()
                    if marker in line
                ),
                "",
            )
            direct_comment = marked_line or (
                turn.comment.strip()
                if issue.uid in turn.issue_uids
                and not turn.comment.startswith("Choose this reading:")
                else ""
            )
            if direct_comment:
                matched_label = f"OTHER DIRECTION · {_line(direct_comment, 72)}"
                break
        if matched_label:
            badges.append(matched_label)
            continue
        related = tuple(
            proposal
            for relation_uid in issue.relation_uids
            for proposal in proposals_by_relation.get(relation_uid, ())
        )
        dispositions = {proposal.disposition for proposal in related}
        if related and dispositions == {"PRESERVE"}:
            option_labels = " + ".join(option.label for option in issue.options)
            badges.append(f"KEPT BOTH · {option_labels}")
        elif "SYNTHESIZE" in dispositions:
            synthesized = tuple(
                proposal for proposal in related if proposal.disposition == "SYNTHESIZE"
            )
            detail = _line(synthesized[0].content, 72)
            if len(synthesized) > 1:
                detail += f" + {len(synthesized) - 1} more"
            badges.append(f"COMBINED · {detail}")
        elif "COALESCE" in dispositions:
            coalesced = next(
                proposal for proposal in related if proposal.disposition == "COALESCE"
            )
            badges.append(f"COALESCED · {_line(coalesced.content, 72)}")
        else:
            badges.append("RESOLVED")
    return tuple(badges)


def run_meld_shell(
    session: MeldSession,
    *,
    navigation: ResolutionNavigation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    read_only: bool = False,
    review_only: bool = False,
    destination=None,
    analysis_origin: str | None = None,
    draft_loader: Callable[[str], tuple[str | None, str]] | None = None,
    draft_saver: Callable[[str, str | None, str], None] | None = None,
) -> MeldShellAction | None:
    """Collect one action through the shared dynamic resolution workbench."""
    from memcommit.adapters.console.terminal.components.resolution.session_shell import (
        ResolutionGlobalStrategy,
        run_resolution_workbench_shell,
    )
    from memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_projection import (
        MeldResolutionWorkbenchAdapter,
    )
    from memcommit.adapters.console.terminal.components.impact import ImpactController
    from memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.review import meld_review_report

    snapshot_hint = (
        "Run the same 'mem meld' command outside a TTY to render its saved snapshot."
    )
    if require_tty:
        require_interactive_terminal(
            "Interactive meld",
            snapshot_hint=snapshot_hint,
        )
    if session.current_assessment is None:
        return None
    adapter = MeldResolutionWorkbenchAdapter(session)

    def current_view():
        view = adapter.view()
        if analysis_origin is None:
            return view
        label = (
            "EXACT PREWARM"
            if analysis_origin == "EXACT_PREWARM"
            else "EQUIVALENT SCOPE PREWARM"
        )
        return replace(view, status=f"{view.status} · {label} · PROVIDER NOT CALLED")

    review_view = None
    if review_only:
        review_view = meld_review_report(session).report().view
        if review_view is None:
            raise ValueError("Meld Review report has no interactive view.")
    relation_report: str | None = None
    if session.mode == "SYMMETRIC" and session.relation_analysis_seed is not None:
        # The relation analysis is already copied into the Meld seed. Re-render
        # that exact artifact instead of maintaining a second summary dialect.
        # Navigation hints are omitted because this target-bound Meld already
        # supplies the next interaction below the shared report.
        relation_report = (
            render_peer_relation_analysis(
                session.relation_analysis_seed.analysis,
                reused=True,
                origin=analysis_origin or "SAVED_REUSE",
                durable=True,
                heading="MEM COMPARE · SYMMETRIC PEERS",
            )
            .partition("\nThe complete source-linked relation ledger")[0]
            .rstrip()
        )
        if analysis_origin is not None:
            label = (
                "EXACT PREWARM"
                if analysis_origin == "EXACT_PREWARM"
                else "EQUIVALENT SCOPE PREWARM"
            )
            first_line, separator, remainder = relation_report.partition("\n")
            relation_report = (
                first_line
                + separator
                + f"ANALYSIS ORIGIN · {label} · PROVIDER NOT CALLED\n"
                + remainder
            )
    report_badges = _relation_issue_resolution_badges(session)
    report_conflicts_remaining = sum(not badge for badge in report_badges)
    global_strategies = (
        ResolutionGlobalStrategy(
            label="Preserve all HELPFUL compatible/scoped items separately",
            action_kind="SUBMIT_ALL",
            comment=(
                "Keep every remaining HELPFUL COMPATIBLE or SCOPED relation "
                "at the preservation-first default: copy each independently "
                "useful source Memory as its own target Memory. Apply this "
                "below the REQUIRED priority threshold without changing any "
                "still-required conflict decision."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Combine HELPFUL items only when one atomic result is lossless",
            action_kind="SUBMIT_ALL",
            comment=(
                "For remaining HELPFUL COMPATIBLE or SCOPED relations, combine "
                "members only when one independently revisable Memory retains "
                "every rate, condition, audience, modality, exception, and "
                "source-specific scope. Otherwise preserve the members "
                "separately. Apply the same rationale to later related issues, "
                "but do not resolve any REQUIRED conflict by this strategy."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Preserve every unresolved distinction",
            action_kind="SUBMIT_ALL",
            comment=(
                "Preserve every unresolved distinction without forcing a "
                "choice, while applying the explicitly reviewed responses."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the broadest applicable choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "For each remaining conflict, choose the option with the "
                "broadest justified applicability or coverage. Retain any "
                "qualification needed to avoid extending a claim beyond its "
                "source support, and preserve compatible distinct information."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the narrowest useful choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "For each remaining conflict, choose the narrowest, most "
                "specific, or most constrained option that remains useful. "
                "Preserve compatible distinct information outside the conflict."
            ),
        ),
        ResolutionGlobalStrategy(
            label="Use the strongest-supported choice for unresolved conflicts",
            action_kind="SUBMIT_ALL",
            comment=(
                "Resolve each remaining conflict independently by choosing "
                "the option with the strongest support in the source Memories "
                "and current user guidance. Preserve compatible and "
                "non-conflicting distinct information from both sources."
            ),
        ),
    )
    active_view = current_view()
    impact_controller = (
        ImpactController.from_text(
            operation=active_view.operation,
            artifact_uid=active_view.artifact_uid,
            revision=active_view.revision,
            title="IMPACT · COMPARE",
            summary=(
                "This saved Compare analysis is the symmetric Meld impact. "
                "It remains read-only until the reviewed Meld is applied."
            ),
            detail=relation_report,
        )
        if relation_report is not None
        else ImpactController.from_resolution(
            current_view,
            title="IMPACT · DIRECTIONAL MELD",
            summary=(
                "These are the exact proposed baseline effects of this "
                "directional Meld, not an equal-authority Compare."
            ),
        )
    )

    def turn_review(action):
        if action.kind == "ACCEPT" or action.kind == "CHANGE_DESTINATION":
            return None
        frame_by_role = {frame.role: frame for frame in session.frames}
        left_frame = (
            frame_by_role["INCOMING"]
            if session.mode == "DIRECTIONAL"
            else session.frames[0]
        )
        right_frame = (
            frame_by_role["BASELINE"]
            if session.mode == "DIRECTIONAL"
            else session.frames[1]
        )
        option_number = None
        if action.item_uid is not None and action.option_uid is not None:
            issue = next(
                issue
                for issue in session.current_assessment.issues
                if issue.uid == action.item_uid
            )
            option_number = next(
                index
                for index, option in enumerate(issue.options, start=1)
                if option.uid == action.option_uid
            )
        return meld_command_review.build_turn_review(
            left_name=left_frame.context_name,
            right_name=right_frame.context_name,
            target_name=(
                session.target.context_name if session.mode == "SYMMETRIC" else None
            ),
            left_descendants=left_frame.include_descendants,
            right_descendants=right_frame.include_descendants,
            left_memory_uid=left_frame.selected_memory_uid,
            right_memory_uid=right_frame.selected_memory_uid,
            incoming_text=(
                left_frame.memories[0].content
                if session.schema_version == MELD_INLINE_MEMORY_SCHEMA_VERSION
                else None
            ),
            expected_session=meld_canonical_digest(session.to_dict()),
            issue_uid=action.item_uid,
            option_number=option_number,
            comment=action.comment,
            preserve_all=action.kind == "PRESERVE_ALL",
            defer_all=action.kind == "DEFER",
        )

    action = run_resolution_workbench_shell(
        review_view if review_view is not None else current_view,
        navigation=navigation,
        app_input=app_input,
        app_output=app_output,
        require_tty=False,
        terminal_label="Interactive meld",
        snapshot_hint=snapshot_hint,
        split_viewer_items=True,
        global_strategies=global_strategies,
        split_report_text=relation_report,
        split_report_item_badges=report_badges,
        split_report_conflicts_remaining=report_conflicts_remaining,
        review_and_apply=not read_only and not review_only,
        decision_free_behavior=(
            ownership_aware_application_review(
                mutates_granted_authority=session.granted_target is not None,
                local_undo_available=True,
            ).decision_free_behavior
            if not read_only and not review_only
            else "REPORT_FIRST"
        ),
        read_only=read_only,
        impact_controller=None if review_only else impact_controller,
        destination=destination,
        draft_loader=draft_loader,
        draft_saver=draft_saver,
        save_draft_on_close=draft_saver is not None,
        turn_command_review=turn_review,
        compact_decisions=not read_only and not review_only,
    )
    if action.kind == "CLOSE":
        return None
    if action.kind == "SUBMIT_ALL":
        return MeldShellAction(kind="COMMENT_ALL", comment=action.comment)
    if action.kind == "PRESERVE_ALL":
        return MeldShellAction(kind="PRESERVE_ALL")
    if action.kind == "DEFER":
        return MeldShellAction(kind="DEFER_ALL")
    if action.kind == "ACCEPT":
        return MeldShellAction(kind="ACCEPT")
    if action.kind == "CHANGE_DESTINATION":
        return MeldShellAction(
            kind="CHANGE_DESTINATION",
            destination=action.destination,
        )
    if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
        raise ValueError(f"Unsupported resolution action '{action.kind}' for Meld.")
    return MeldShellAction(
        kind="COMMENT_ISSUE",
        issue_uid=action.item_uid,
        option_uid=action.option_uid,
        comment=action.comment,
    )


# Historical tests and callers may still import the private Compare-era helper.
_comparison_issue_resolution_badges = _relation_issue_resolution_badges
