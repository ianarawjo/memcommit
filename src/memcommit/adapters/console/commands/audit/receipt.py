"""Compact saved-result receipt for Memory quality Audit."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.findings import (
    echo_issue_one_line,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
)
from memcommit.adapters.console.terminal.core.theme import (
    semantic_color_rgb,
    semantic_quality_role,
)
from memcommit.application.operations.audit.model import QualityAuditSession
from memcommit.application.capabilities.memory_issue_analysis.report import (
    QualityFindingReportItem,
    quality_find_report_summary_text,
)
from memcommit.application.operations.audit.report import (
    audit_check_label,
    audit_check_report_view,
    ordered_audit_checks,
)


_AUDIT_RECEIPT_PREVIEW_LIMIT = 3


def _render_quality_audit_finding_preview(
    item: QualityFindingReportItem,
    *,
    uid_prefixes: dict[str, str],
) -> None:
    echo_issue_one_line(
        item,
        prefix="  ",
        show_context=False,
        show_label=False,
        uid_prefixes=uid_prefixes,
    )


def render_quality_audit_receipt(session: QualityAuditSession) -> None:
    """Print the saved artifact with each finder's truthful result unit."""

    typer.secho("Audit saved:", bold=True, nl=False)
    check_count = len(session.completed_checks)
    check_label = "check" if check_count == 1 else "checks"
    typer.echo(f" {check_count} quality {check_label}.")
    memory_count = len(session.source.memories)
    memory_label = "memory" if memory_count == 1 else "memories"
    typer.secho("Source:", bold=True, nl=False)
    typer.echo(
        f" {display_escape_text(session.source.context_name)} · "
        f"{len(session.source.items)} direct items · {memory_count} {memory_label}"
    )

    uid_prefixes = collision_safe_uid_prefixes(
        item.uid for item in session.source.items
    )
    typer.echo()
    for check in ordered_audit_checks(session):
        label = audit_check_label(check.kind)
        role = semantic_quality_role(check.kind)
        if role is None:  # pragma: no cover - Audit validates this union.
            raise ValueError("Unsupported Audit quality check kind.")
        report_view = audit_check_report_view(session, check)
        typer.secho(
            label,
            fg=semantic_color_rgb(role),
            bold=True,
            nl=False,
        )
        typer.echo(
            f"{' ' * (15 - len(label))}{quality_find_report_summary_text(report_view)}"
        )
        for item in report_view.items[:_AUDIT_RECEIPT_PREVIEW_LIMIT]:
            _render_quality_audit_finding_preview(
                item,
                uid_prefixes=uid_prefixes,
            )
        remaining = len(report_view.items) - _AUDIT_RECEIPT_PREVIEW_LIMIT
        if remaining > 0:
            typer.echo(f"  … {remaining} more")

    typer.echo()
    typer.secho("Audit record:", bold=True, nl=False)
    typer.echo(f" {session.uid}")


__all__ = ["render_quality_audit_receipt"]
