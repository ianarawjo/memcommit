"""Explain one Memory using provenance, saved analysis, and local context."""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
import textwrap
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
from memcommit.provenance import ProvenanceError
from memcommit.query_provider import connect_codex_chatgpt_provider
from memcommit.rationale import (
    RationaleError,
    RationaleReport,
    build_rationale,
)
from memcommit.rationale_scope import (
    authorize_rationale_inference,
    freeze_rationale_profile_catalog,
    load_rationale_scope,
    rationale_candidates,
    rationale_scope_from_catalog,
    rationale_trace,
    resolve_rationale_target,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.store import MemoryStore


def _uid(value: str, verbose: bool) -> str:
    return value if verbose else value[:8]


def _bounded_summary(value: str, character_limit: int) -> str:
    if character_limit <= 0:
        return ""
    if len(value) <= character_limit:
        return value
    if character_limit == 1:
        return "…"
    prefix = value[: character_limit - 1].rstrip()
    boundary = prefix.rfind(" ")
    if boundary >= character_limit // 2:
        prefix = prefix[:boundary].rstrip()
    return prefix + "…"


def _provenance_summary(report: RationaleReport) -> str:
    reasons = tuple(
        dict.fromkeys(
            event.reason.strip()
            for event in report.recorded_reason_events
            if event.reason and event.reason.strip()
        )
    )
    return _bounded_summary(
        " / ".join(reasons),
        report.provenance_character_limit,
    )


def render_rationale(
    report: RationaleReport,
    *,
    verbose: bool = False,
) -> None:
    typer.secho(
        f"Rationale [{_uid(report.trace.selected_uid, verbose)}] · "
        f"{display_escape_text(report.trace.context_name)}",
        bold=True,
    )
    if verbose:
        typer.secho(f"Context UID: {report.trace.context_uid}", dim=True)
    typer.secho("\nMEMORY", bold=True)
    for line in safe_terminal_text(report.target.content).splitlines() or [""]:
        typer.echo(f"  {line}")

    if not report.recorded_evidence_available:
        typer.secho("\nPROVENANCE — hidden by Grant", bold=True)
    elif not report.recorded_reason_events:
        typer.secho("\nPROVENANCE — no reason recorded", bold=True)
    else:
        typer.secho("\nPROVENANCE — recorded reason", bold=True)
        provenance = safe_terminal_text(_provenance_summary(report))
        typer.echo(
            "  "
            + _bounded_summary(
                provenance,
                report.provenance_character_limit,
            )
        )

    inference = report.inference
    if inference is not None:
        cache_label = " · cached" if report.inference_cached else ""
        typer.secho(
            "\nAPPARENT PURPOSE — inferred from Context, not recorded"
            + cache_label,
            bold=True,
        )
        typer.echo(
            "  "
            + _bounded_summary(
                safe_terminal_text(inference.explanation),
                report.inference_character_limit,
            )
        )
    elif report.inference_status == "NOT_REQUESTED":
        typer.secho("\nAPPARENT PURPOSE — not requested", bold=True)
    elif report.inference_status == "INSUFFICIENT_EVIDENCE":
        typer.secho("\nAPPARENT PURPOSE — insufficient Context", bold=True)
    else:
        typer.secho(
            "\nAPPARENT PURPOSE — unavailable",
            bold=True,
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
    # The shared Viewer hard-wraps at the canvas edge. Keep this compact
    # prose projection narrower so wrapping occurs between words and remains
    # legible in both the standard 180-column study viewport and smaller TUIs.
    lines: list[str] = []
    for line in output.getvalue().rstrip("\n").splitlines():
        indentation = line[: len(line) - len(line.lstrip())]
        content = line[len(indentation) :]
        lines.extend(
            textwrap.wrap(
                content,
                width=140,
                initial_indent=indentation,
                subsequent_indent=indentation,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    return "\n".join(lines)


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "UID (or unambiguous prefix) of a current or historical "
                "direct Memory; omit in a terminal to select from the current "
                "readable Context or its descendants"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help=(
                "Start Memory selection in this readable Context instead of "
                "the current Context"
            ),
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
        explicit_context = context_name is not None
        if selector is None and not explicit_context and interactive_report_terminal():
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
        selected_from_profile = False
        if selector is None:
            profile_catalog = (
                None
                if explicit_context
                else freeze_rationale_profile_catalog(
                    store,
                    None,
                    current_name=context_snapshot.current_name,
                )
            )
            # A bare report starts where the person already is. The Profile
            # catalog supplies authorized lexical descendants without turning
            # unrelated readable Contexts into an extra location-picking step.
            if profile_catalog is not None:
                picker_scope = rationale_scope_from_catalog(
                    profile_catalog,
                    name,
                    include_descendants=True,
                )
            else:
                picker_scope = load_rationale_scope(
                    store,
                    name,
                    current_name=context_snapshot.current_name,
                    # Freeze every eligible row before the shared RANGE
                    # control narrows or broadens selectable Memories.
                    include_descendants=True,
                )
            candidates, owners = rationale_candidates(picker_scope)
            scope_names = tuple(context.name for context in picker_scope.contexts)
            selected = choose_memory_report_target(
                tuple(
                    ScopedMemoryPickerItem(
                        context_name=owners[candidate.uid][0].name,
                        uid=candidate.uid,
                        content=candidate.content,
                        status=candidate.status,
                        catalog_context_names=scope_names,
                        change_count=candidate.change_count,
                    )
                    for candidate in candidates
                ),
                context_name=picker_scope.root_name,
                operation="rationale",
                catalog_context_names=scope_names,
                initial_include_descendants=False,
            )
            if selected is None:
                typer.echo("Rationale cancelled.")
                return
            context_name = selected.root_context_name
            selector = selected.memory_uid
            include_descendants = selected.include_descendants
            selected_from_profile = profile_catalog is not None
            # Do not connect the inference provider until an exact Memory has
            # been chosen. Re-read live state after the full-screen picker.
        if selected_from_profile:
            # Revalidate through the same Profile-wide namespace used by the
            # picker.  Re-anchoring a granted target to its grant-only catalog
            # here could silently drop local or separately granted lexical
            # contributors that were visible in the reviewed range.
            refreshed_profile_catalog = freeze_rationale_profile_catalog(
                store,
                context_name,
                current_name=context_snapshot.current_name,
            )
            scope = rationale_scope_from_catalog(
                refreshed_profile_catalog,
                context_name,
                include_descendants=include_descendants,
            )
        else:
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
