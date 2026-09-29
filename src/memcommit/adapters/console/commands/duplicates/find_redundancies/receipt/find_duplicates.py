"""Render provider-free exact duplicate reports."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    plural,
    render_cleanup_member,
    render_heading,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
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
            typer.echo("\n  Read-only report. Apply exact cleanup with mem dedup -r.")
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
        typer.echo("\n  Read-only report. Apply exact cleanup with mem dedup.")


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
        uid_prefixes = collision_safe_uid_prefixes(member_uids)
        render_cleanup_member(
            "SURVIVOR",
            uid_prefixes[group.survivor_uid],
            content=group.content if group.content is not None else group.summary,
        )
        for uid in group.absorbed_uids:
            render_cleanup_member(
                "ABSORB",
                uid_prefixes[uid],
                content=group.content if group.content is not None else group.summary,
            )
