"""Terminal projection for one complete Context lineage."""

from __future__ import annotations

from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.console.commands.trace.projection import (
    DEFAULT_TRACE_OPERATION_LIMIT,
    MAX_TRACE_OPERATION_LIMIT,
)
from memcommit.application.retained_history.context_history import (
    ContextTraceChange,
    ContextTraceEvent,
    ContextTraceReport,
)
from memcommit.adapters.interfaces.console.text import display_escape_text
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import (
    plain_text_from_fragments,
)
from memcommit.adapters.interfaces.tui.core.theme import semantic_action_style
from memcommit.adapters.interfaces.tui.viewers.read_only import run_read_only_viewer
from memcommit.application.reviewing.memory_diff import MemoryChange, memory_diff_lines


_CONTEXT_TRACE_VIEWER_MIN_HEIGHT = 10
_CONTEXT_TRACE_VIEWER_MAX_HEIGHT = 28


def _short_uid(value: str, verbose: bool) -> str:
    return value if verbose else value[:8]


def _append_change(
    fragments: StyleAndTextTuples,
    change: ContextTraceChange,
    *,
    verbose: bool,
) -> None:
    treatment = {
        "CREATED": "ADD",
        "EDITED": "EDIT",
        "REMOVED": "REMOVE",
        "RESTORED": "EDIT",
    }[change.kind]
    mechanical = MemoryChange(
        marker={"ADD": "+", "EDIT": "~", "REMOVE": "−"}[treatment],
        treatment=treatment,
        location="context-trace",
        memory_uid=change.memory_uid,
        before=change.before.content if change.before is not None else None,
        after=change.after.content if change.after is not None else None,
    )
    uid = display_escape_text(_short_uid(change.memory_uid, verbose))
    for line in memory_diff_lines(mechanical):
        style_key = {
            "-": "remove",
            "+": "add",
            "=": "equal",
            " ": "equal",
        }[line.marker]
        visible_marker = line.marker if line.marker in {"-", "+"} else " "
        marker_style = {
            "-": "class:memory-diff.before-marker",
            "+": "class:memory-diff.after-marker",
        }.get(line.marker, "class:memory-diff.equal")
        fragments.extend(
            (
                (marker_style, f"  {visible_marker} "),
                ("class:report-neutral", "["),
                (
                    semantic_action_style(
                        treatment,
                        fallback="class:report-neutral",
                    ),
                    treatment,
                ),
                ("class:report-neutral", "] "),
                ("class:memory-object", f"[MEMORY {uid}] "),
            )
        )
        fragments.extend(
            (
                (
                    f"class:memory-diff.{style_key}"
                    + (".changed" if span.changed else ""),
                    display_escape_text(span.text),
                )
                for span in line.spans
            )
        )
        fragments.append(("", "\n"))


def _append_event(
    fragments: StyleAndTextTuples,
    event: ContextTraceEvent,
    *,
    verbose: bool,
) -> None:
    checkpoint = (
        f"CHECKPOINT {_short_uid(event.checkpoint_uid, verbose)}"
        if event.checkpoint_uid is not None
        else "UNRECORDED"
    )
    timestamp = (
        event.timestamp[:16].replace("T", " ")
        if event.timestamp is not None
        else "current"
    )
    fragments.extend(
        (
            (
                semantic_action_style(
                    event.command,
                    fallback="class:report-neutral",
                ),
                display_escape_text(event.command),
            ),
            ("class:report-neutral", " "),
            ("class:history-receipt", f"[{display_escape_text(checkpoint)}]"),
            (
                "class:report-neutral",
                f"  {display_escape_text(timestamp)} · "
                f"{len(event.changes)} MEMORY CHANGE"
                f"{'S' if len(event.changes) != 1 else ''}\n",
            ),
        )
    )
    if event.description:
        fragments.append(
            (
                "class:report-neutral",
                f"  {display_escape_text(event.description)}\n",
            )
        )
    if event.changes:
        for change in event.changes:
            _append_change(fragments, change, verbose=verbose)
    else:
        fragments.append(("class:report-neutral", "  (no direct Memory change)\n"))
    fragments.append(("", "\n"))


def context_trace_document_fragments(
    report: ContextTraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> StyleAndTextTuples:
    """Project the whole Context timeline, bounded by complete operations."""

    if limit is not None and not 1 <= limit <= MAX_TRACE_OPERATION_LIMIT:
        raise ValueError(
            f"Trace operation limit must be between 1 and {MAX_TRACE_OPERATION_LIMIT}."
        )
    newest = tuple(reversed(report.events))
    shown = newest if limit is None else newest[:limit]
    hidden = len(newest) - len(shown)
    context_uid = f" [{display_escape_text(report.context_uid)}]" if verbose else ""
    total_changes = sum(len(event.changes) for event in report.events)
    fragments: StyleAndTextTuples = [
        ("class:report-label", "TRACE"),
        (
            "class:report-neutral",
            f" · {display_escape_text(report.context_name)}{context_uid}\n",
        ),
        ("class:report-label", "[CONTEXT]"),
        (
            "class:report-neutral",
            f" · {len(report.events)} OPERATION"
            f"{'S' if len(report.events) != 1 else ''}"
            f" · {total_changes} MEMORY CHANGE"
            f"{'S' if total_changes != 1 else ''} · LATEST FIRST",
        ),
    ]
    if hidden:
        fragments.append(
            ("class:report-neutral", f" · SHOWING {len(shown)} OF {len(newest)}")
        )
    fragments.append(("class:report-neutral", "\n\n"))
    if shown:
        for event in shown:
            _append_event(fragments, event, verbose=verbose)
    else:
        fragments.append(
            ("class:report-neutral", "No retained operation affects this Context.\n")
        )
    if hidden:
        fragments.extend(
            (
                ("class:history-receipt", f"… {hidden} OLDER OPERATIONS HIDDEN"),
                ("class:report-neutral", " · use --all or --limit N\n"),
            )
        )
    if report.warnings:
        fragments.extend((("", "\n"), ("class:report-label", "LIMITS\n")))
        fragments.extend(
            ("class:report-neutral", f"  − {display_escape_text(warning)}\n")
            for warning in report.warnings
        )
    return fragments


def format_context_trace_report(
    report: ContextTraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
) -> str:
    return plain_text_from_fragments(
        context_trace_document_fragments(report, verbose=verbose, limit=limit),
        whole_document=True,
    )


def open_context_trace_viewer(
    report: ContextTraceReport,
    *,
    verbose: bool = False,
    limit: int | None = DEFAULT_TRACE_OPERATION_LIMIT,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> None:
    """Read one lineage document without a checkpoint-selection surface."""

    fragments = context_trace_document_fragments(
        report,
        verbose=verbose,
        limit=limit,
    )
    plain = plain_text_from_fragments(fragments, whole_document=True)
    compact_height = min(
        max(plain.count("\n") + 4, _CONTEXT_TRACE_VIEWER_MIN_HEIGHT),
        _CONTEXT_TRACE_VIEWER_MAX_HEIGHT,
    )
    run_read_only_viewer(
        fragments,
        title="TRACE REPORT",
        frame_title="CONTEXT LINEAGE",
        compact_height=compact_height,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )


__all__ = [
    "context_trace_document_fragments",
    "format_context_trace_report",
    "open_context_trace_viewer",
]
