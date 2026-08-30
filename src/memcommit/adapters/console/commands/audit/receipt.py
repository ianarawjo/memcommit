"""Compact saved-result receipt for Memory quality Audit."""

from __future__ import annotations

from collections.abc import Mapping

import typer

from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.theme import (
    memory_object_color_rgb,
    semantic_color_rgb,
    semantic_quality_role,
)
from memcommit.application.capabilities.reviewing.quality.audit import (
    QualityAuditSession,
)
from memcommit.application.capabilities.reviewing.quality.report import (
    QualityFindingReportItem,
    quality_find_category_label,
    quality_finding_label_parts,
    quality_find_report_summary_text,
)
from memcommit.application.capabilities.reviewing.quality.workbench import (
    QualityFindSourceFrame,
    QualityFindWorkbenchSession,
    quality_find_report_view,
)


_AUDIT_RECEIPT_PREVIEW_LIMIT = 3
_AUDIT_RECEIPT_MEMORY_PREVIEW_LIMIT = 48


def _receipt_memory_preview(value: str) -> str:
    compact = " ".join(safe_terminal_text(value).split()) or "(empty Memory)"
    if len(compact) <= _AUDIT_RECEIPT_MEMORY_PREVIEW_LIMIT:
        return compact
    return compact[: _AUDIT_RECEIPT_MEMORY_PREVIEW_LIMIT - 1].rstrip() + "…"


def _render_quality_audit_finding_preview(
    item: QualityFindingReportItem,
    *,
    uid_prefixes: Mapping[str, str],
) -> None:
    marker, finding_label, classification = quality_finding_label_parts(item)
    role = semantic_quality_role(item.category)
    if role is None:  # pragma: no cover - the typed item validates this union.
        raise ValueError("Unsupported Audit quality finding category.")
    typer.echo(f"  {marker} ", nl=False)
    typer.secho(
        finding_label,
        fg=semantic_color_rgb(role),
        bold=True,
        nl=False,
    )
    if classification:
        typer.secho(f" · {classification}", bold=True, nl=False)
    typer.echo(" · ", nl=False)
    for index, source in enumerate(item.sources):
        if index:
            typer.echo(" ↔ ", nl=False)
        typer.secho(
            f"[MEMORY {uid_prefixes[source.memory_uid]}] ",
            bold=True,
            nl=False,
        )
        typer.secho(
            f"“{_receipt_memory_preview(source.content)}”",
            fg=memory_object_color_rgb(),
            nl=False,
        )
    typer.echo()


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
