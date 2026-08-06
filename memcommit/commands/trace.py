"""Render retained per-Memory content history and lineage."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from typing import Annotated, Optional

import typer

from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.granted_context import resolve_context_access
from memcommit.commands.memory_picker import choose_memory
from memcommit.commands.read_only_viewer import (
    interactive_report_terminal,
    run_read_only_viewer,
)
from memcommit.commands.tui_primitives import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.provenance import (
    MemoryState,
    ProvenanceError,
    TraceEvent,
    TraceReport,
    build_trace,
    collect_trace_candidates,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.study_operation_policy import require_trace_access


_EVIDENCE_COLORS = {
    "RECORDED": typer.colors.GREEN,
    "RECONSTRUCTED": typer.colors.CYAN,
    "INFERRED": typer.colors.YELLOW,
    "UNRECORDED": typer.colors.RED,
}

_COMPACT_CONTENT_LIMIT = 44
_COMPACT_STATES_LIMIT = 2


@dataclass(frozen=True)
class _OperationRow:
    """One presentation-only command boundary in a Memory lineage."""

    events: tuple[TraceEvent, ...]
    before: tuple[MemoryState, ...]
    after: tuple[MemoryState, ...]


def _uid(uid: str, verbose: bool) -> str:
    return uid if verbose else uid[:8]


def _operation_uid(uid: str, verbose: bool) -> str:
    """Keep compound command-unit identifiers useful in compact output."""
    if verbose:
        return uid
    parts = uid.split(":")
    if len(parts) >= 2 and parts[0] in {"checkpoint", "revert", "update"}:
        return parts[1][:8]
    return uid[:8]


def _operation_key(event: TraceEvent, index: int) -> tuple[str, str]:
    """Prefer retained operation identity over its storage checkpoint."""
    if event.command_operation is not None:
        return ("command", event.command_operation.uid)
    if event.operation_id is not None:
        return ("operation", event.operation_id)
    if event.checkpoint_uid is not None:
        # Legacy one-checkpoint/one-command history has no stronger operation
        # identity. The checkpoint remains an internal grouping fallback, not
        # the primary compact UI label.
        return ("checkpoint", event.checkpoint_uid)
    return ("event", str(index))


def _ordered_states(
    events: tuple[TraceEvent, ...],
    attribute: str,
    component_uids: frozenset[str],
) -> tuple[MemoryState, ...]:
    by_uid: dict[str, MemoryState] = {}
    for event in events:
        states = event.before if attribute == "before" else event.after
        for state in states:
            if state.uid not in component_uids:
                continue
            if attribute == "before":
                by_uid.setdefault(state.uid, state)
            else:
                by_uid[state.uid] = state
    return tuple(sorted(by_uid.values(), key=lambda state: state.position))


def _operation_rows(report: TraceReport) -> tuple[_OperationRow, ...]:
    """Group chronological TraceEvents into newest-first operation rows."""
    grouped: list[list[TraceEvent]] = []
    index_by_key: dict[tuple[str, str], int] = {}
    for index, event in enumerate(report.events):
        key = _operation_key(event, index)
        group_index = index_by_key.get(key)
        if group_index is None:
            group_index = len(grouped)
            index_by_key[key] = group_index
            grouped.append([])
        grouped[group_index].append(event)

    component_uids = frozenset(report.component_uids)
    rows = [
        _OperationRow(
            events=tuple(events),
            before=_ordered_states(
                tuple(events),
                "before",
                component_uids,
            ),
            after=_ordered_states(
                tuple(events),
                "after",
                component_uids,
            ),
        )
        for events in grouped
    ]
    return tuple(reversed(rows))


def _compact(value: str, limit: int = _COMPACT_CONTENT_LIMIT) -> str:
    escaped = display_escape_text(value)
    if not escaped:
        return "(empty)"
    if len(escaped) <= limit:
        return escaped
    return escaped[: limit - 1].rstrip() + "…"


def _compact_states(states: tuple[MemoryState, ...], *, verbose: bool) -> str:
    if not states:
        return "∅"
    shown = states[:_COMPACT_STATES_LIMIT]
    rendered = [
        (
            f"[{display_escape_text(_uid(state.uid, verbose))}]"
            f"@{state.position + 1} "
            f"“{_compact(state.content)}”"
        )
        for state in shown
    ]
    remaining = len(states) - len(shown)
    if remaining:
        rendered.append(f"+{remaining} more")
    return " + ".join(rendered)


def _row_effect(row: _OperationRow) -> str:
    kinds = tuple(dict.fromkeys(event.kind for event in row.events))
    if kinds == ("RESTORED",):
        if row.before and not row.after:
            return "RESTORED/REMOVED"
        if row.after and not row.before:
            return "RESTORED/ADDED"
        return "RESTORED/CHANGED"
    return "+".join(kinds)


def _row_command(row: _OperationRow) -> str:
    operations = [
        event.command_operation
        for event in row.events
        if event.command_operation is not None
    ]
    if operations:
        operation = operations[0]
        label = f"mem {display_escape_text(operation.command)}"
        if operation.source_command is not None:
            label += f" ← mem {display_escape_text(operation.source_command)}"
        return label
    commands = tuple(dict.fromkeys(event.command for event in row.events))
    return "/".join(f"mem {display_escape_text(command)}" for command in commands)


def _render_operation_row(row: _OperationRow, *, verbose: bool) -> None:
    timestamp = display_escape_text(
        next(
            (
                event.timestamp[:16].replace("T", " ")
                for event in reversed(row.events)
                if event.timestamp
            ),
            "(current)",
        )
    )
    evidence = "/".join(dict.fromkeys(event.evidence for event in row.events))
    typer.echo(
        f"{timestamp} · {_row_command(row)} · {_row_effect(row)} · "
        f"{_compact_states(row.before, verbose=verbose)} → "
        f"{_compact_states(row.after, verbose=verbose)} · {evidence}"
    )


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
    typer.secho(
        f"Trace [{display_escape_text(_uid(report.selected_uid, False))}] · "
        f"{display_escape_text(report.context_name)}",
        bold=True,
    )
    typer.secho(
        "RANGE · earliest retained evidence → current Context · "
        "LATEST FIRST (↓ older); each row is BEFORE → AFTER",
        dim=True,
    )
    typer.echo(
        "NOW · "
        + (
            _compact_states(report.current, verbose=False)
            if report.current
            else "∅ (lineage absent from current Context)"
        )
    )

    rows = _operation_rows(report)
    if not rows:
        typer.echo("(no retained operations for this lineage)")
    for row in rows:
        _render_operation_row(row, verbose=False)

    typer.echo(
        "ORIGIN · "
        + (
            _compact_states(report.originals, verbose=False)
            if report.originals
            else "? (earliest origin is not retained)"
        )
    )
    if report.analyses:
        label = "analysis" if len(report.analyses) == 1 else "analyses"
        typer.echo(
            f"ATTACHMENTS · {len(report.analyses)} saved {label} "
            "(use --verbose for details)"
        )
    else:
        typer.echo("ATTACHMENTS · none")
    for warning in report.warnings:
        typer.secho(
            "LIMIT · " + _compact(warning, 120),
            fg=typer.colors.YELLOW,
        )


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


def trace_report_text(report: TraceReport, *, verbose: bool = False) -> str:
    """Render once into neutral text for the common read-only Viewer."""
    output = StringIO()
    with redirect_stdout(output):
        render_trace(report, verbose=verbose)
    return output.getvalue().rstrip("\n")


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
) -> None:
    """Show recorded and safely reconstructed content lineage."""
    opened_picker = selector is None
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        name = context_snapshot.resolve_or_current(context_name)
        if not name:
            raise ProvenanceError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        access = resolve_context_access(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
        # Trace is a retained command/checkpoint log, not a content reading.
        # Enforce the Study and grant boundary before opening any history.
        require_trace_access(
            access.display_name,
            granted=access.is_granted,
            store_root=store.store_dir,
        )
        ctx = store.load_direct(access.context_name)
        if selector is None:
            if as_json:
                raise ProvenanceError("JSON output requires an explicit Memory UID.")
            selector = choose_memory(
                collect_trace_candidates(store, ctx),
                context_name=name,
                operation="trace",
            )
            if selector is None:
                typer.echo("Trace cancelled.")
                return
            # The picker is read-only, but another process may have changed the
            # Context while it was open. Re-read before resolving the exact UID
            # so the rendered report never mixes old live state with new history.
            ctx = store.load_direct(access.context_name)
        report = build_trace(store, ctx, selector)
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
    if opened_picker and interactive_report_terminal():
        run_read_only_viewer(
            trace_report_text(report, verbose=verbose),
            title="TRACE REPORT",
        )
        return
    render_trace(report, verbose=verbose)
