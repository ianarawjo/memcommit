"""Render a Resolve decision's expected impact as located Memory diffs."""

from memcommit.adapters.console.terminal.components.inline_diff import (
    render_inline_memory_change,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.resolve.model import ResolveAnalysis


def _placement(analysis, uid, extra_origins=()):
    if analysis.frame.memory_target is None:
        return analysis.frame.display_name, uid
    origin = next(
        item
        for item in (*analysis.frame.memory_target.origins, *extra_origins)
        if item.analysis_uid == uid
    )
    return origin.context_name, origin.memory_uid


def project_choice_previews(analysis: ResolveAnalysis):
    """Preservation cards show the current Context; no Source/Target choices."""
    previews = {}
    for issue in analysis.issues:
        if issue.item_kind != "MEMORY":
            continue
        fragments = []
        for uid in issue.item_uids:
            item = analysis.frame.source.context().memories[uid]
            fragments.extend(
                render_inline_memory_change(
                    MemoryChange(
                        marker="=",
                        treatment="KEEP",
                        location=_placement(analysis, uid)[0],
                        memory_uid=_placement(analysis, uid)[1],
                        before=item.content,
                        after=item.content,
                    )
                )
            )
        keep = "keep_both" if len(issue.item_uids) > 1 else "keep_as_is"
        previews[f"{issue.uid}:{keep}"] = tuple(fragments)
        if issue.kind == "REDUNDANCY":
            retained = analysis.frame.source.context()
            fragments = []
            for index, uid in enumerate(issue.item_uids):
                text = retained.memories[uid].content
                fragments.extend(
                    render_inline_memory_change(
                        MemoryChange(
                            marker="=" if index == 0 else "-",
                            treatment="KEEP" if index == 0 else "REMOVE",
                            location=_placement(analysis, uid)[0],
                            memory_uid=_placement(analysis, uid)[1],
                            before=text,
                            after=text if index == 0 else None,
                        )
                    )
                )
            previews[f"{issue.uid}:confirm"] = tuple(fragments)
    return previews


def project_semantic_choice(analysis, choice, *, include_explanation=True):
    """Project exact Memory effects, optionally preceded by their explanation."""
    issue = next(
        item for item in analysis.issues if item.uid == choice.decision.issue_uid
    )
    explanation = (
        issue.proposed_direction
        if choice.decision.kind == "CONFIRM"
        else choice.decision.intent.strip()
    )
    fragments = (
        [("class:report-neutral", display_escape_text(explanation) + "\n")]
        if include_explanation
        else []
    )
    before, after = choice.before(), choice.after()
    uids = tuple(
        dict.fromkeys(
            (*issue.item_uids, *(op.memory_uid for op in choice.plan.operations))
        )
    )
    for uid in uids:
        location, memory_uid = _placement(analysis, uid, choice.memory_origins)
        identity = f"[{location}:{memory_uid[:8]}]"
        old = before.memories[uid].content if uid in before.memories else None
        new = after.memories[uid].content if uid in after.memories else None
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
                    marker={"ADD": "+", "REMOVE": "-", "KEEP": "=", "EDIT": "~"}[
                        treatment
                    ],
                    treatment=treatment,
                    location=location,
                    memory_uid=memory_uid,
                    before=old,
                    after=new,
                ),
                identity=identity,
            )
        )
    return tuple(fragments)
