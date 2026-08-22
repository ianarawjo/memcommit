"""Render retained per-Memory content history and lineage."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.command_attempts import annotate_memory_report_attempt
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.memory_history import (
    build_memory_history,
    load_retained_history_context,
    load_retained_history_scope,
)
from memcommit.commands.memory_picker import (
    ScopedMemoryPickerItem,
    choose_memory_report_target,
)
from memcommit.commands.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
)
from memcommit.interfaces.tui.viewers.read_only import interactive_report_terminal
from memcommit.commands.trace_projection import (
    DEFAULT_TRACE_OPERATION_LIMIT,
    MAX_TRACE_OPERATION_LIMIT,
    format_compact_trace_report,
    open_trace_viewer,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.provenance import (
    ProvenanceError,
    TraceReport,
    collect_trace_candidates,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


def render_trace(
    report: TraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> None:
    """Print the same bounded vertical lineage document used by the TUI."""

    typer.echo(
        format_compact_trace_report(
            report,
            verbose=verbose,
            limit=limit,
        )
    )


def render_trace_receipt(report: TraceReport) -> None:
    """Return a bounded lineage result; the document remains explicitly reachable."""

    typer.echo(
        "\n".join(
            [
                f"TRACE COMPLETE · {display_escape_text(report.context_name)}",
                f"MEMORY · {report.selected_uid}",
                f"LINEAGE · {len(report.events)} events · "
                f"{len(report.component_uids)} components",
                f"ATTENTION · {len(report.warnings)} limits",
                "DETAILS · mem trace "
                f"{report.selected_uid} --context "
                f"{display_escape_text(report.context_name)} --plain",
            ]
        )
    )


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "UID (or unambiguous prefix) of a current or historical "
                "direct Memory; omit in a terminal to select from the current "
                "Context or its descendants"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Start Memory selection in this Context instead of the current "
                "Context"
            ),
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Expand full evidence detail and complete UIDs",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help=(
                "Maximum newest lineage operations to show "
                f"(1-{MAX_TRACE_OPERATION_LIMIT})"
            ),
        ),
    ] = DEFAULT_TRACE_OPERATION_LIMIT,
    all_operations: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Show every retained lineage operation",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the structured trace as JSON"),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the lineage document (the default result route)",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Open the retained lineage in the read-only Viewer",
        ),
    ] = False,
) -> None:
    """Show recorded and safely reconstructed content lineage."""
    if plain and tui:
        typer.secho(
            "Trace error: choose either --plain or --tui, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if not 1 <= limit <= MAX_TRACE_OPERATION_LIMIT:
        typer.secho(
            "Trace error: --limit must be between 1 and "
            f"{MAX_TRACE_OPERATION_LIMIT}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    operation_limit = None if all_operations else limit
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if selector is None and as_json:
            raise ProvenanceError("JSON output requires an explicit Memory UID.")
        explicit_context = context_name is not None
        if selector is None and not explicit_context and interactive_report_terminal():
            launch = choose_memory_report_recent(store, operation="trace")
            if launch is None:
                typer.echo("Trace cancelled.")
                return
            if isinstance(launch, MemoryReportRecentSelection):
                context_name = launch.context_name
                selector = launch.memory_uid
            elif not isinstance(launch, MemoryReportSelectAction):
                raise ProvenanceError("Trace launcher returned an invalid action.")
        name = context_snapshot.resolve_or_current(context_name)
        if not name:
            raise ProvenanceError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        if selector is None:
            # The current or explicit Context is already the useful default.
            # Freeze its descendants for the range control, but do not force a
            # second location decision before the person can see its Memories.
            history_scope = load_retained_history_scope(
                store,
                context_locator=name,
                current_name=context_snapshot.current_name,
                # Freeze every descendant before the shared RANGE control
                # narrows or broadens what can actually be selected.
                include_descendants=True,
            )
            catalog_names = tuple(item.display_name for item in history_scope)
            candidate_items = tuple(
                ScopedMemoryPickerItem(
                    context_name=context.display_name,
                    uid=candidate.uid,
                    content=candidate.content,
                    status=candidate.status,
                    catalog_context_names=catalog_names,
                    change_count=candidate.change_count,
                )
                for context in history_scope
                for candidate in collect_trace_candidates(
                    store,
                    context.context,
                )
            )
            selected = choose_memory_report_target(
                candidate_items,
                context_name=name,
                operation="trace",
                catalog_context_names=catalog_names,
                initial_include_descendants=False,
            )
            if selected is None:
                typer.echo("Trace cancelled.")
                return
            selector = selected.memory_uid
            context_name = selected.owner_context_name
            # The pickers are read-only, but another process may have changed
            # the Context while they were open. Re-read before resolving the
            # exact UID so the report never mixes old live state with new history.
        history_context = load_retained_history_context(
            store,
            context_locator=context_name,
            current_name=context_snapshot.current_name,
        )
        name = history_context.display_name
        report = build_memory_history(store, history_context, selector)
        annotate_memory_report_attempt(
            operation="trace",
            context_name=name,
            memory_uid=report.selected_uid,
            include_descendants=False,
        )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        ProvenanceError,
        ProfileConfigError,
        ProfileError,
        PermissionError,
    ) as error:
        typer.secho(
            f"Trace error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if as_json:
        typer.echo(
            json.dumps(
                report.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if tui:
        if not interactive_report_terminal():
            typer.secho(
                "Trace error: --tui requires an interactive terminal.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(2)
        open_trace_viewer(
            report,
            verbose=verbose,
            limit=operation_limit,
        )
        return
    if plain:
        render_trace(report, verbose=verbose, limit=operation_limit)
        return
    render_trace_receipt(report)
