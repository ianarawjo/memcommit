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
    format_compact_trace_report,
    open_trace_history,
    short_operation_uid as _operation_uid,
    short_uid as _uid,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.provenance import (
    MemoryState,
    ProvenanceError,
    TraceEvent,
    TraceReport,
    collect_trace_candidates,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


_EVIDENCE_COLORS = {
    "RECORDED": typer.colors.GREEN,
    "RECONSTRUCTED": typer.colors.CYAN,
    "INFERRED": typer.colors.YELLOW,
    "UNRECORDED": typer.colors.RED,
}

def _render_content(prefix: str, state: MemoryState, *, verbose: bool) -> None:
    typer.secho(f"  {prefix} [{_uid(state.uid, verbose)}]", bold=True)
    for line in safe_terminal_text(state.content).splitlines() or [""]:
        typer.echo(f"      {line}")


def _render_event(event: TraceEvent, *, verbose: bool) -> None:
    timestamp = (
        event.timestamp[:16].replace("T", " ") if event.timestamp else "(current)"
    )
    typer.secho(f"{timestamp}  {event.kind}", bold=True, nl=False)
    typer.secho(
        f"  {event.evidence}",
        fg=_EVIDENCE_COLORS[event.evidence],
        bold=True,
    )
    checkpoint = (
        _uid(event.checkpoint_uid, verbose)
        if event.checkpoint_uid is not None
        else "none"
    )
    typer.secho(
        f"  Command: {safe_terminal_text(event.command)}  |  Checkpoint: {checkpoint}",
        dim=True,
    )
    if event.description:
        typer.secho(
            f"  {safe_terminal_text(event.description)}",
            dim=True,
        )
    operation = event.command_operation
    if operation is not None:
        typer.secho(
            "  Operation: "
            f"{safe_terminal_text(operation.command)} "
            f"[{_operation_uid(operation.uid, verbose)}]",
            bold=True,
        )
        if operation.source_command is not None and operation.source_uid is not None:
            typer.echo(
                "  Source operation: mem "
                f"{safe_terminal_text(operation.source_command)} "
                f"[{_operation_uid(operation.source_uid, verbose)}]"
            )
        if len(operation.contexts) == 1:
            context = operation.contexts[0]
            typer.echo(
                "  Affected Context: "
                f"{display_escape_text(context.name)} "
                f"[{_uid(context.uid, verbose)}]"
            )
        else:
            typer.echo(f"  Affected Contexts: {len(operation.contexts)}")
            for context in operation.contexts:
                typer.echo(
                    "    - "
                    f"{display_escape_text(context.name)} "
                    f"[{_uid(context.uid, verbose)}]"
                )
    if event.kind in {
        "EDITED",
        "RESTORED",
        "REORDERED",
        "HISTORY_GAP",
    }:
        for state in event.before:
            _render_content("-", state, verbose=verbose)
        for state in event.after:
            _render_content("+", state, verbose=verbose)
    elif event.kind in {"SPLIT", "ABSORBED", "TRANSLATED"}:
        for state in event.before:
            _render_content("FROM", state, verbose=verbose)
        for state in event.after:
            _render_content("TO", state, verbose=verbose)
    elif event.kind == "REMOVED":
        for state in event.before:
            _render_content("-", state, verbose=verbose)
    else:
        for state in event.after:
            _render_content("+", state, verbose=verbose)

    occurrence = event.source_occurrence
    if occurrence is not None:
        details = f"{occurrence.mode} item {occurrence.ordinal}/{occurrence.total}"
        if occurrence.line_number is not None:
            details += f", source line {occurrence.line_number}"
        qualifier = (
            "exact raw line retained"
            if occurrence.exact_raw_source
            else "normalized line/order reconstructed"
        )
        typer.secho(f"  Source occurrence: {details} ({qualifier})", dim=True)
    if event.reason:
        typer.echo(f"  Reason: {safe_terminal_text(event.reason)}")
    if event.reason_codes:
        typer.secho(
            "  Rules: " + ", ".join(event.reason_codes),
            dim=True,
        )
    if event.declared_frame is not None:
        review_uid = (
            _uid(event.source_review_uid, verbose)
            if event.source_review_uid is not None
            else "unrecorded"
        )
        typer.secho(
            f"  Reviewed declared context/comment (review {review_uid}):",
            fg=typer.colors.YELLOW,
        )
        for line in safe_terminal_text(event.declared_frame).splitlines() or [""]:
            typer.echo(f"      {line}")
        if event.uncertainty_reason:
            typer.echo(
                "  Requested because: " + safe_terminal_text(event.uncertainty_reason)
            )
    for evidence in event.child_evidence:
        typer.secho(
            f"  Applied citations for [{_uid(evidence.result_uid, verbose)}]:",
            dim=True,
        )
        typer.secho(
            "      Source spans: "
            + " | ".join(safe_terminal_text(span) for span in evidence.source_spans),
            dim=True,
        )
        if evidence.frame_spans:
            typer.secho(
                "      Declared-frame spans: "
                + " | ".join(safe_terminal_text(span) for span in evidence.frame_spans),
                dim=True,
            )


def _render_compact_trace(report: TraceReport) -> None:
    """Render the complete retained range as newest-first operation rows."""
    typer.echo(format_compact_trace_report(report))


def _render_detailed_trace(report: TraceReport, *, verbose: bool) -> None:
    typer.secho(
        f"Trace for [{_uid(report.selected_uid, verbose)}]",
        bold=True,
    )
    typer.echo(
        f"Context: {display_escape_text(report.context_name)} "
        f"[{_uid(report.context_uid, verbose)}]"
    )

    typer.secho("\nORIGINAL", bold=True)
    if not report.originals:
        typer.secho("  (original state is not retained)", fg=typer.colors.YELLOW)
    for state in report.originals:
        _render_content("ORIGIN", state, verbose=verbose)

    typer.secho("\nCONTENT LINEAGE", bold=True)
    if not report.events:
        typer.echo("  (no retained content events)")
    for index, event in enumerate(report.events):
        if index:
            typer.echo()
        _render_event(event, verbose=verbose)

    typer.secho("\nANALYSIS ATTACHMENTS — separated from content history", bold=True)
    if not report.analyses:
        typer.echo("  (no saved analysis for this lineage)")
    for analysis in report.analyses:
        color = (
            typer.colors.GREEN
            if analysis.status == "APPLIED"
            else (
                typer.colors.CYAN
                if analysis.status == "CURRENT"
                else typer.colors.YELLOW
            )
        )
        typer.secho(
            f"  {analysis.kind}  {analysis.status}  "
            f"{analysis.classification} / {analysis.action}",
            fg=color,
            bold=True,
        )
        typer.secho(
            f"  Analysis: {_uid(analysis.analysis_uid, verbose)}  "
            f"|  Source: {_uid(analysis.memory_uid, verbose)}",
            dim=True,
        )
        typer.echo(f"  Reason: {safe_terminal_text(analysis.reason)}")
        typer.secho(
            "  Rules: " + ", ".join(analysis.reason_codes),
            dim=True,
        )
        if analysis.declared_frame is not None:
            review_uid = (
                _uid(analysis.source_review_uid, verbose)
                if analysis.source_review_uid is not None
                else "unrecorded"
            )
            typer.secho(
                f"  Reviewed declared context/comment (review {review_uid}):",
                fg=typer.colors.YELLOW,
            )
            for line in safe_terminal_text(analysis.declared_frame).splitlines() or [
                ""
            ]:
                typer.echo(f"      {line}")
            if analysis.declared_frame_reason:
                typer.echo(
                    "  Requested because: "
                    + safe_terminal_text(analysis.declared_frame_reason)
                )
        for index, child in enumerate(analysis.children, 1):
            typer.secho(f"  Proposed child {index}:", fg=typer.colors.GREEN)
            for line in safe_terminal_text(child.content).splitlines() or [""]:
                typer.echo(f"      {line}")
            typer.secho(
                "      Source spans: "
                + " | ".join(safe_terminal_text(span) for span in child.source_spans),
                dim=True,
            )
            if child.frame_spans:
                typer.secho(
                    "      Declared-frame spans: "
                    + " | ".join(
                        safe_terminal_text(span) for span in child.frame_spans
                    ),
                    dim=True,
                )

    typer.secho("\nCURRENT", bold=True)
    if not report.current:
        typer.secho(
            "  (no descendant from this lineage is currently present)",
            fg=typer.colors.YELLOW,
        )
    else:
        for state in report.current:
            _render_content("CURRENT", state, verbose=verbose)
        if (
            len(report.originals) == 1
            and len(report.current) == 1
            and report.originals[0].uid == report.current[0].uid
            and report.originals[0].content == report.current[0].content
        ):
            typer.secho(
                "  Same UID and content as the retained original — UNCHANGED",
                fg=typer.colors.GREEN,
            )

    if report.warnings:
        typer.secho("\nLIMITS", bold=True)
        for warning in report.warnings:
            typer.secho(
                f"  - {safe_terminal_text(warning)}",
                fg=typer.colors.YELLOW,
            )


def render_trace(report: TraceReport, *, verbose: bool = False) -> None:
    """Use compact operation rows by default; retain full evidence on demand."""
    if verbose:
        _render_detailed_trace(report, verbose=True)
        return
    _render_compact_trace(report)


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "UID (or unambiguous prefix) of a current or historical "
                "direct Memory; omit to enter the interactive Memory picker"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context whose retained history to inspect (defaults to current)",
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
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the structured trace as JSON"),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the lineage instead of opening the shared History explorer",
        ),
    ] = False,
) -> None:
    """Show recorded and safely reconstructed content lineage."""
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        if selector is None and as_json:
            raise ProvenanceError("JSON output requires an explicit Memory UID.")
        if selector is None and interactive_report_terminal():
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
            history_scope = load_retained_history_scope(
                store,
                context_locator=context_name,
                current_name=context_snapshot.current_name,
                # The shared range control starts narrow but must know every
                # eligible descendant before the person broadens it.
                include_descendants=True,
            )
            candidate_items = tuple(
                ScopedMemoryPickerItem(
                    context_name=context.display_name,
                    uid=candidate.uid,
                    content=candidate.content,
                    status=candidate.status,
                    catalog_context_names=tuple(
                        item.display_name for item in history_scope
                    ),
                    change_count=candidate.change_count,
                )
                for context in history_scope
                for candidate in collect_trace_candidates(store, context.context)
            )
            selected = choose_memory_report_target(
                candidate_items,
                context_name=name,
                operation="trace",
                initial_include_descendants=False,
            )
            if selected is None:
                typer.echo("Trace cancelled.")
                return
            selector = selected.memory_uid
            context_name = selected.owner_context_name
            # The picker is read-only, but another process may have changed the
            # Context while it was open. Re-read before resolving the exact UID
            # so the rendered report never mixes old live state with new history.
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
    if interactive_report_terminal() and not plain:
        open_trace_history(
            report,
            context_name=name,
            verbose=verbose,
        )
        return
    render_trace(report, verbose=verbose)
