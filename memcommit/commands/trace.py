"""Render retained per-Memory content history and lineage."""
from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from memcommit.commands.tui_primitives import safe_terminal_text
from memcommit.provenance import (
    MemoryState,
    ProvenanceError,
    TraceEvent,
    TraceReport,
    build_trace,
)
from memcommit.store import MemoryStore


_EVIDENCE_COLORS = {
    "RECORDED": typer.colors.GREEN,
    "RECONSTRUCTED": typer.colors.CYAN,
    "INFERRED": typer.colors.YELLOW,
    "UNRECORDED": typer.colors.RED,
}


def _uid(uid: str, verbose: bool) -> str:
    return uid if verbose else uid[:8]


def _render_content(prefix: str, state: MemoryState, *, verbose: bool) -> None:
    typer.secho(f"  {prefix} [{_uid(state.uid, verbose)}]", bold=True)
    for line in safe_terminal_text(state.content).splitlines() or [""]:
        typer.echo(f"      {line}")


def _render_event(event: TraceEvent, *, verbose: bool) -> None:
    timestamp = (
        event.timestamp[:16].replace("T", " ")
        if event.timestamp
        else "(current)"
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
        f"  Command: {safe_terminal_text(event.command)}"
        f"  |  Checkpoint: {checkpoint}",
        dim=True,
    )
    if event.description:
        typer.secho(
            f"  {safe_terminal_text(event.description)}",
            dim=True,
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
        details = (
            f"{occurrence.mode} item {occurrence.ordinal}/{occurrence.total}"
        )
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
                "  Requested because: "
                + safe_terminal_text(event.uncertainty_reason)
            )
    for evidence in event.child_evidence:
        typer.secho(
            f"  Applied citations for [{_uid(evidence.result_uid, verbose)}]:",
            dim=True,
        )
        typer.secho(
            "      Source spans: "
            + " | ".join(
                safe_terminal_text(span)
                for span in evidence.source_spans
            ),
            dim=True,
        )
        if evidence.frame_spans:
            typer.secho(
                "      Declared-frame spans: "
                + " | ".join(
                    safe_terminal_text(span)
                    for span in evidence.frame_spans
                ),
                dim=True,
            )


def render_trace(report: TraceReport, *, verbose: bool = False) -> None:
    typer.secho(
        f"Trace for [{_uid(report.selected_uid, verbose)}]",
        bold=True,
    )
    typer.echo(
        f"Context: {safe_terminal_text(report.context_name)} "
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
            for line in safe_terminal_text(
                analysis.declared_frame
            ).splitlines() or [""]:
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
                + " | ".join(
                    safe_terminal_text(span)
                    for span in child.source_spans
                ),
                dim=True,
            )
            if child.frame_spans:
                typer.secho(
                    "      Declared-frame spans: "
                    + " | ".join(
                        safe_terminal_text(span)
                        for span in child.frame_spans
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


def cmd(
    selector: Annotated[
        str,
        typer.Argument(
            help=(
                "UID (or unambiguous prefix) of a current or historical "
                "direct Memory"
            )
        ),
    ],
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
            help="Show complete Context, Memory, and checkpoint UIDs",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the structured trace as JSON"),
    ] = False,
) -> None:
    """Show recorded and safely reconstructed content lineage."""
    store = MemoryStore(create=False)
    try:
        name = context_name or store.current_context_name()
        if not name:
            raise ProvenanceError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        ctx = store.load_direct(name)
        report = build_trace(store, ctx, selector)
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        ProvenanceError,
    ) as error:
        typer.secho(f"Trace error: {error}", fg=typer.colors.RED, err=True)
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
    render_trace(report, verbose=verbose)
