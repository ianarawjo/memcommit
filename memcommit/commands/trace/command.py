"""Render retained per-Memory content history and lineage."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.authority.access import resolve_context_access
from memcommit.infrastructure.command_ledger.attempts import annotate_memory_report_attempt
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.commands.shared.memory_history import (
    build_memory_history,
    load_retained_history_context,
    load_retained_history_scope,
)
from memcommit.commands.shared.memory_picker import (
    ScopedMemoryPickerItem,
    choose_memory_report_target,
)
from memcommit.commands.shared.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
)
from memcommit.commands.shared.history_target import resolve_explicit_context_history_target
from memcommit.commands.trace.context_projection import (
    format_context_trace_report,
    open_context_trace_viewer,
)
from memcommit.interfaces.tui.viewers.read_only import interactive_report_terminal
from memcommit.commands.trace.projection import (
    DEFAULT_TRACE_OPERATION_LIMIT,
    MAX_TRACE_OPERATION_LIMIT,
    format_compact_trace_report,
    open_trace_viewer,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.retained_history.granted_provenance import (
    GrantedMemoryTraceReport,
    build_granted_memory_trace,
)
from memcommit.retained_history.context_history import ContextTraceReport, build_context_trace
from memcommit.context_targeting.model import ContextTarget
from memcommit.context_targeting.report_items import (
    ReadableMemoryTargetNotFoundError,
    freeze_memory_report_readable_catalog,
    parse_memory_report_locator,
    resolve_local_memory_report_target,
    resolve_readable_memory_target,
)
from memcommit.retained_history.provenance import (
    ProvenanceError,
    TraceReport,
    collect_trace_candidates,
)
from memcommit.operations.reference.provenance import (
    MemoryReferenceTraceReport,
    build_reference_trace,
)
from memcommit.store import MemoryStore
from memcommit.operations.profile.config import ProfileConfigError
from memcommit.operations.profile.model import ProfileError


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


def _present_context_trace(
    report: ContextTraceReport,
    *,
    as_json: bool,
    tui: bool,
    verbose: bool,
    limit: int | None,
) -> None:
    """Present one whole lineage without introducing checkpoint selection."""

    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return
    if tui:
        if not interactive_report_terminal():
            raise ProvenanceError("--tui requires an interactive terminal.")
        open_context_trace_viewer(report, verbose=verbose, limit=limit)
        return
    typer.echo(
        format_context_trace_report(
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
                f"TRACE · {display_escape_text(report.context_name)}",
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


def _shown_uid(value: str, *, verbose: bool) -> str:
    return value if verbose else value[:8]


def render_reference_trace(
    report: MemoryReferenceTraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> None:
    """Render a pointer occurrence without collapsing it into target lineage."""

    reference = report.reference
    events = tuple(reversed(report.events))
    if limit is not None:
        events = events[:limit]
    typer.echo(f"TRACE · {display_escape_text(report.context_name)}")
    typer.echo(
        f"[REFERENCE {_shown_uid(report.selected_uid, verbose=verbose)}] · "
        f"{reference.mode} · {len(report.events)} OCCURRENCE "
        f"{'OPERATION' if len(report.events) == 1 else 'OPERATIONS'} · LATEST FIRST"
    )
    typer.echo(
        "TARGET · "
        f"{display_escape_text(reference.target_context_name)}"
        f":[{_shown_uid(reference.target_memory_uid, verbose=verbose)}]"
    )
    typer.echo("\nREFERENCE OCCURRENCE")
    for event in events:
        checkpoint = (
            _shown_uid(event.checkpoint_uid, verbose=verbose)
            if event.checkpoint_uid is not None
            else "unrecorded"
        )
        timestamp = event.timestamp or "(current)"
        detail = event.description.strip()
        suffix = f" · {safe_terminal_text(detail)}" if detail else ""
        typer.echo(
            f"[{display_escape_text(event.command)}] "
            f"[CHECKPOINT {checkpoint}] "
            f"[{event.kind} · {event.evidence}]  "
            f"{display_escape_text(timestamp)}{suffix}"
        )
    if not events:
        typer.echo("  no retained occurrence changes")

    typer.echo("\nTARGET MEMORY")
    if report.target_trace is not None:
        typer.echo(
            format_compact_trace_report(
                report.target_trace,
                verbose=verbose,
                limit=limit,
            )
        )
    elif reference.mode == "SNAPSHOT":
        typer.echo("  SNAPSHOT · source changes do not rewrite this retained value")
        for line in safe_terminal_text(
            reference.snapshot_content or ""
        ).splitlines() or [""]:
            typer.echo(f"  {line}")
    else:
        typer.echo("  HISTORY UNAVAILABLE")
    if report.warnings:
        typer.echo("\nATTENTION")
        for warning in report.warnings:
            typer.echo(f"  {display_escape_text(warning)}")


def render_reference_trace_receipt(report: MemoryReferenceTraceReport) -> None:
    reference = report.reference
    typer.echo(
        "\n".join(
            [
                f"TRACE · {display_escape_text(report.context_name)}",
                f"REFERENCE · {report.selected_uid} · {reference.mode}",
                "TARGET · "
                f"{display_escape_text(reference.target_context_name)}:"
                f"{reference.target_memory_uid}",
                f"OCCURRENCE · {len(report.events)} events",
                f"TARGET HISTORY · {report.target_history_status}",
                "DETAILS · mem trace "
                f"{display_escape_text(report.context_name)}:{report.selected_uid} "
                "--plain",
            ]
        )
    )


def render_granted_trace(
    report: GrantedMemoryTraceReport,
    *,
    verbose: bool = False,
) -> None:
    typer.echo(f"TRACE · {display_escape_text(report.context_name)}")
    typer.echo(
        f"[MEMORY {_shown_uid(report.selected_uid, verbose=verbose)}] · "
        "CURRENT GRANTED VIEW"
    )
    typer.echo("\nMEMORY")
    for line in safe_terminal_text(report.current.content).splitlines() or [""]:
        typer.echo(f"  {line}")
    typer.echo("\nACCESS ROUTE")
    typer.echo(
        f"  GRANT {_shown_uid(report.grant_uid, verbose=verbose)} · "
        f"REVISION {report.grant_revision} · " + " + ".join(report.permissions)
    )
    if verbose:
        typer.echo(f"  AUTHORITY PROFILE · {report.authority_profile_uid}")
        typer.echo(f"  GRANTEE PROFILE · {report.grantee_profile_uid}")
        typer.echo(
            f"  RESOURCE · {display_escape_text(report.resource_name)} "
            f"[{report.resource_uid}]"
        )
    typer.echo("\nHISTORY — hidden by Grant")
    typer.echo(f"  {display_escape_text(report.warning)}")


def render_granted_trace_receipt(report: GrantedMemoryTraceReport) -> None:
    typer.echo(
        "\n".join(
            [
                f"TRACE · {display_escape_text(report.context_name)}",
                f"MEMORY · {report.selected_uid}",
                f"ACCESS · GRANT {report.grant_uid} · REVISION {report.grant_revision}",
                "HISTORY · HIDDEN BY GRANT",
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
                "select from the current Context or descendants when omitted; "
                "otherwise accepts CONTEXT, Memory/MemoryRef UID/prefix, or "
                "CONTEXT:UID"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Start Memory selection in this Context instead of the current Context"
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
    """Show one Context lineage or one Memory's retained provenance."""
    if plain and tui:
        typer.secho(
            "Trace error: choose either --plain or --tui, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if not 1 <= limit <= MAX_TRACE_OPERATION_LIMIT:
        typer.secho(
            f"Trace error: --limit must be between 1 and {MAX_TRACE_OPERATION_LIMIT}.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    operation_limit = None if all_operations else limit
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if selector is None and as_json:
            raise ProvenanceError("JSON output requires an explicit item UID.")
        explicit_context = context_name is not None
        if selector is not None and not explicit_context:
            explicit_target = resolve_explicit_context_history_target(
                selector,
                current_context=context_snapshot.current_name,
                available_context_names=store.list_context_names(),
            )
            if isinstance(explicit_target, ContextTarget):
                history_context = load_retained_history_context(
                    store,
                    context_locator=explicit_target.context_name,
                    current_name=context_snapshot.current_name,
                )
                context_report = build_context_trace(
                    store,
                    history_context.storage_name,
                )
                _present_context_trace(
                    context_report,
                    as_json=as_json,
                    tui=tui,
                    verbose=verbose,
                    limit=operation_limit,
                )
                return
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

        if selector is None:
            name = context_snapshot.resolve_or_current(context_name)
            if not name:
                raise ProvenanceError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
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
        assert selector is not None
        owner_locator, item_selector = parse_memory_report_locator(
            selector,
            explicit_context=context_name,
        )
        report: TraceReport | MemoryReferenceTraceReport | GrantedMemoryTraceReport
        granted_access = None
        if owner_locator is not None:
            access = resolve_context_access(
                store,
                owner_locator,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            if access.is_granted:
                granted_access = access
                resolved_target = None
            else:
                resolved_target = resolve_local_memory_report_target(
                    store,
                    item_selector,
                    current=context_snapshot.current_name,
                    context_locator=access.context_name,
                )
        else:
            # Read-only report UIDs round-trip from Profile-wide Find/List/Search
            # results. Current local and READ-granted Memories therefore share
            # one ambiguity-preserving catalog. Retained local history and
            # Memory references remain a fallback only when no current row
            # matches anywhere in that readable namespace.
            readable_catalog = freeze_memory_report_readable_catalog(
                store,
                current=context_snapshot.current_name,
            )
            try:
                readable_target = (
                    resolve_readable_memory_target(
                        readable_catalog,
                        item_selector,
                    )
                    if readable_catalog is not None
                    else None
                )
            except ReadableMemoryTargetNotFoundError:
                readable_target = None
            if readable_target is not None:
                if readable_target.access.is_granted:
                    granted_access = readable_target.access
                    resolved_target = None
                    item_selector = readable_target.uid
                else:
                    resolved_target = resolve_local_memory_report_target(
                        store,
                        readable_target.uid,
                        current=context_snapshot.current_name,
                        context_locator=readable_target.context_name,
                    )
            else:
                resolved_target = resolve_local_memory_report_target(
                    store,
                    item_selector,
                    current=context_snapshot.current_name,
                    context_locator=None,
                )

        if granted_access is not None:
            report = build_granted_memory_trace(granted_access, item_selector)
            annotate_memory_report_attempt(
                operation="trace",
                context_name=report.context_name,
                memory_uid=report.selected_uid,
                include_descendants=False,
            )
        else:
            assert resolved_target is not None
            if resolved_target.kind == "MEMORY_REFERENCE":
                owner = store.load_direct(resolved_target.context_name)
                report = build_reference_trace(
                    store,
                    owner,
                    resolved_target.uid,
                )
            else:
                history_context = load_retained_history_context(
                    store,
                    context_locator=resolved_target.context_name,
                    current_name=context_snapshot.current_name,
                )
                report = build_memory_history(
                    store,
                    history_context,
                    resolved_target.uid,
                )
                annotate_memory_report_attempt(
                    operation="trace",
                    context_name=history_context.display_name,
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
        if not isinstance(report, TraceReport):
            typer.secho(
                "Trace error: --tui currently supports direct local Memory "
                "lineage; use --plain for a reference or granted Memory.",
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
        if isinstance(report, MemoryReferenceTraceReport):
            render_reference_trace(
                report,
                verbose=verbose,
                limit=operation_limit,
            )
        elif isinstance(report, GrantedMemoryTraceReport):
            render_granted_trace(report, verbose=verbose)
        else:
            render_trace(report, verbose=verbose, limit=operation_limit)
        return
    if isinstance(report, MemoryReferenceTraceReport):
        render_reference_trace_receipt(report)
    elif isinstance(report, GrantedMemoryTraceReport):
        render_granted_trace_receipt(report)
    else:
        render_trace_receipt(report)
