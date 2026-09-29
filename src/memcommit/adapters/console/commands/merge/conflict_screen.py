"""Merge-owned exact choice screen, composed from the compact UI pieces."""

from dataclasses import replace

from memcommit.adapters.console.commands.resolve.decision_round.screen.screen import (
    build_compact_application,
)
from memcommit.adapters.console.commands.resolve.decision_round.screen.screen_state import (
    DecisionScreenState,
)
from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.operations.merge.analysis.candidate import digest
from memcommit.application.operations.merge.analysis.choices import (
    EXACT_DECISIONS,
    MergeConflictAnalysis,
    MergeConflictDecision,
    MergeConflictIssue,
    MergeDecisionSet,
    finalize_merge_decisions,
    initial_review_decisions,
    merge_sides,
    structural_item_description,
)
from memcommit.application.operations.merge.analysis.materialization import (
    materialize_exact_decisions,
)


def run_merge_conflicts(
    review, *, bulk=None, require_tty=True, app_input=None, app_output=None
):
    """Collect fixed Merge choices and calculate an unsaved, complete Context."""
    if review.structural_input is None:
        raise ValueError("Merge conflict screen requires an exact Merge review.")
    decisions = initial_review_decisions(review, bulk.value if bulk else None)
    issues = review.analysis.review_issues
    if decisions is not None or not issues:
        return review.prepare_result(decisions or ())
    if require_tty:
        require_interactive_terminal("Merge conflict review")
    view = compact_resolve_views((review.analysis,))
    selected = {
        item.uid: item.selected_option_uid
        for item in view.items
        if item.selected_option_uid
    }
    available = {
        issue.uid: {choice.uid for choice in issue.choices} for issue in issues
    }
    common = set.intersection(*available.values())

    def stage(uid, option):
        if option.rpartition(":")[2].upper() not in available[uid]:
            raise ValueError("Merge selected an unavailable choice.")
        selected[uid] = option

    def stage_bulk(choice):
        if choice not in common:
            raise ValueError("Merge bulk choice is unavailable.")
        for issue in issues:
            stage(issue.uid, f"{issue.uid}:{choice.lower()}")

    def finish(_):
        if not all(selected.get(issue.uid) for issue in issues):
            return None
        return ResolutionWorkbenchAction(kind="ACCEPT")

    state = DecisionScreenState(
        lambda: view,
        selected.get,
        stage,
        lambda: "Finalize decisions",
        bulk_options=tuple(
            ResolutionOption(c.uid, c.label + " FOR ALL", c.text)
            for c in issues[0].choices
            if c.uid in common
        ),
        show_item_navigation=True,
    )
    state.initialize_selection()
    # No Intent editor or provider callback is part of exact Merge selection.
    app = build_compact_application(
        state,
        build_continue_action=finish,
        stage_bulk_choice=stage_bulk,
        choice_previews=project_choice_previews(
            (review.analysis,),
            copy_uids={
                c.issue_uid: c.keep_both_uid
                for c in review.structural_input.conflicts
                if c.keep_both_uid is not None
            },
        ),
        header_label="MERGE · LITERAL",
        activation_hint="select/finalize",
        app_input=app_input,
        app_output=app_output,
    )
    action = app.run()
    if action.kind == "CLOSE":
        return None
    if action.kind != "ACCEPT":
        raise ValueError("Merge conflict screen returned an invalid action.")
    decisions = tuple(
        MergeConflictDecision(issue.uid, selected[issue.uid].rpartition(":")[2].upper())
        for issue in issues
    )
    finalize_merge_decisions(review.analysis, decisions)
    return review.prepare_result(decisions)


