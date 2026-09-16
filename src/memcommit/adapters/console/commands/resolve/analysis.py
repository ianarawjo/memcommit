"""Plain terminal projection for typed Resolve analyses."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.resolve.application import ResolveAnalysis


def _line(label: str, value: str, *, color: str | None = None) -> None:
    typer.secho(
        f"{label} · {display_escape_text(value)}",
        fg=color,
    )


def _title(analysis: ResolveAnalysis) -> None:
    typer.secho(
        f"RESOLVE · {display_escape_text(analysis.frame.display_name)}",
        bold=True,
    )


def render_resolve_plain(analysis: ResolveAnalysis) -> None:
    """Render one compact outcome without inventing a non-interactive decision."""

    _title(analysis)

    if analysis.review_issues:
        memory_by_uid = {
            memory.uid: memory.content for memory in analysis.frame.memories
        }
        _line("NEEDS DECISIONS", str(len(analysis.review_issues)))
        for position, issue in enumerate(analysis.review_issues, 1):
            relation = " ↔ ".join(
                f"[{uid[:8]}] {memory_by_uid[uid]}" for uid in issue.memory_uids
            ) or issue.classification
            _line(f"{issue.kind} {position}", relation)
            _line("DIRECTION", issue.proposed_direction)
        return

    if analysis.status == "NO_ISSUES":
        _line("RESOLVED", "NO ACTIONABLE AUDIT ISSUE · NO CHANGE")
        return

    if analysis.status in {"NEEDS_INPUT", "NEEDS_AUTHORITY"}:
        label = analysis.status.replace("_", " ")
        _line(label, analysis.question or "Resolve cannot continue.")
        return

    _line("NO CHANGE", analysis.question or "No Audit decision is available.")


__all__ = ["render_resolve_plain"]
