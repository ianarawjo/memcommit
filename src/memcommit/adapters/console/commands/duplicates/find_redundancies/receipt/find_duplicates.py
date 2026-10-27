"""Render provider-free exact duplicate reports."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    plural,
    render_cleanup_memory_change,
    render_heading,
)
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.core.uid_prefixes import (
    extend_uid_prefixes_until_unique,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.duplicates.find_duplicates.application import (
    ExactDuplicateContextReport,
    ExactDuplicateScopeReport,
)


def render_find_duplicates_receipt(scope: ExactDuplicateScopeReport) -> None:
    """Print direct or recursive exact groups and their cleanup guidance."""

    if scope.include_descendants:
        render_heading(
            operation_label="Find Duplicates",
            context_name=display_escape_text(scope.root_name),
            facts=(
                plural(len(scope.contexts), "Context") + " checked",
                plural(scope.item_count, "direct item") + " checked",
                plural(scope.group_count, "exact group"),
                plural(scope.duplicate_count, "proposed absorption"),
            ),
        )
        for index, frame in enumerate(scope.contexts, start=1):
            typer.echo()
            typer.secho(
                f"CONTEXT {index}/{len(scope.contexts)} · "
                f"{display_escape_text(frame.context_name)}",
                bold=True,
            )
            _render_context_report(frame)
        if scope.group_count:
            typer.echo("\n  Read-only report. Apply exact cleanup with mem dedup --literal -r.")
        return

    frame = scope.contexts[0]
    report = frame.report
    render_heading(
        operation_label="Find Duplicates",
        context_name=display_escape_text(frame.context_name),
        facts=(
            plural(report.item_count, "direct item") + " checked",
            plural(len(report.groups), "exact group"),
            plural(report.duplicate_count, "proposed absorption"),
        ),
    )
    _render_context_report(frame)
    if report.groups:
        typer.echo("\n  Read-only report. Apply exact cleanup with mem dedup --literal.")


def _render_context_report(frame: ExactDuplicateContextReport) -> None:
    """Render groups from one direct Context without implying cross-frame DUN."""

    report = frame.report
    if not report.groups:
        typer.echo("  No exact duplicate direct items.")
        return

    for index, group in enumerate(report.groups, start=1):
        typer.echo()
        typer.secho(
            f"  DUP / EXACT  {index}/{len(report.groups)} \u00b7 {group.item_kind}",
            bold=True,
        )
        member_uids = (group.survivor_uid, *group.absorbed_uids)
        uid_prefixes = extend_uid_prefixes_until_unique(member_uids)
        for memory_uid in member_uids:
            keep_memory = memory_uid == group.survivor_uid
            content = group.content if group.content is not None else group.summary
            render_cleanup_memory_change(
                MemoryChange(
                    marker="=" if keep_memory else "-",
                    treatment="KEEP" if keep_memory else "REMOVE",
                    location=frame.context_name,
                    memory_uid=memory_uid,
                    before=content,
                    after=content if keep_memory else None,
                ),
                uid_prefix=uid_prefixes[memory_uid],
            )
