"""Provider-free read-only discovery of same-role exact direct items."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.command_attempts import annotate_read_report_attempt
from memcommit.commands.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.commands.findings_render import (
    plural,
    render_cleanup_member,
    render_heading,
)
from memcommit.interfaces.console.identity import collision_safe_uid_prefixes
from memcommit.interfaces.console.text import display_escape_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.read_report import ReadReportTarget
from memcommit.store import MemoryStore


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
) -> None:
    """Report exact duplicate groups without provider access or mutation."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
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
        context = (
            GrantedReadStore(access).load_direct(access.display_name)
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
        report = ops.find_duplicates(context)
        annotate_read_report_attempt(
            ReadReportTarget(
                operation="find-duplicates",
                context_names=(access.display_name,),
                target_names=(access.display_name,),
                selection_mode="SINGLE",
                ranges=("DIRECT",),
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

    context_label = display_escape_text(access.display_name)
    render_heading(
        operation_label="Find Duplicates",
        context_name=context_label,
        facts=(
            plural(report.item_count, "direct item") + " checked",
            plural(len(report.groups), "exact group"),
            plural(report.duplicate_count, "proposed absorption"),
        ),
    )
    if not report.groups:
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
    typer.echo("\n  Read-only report. Apply exact cleanup with mem dedup.")


__all__ = ["cmd"]
