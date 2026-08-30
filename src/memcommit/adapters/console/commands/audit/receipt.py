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
from memcommit.application.capabilities.reviewing.memory_issue_finding.report import (
    QualityFindingReportItem,
    quality_find_category_label,
    quality_find_report_summary_text,
)
from memcommit.application.capabilities.reviewing.memory_issue_finding.workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
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
        uid_prefixes=uid_prefixes,
    )


def render_quality_audit_receipt(session: QualityAuditSession) -> None:
    """Print the saved artifact with each finder's truthful result unit."""

    typer.secho("Audit saved:", bold=True, nl=False)
    typer.echo(f" {len(session.checks)} quality checks.")
    memory_count = len(session.source.memories)
    memory_label = "memory" if memory_count == 1 else "memories"
    typer.secho("Source:", bold=True, nl=False)
    typer.echo(
        f" {display_escape_text(session.source.context_name)} · "
        f"{memory_count} {memory_label}"
    )

    context = session.source.context()
    source_frame = QualityFindSourceFrame.create((context,))
    uid_prefixes = collision_safe_uid_prefixes(
        memory.uid for memory in session.source.memories
    )
    typer.echo()
    for check in session.checks:
        label = quality_find_category_label(check.kind)
        role = semantic_quality_role(check.kind)
        if role is None:  # pragma: no cover - Audit validates this union.
            raise ValueError("Unsupported Audit quality check kind.")
        report_view = quality_find_report_view(
            QualityFindWorkbenchSession(
                uid=session.uid,
                kind=check.kind,
                source=source_frame,
                report=check.report,
                responses=session.responses,
            ),
            source_frame,
            operation_label=f"AUDIT · {label}",
        )
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
    typer.secho("Review full audit:", bold=True)
    typer.echo(f"mem review audit --session {session.uid}")


__all__ = ["render_quality_audit_receipt"]
