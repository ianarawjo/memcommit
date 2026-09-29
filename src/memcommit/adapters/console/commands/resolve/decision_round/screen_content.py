"""Build screen data from Resolve issues and application-owned choices."""

from __future__ import annotations

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.resolve.model import ResolveAnalysis, ResolveIssue
from memcommit.application.capabilities.memory_issue_analysis.report import (
    conflict_label,
)
from memcommit.application.operations.resolve.resolution_options.catalog import (
    build_resolution_options,
)


def _issue_options(
    analysis: ResolveAnalysis, issue: ResolveIssue
) -> tuple[ResolutionOption, ...]:
    return tuple(
        ResolutionOption(
            f"{issue.uid}:{choice.uid.lower()}",
            choice.label,
            choice.text,
        )
        for choice in build_resolution_options(analysis, issue)
    )


def _issue_memory_blocks(analysis: ResolveAnalysis, issue: ResolveIssue):
    by_uid = {item.uid: item for item in analysis.frame.source.items}
    blocks = []
    for uid in issue.item_uids:
        location = analysis.frame.display_name
        memory_uid = uid
        blocks.append(
            ResolutionDetailBlock(
                heading=f"[{location}:{memory_uid[:8]}]",
                text=by_uid[uid].summary,
            )
        )
    return tuple(blocks)


def build_decision_view(analysis: ResolveAnalysis) -> ResolutionWorkbenchView:
    """Arrange issue evidence, choices and input availability for the screen."""

    return ResolutionWorkbenchView(
        operation="RESOLVE",
        artifact_uid=analysis.frame.source.context_uid,
        revision=analysis.frame.revision,
        title="Resolve Audit directions",
        route=analysis.frame.display_name,
        status="NEEDS DECISIONS",
        metrics=(),
        overview="",
        list_label="AUDIT ITEMS",
        items=tuple(
            ResolutionItem(
                uid=issue.uid,
                kind=issue.kind,
                status="OPEN",
                priority="REQUIRED",
                title=issue.classification,
                kind_label=conflict_label(issue.classification)
                if issue.kind == "CONFLICT"
                else issue.kind.replace("_", " "),
                blocks=_issue_memory_blocks(analysis, issue),
                summary=issue.reason,
                obligation="REQUIRED",
                response_state="OPEN",
                question=issue.question or issue.reason,
                options=_issue_options(analysis, issue),
                selected_option_uid=f"{issue.uid}:{issue.default_choice.lower()}"
                if issue.default_choice is not None
                else None,
                commentable=any(
                    choice.uid == "INTENT"
                    for choice in build_resolution_options(analysis, issue)
                ),
            )
            for issue in analysis.issues
        ),
        empty_message="No Audit decision is available.",
        results_label="UPDATE PLAN",
        results=(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=False,
        show_results=False,
    )


__all__ = ["build_decision_view"]
