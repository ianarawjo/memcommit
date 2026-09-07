"""Render retained per-Memory content history and lineage."""

from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
    try_resolve_existing_context_access,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.memory_report_picker import (
    ScopedMemoryPickerItem,
    choose_history_report_target,
)
from memcommit.adapters.console.coordination.history_target import (
    resolve_explicit_context_history_target,
)
from memcommit.adapters.console.commands.trace.context_projection import (
    format_context_trace_report,
    open_context_trace_viewer,
)
from memcommit.adapters.console.terminal.components.read_only_viewer import (
    interactive_report_terminal,
)
from memcommit.adapters.console.commands.trace.projection import (
    DEFAULT_TRACE_OPERATION_LIMIT,
    MAX_TRACE_OPERATION_LIMIT,
    format_compact_trace_report,
    open_trace_viewer,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.core.context_targeting.model import ContextTarget, DirectMemoryTarget
from memcommit.application.capabilities.history.verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.capabilities.history.query.context_history_slicing import (
    ContextHistorySlice,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
)
from memcommit.application.operations.trace.application import (
    TraceContextTarget,
    TraceMemoryTarget,
    TraceReport,
    TraceRequest,
    TraceTargetCatalogRequest,
)
from memcommit.application.operations.trace.granted_view import (
    GrantedMemoryTraceReport,
)
from memcommit.application.operations.trace.reference_lineage import (
    MemoryReferenceTraceReport,
)
from memcommit.application.operations.trace.runtime import (
    execute_trace,
    load_trace_target_catalog,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError


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
    if interactive_report_terminal():
        # Context Trace already owns one complete, frozen report.  The Viewer
        # only bounds that document inside the terminal; it does not introduce
        # checkpoint selection or another semantic execution path.
        open_context_trace_viewer(report, verbose=verbose, limit=limit)
        return
    typer.echo(
        format_context_trace_report(
            report,
            verbose=verbose,
            limit=limit,
        )
    )


def _execute_context_trace(
    store: MemoryStore,
    *,
    context_name: str,
    current_context_name: str | None,
    as_json: bool,
    verbose: bool,
    limit: int | None,
) -> None:
    """Run and present one exact Context target through the shared boundary."""

    trace_result = execute_trace(
        TraceRequest(
            target=TraceContextTarget(context_name),
            current_context_name=current_context_name,
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
        limit=limit,
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
                "browse the current local subtree for one exact Context or "
                "Memory when omitted; otherwise accepts CONTEXT, "
                "Memory/MemoryRef UID/prefix, or CONTEXT:UID"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Trace this exact Context; cannot be combined with SELECTOR",
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
        if selector is not None and context_name is not None:
            raise MemoryHistoryReconstructionError(
                "--context selects a Context and cannot be combined with SELECTOR; "
                "use CONTEXT:UID for an exact Memory."
            )
        if selector is None and context_name is None and as_json:
            raise MemoryHistoryReconstructionError(
                "JSON output requires an explicit Context or Memory target."
            )
        if context_name is not None:
            context_name = resolve_existing_context_access(
                store,
                context_name,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            ).name
            _execute_context_trace(
                store,
                context_name=context_name,
                current_context_name=context_snapshot.current_name,
                as_json=as_json,
                verbose=verbose,
                limit=operation_limit,
            )
            return
        if selector is not None:
            context_identity = try_resolve_existing_context_access(
                store,
                selector,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            explicit_target = (
                ContextTarget(context_identity.name)
                if context_identity is not None
                else resolve_explicit_context_history_target(
                    selector,
                    current_context=context_snapshot.current_name,
                    available_context_names=store.list_context_names(),
                )
            )
            if isinstance(explicit_target, ContextTarget):
                _execute_context_trace(
                    store,
                    context_name=explicit_target.context_name,
                    current_context_name=context_snapshot.current_name,
                    as_json=as_json,
                    verbose=verbose,
                    limit=operation_limit,
                )
                return

        if selector is None:
            name = context_snapshot.current_name
            if not name:
                raise MemoryHistoryReconstructionError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
            # The Switch-style browser freezes the current lexical subtree, but
            # every returned Context or Memory remains one exact target.
            target_catalog = load_trace_target_catalog(
                TraceTargetCatalogRequest(
                    context_locator=name,
                    current_context_name=context_snapshot.current_name,
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
            selected = choose_history_report_target(
                candidate_items,
                context_name=name,
                operation="trace",
                catalog_context_names=catalog_names,
            )
            if selected is None:
                typer.echo("Trace cancelled.")
                return
            if isinstance(selected, ContextTarget):
                _execute_context_trace(
                    store=store,
                    context_name=selected.context_name,
                    current_context_name=context_snapshot.current_name,
                    as_json=False,
                    verbose=verbose,
                    limit=operation_limit,
                )
                return
            if not isinstance(selected, DirectMemoryTarget):
                raise MemoryHistoryReconstructionError(
                    "Trace browser returned an invalid target."
                )
            selector = selected.memory_uid
            context_name = selected.context_name
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
        if interactive_report_terminal():
            # Keep stdout available to pipes and `mem log --memory`, while the
            # direct human Trace route contains the same document in one
            # scrollable read-only viewport.
            open_trace_viewer(report, verbose=verbose, limit=operation_limit)
        else:
            render_trace(report, verbose=verbose, limit=operation_limit)
