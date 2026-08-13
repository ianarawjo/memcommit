"""Explain one Memory using provenance, saved analysis, and local context."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from typing import Annotated, Optional

import typer

from memcommit.command_attempts import annotate_memory_report_attempt
from memcommit.commands.command_progress import progressing_provider_factory
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.memory_picker import (
    ScopedMemoryPickerItem,
    choose_memory_report_target,
)
from memcommit.commands.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
)
from memcommit.interfaces.tui.viewers.read_only import (
    interactive_report_terminal,
    run_read_only_viewer,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.provenance import (
    ProvenanceError,
    TraceEvent,
)
from memcommit.query_provider import connect_codex_chatgpt_provider
from memcommit.rationale import (
    ContextEvidence,
    RationaleError,
    RationaleReport,
    build_rationale,
)
from memcommit.rationale_scope import (
    authorize_rationale_inference,
    load_rationale_scope,
    rationale_candidates,
    rationale_trace,
    resolve_rationale_target,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def _uid(value: str, verbose: bool) -> str:
    return value if verbose else value[:8]


def _render_memory(
    evidence: ContextEvidence,
    *,
    verbose: bool,
) -> None:
    typer.secho(
        f"  [{_uid(evidence.memory.uid, verbose)}] "
        f"{display_escape_text(evidence.context_name)} · "
        f"position {evidence.position + 1}",
        bold=True,
    )
    for line in safe_terminal_text(evidence.memory.content).splitlines() or [""]:
        typer.echo(f"      {line}")


def _render_origin(event: TraceEvent, *, verbose: bool) -> None:
    timestamp = (
        event.timestamp[:16].replace("T", " ") if event.timestamp else "(unknown time)"
    )
    checkpoint = _uid(event.checkpoint_uid, verbose) if event.checkpoint_uid else "none"
    typer.echo(f"  {event.kind} via {safe_terminal_text(event.command)} at {timestamp}")
    typer.secho(
        f"  Checkpoint: {checkpoint}  |  Evidence: {event.evidence}",
        dim=True,
    )
    if event.source_occurrence is not None:
        occurrence = event.source_occurrence
        detail = f"{occurrence.mode} item {occurrence.ordinal}/{occurrence.total}"
        if occurrence.line_number is not None:
            detail += f", original line {occurrence.line_number}"
        typer.echo(f"  Source occurrence: {detail}")


def render_rationale(
    report: RationaleReport,
    *,
    verbose: bool = False,
) -> None:
    scope_reach = (
        "and readable descendants"
        if report.inference_scope_include_descendants
        else "this Context only"
    )
    scope_display = (
        f"{display_escape_text(report.inference_scope_name)} {scope_reach}"
        if report.inference_scope_include_descendants
        else f"{display_escape_text(report.inference_scope_name)} · {scope_reach}"
    )
    typer.secho(
        f"Rationale for [{_uid(report.trace.selected_uid, verbose)}]",
        bold=True,
    )
    typer.echo(
        f"Context: {display_escape_text(report.trace.context_name)} "
        f"[{_uid(report.trace.context_uid, verbose)}]"
    )
    typer.echo(
        "Rationale scope: "
        f"{scope_display} "
        f"· {report.inference_scope_context_count} Context(s)"
    )
    typer.secho("\nMEMORY", bold=True)
    for line in safe_terminal_text(report.target.content).splitlines() or [""]:
        typer.echo(f"  {line}")

    if report.recorded_evidence_available:
        typer.secho("\nRECORDED ORIGIN", bold=True)
        if not report.origin_events:
            typer.secho(
                "  No retained creation event was found.",
                fg=typer.colors.YELLOW,
            )
        for event in report.origin_events:
            _render_origin(event, verbose=verbose)

        typer.secho("\nRECORDED RATIONALE", bold=True)
        if not report.recorded_reason_events:
            typer.echo(
                "  No semantic creation or transformation rationale was recorded."
            )
        for event in report.recorded_reason_events:
            typer.secho(
                f"  {event.kind}  {event.evidence}",
                bold=True,
            )
            typer.echo(f"  {safe_terminal_text(event.reason or '')}")
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
                for line in safe_terminal_text(event.declared_frame).splitlines() or [
                    ""
                ]:
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
                        safe_terminal_text(span) for span in evidence.source_spans
                    ),
                    dim=True,
                )
                if evidence.frame_spans:
                    typer.secho(
                        "      Declared-frame spans: "
                        + " | ".join(
                            safe_terminal_text(span) for span in evidence.frame_spans
                        ),
                        dim=True,
                    )

    else:
        typer.secho("\nAUTHORITY HISTORY", bold=True)
        typer.secho(
            "  Not exposed by this granted READ view. Trace, checkpoints, "
            "and authority analysis artifacts remain unavailable.",
            fg=typer.colors.YELLOW,
        )

    typer.secho("\nSAVED ANALYSIS — not a creation cause", bold=True)
    analysis = report.saved_analysis
    if analysis is None:
        if report.stale_analysis:
            typer.secho(
                "  A related saved review exists but is stale and was not "
                "used as current evidence.",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.echo("  (no current saved analysis for this Memory)")
    else:
        typer.secho(
            f"  {analysis.interpretation} / {analysis.clarification}",
            fg=typer.colors.YELLOW,
            bold=True,
        )
        typer.echo(f"  Reason: {safe_terminal_text(analysis.reason)}")
        if analysis.question:
            typer.echo(f"  Question: {safe_terminal_text(analysis.question)}")
        for label, reading in analysis.readings:
            typer.echo(f"  [{label}] {safe_terminal_text(reading)}")
        if analysis.selected_reading is not None:
            typer.secho(
                "  Selected: " + safe_terminal_text(analysis.selected_reading),
                fg=typer.colors.GREEN,
            )
        if analysis.response.strip():
            typer.echo("  Reviewer response: " + safe_terminal_text(analysis.response))

    typer.secho("\nSAVED ATOMIZE ANALYSIS", bold=True)
    if not report.trace.analyses:
        typer.echo("  (no saved atomize analysis for this lineage)")
    for atomize in report.trace.analyses:
        typer.secho(
            f"  {atomize.status}  {atomize.classification} / {atomize.action}",
            fg=(
                typer.colors.GREEN
                if atomize.status == "APPLIED"
                else (
                    typer.colors.CYAN
                    if atomize.status == "CURRENT"
                    else typer.colors.YELLOW
                )
            ),
            bold=True,
        )
        typer.echo(f"  Reason: {safe_terminal_text(atomize.reason)}")
        typer.secho(
            "  Rules: " + ", ".join(atomize.reason_codes),
            dim=True,
        )
        if atomize.declared_frame is not None:
            review_uid = (
                _uid(atomize.source_review_uid, verbose)
                if atomize.source_review_uid is not None
                else "unrecorded"
            )
            typer.secho(
                f"  Reviewed declared context/comment (review {review_uid}):",
                fg=typer.colors.YELLOW,
            )
            for line in safe_terminal_text(atomize.declared_frame).splitlines() or [""]:
                typer.echo(f"      {line}")
            if atomize.declared_frame_reason:
                typer.echo(
                    "  Requested because: "
                    + safe_terminal_text(atomize.declared_frame_reason)
                )
        for index, child in enumerate(atomize.children, 1):
            typer.echo(f"  Proposed child {index}:")
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
        if atomize.status != "APPLIED":
            typer.secho(
                "  This analysis is not recorded as an applied content change.",
                dim=True,
            )

    typer.secho("\nUNAPPLIED PROPOSALS", bold=True)
    if not report.proposals:
        typer.echo("  (none linked to this lineage)")
    for proposal in report.proposals:
        typer.secho(
            f"  {proposal.status.upper()} {proposal.operation.upper()} "
            f"as {proposal.role}",
            fg=typer.colors.CYAN,
            bold=True,
        )
        typer.echo(f"  Reason: {safe_terminal_text(proposal.reason)}")
        typer.secho(
            "  This is a proposal, not part of the current Memory history.",
            dim=True,
        )

    inference = report.inference
    if inference is not None:
        typer.secho(
            "\nEVIDENCE USED FOR INFERENCE WITHIN THE CURRENT CONTEXT RANGE",
            bold=True,
        )
        typer.secho(
            "  These Memories support an ordinary reading; they are not "
            "historical provenance.",
            dim=True,
        )
        if not inference.evidence:
            typer.echo("  (the inference cited no supporting Memory)")
        for evidence in inference.evidence:
            _render_memory(evidence, verbose=verbose)

        typer.secho(
            "\nBEST-EFFORT EXPLANATION — INFERRED WITHIN CONTEXT, not recorded "
            f"· {scope_reach}",
            bold=True,
        )
        if report.inference_cached:
            typer.secho(
                "  Reused cached inference for unchanged input; this is still "
                "not recorded provenance.",
                dim=True,
            )
        typer.echo(
            "  Best-supported reading: "
            + safe_terminal_text(inference.best_supported_reading)
        )
        typer.echo(
            "  Contextual flow: " + safe_terminal_text(inference.contextual_flow)
        )
        typer.secho("\nUNRESOLVED", bold=True)
        if not inference.unresolved:
            typer.echo("  (none reported by the contextual inference)")
        for unresolved in inference.unresolved:
            typer.echo(f"  - {safe_terminal_text(unresolved)}")
    else:
        typer.secho(
            f"\nCURRENT CONTEXT WINDOW — {scope_reach}, "
            "deterministic fallback only",
            bold=True,
        )
        typer.secho(
            "  No semantic relationship is asserted by this list.",
            dim=True,
        )
        if not report.fallback_evidence:
            typer.echo("  (no other direct Memories)")
        for evidence in report.fallback_evidence:
            _render_memory(evidence, verbose=verbose)
        typer.secho("\nUNRESOLVED / UNRECORDED", bold=True)
        typer.echo(
            "  The author's intended meaning cannot be recovered from provenance alone."
        )
        if report.inference_error:
            typer.secho(
                "  Context inference unavailable: "
                + safe_terminal_text(report.inference_error),
                fg=typer.colors.YELLOW,
            )

    combined_warnings = tuple(dict.fromkeys((*report.trace.warnings, *report.warnings)))
    if combined_warnings:
        typer.secho("\nLIMITS", bold=True)
        for warning in combined_warnings:
            typer.secho(
                f"  - {safe_terminal_text(warning)}",
                fg=typer.colors.YELLOW,
            )


def rationale_report_text(
    report: RationaleReport,
    *,
    verbose: bool = False,
) -> str:
    """Render once into neutral text for the common read-only Viewer."""
    output = StringIO()
    with redirect_stdout(output):
        render_rationale(report, verbose=verbose)
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
            help="Context to explain (defaults to current)",
        ),
    ] = None,
    recorded_only: Annotated[
        bool,
        typer.Option(
            "--recorded-only",
            help="Skip contextual inference and its cache",
        ),
    ] = False,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Ignore and replace a cached contextual inference",
        ),
    ] = False,
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
        typer.Option("--json", help="Emit structured rationale evidence as JSON"),
    ] = False,
) -> None:
    """Separate recorded origin from inference within the current Context."""
    store = MemoryStore(create=False)
    try:
        include_descendants = True
        if recorded_only and refresh:
            raise RationaleError("--refresh cannot be combined with --recorded-only.")
        context_snapshot = ContextOperandSnapshot.capture(store)
        if selector is None and as_json:
            raise RationaleError("JSON output requires an explicit Memory UID.")
        if selector is None and interactive_report_terminal():
            launch = choose_memory_report_recent(store, operation="rationale")
            if launch is None:
                typer.echo("Rationale cancelled.")
                return
            if isinstance(launch, MemoryReportRecentSelection):
                context_name = launch.context_name
                selector = launch.memory_uid
                include_descendants = launch.include_descendants
            elif not isinstance(launch, MemoryReportSelectAction):
                raise RationaleError("Rationale launcher returned an invalid action.")
        name = context_snapshot.resolve_or_current(context_name)
        if not name:
            raise RationaleError(
                "No current context. Pass --context or run 'mem init <name>' first."
            )
        if selector is None:
            picker_scope = load_rationale_scope(
                store,
                context_name,
                current_name=context_snapshot.current_name,
                # Freeze every eligible row before the shared RANGE control
                # narrows or broadens what can actually be selected.
                include_descendants=True,
            )
            candidates, owners = rationale_candidates(picker_scope)
            selected = choose_memory_report_target(
                tuple(
                    ScopedMemoryPickerItem(
                        context_name=owners[candidate.uid][0].name,
                        uid=candidate.uid,
                        content=candidate.content,
                        status=candidate.status,
                        catalog_context_names=tuple(
                            context.name for context in picker_scope.contexts
                        ),
                        change_count=candidate.change_count,
                    )
                    for candidate in candidates
                ),
                context_name=picker_scope.root_name,
                operation="rationale",
                initial_include_descendants=False,
            )
            if selected is None:
                typer.echo("Rationale cancelled.")
                return
            selector = selected.memory_uid
            include_descendants = selected.include_descendants
            # Do not connect the inference provider until an exact Memory has
            # been chosen. Re-read live state after the full-screen picker.
        scope = load_rationale_scope(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            include_descendants=include_descendants,
        )
        target = resolve_rationale_target(scope, selector)
        if target.access.is_granted and recorded_only:
            raise RationaleError(
                "--recorded-only is unavailable for a granted READ view because "
                "authority history is not granted."
            )
        if not recorded_only:
            authorize_rationale_inference(scope)
        trace = rationale_trace(scope, target)
        if recorded_only:
            report = build_rationale(
                target.access.store,
                target.owner,
                trace,
                None,
                cache_inference=False,
                refresh_inference=refresh,
                inference_contexts=scope.contexts,
                inference_scope_name=scope.root_name,
                inference_scope_include_descendants=include_descendants,
                recorded_evidence_available=not target.access.is_granted,
            )
        else:
            with progressing_provider_factory(
                "RATIONALE",
                "inferring rationale",
                connect_codex_chatgpt_provider,
            ) as provider_factory:
                report = build_rationale(
                    target.access.store,
                    target.owner,
                    trace,
                    provider_factory,
                    cache_inference=not target.access.is_granted,
                    refresh_inference=refresh,
                    inference_contexts=scope.contexts,
                    inference_scope_name=scope.root_name,
                    inference_scope_include_descendants=include_descendants,
                    recorded_evidence_available=not target.access.is_granted,
                )
        annotate_memory_report_attempt(
            operation="rationale",
            context_name=scope.root_name,
            memory_uid=report.trace.selected_uid,
            include_descendants=include_descendants,
        )
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        ValueError,
        ProvenanceError,
        RationaleError,
        ProfileConfigError,
        ProfileError,
        PermissionError,
    ) as error:
        typer.secho(
            f"Rationale error: {display_escape_text(str(error))}",
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
    if interactive_report_terminal():
        run_read_only_viewer(
            rationale_report_text(report, verbose=verbose),
            title="RATIONALE REPORT",
        )
        return
    render_rationale(report, verbose=verbose)
