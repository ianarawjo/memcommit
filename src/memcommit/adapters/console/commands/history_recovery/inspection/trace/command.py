"""Render retained per-Memory content history and lineage."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_memory_report_attempt
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.memory_report_picker import (
    ScopedMemoryPickerItem,
    choose_memory_report_target,
)
from memcommit.adapters.console.coordination.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
)
from memcommit.adapters.console.coordination.history_target import (
    resolve_explicit_context_history_target,
)
from memcommit.adapters.console.commands.history_recovery.inspection.trace.context_projection import (
    format_context_trace_report,
)
from memcommit.adapters.console.terminal.components.read_only_viewer import (
    interactive_report_terminal,
)
from memcommit.adapters.console.commands.history_recovery.inspection.trace.projection import (
    DEFAULT_TRACE_OPERATION_LIMIT,
    MAX_TRACE_OPERATION_LIMIT,
    format_compact_trace_report,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.core.context_targeting.model import ContextTarget
from memcommit.application.capabilities.history.verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.operations.history_recovery.inspection.trace.application import (
    ContextHistorySlice,
    GrantedMemoryTraceReport,
    MemoryHistory,
    MemoryReferenceTraceReport,
    TraceContextTarget,
    TraceMemoryTarget,
    TraceReport,
    TraceRequest,
    TraceTargetCatalogRequest,
)
from memcommit.application.operations.history_recovery.inspection.trace.runtime import (
    execute_trace,
    load_trace_target_catalog,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.profiles.profile.config import ProfileConfigError
from memcommit.application.operations.profiles.profile.model import ProfileError


def render_trace(
    report: MemoryHistory,
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
    report: ContextHistorySlice,
    *,
    as_json: bool,
    verbose: bool,
    limit: int | None,
) -> None:
    """Present one whole lineage without introducing checkpoint selection."""

    if as_json:
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return
    typer.echo(
        format_context_trace_report(
            report,
            verbose=verbose,
            limit=limit,
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
) -> None:
    """Show one Context lineage or one Memory's retained provenance."""
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
            raise MemoryHistoryReconstructionError(
                "JSON output requires an explicit item UID."
            )
        explicit_context = context_name is not None
        if selector is not None and not explicit_context:
            explicit_target = resolve_explicit_context_history_target(
                selector,
                current_context=context_snapshot.current_name,
                available_context_names=store.list_context_names(),
            )
            if isinstance(explicit_target, ContextTarget):
                trace_result = execute_trace(
                    TraceRequest(
                        target=TraceContextTarget(explicit_target.context_name),
                        current_context_name=context_snapshot.current_name,
                    ),
                    store=store,
                )
                context_report = trace_result.report
                if not isinstance(context_report, ContextHistorySlice):
                    raise RuntimeError("Context Trace returned an invalid report.")
                _present_context_trace(
                    context_report,
                    as_json=as_json,
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
                raise MemoryHistoryReconstructionError(
                    "Trace launcher returned an invalid action."
                )

        if selector is None:
            name = context_snapshot.resolve_or_current(context_name)
            if not name:
                raise MemoryHistoryReconstructionError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
            # The current or explicit Context is already the useful default.
            # Freeze its descendants for the range control, but do not force a
            # second location decision before the person can see its Memories.
            target_catalog = load_trace_target_catalog(
                TraceTargetCatalogRequest(
                    context_locator=name,
                    current_context_name=context_snapshot.current_name,
                    # Freeze every descendant before the shared RANGE control
                    # narrows or broadens what can actually be selected.
                    include_descendants=True,
                ),
                store=store,
            )
            catalog_names = target_catalog.context_names
            candidate_items = tuple(
                ScopedMemoryPickerItem(
                    context_name=candidate.context_name,
                    uid=candidate.uid,
                    content=candidate.content,
                    status=candidate.status,
                    catalog_context_names=catalog_names,
                    change_count=candidate.change_count,
                )
                for candidate in target_catalog.candidates
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
        trace_result = execute_trace(
            TraceRequest(
                target=TraceMemoryTarget(
                    selector=selector,
                    context_locator=context_name,
                ),
                current_context_name=context_snapshot.current_name,
            ),
            store=store,
        )
        report: TraceReport = trace_result.report
        if isinstance(report, GrantedMemoryTraceReport):
            annotate_memory_report_attempt(
                operation="trace",
                context_name=report.context_name,
                memory_uid=report.selected_uid,
                include_descendants=False,
            )
        elif isinstance(report, MemoryHistory):
            annotate_memory_report_attempt(
                operation="trace",
                context_name=report.context_name,
                memory_uid=report.selected_uid,
                include_descendants=False,
            )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        MemoryHistoryReconstructionError,
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
