"""Provider-free read-only discovery of same-role exact direct items."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.persistence.command_ledger.attempts import annotate_read_report_attempt
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    plural,
    render_cleanup_member,
    render_heading,
)
from memcommit.core.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.application.operations.dedup.application import (
    ExactDuplicateContextReport,
    find_exact_duplicate_scope,
)
from memcommit.adapters.console.terminal.core.identity import collision_safe_uid_prefixes
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.capabilities.reviewing.read_report import ReadReportTarget
from memcommit.persistence.store import MemoryStore


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Inspect direct items in the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Inspect each readable lexical descendant as an independent "
                "direct Context frame"
            ),
        ),
    ] = False,
) -> None:
    """Report exact duplicate groups without provider access or mutation."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(
            "Find Duplicates error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    try:
        snapshot = ContextOperandSnapshot.capture(store)
        access = resolve_context_access(
            store,
            context_name,
            current_name=snapshot.current_name,
            required_permission="READ",
        )
        scope = find_exact_duplicate_scope(
            store,
            access,
            include_descendants=preset is ContextScopePreset.RECURSIVE,
        )
        annotate_read_report_attempt(
            ReadReportTarget(
                operation="find-duplicates",
                context_names=tuple(
                    frame.context_name for frame in scope.contexts
                ),
                target_names=(access.display_name,),
                selection_mode="SINGLE",
                ranges=("RECURSIVE" if scope.include_descendants else "DIRECT",),
            )
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Find Duplicates error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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


__all__ = ["cmd"]
