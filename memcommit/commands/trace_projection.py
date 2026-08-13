"""Project one Memory lineage into the common temporal-history workbench."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.commands.history_picker import HistoryPickerEntry, choose_history
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.core.text_layout import elide_terminal_text
from memcommit.provenance import MemoryState, TraceEvent, TraceReport


_COMPACT_CONTENT_LIMIT = 44
_COMPACT_STATES_LIMIT = 2


@dataclass(frozen=True)
class TraceOperationRow:
    """One retained command boundary touching a selected lineage."""

    identity: str
    events: tuple[TraceEvent, ...]
    before: tuple[MemoryState, ...]
    after: tuple[MemoryState, ...]


def short_uid(uid: str, verbose: bool) -> str:
    return uid if verbose else uid[:8]


def short_operation_uid(uid: str, verbose: bool) -> str:
    """Keep compound command-unit identifiers useful in compact output."""

    if verbose:
        return uid
    parts = uid.split(":")
    if len(parts) >= 2 and parts[0] in {"checkpoint", "revert", "update"}:
        return parts[1][:8]
    return uid[:8]


def _operation_key(event: TraceEvent, index: int) -> tuple[str, str]:
    if event.command_operation is not None:
        return ("command", event.command_operation.uid)
    if event.operation_id is not None:
        return ("operation", event.operation_id)
    if event.checkpoint_uid is not None:
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


def trace_operation_rows(report: TraceReport) -> tuple[TraceOperationRow, ...]:
    """Group chronological events into newest-first command rows."""

    grouped: list[tuple[str, list[TraceEvent]]] = []
    index_by_key: dict[tuple[str, str], int] = {}
    identities: set[str] = set()
    for index, event in enumerate(report.events):
        key = _operation_key(event, index)
        group_index = index_by_key.get(key)
        if group_index is None:
            group_index = len(grouped)
            index_by_key[key] = group_index
            identity = key[1]
            if identity in identities:
                identity = f"{key[0]}:{identity}"
            identities.add(identity)
            grouped.append((identity, []))
        grouped[group_index][1].append(event)

    component_uids = frozenset(report.component_uids)
    rows = [
        TraceOperationRow(
            identity=identity,
            events=tuple(events),
            before=_ordered_states(tuple(events), "before", component_uids),
            after=_ordered_states(tuple(events), "after", component_uids),
        )
        for identity, events in grouped
    ]
    return tuple(reversed(rows))


def compact_text(value: str, limit: int = _COMPACT_CONTENT_LIMIT) -> str:
    escaped = display_escape_text(value)
    if not escaped:
        return "(empty)"
    return elide_terminal_text(escaped, limit)


def format_trace_states(
    states: tuple[MemoryState, ...],
    *,
    verbose: bool,
) -> str:
    if not states:
        return "∅"
    visible = states[:_COMPACT_STATES_LIMIT]
    rendered = [
        (
            f"[{display_escape_text(short_uid(state.uid, verbose))}]"
            f"@{state.position + 1} "
            f"“{compact_text(state.content)}”"
        )
        for state in visible
    ]
    remaining = len(states) - len(visible)
    if remaining:
        rendered.append(f"+{remaining} more")
    return " + ".join(rendered)


def trace_row_effect(row: TraceOperationRow) -> str:
    kinds = tuple(dict.fromkeys(event.kind for event in row.events))
    if kinds == ("RESTORED",):
        if row.before and not row.after:
            return "RESTORED/REMOVED"
        if row.after and not row.before:
            return "RESTORED/ADDED"
        return "RESTORED/CHANGED"
    return "+".join(kinds)


def trace_row_command(row: TraceOperationRow) -> str:
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


def trace_row_timestamp(row: TraceOperationRow) -> str:
    return next(
        (
            event.timestamp
            for event in reversed(row.events)
            if event.timestamp
        ),
        "(current)",
    )


def trace_row_evidence(row: TraceOperationRow) -> str:
    return "/".join(dict.fromkeys(event.evidence for event in row.events))


def format_trace_operation(
    row: TraceOperationRow,
    *,
    verbose: bool,
) -> str:
    timestamp = display_escape_text(
        trace_row_timestamp(row)[:16].replace("T", " ")
    )
    return (
        f"{timestamp} · {trace_row_command(row)} · {trace_row_effect(row)} · "
        f"{format_trace_states(row.before, verbose=verbose)} → "
        f"{format_trace_states(row.after, verbose=verbose)} · "
        f"{trace_row_evidence(row)}"
    )


def format_compact_trace_report(report: TraceReport) -> str:
    """Return the stable plain projection shared by Log and Trace."""

    lines = [
        f"Trace [{display_escape_text(short_uid(report.selected_uid, False))}] · "
        f"{display_escape_text(report.context_name)}",
        (
            "RANGE · earliest retained evidence → current Context · "
            "LATEST FIRST (↓ older); each row is BEFORE → AFTER"
        ),
        "NOW · "
        + (
            format_trace_states(report.current, verbose=False)
            if report.current
            else "∅ (lineage absent from current Context)"
        ),
        "OPERATIONS · latest first",
    ]
    rows = trace_operation_rows(report)
    if not rows:
        lines.append("(no retained operations for this lineage)")
    else:
        lines.extend(format_trace_operation(row, verbose=False) for row in rows)
    lines.append(
        "ORIGIN · "
        + (
            format_trace_states(report.originals, verbose=False)
            if report.originals
            else "? (earliest origin is not retained)"
        )
    )
    if report.analyses:
        label = "analysis" if len(report.analyses) == 1 else "analyses"
        lines.append(
            f"ATTACHMENTS · {len(report.analyses)} saved {label} "
            "(use --verbose for details)"
        )
    else:
        lines.append("ATTACHMENTS · none")
    lines.extend(
        "LIMIT · " + compact_text(warning, 120)
        for warning in report.warnings
    )
    return "\n".join(lines)


def _full_states(label: str, states: tuple[MemoryState, ...]) -> tuple[str, ...]:
    if not states:
        return (f"{label}: ∅",)
    return (
        f"{label}:",
        *(
            "  "
            + f"[{display_escape_text(state.uid)}]@{state.position + 1} "
            + display_escape_text(state.content)
            for state in states
        ),
    )


def _lineage_summary(report: TraceReport) -> tuple[str, ...]:
    return (
        f"Selected Memory: {display_escape_text(report.selected_uid)}",
        "Lineage UIDs: "
        + ", ".join(display_escape_text(uid) for uid in report.component_uids),
        *_full_states("NOW", report.current),
        *_full_states("EARLIEST RETAINED", report.originals),
    )


def _row_detail(report: TraceReport, row: TraceOperationRow) -> str:
    reasons = tuple(
        dict.fromkeys(
            display_escape_text(event.reason)
            for event in row.events
            if event.reason
        )
    )
    descriptions = tuple(
        dict.fromkeys(
            display_escape_text(event.description)
            for event in row.events
            if event.description
        )
    )
    return "\n".join(
        (
            *_lineage_summary(report),
            "",
            f"Operation: {trace_row_command(row)}",
            f"Effect: {trace_row_effect(row)}",
            f"Evidence: {trace_row_evidence(row)}",
            *_full_states("BEFORE", row.before),
            *_full_states("AFTER", row.after),
            *(f"Description: {value}" for value in descriptions),
            *(f"Recorded reason: {value}" for value in reasons),
            *(
                ("", "LIMITS", *(f"  - {display_escape_text(value)}" for value in report.warnings))
                if report.warnings
                else ()
            ),
        )
    )


def trace_history_entries(
    report: TraceReport,
    *,
    verbose: bool = False,
) -> tuple[HistoryPickerEntry, ...]:
    """Adapt lineage operations to the common log/diff history picker."""

    return tuple(
        HistoryPickerEntry(
            uid=row.identity,
            timestamp=trace_row_timestamp(row),
            command=trace_row_command(row),
            description=(
                f"{trace_row_effect(row)} · {trace_row_evidence(row)} · "
                f"{format_trace_states(row.before, verbose=verbose)} → "
                f"{format_trace_states(row.after, verbose=verbose)}"
            ),
            detail=_row_detail(report, row),
        )
        for row in trace_operation_rows(report)
    )


def trace_empty_detail(report: TraceReport) -> str:
    """Render a lineage endpoint even when no retained operation exists."""

    return "\n".join(
        (
            *_lineage_summary(report),
            "",
            "No retained operation affects this lineage.",
            *(f"LIMIT: {display_escape_text(value)}" for value in report.warnings),
        )
    )


def open_trace_history(
    report: TraceReport,
    *,
    context_name: str | None = None,
    verbose: bool = False,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> None:
    """Open a Memory lineage through the same Items/Viewer shell as Log."""

    entries = trace_history_entries(report, verbose=verbose)
    choose_history(
        entries,
        context_name=context_name or report.context_name,
        mode="log",
        initial_details_open=True,
        empty_message="No retained operations for this Memory lineage.",
        empty_detail=trace_empty_detail(report),
        title=f"TRACE · MEMORY [{report.selected_uid[:8]}]",
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
