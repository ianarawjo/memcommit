"""Resolve Audit-direction projection into terminal-owned presentation values."""

from __future__ import annotations

from memcommit.adapters.console.terminal.components.semantic_viewer import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionOption,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
)


def _memory_line(analysis: ResolveAnalysis, memory_uid: str) -> str:
    memory = next(
        memory for memory in analysis.frame.memories if memory.uid == memory_uid
    )
    content = " ".join(memory.content.split())
    # Both members form one relation row. Keep each claim bounded so the
    # entire A ↔ B identity remains legible on the standard 180-column canvas.
    if len(content) > 58:
        content = content[:55].rstrip() + "..."
    return f"[{memory_uid[:8]}] “{content}”"


def _issue_title(analysis: ResolveAnalysis, issue) -> str:
    members = " ↔ ".join(
        _memory_line(analysis, uid) for uid in issue.memory_uids
    )
    return members or issue.classification


def project_resolve_analysis(analysis: ResolveAnalysis) -> SemanticViewerDocument:
    """Build the read-only outcome used when no decision surface can open."""

    fragments: list[tuple[str, str]] = [
        ("class:title", "RESOLVE\n"),
        (
            "class:report-label",
            f"CONTEXT · {safe_terminal_text(analysis.frame.display_name)}\n"
            f"STATUS · {safe_terminal_text(analysis.status)}\n",
        ),
    ]
    if analysis.question:
        fragments.append(
            ("class:report-neutral", safe_terminal_text(analysis.question) + "\n")
        )
    for issue in analysis.review_issues:
        fragments.extend(
            (
                (
                    "class:section",
                    f"\n{safe_terminal_text(issue.kind)} · "
                    + safe_terminal_text(_issue_title(analysis, issue))
                    + "\n",
                ),
                (
                    "class:viewer-body",
                    "DIRECTION · "
                    + safe_terminal_text(issue.proposed_direction)
                    + "\nWHY · "
                    + safe_terminal_text(issue.reason)
                    + "\n",
                ),
            )
        )
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                uid="resolve-report",
                kind="REPORT",
                block=SemanticViewerBlock(tuple(fragments), anchor="both"),
            ),
        )
    )


def compact_resolve_view(analysis: ResolveAnalysis) -> ResolutionWorkbenchView:
    """Project unresolved meanings, never mutations, for finalization."""

    return ResolutionWorkbenchView(
        operation="RESOLVE",
        artifact_uid=analysis.frame.context_uid,
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
                title=_issue_title(analysis, issue),
                summary=issue.reason,
                obligation="REQUIRED",
                response_state="OPEN",
                question=issue.question or issue.reason,
                options=(
                    ResolutionOption(
                        f"{issue.uid}:confirm",
                        "1 · ACCEPT THIS DIRECTION",
                        issue.proposed_direction,
                    ),
                    ResolutionOption(
                        f"{issue.uid}:intent",
                        "2 · ADJUST WITH YOUR INTENT",
                        "Enter the direction this should follow.",
                    ),
                    ResolutionOption(
                        f"{issue.uid}:force",
                        "3 · LEAVE UNRESOLVED",
                        "Exclude this item from Update input and retain it as unresolved.",
                    ),
                ),
                selected_option_uid=None,
                commentable=True,
            )
            for issue in analysis.review_issues
        ),
        empty_message="No Audit decision is available.",
        results_label="UPDATE PLAN",
        results=(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=False,
        show_results=False,
    )


__all__ = ["compact_resolve_view", "project_resolve_analysis"]
