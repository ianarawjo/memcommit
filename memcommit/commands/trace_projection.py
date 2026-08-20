"""Project one Memory lineage as a bounded vertical diff document."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output
from prompt_toolkit.formatted_text.base import StyleAndTextTuples

from memcommit.history_display import (
    HistoryDisplayBadge,
    HistoryDisplayRow,
    HistoryRowSegment,
    history_display_row_segments,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.tui.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
)
from memcommit.interfaces.tui.core.theme import (
    semantic_action_style,
)
from memcommit.interfaces.tui.viewers.read_only import run_read_only_viewer
from memcommit.provenance import MemoryState, TraceEvent, TraceReport


_COMPACT_CONTENT_LIMIT = 44
_COMPACT_STATES_LIMIT = 2
DEFAULT_TRACE_OPERATION_LIMIT = 20
MAX_TRACE_OPERATION_LIMIT = 200
_TRACE_VIEWER_MIN_HEIGHT = 10
_TRACE_VIEWER_MAX_HEIGHT = 28


@dataclass(frozen=True)
class TraceOperationRow:
    """One retained command boundary touching a selected lineage."""

    identity: str
    events: tuple[TraceEvent, ...]
    before: tuple[MemoryState, ...]
    after: tuple[MemoryState, ...]


def short_uid(uid: str, verbose: bool) -> str:
    return uid if verbose else uid[:8]


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


def trace_row_action(row: TraceOperationRow) -> str:
    """Return the action token used by the shared compact History row."""

    operations = _unique_text(
        event.command_operation.command
        for event in row.events
        if event.command_operation is not None
    )
    if operations:
        return "/".join(operations)
    return "/".join(_unique_text(event.command for event in row.events))


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


def _trace_row_summary(row: TraceOperationRow) -> str:
    action = trace_row_action(row)
    operation = next(
        (
            event.command_operation
            for event in row.events
            if event.command_operation is not None
        ),
        None,
    )
    if action in {"undo", "redo"} and operation is not None:
        if operation.source_command:
            effect = "restored" if action == "undo" else "reapplied"
            return f"{effect} mem {operation.source_command}"
    if action == "add" and row.after:
        content = row.after[0].content
        compact = (
            elide_terminal_text(content, _COMPACT_CONTENT_LIMIT)
            if content
            else "(empty)"
        )
        return f'created "{compact}"'
    if action == "edit":
        return ""
    if action == "remove" and row.before:
        content = row.before[0].content
        compact = (
            elide_terminal_text(content, _COMPACT_CONTENT_LIMIT)
            if content
            else "(empty)"
        )
        return f'removed "{compact}"'
    descriptions = _unique_text(event.description for event in row.events)
    if descriptions:
        return " / ".join(" ".join(description.split()) for description in descriptions)
    return trace_row_effect(row).lower().replace("_", " ")


def _short_identity(value: str) -> str:
    parts = value.split(":")
    return (parts[1] if len(parts) > 1 and parts[1] else parts[0])[:8]


def trace_history_display_row(row: TraceOperationRow) -> HistoryDisplayRow:
    """Adapt one lineage operation to the exact typed row used by Log."""

    checkpoint_uids = _unique_text(event.checkpoint_uid for event in row.events)
    checkpoint_uid = checkpoint_uids[0] if checkpoint_uids else row.identity
    badges: list[HistoryDisplayBadge] = []
    if len(checkpoint_uids) == 1:
        badges.append(HistoryDisplayBadge(f"CHECKPOINT {checkpoint_uid[:8]}"))
    elif checkpoint_uids:
        badges.append(HistoryDisplayBadge(f"CHECKPOINTS {len(checkpoint_uids)}"))

    operation = next(
        (
            event.command_operation
            for event in row.events
            if event.command_operation is not None
        ),
        None,
    )
    if operation is not None and operation.source_uid is not None:
        badges.extend(
            (
                HistoryDisplayBadge(
                    f"RECEIPT {_short_identity(operation.uid)}",
                    "history-receipt",
                ),
                HistoryDisplayBadge(
                    "SOURCE "
                    f"{operation.source_command or 'command'} "
                    f"{_short_identity(operation.source_uid)}",
                    "history-source",
                ),
            )
        )
    elif row.identity not in checkpoint_uids:
        badges.append(
            HistoryDisplayBadge(
                f"COMMAND {_short_identity(row.identity)}",
                "history-source",
            )
        )

    memory_uids = _unique_text(
        state.uid for state in (*row.before, *row.after)
    )
    if len(memory_uids) == 1:
        badges.append(
            HistoryDisplayBadge(f"MEMORY {memory_uids[0][:8]}", "memory-object")
        )
    elif memory_uids:
        badges.append(
            HistoryDisplayBadge(f"MEMORIES {len(memory_uids)}", "memory-object")
        )

    return HistoryDisplayRow(
        command=trace_row_action(row),
        timestamp=trace_row_timestamp(row)[:16].replace("T", " "),
        checkpoint_uid=checkpoint_uid,
        command_identity=row.identity,
        summary=_trace_row_summary(row),
        badges=tuple(badges),
        details=(),
    )


def format_trace_operation(
    row: TraceOperationRow,
    *,
    verbose: bool,
) -> str:
    history_row = trace_history_display_row(row)
    header = "".join(
        display_escape_text(segment.text)
        for segment in history_display_row_segments(history_row)
    )
    # The shared Log summary is the compact semantic label; repeating the
    # typed effect and evidence here would make one operation read three times.
    if not verbose and trace_row_action(row) in {"add", "remove"}:
        return header
    return (
        f"{header} · {format_trace_states(row.before, verbose=verbose)} → "
        f"{format_trace_states(row.after, verbose=verbose)}"
    )


def _extend_effect_fragments(
    fragments: StyleAndTextTuples,
    effect: str,
) -> None:
    """Color typed child effects without assigning one hue to a mixed row."""

    for index, token in enumerate(effect.split("+")):
        if index:
            fragments.append(("class:report-neutral", "+"))
        fragments.append(
            (
                semantic_action_style(token, fallback="class:report-label"),
                display_escape_text(token),
            )
        )


def _state_uid(state: MemoryState, *, verbose: bool) -> str:
    return display_escape_text(short_uid(state.uid, verbose))


def _after_marker_action(row: TraceOperationRow) -> str:
    before_uids = {state.uid for state in row.before}
    after_uids = {state.uid for state in row.after}
    if before_uids and before_uids == after_uids:
        return "edit"
    if trace_row_effect(row).startswith("RESTORED/"):
        return "restored"
    return "add"


def _extend_diff_states(
    fragments: StyleAndTextTuples,
    row: TraceOperationRow,
    *,
    verbose: bool,
) -> None:
    """Render one lineage edge inline instead of opening a second Viewer."""

    before = row.before or (None,)
    after = row.after or (None,)
    for marker, action, states in (
        ("−", "remove", before),
        ("+", _after_marker_action(row), after),
    ):
        marker_style = semantic_action_style(action, fallback="class:report-label")
        for state in states:
            fragments.append((marker_style, f"  {marker} "))
            if state is None:
                fragments.append(("class:report-neutral", "∅\n"))
                continue
            fragments.extend(
                (
                    (
                        "class:memory-object",
                        f"[{_state_uid(state, verbose=verbose)}]"
                        f"@{state.position + 1} ",
                    ),
                    (
                        "class:memory-object",
                        display_escape_text(state.content) + "\n",
                    ),
                )
            )


def _unique_text(values: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _extend_verbose_event_evidence(
    fragments: StyleAndTextTuples,
    row: TraceOperationRow,
) -> None:
    checkpoints = _unique_text(event.checkpoint_uid for event in row.events)
    for checkpoint in checkpoints:
        fragments.extend(
            (
                ("class:report-label", "  Checkpoint: "),
                ("class:history-receipt", display_escape_text(checkpoint) + "\n"),
            )
        )
    operations = tuple(
        dict.fromkeys(
            event.command_operation
            for event in row.events
            if event.command_operation is not None
        )
    )
    if not operations and row.identity not in checkpoints:
        fragments.extend(
            (
                ("class:report-label", "  Command unit: "),
                (
                    "class:history-source",
                    display_escape_text(row.identity) + "\n",
                ),
            )
        )
    for operation in operations:
        fragments.extend(
            (
                ("class:report-label", "  Operation: "),
                (
                    semantic_action_style(
                        operation.command,
                        fallback="class:report-neutral",
                    ),
                    display_escape_text(operation.command),
                ),
                (
                    "class:history-receipt",
                    f" [{display_escape_text(operation.uid)}]\n",
                ),
            )
        )
        if operation.source_command is not None and operation.source_uid is not None:
            fragments.extend(
                (
                    ("class:report-label", "  Source operation: "),
                    (
                        semantic_action_style(
                            operation.source_command,
                            fallback="class:report-neutral",
                        ),
                        f"mem {display_escape_text(operation.source_command)}",
                    ),
                    (
                        "class:history-receipt",
                        f" [{display_escape_text(operation.source_uid)}]\n",
                    ),
                )
            )
        if len(operation.contexts) > 1:
            fragments.extend(
                (
                    ("class:report-label", "  Affected Contexts: "),
                    (
                        "class:report-neutral",
                        f"{len(operation.contexts)}\n",
                    ),
                )
            )
        for context in operation.contexts:
            prefix = (
                "  Affected Context: "
                if len(operation.contexts) == 1
                else "    − "
            )
            fragments.extend(
                (
                    ("class:report-label", prefix),
                    (
                        "class:report-neutral",
                        f"{display_escape_text(context.name)} "
                        f"[{display_escape_text(context.uid)}]\n",
                    ),
                )
            )
    for description in _unique_text(event.description for event in row.events):
        fragments.extend(
            (
                ("class:report-label", "  Description: "),
                ("class:report-neutral", display_escape_text(description) + "\n"),
            )
        )
    for event in row.events:
        occurrence = event.source_occurrence
        if occurrence is not None:
            detail = f"{occurrence.mode} item {occurrence.ordinal}/{occurrence.total}"
            if occurrence.line_number is not None:
                detail += f", source line {occurrence.line_number}"
            qualifier = (
                "exact raw line retained"
                if occurrence.exact_raw_source
                else "normalized line/order reconstructed"
            )
            fragments.extend(
                (
                    ("class:report-label", "  Source occurrence: "),
                    ("class:report-neutral", f"{detail} ({qualifier})\n"),
                )
            )
        if event.reason_codes:
            fragments.extend(
                (
                    ("class:report-label", "  Rules: "),
                    (
                        "class:report-neutral",
                        ", ".join(display_escape_text(code) for code in event.reason_codes)
                        + "\n",
                    ),
                )
            )
        if event.declared_frame is not None:
            review_uid = event.source_review_uid or "unrecorded"
            fragments.extend(
                (
                    (
                        "class:report-label",
                        "  Reviewed declared context/comment "
                        f"(review {display_escape_text(review_uid)}):\n",
                    ),
                    (
                        "class:report-neutral",
                        "    " + display_escape_text(event.declared_frame) + "\n",
                    ),
                )
            )
            if event.uncertainty_reason:
                fragments.extend(
                    (
                        ("class:report-label", "  Requested because: "),
                        (
                            "class:report-neutral",
                            display_escape_text(event.uncertainty_reason) + "\n",
                        ),
                    )
                )
        for evidence in event.child_evidence:
            fragments.extend(
                (
                    (
                        "class:report-label",
                        "  Applied citations for "
                        f"[{display_escape_text(evidence.result_uid)}]:\n",
                    ),
                    (
                        "class:report-neutral",
                        "    Source spans: "
                        + " | ".join(
                            display_escape_text(span) for span in evidence.source_spans
                        )
                        + "\n",
                    ),
                )
            )
            if evidence.frame_spans:
                fragments.append(
                    (
                        "class:report-neutral",
                        "    Declared-frame spans: "
                        + " | ".join(
                            display_escape_text(span) for span in evidence.frame_spans
                        )
                        + "\n",
                    )
                )


def _history_segment_style(segment: HistoryRowSegment) -> str:
    if segment.style == "semantic-action":
        return semantic_action_style(
            segment.action or segment.text,
            fallback="class:report-label",
        )
    return f"class:{segment.style}"


def _extend_operation(
    fragments: StyleAndTextTuples,
    row: TraceOperationRow,
    *,
    verbose: bool,
) -> None:
    fragments.extend(
        (
            _history_segment_style(segment),
            display_escape_text(segment.text),
        )
        for segment in history_display_row_segments(trace_history_display_row(row))
    )
    fragments.append(("class:report-neutral", "\n"))
    # Direct Add/Remove rows already name their one content-bearing endpoint.
    # Edits and structural/restoration commands need the diff to communicate
    # their meaning; verbose inspection deliberately expands every operation.
    if verbose or trace_row_action(row) not in {"add", "remove"}:
        _extend_diff_states(fragments, row, verbose=verbose)
    for reason in _unique_text(event.reason for event in row.events):
        fragments.extend(
            (
                ("class:report-label", "  Reason · "),
                ("class:report-neutral", display_escape_text(reason) + "\n"),
            )
        )
    if verbose:
        fragments.append(("class:report-label", "  Lineage: "))
        _extend_effect_fragments(fragments, trace_row_effect(row))
        fragments.extend(
            (
                ("class:report-neutral", " · "),
                ("class:report-label", trace_row_evidence(row)),
                ("class:report-neutral", "\n"),
            )
        )
        _extend_verbose_event_evidence(fragments, row)
    fragments.append(("class:report-neutral", "\n"))


def _extend_analyses(
    fragments: StyleAndTextTuples,
    report: TraceReport,
    *,
    verbose: bool,
) -> None:
    if not report.analyses:
        fragments.extend(
            (
                ("class:report-label", "ATTACHMENTS\n"),
                ("class:report-neutral", "  none\n"),
            )
        )
        return
    label = "analysis" if len(report.analyses) == 1 else "analyses"
    fragments.append(("class:report-label", "ATTACHMENTS\n"))
    if not verbose:
        fragments.append(
            (
                "class:report-neutral",
                f"  {len(report.analyses)} saved {label} · use --verbose for details\n",
            )
        )
        return
    for analysis in report.analyses:
        fragments.extend(
            (
                (
                    "class:report-label",
                    f"  {display_escape_text(analysis.kind)}  "
                    f"{display_escape_text(analysis.status)}  ",
                ),
                (
                    "class:report-neutral",
                    f"{display_escape_text(analysis.classification)} / "
                    f"{display_escape_text(analysis.action)}\n",
                ),
                (
                    "class:history-receipt",
                    f"  Analysis: {display_escape_text(analysis.analysis_uid)}"
                    f" · Source: {display_escape_text(analysis.memory_uid)}\n",
                ),
                ("class:report-label", "  Reason: "),
                ("class:report-neutral", display_escape_text(analysis.reason) + "\n"),
            )
        )
        if analysis.reason_codes:
            fragments.append(
                (
                    "class:report-neutral",
                    "  Rules: "
                    + ", ".join(
                        display_escape_text(code) for code in analysis.reason_codes
                    )
                    + "\n",
                )
            )
        if analysis.declared_frame is not None:
            review_uid = analysis.source_review_uid or "unrecorded"
            fragments.extend(
                (
                    (
                        "class:report-label",
                        "  Reviewed declared context/comment "
                        f"(review {display_escape_text(review_uid)}):\n",
                    ),
                    (
                        "class:report-neutral",
                        "    " + display_escape_text(analysis.declared_frame) + "\n",
                    ),
                )
            )
            if analysis.declared_frame_reason:
                fragments.extend(
                    (
                        ("class:report-label", "  Requested because: "),
                        (
                            "class:report-neutral",
                            display_escape_text(analysis.declared_frame_reason) + "\n",
                        ),
                    )
                )
        for index, child in enumerate(analysis.children, 1):
            fragments.extend(
                (
                    ("class:report-label", f"  Proposed child {index}: "),
                    ("class:memory-object", display_escape_text(child.content) + "\n"),
                    (
                        "class:report-neutral",
                        "    Source spans: "
                        + " | ".join(
                            display_escape_text(span) for span in child.source_spans
                        )
                        + "\n",
                    ),
                )
            )
            if child.frame_spans:
                fragments.append(
                    (
                        "class:report-neutral",
                        "    Declared-frame spans: "
                        + " | ".join(
                            display_escape_text(span) for span in child.frame_spans
                        )
                        + "\n",
                    )
                )


def trace_document_fragments(
    report: TraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> StyleAndTextTuples:
    """Project one Memory lineage as a bounded, continuous vertical document."""

    if limit is not None and not 1 <= limit <= MAX_TRACE_OPERATION_LIMIT:
        raise ValueError(
            f"Trace operation limit must be between 1 and {MAX_TRACE_OPERATION_LIMIT}."
        )
    rows = trace_operation_rows(report)
    shown = rows if limit is None else rows[:limit]
    hidden = len(rows) - len(shown)
    selected_uid = display_escape_text(short_uid(report.selected_uid, verbose))
    context_uid = (
        f" [{display_escape_text(report.context_uid)}]" if verbose else ""
    )
    fragments: StyleAndTextTuples = [
        ("class:report-label", "TRACE"),
        (
            "class:report-neutral",
            f" · {display_escape_text(report.context_name)}{context_uid}\n",
        ),
        ("class:memory-object", f"[MEMORY {selected_uid}]"),
        (
            "class:report-neutral",
            f" · {len(rows)} OPERATION{'S' if len(rows) != 1 else ''}"
            " · LATEST FIRST",
        ),
    ]
    if hidden:
        fragments.append(
            ("class:report-neutral", f" · SHOWING {len(shown)} OF {len(rows)}")
        )
    fragments.extend(
        (
            ("class:report-neutral", "\n\n"),
        )
    )
    if shown:
        for row in shown:
            _extend_operation(fragments, row, verbose=verbose)
    else:
        fragments.append(
            ("class:report-neutral", "No retained operation affects this lineage.\n\n")
        )
    if hidden:
        fragments.extend(
            (
                ("class:history-receipt", f"… {hidden} OLDER OPERATIONS HIDDEN"),
                (
                    "class:report-neutral",
                    " · use --all or --limit N\n\n",
                ),
            )
        )
    _extend_analyses(fragments, report, verbose=verbose)
    if report.warnings:
        fragments.append(("class:report-neutral", "\n"))
        fragments.append(("class:report-label", "LIMITS\n"))
        fragments.extend(
            ("class:report-neutral", f"  − {display_escape_text(warning)}\n")
            for warning in report.warnings
        )
    return fragments


def format_compact_trace_report(
    report: TraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> str:
    """Return the ANSI-free document shared by Log and non-TTY Trace."""

    return plain_text_from_fragments(
        trace_document_fragments(report, verbose=verbose, limit=limit),
        whole_document=True,
    )


def open_trace_viewer(
    report: TraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> None:
    """Open the bounded lineage document without a second Items surface."""

    fragments = trace_document_fragments(report, verbose=verbose, limit=limit)
    plain = plain_text_from_fragments(fragments, whole_document=True)
    # Frame borders and the footer need three rows beyond the logical document.
    # Long traces stop growing and keep the same wrapped-row scroll mechanics.
    compact_height = min(
        max(plain.count("\n") + 4, _TRACE_VIEWER_MIN_HEIGHT),
        _TRACE_VIEWER_MAX_HEIGHT,
    )
    run_read_only_viewer(
        fragments,
        title="TRACE REPORT",
        frame_title="LINEAGE",
        compact_height=compact_height,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
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
    """Compatibility adapter for callers migrating from the Items workbench.

    The Context name no longer changes presentation because the frozen report
    already owns its canonical Context identity.  Existing callers still land
    in the same single vertical Viewer instead of requiring a broad migration
    alongside this focused Trace change.
    """

    del context_name
    open_trace_viewer(
        report,
        verbose=verbose,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
