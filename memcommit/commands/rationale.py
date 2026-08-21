"""Show one Memory with grounded natural-language provenance."""

from __future__ import annotations

import json
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
)
from memcommit.interfaces.console.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.provenance import ProvenanceError
from memcommit.rationale import (
    RationaleError,
    RationaleReport,
    build_rationale,
)
from memcommit.rationale_rules import (
    DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    MAX_RATIONALE_PROVENANCE_LIMIT,
    RationaleLimitUnit,
    RationaleNarrativeStatus,
    RationaleRulesError,
    validate_rationale_limit,
)
from memcommit.rationale_semantic import (
    RationaleNarrativeProjection,
    RationaleSynthesisError,
    synthesize_rationale_provenance,
)
from memcommit.rationale_scope import (
    freeze_rationale_profile_catalog,
    load_rationale_scope,
    rationale_candidates,
    rationale_scope_from_catalog,
    rationale_trace,
    resolve_rationale_target,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore


def _uid(value: str, verbose: bool) -> str:
    return value if verbose else value[:8]


def render_rationale(
    report: RationaleReport,
    projection: RationaleNarrativeProjection,
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

    if projection.status is RationaleNarrativeStatus.HIDDEN:
        typer.secho("\nPROVENANCE — hidden by Grant", bold=True)
    elif projection.status is RationaleNarrativeStatus.EMPTY:
        typer.secho("\nPROVENANCE — no retained history", bold=True)
    else:
        typer.secho("\nPROVENANCE", bold=True)
        typer.echo("  " + safe_terminal_text(projection.text))


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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show complete Context, Memory, and checkpoint UIDs",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help=(
                "Maximum complete natural-language provenance length "
                f"(1-{MAX_RATIONALE_PROVENANCE_LIMIT})"
            ),
        ),
    ] = DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    unit: Annotated[
        RationaleLimitUnit,
        typer.Option(
            "--unit",
            "-u",
            help=(
                "Measure --limit in Unicode characters, UTF-8 bytes, or "
                "whitespace-delimited words"
            ),
        ),
    ] = RationaleLimitUnit.WORDS,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit structured rationale evidence as JSON"),
    ] = False,
) -> None:
    """Explain where one Memory came from and how it changed over time."""
    try:
        unit = validate_rationale_limit(limit, unit)
    except RationaleRulesError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    store = MemoryStore(create=False)
    try:
        include_descendants = True
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
            # Re-read live state after the full-screen picker so the report is
            # tied to the exact Memory the person selected.
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
        trace = rationale_trace(scope, target)
        report = build_rationale(
            target.access.store,
            target.owner,
            trace,
            None,
            recorded_evidence_available=not target.access.is_granted,
        )
        with progressing_provider_factory(
            "RATIONALE",
            "synthesizing complete provenance",
            connect_semantic_provider,
        ) as provider_factory:
            projection = synthesize_rationale_provenance(
                report.trace,
                provider_factory=provider_factory,
                history_available=report.recorded_evidence_available,
                limit=limit,
                unit=unit,
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
        RationaleRulesError,
        RationaleSynthesisError,
        QueryProviderError,
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
        payload = report.to_dict()
        payload["provenance_projection"] = projection.to_dict()
        typer.echo(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    # Selection is the only full-screen phase. The compact narrative is the
    # result itself, so it returns as a receipt instead of opening a Viewer.
    render_rationale(report, projection, verbose=verbose)