def project_choice_previews(analyses, *, copy_uids=None, retained_uids=frozenset()):
    """Each card previews one choice, independent of other staged decisions."""
    previews = {}
    for analysis in analyses:
        candidate = analysis.candidate
        if candidate is None:
            continue
        before = candidate.context()
        for issue in analysis.review_issues:
            if issue.item_kind != "MEMORY":
                continue
            for choice in issue.choices:
                if choice.uid not in EXACT_DECISIONS:
                    continue
                decisions = MergeDecisionSet(
                    analysis.revision,
                    (MergeConflictDecision(issue.uid, choice.uid),),
                )
                after = materialize_exact_decisions(analysis, decisions, before)
                fragments = []
                for uid in issue.item_uids:
                    origin = candidate.origin(uid)
                    old = before.memories[uid].content
                    memory = after.memories.get(uid)
                    new = memory.content if memory is not None else None
                    result_uid = uid
                    identity = f"[{origin.context_name}:{origin.item_uid[:8]}]"
                    if (
                        choice.uid == "TAKE_SOURCE"
                        and origin.context_name != origin.placement
                    ):
                        fragments.extend(
                            (
                                (
                                    "class:report-neutral",
                                    "FROM " + display_escape_text(identity) + " ",
                                ),
                                ("class:memory-diff.equal", display_escape_text(old)),
                                ("", "\n"),
                            )
                        )
                        continue
                    if new is not None and origin.context_name != origin.placement:
                        # Literal freezes a new copy ID; Semantic retains its frozen
                        # candidate ID. Neither ID may be allocated during rendering.
                        result_uid = (copy_uids or {}).get(issue.uid, uid)
                        identity += f" → [{origin.placement}:{result_uid[:8]}]"
                        if uid not in retained_uids:
                            old = None
                    treatment = (
                        "ADD"
                        if old is None
                        else "REMOVE"
                        if new is None
                        else "KEEP"
                        if old == new
                        else "EDIT"
                    )
                    fragments.extend(
                        render_inline_memory_change(
                            MemoryChange(
                                marker={
                                    "ADD": "+",
                                    "REMOVE": "-",
                                    "KEEP": "=",
                                    "EDIT": "~",
                                }[treatment],
                                treatment=treatment,
                                location=origin.placement,
                                memory_uid=result_uid,
                                before=old,
                                after=new,
                            ),
                            identity=identity,
                        )
                    )
                previews[f"{issue.uid}:{choice.uid.lower()}"] = tuple(fragments)
    return previews


def _merge_choice_text(analysis, issue, choice):
    if issue.item_kind != "MEMORY" or choice.uid not in {
        "KEEP_TARGET",
        "TAKE_SOURCE",
        "KEEP_BOTH",
    }:
        return choice.text
    targets, sources = merge_sides(analysis.candidate, issue)
    members = {
        "KEEP_TARGET": targets,
        "TAKE_SOURCE": sources,
        "KEEP_BOTH": issue.item_uids,
    }[choice.uid]
    blocks = dict(
        zip(issue.item_uids, _issue_memory_blocks(analysis, issue), strict=True)
    )
    return "\n".join(f"{blocks[uid].heading} {blocks[uid].text}" for uid in members)


def _issue_memory_blocks(analysis: MergeConflictAnalysis, issue: MergeConflictIssue):
    candidate = analysis.candidate
    by_uid = analysis.candidate.context().memories
    blocks = []
    for uid in issue.item_uids:
        origin = candidate.origin(uid)
        location = origin.context_name
        memory_uid = origin.item_uid
        blocks.append(
            ResolutionDetailBlock(
                heading=f"[{location}:{memory_uid[:8]}]",
                text=by_uid[uid].content
                if issue.item_kind == "MEMORY"
                else structural_item_description(candidate.original_item(uid)),
            )
        )
    return tuple(blocks)


def compact_resolve_view(analysis: MergeConflictAnalysis) -> ResolutionWorkbenchView:
    """Project unresolved meanings, never mutations, for finalization."""

    return ResolutionWorkbenchView(
        operation="MERGE",
        artifact_uid=analysis.candidate.context().uid,
        revision=analysis.revision,
        title="Merge structural choices",
        route=analysis.candidate.context().name,
        status="NEEDS DECISIONS",
        metrics=(),
        overview="",
        list_label="MERGE CONFLICTS",
        items=tuple(
            ResolutionItem(
                uid=issue.uid,
                kind=issue.kind,
                status="OPEN",
                priority="REQUIRED",
                title=issue.classification,
                kind_label=issue.kind.replace("_", " "),
                blocks=_issue_memory_blocks(analysis, issue),
                summary=issue.reason,
                obligation="REQUIRED",
                response_state="OPEN",
                question=issue.question or issue.reason,
                options=tuple(
                    ResolutionOption(
                        f"{issue.uid}:{c.uid.lower()}",
                        c.label,
                        _merge_choice_text(analysis, issue, c),
                    )
                    for c in issue.choices
                ),
                selected_option_uid=f"{issue.uid}:{issue.default_choice.lower()}"
                if issue.default_choice is not None
                else None,
                commentable=issue.item_kind == "MEMORY"
                and (
                    not issue.choices
                    or any(choice.uid == "INTENT" for choice in issue.choices)
                ),
            )
            for issue in analysis.review_issues
        ),
        empty_message="No Merge decision is available.",
        results_label="MERGE RESULT",
        results=(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=False,
        show_results=False,
    )


def compact_resolve_views(
    analyses: tuple[MergeConflictAnalysis, ...],
) -> ResolutionWorkbenchView:
    """One decision surface, retaining each destination's independent binding."""
    if not analyses:
        raise ValueError("Resolve requires at least one analysis.")
    views = tuple(compact_resolve_view(analysis) for analysis in analyses)
    return replace(
        views[0],
        items=tuple(item for view in views for item in view.items),
        revision=digest([view.revision for view in views]),
        route=" · ".join(dict.fromkeys(view.route for view in views)),
    )
