"""Show one Memory with grounded natural-language provenance."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Annotated, Optional

import typer

from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.persistence.command_ledger.attempts import annotate_memory_report_attempt
from memcommit.adapters.console.terminal.components.progress import progressing_provider_factory
from memcommit.adapters.console.coordination.context_operand import ContextOperandSnapshot
from memcommit.adapters.console.terminal.components.memory_report_picker import (
    ScopedMemoryPickerItem,
    choose_memory_report_target,
)
from memcommit.adapters.console.coordination.memory_report_recents import (
    MemoryReportRecentSelection,
    MemoryReportSelectAction,
    choose_memory_report_recent,
)
from memcommit.adapters.console.coordination.history_target import resolve_explicit_context_history_target
from memcommit.adapters.console.terminal.components.read_only_viewer import (
    interactive_report_terminal,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.capabilities.retained_history.granted_provenance import (
    GrantedMemoryTraceReport,
    build_granted_memory_trace,
)
from memcommit.application.capabilities.retained_history.context_history import (
    ContextTraceReport,
    build_context_trace,
    current_context_trace,
)
from memcommit.application.operations.rationale.context import synthesize_context_rationale
from memcommit.core.context_targeting.model import ContextTarget
from memcommit.application.capabilities.memory_report_targeting import (
    ReadableMemoryTargetNotFoundError,
    freeze_memory_report_readable_catalog,
    parse_memory_report_locator,
    resolve_local_memory_report_target,
    resolve_readable_memory_target,
)
from memcommit.application.capabilities.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.operations.reference.provenance import (
    MemoryReferenceTraceReport,
    build_reference_trace,
)
from memcommit.application.operations.rationale.model import (
    RationaleError,
    RationaleReport,
    build_rationale,
)
from memcommit.application.operations.rationale.rules import (
    DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    MAX_RATIONALE_PROVENANCE_LIMIT,
    RationaleLimitUnit,
    RationaleNarrativeStatus,
    RationaleRulesError,
    validate_rationale_limit,
)
from memcommit.application.operations.rationale.semantic import (
    RationaleNarrativeProjection,
    RationaleSynthesisError,
    synthesize_rationale_provenance,
)
from memcommit.application.operations.rationale.scope import (
    freeze_rationale_profile_catalog,
    load_rationale_scope,
    rationale_candidates,
    rationale_scope_from_catalog,
    rationale_memory_history,
    resolve_rationale_target,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import QueryProviderError, connect_semantic_provider
from memcommit.persistence.store import MemoryStore


def _uid(value: str, verbose: bool) -> str:
    return value if verbose else value[:8]


def render_rationale(
    report: RationaleReport,
    projection: RationaleNarrativeProjection,
    *,
    verbose: bool = False,
    granted_trace: GrantedMemoryTraceReport | None = None,
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

    if granted_trace is not None:
        typer.secho("\nACCESS ROUTE", bold=True)
        typer.echo(
            f"  GRANT {_uid(granted_trace.grant_uid, verbose)} · "
            f"REVISION {granted_trace.grant_revision} · "
            + " + ".join(granted_trace.permissions)
        )
        if verbose:
            typer.echo(
                f"  RESOURCE · {display_escape_text(granted_trace.resource_name)} "
                f"[{granted_trace.resource_uid}]"
            )

    if projection.status is RationaleNarrativeStatus.HIDDEN:
        typer.secho("\nPROVENANCE — hidden by Grant", bold=True)
    elif projection.status is RationaleNarrativeStatus.EMPTY:
        typer.secho("\nPROVENANCE — no retained history", bold=True)
    else:
        typer.secho("\nPROVENANCE", bold=True)
        typer.echo("  " + safe_terminal_text(projection.text))
    if any(
        event.kind == "HISTORY_GAP" or event.evidence == "UNRECORDED"
        for event in report.trace.events
    ):
        typer.secho("\nATTENTION", bold=True)
        for warning in report.trace.warnings:
            typer.echo(f"  {display_escape_text(warning)}")


def render_reference_rationale(
    reference_trace: MemoryReferenceTraceReport,
    target_report: RationaleReport | None,
    target_projection: RationaleNarrativeProjection | None,
    *,
    verbose: bool = False,
) -> None:
    """Explain a pointer relation and, independently, its target provenance."""

    reference = reference_trace.reference
    typer.secho(
        f"Rationale [{_uid(reference.uid, verbose)}] · "
        f"{display_escape_text(reference_trace.context_name)}",
        bold=True,
    )
    typer.secho("\nREFERENCE", bold=True)
    relationship = "LIVE EMBED" if reference.mode == "LIVE" else "IMMUTABLE SNAPSHOT"
    typer.echo(
        f"  {relationship} → {display_escape_text(reference.target_context_name)}:"
        f"{_uid(reference.target_memory_uid, verbose)}"
    )

    typer.secho("\nRELATION PROVENANCE", bold=True)
    material_events = tuple(
        event for event in reference_trace.events if event.kind != "HISTORY_GAP"
    )
    if material_events:
        first = material_events[0]
        detail = first.description.strip()
        if detail:
            typer.echo(f"  {safe_terminal_text(detail)}")
        else:
            typer.echo(
                f"  The reference first appears in retained {first.command} evidence."
            )
    else:
        typer.echo("  No retained occurrence change explains this reference.")
    if reference.mode == "LIVE":
        typer.echo(
            "  The pointer and target keep separate identities; Source changes "
            "may change the resolved content without changing this pointer."
        )
    else:
        typer.echo(
            "  This snapshot keeps the reviewed content; later Source changes "
            "do not rewrite it."
        )

    typer.secho("\nTARGET MEMORY", bold=True)
    if target_report is not None:
        for line in safe_terminal_text(target_report.target.content).splitlines() or [
            ""
        ]:
            typer.echo(f"  {line}")
    else:
        for line in safe_terminal_text(
            reference.snapshot_content or ""
        ).splitlines() or [""]:
            typer.echo(f"  {line}")

    if target_projection is not None:
        if target_projection.status is RationaleNarrativeStatus.EMPTY:
            typer.secho("\nTARGET PROVENANCE — no retained history", bold=True)
        elif target_projection.status is RationaleNarrativeStatus.HIDDEN:
            typer.secho("\nTARGET PROVENANCE — hidden", bold=True)
        else:
            typer.secho("\nTARGET PROVENANCE", bold=True)
            typer.echo("  " + safe_terminal_text(target_projection.text))
    elif reference.mode == "SNAPSHOT":
        typer.secho("\nTARGET PROVENANCE — snapshot fixed at reference time", bold=True)
    else:
        typer.secho("\nTARGET PROVENANCE — unavailable", bold=True)
    if reference_trace.warnings:
        typer.secho("\nATTENTION", bold=True)
        for warning in reference_trace.warnings:
            typer.echo(f"  {display_escape_text(warning)}")


def render_context_rationale(
    report: ContextTraceReport,
    projection: RationaleNarrativeProjection,
    *,
    verbose: bool = False,
) -> None:
    """Render the semantic explanation of one whole Context timeline."""

    typer.secho(
        f"Rationale · {display_escape_text(report.context_name)}",
        bold=True,
    )
    if verbose:
        typer.secho(f"Context UID: {report.context_uid}", dim=True)
    typer.secho("\nCONTEXT", bold=True)
    typer.echo(
        f"  {len(report.current)} direct Memor"
        f"{'y' if len(report.current) == 1 else 'ies'}"
        f" · {len(report.events)} retained operation"
        f"{'s' if len(report.events) != 1 else ''}"
    )
    if projection.status is RationaleNarrativeStatus.HIDDEN:
        typer.secho("\nRATIONALE — hidden by Grant", bold=True)
    elif projection.status is RationaleNarrativeStatus.EMPTY:
        typer.secho("\nRATIONALE — no retained history", bold=True)
    else:
        typer.secho("\nRATIONALE", bold=True)
        typer.echo("  " + safe_terminal_text(projection.text))


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "select from the current readable Context or descendants when "
                "omitted; otherwise accepts CONTEXT, Memory/MemoryRef UID/prefix, "
                "or CONTEXT:UID"
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
            help="Show full Context, Memory, and checkpoint UIDs",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help=(
                "Maximum natural-language provenance length "
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
    """Explain how one Context or Memory evolved over time."""
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
            raise RationaleError("JSON output requires an explicit item UID.")
        explicit_context = context_name is not None
        if selector is not None and not explicit_context:
            explicit_target = resolve_explicit_context_history_target(
                selector,
                current_context=context_snapshot.current_name,
                available_context_names=store.list_context_names(),
            )
            if isinstance(explicit_target, ContextTarget):
                access = resolve_context_access(
                    store,
                    explicit_target.context_name,
                    current_name=context_snapshot.current_name,
                    required_permission="READ",
                )
                context_report = (
                    current_context_trace(
                        access.store.load_direct(access.context_name),
                        warnings=(
                            "Authority history is outside this granted READ view.",
                        ),
                    )
                    if access.is_granted
                    else build_context_trace(access.store, access.context_name)
                )
                with progressing_provider_factory(
                    "RATIONALE",
                    "writing Context rationale",
                    connect_semantic_provider,
                ) as provider_factory:
                    context_projection = synthesize_context_rationale(
                        context_report,
                        provider_factory=provider_factory,
                        history_available=not access.is_granted,
                        limit=limit,
                        unit=unit,
                    )
                if as_json:
                    typer.echo(
                        json.dumps(
                            {
                                "target": "CONTEXT",
                                "trace": context_report.to_dict(),
                                "rationale_projection": context_projection.to_dict(),
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    render_context_rationale(
                        context_report,
                        context_projection,
                        verbose=verbose,
                    )
                return
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
        selected_from_profile = False
        if selector is None:
            name = context_snapshot.resolve_or_current(context_name)
            if not name:
                raise RationaleError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
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

        assert selector is not None
        qualified_selector = ":" in selector
        owner_locator, item_selector = parse_memory_report_locator(
            selector,
            explicit_context=context_name,
        )
        resolved_target = None
        if owner_locator is not None:
            access = resolve_context_access(
                store,
                owner_locator,
                current_name=context_snapshot.current_name,
                required_permission="READ",
            )
            if access.is_granted:
                context_name = access.display_name
                selector = item_selector
                if qualified_selector:
                    include_descendants = False
            else:
                try:
                    resolved_target = resolve_local_memory_report_target(
                        store,
                        item_selector,
                        current=context_snapshot.current_name,
                        context_locator=access.context_name,
                    )
                except ValueError as error:
                    # ``--context ROOT`` historically searches readable
                    # descendants. A qualified ``ROOT:UID`` is an exact owner
                    # coordinate and must not silently broaden after a miss.
                    if qualified_selector or "No reportable" not in str(error):
                        raise
                    context_name = owner_locator
                    selector = item_selector
        else:
            try:
                readable_catalog = freeze_memory_report_readable_catalog(
                    store,
                    current=context_snapshot.current_name,
                )
                readable_target = (
                    resolve_readable_memory_target(
                        readable_catalog,
                        item_selector,
                    )
                    if readable_catalog is not None
                    else None
                )
            except ReadableMemoryTargetNotFoundError:
                readable_target = None
            if readable_target is not None:
                if readable_target.access.is_granted:
                    context_name = readable_target.context_name
                    selector = readable_target.uid
                    include_descendants = False
                else:
                    resolved_target = resolve_local_memory_report_target(
                        store,
                        readable_target.uid,
                        current=context_snapshot.current_name,
                        context_locator=readable_target.context_name,
                    )
            else:
                # Current readable Memories are the round-trip namespace for
                # Find/List/Search. Retained local history and MemoryRefs remain
                # addressable when no current row matches that UID.
                resolved_target = resolve_local_memory_report_target(
                    store,
                    item_selector,
                    current=context_snapshot.current_name,
                    context_locator=None,
                )

        if resolved_target is not None:
            context_name = resolved_target.context_name
            selector = resolved_target.uid
            include_descendants = False
            selected_from_profile = False
            if resolved_target.kind == "MEMORY_REFERENCE":
                reference_trace = build_reference_trace(
                    store,
                    store.load_direct(resolved_target.context_name),
                    resolved_target.uid,
                )
                target_report: RationaleReport | None = None
                target_projection: RationaleNarrativeProjection | None = None
                if reference_trace.target_trace is not None:
                    target_context = store.load_direct(
                        reference_trace.target_trace.context_name
                    )
                    target_report = build_rationale(
                        store,
                        target_context,
                        reference_trace.target_trace,
                        None,
                    )
                    try:
                        with progressing_provider_factory(
                            "RATIONALE",
                            "writing target provenance",
                            connect_semantic_provider,
                        ) as provider_factory:
                            target_projection = synthesize_rationale_provenance(
                                target_report.trace,
                                provider_factory=provider_factory,
                                history_available=True,
                                limit=limit,
                                unit=unit,
                            )
                    except (
                        QueryProviderError,
                        ProfileConfigError,
                        ProfileError,
                        RuntimeError,
                    ) as error:
                        # The retained pointer relation remains useful even
                        # when its optional natural-language target projection
                        # cannot connect. Never discard deterministic evidence.
                        reference_trace = replace(
                            reference_trace,
                            warnings=(
                                *reference_trace.warnings,
                                f"Target provenance narrative is unavailable: {error}",
                            ),
                        )
                if as_json:
                    target_payload = None
                    if target_report is not None:
                        target_payload = target_report.to_dict()
                        target_payload["provenance_projection"] = (
                            target_projection.to_dict()
                            if target_projection is not None
                            else None
                        )
                    typer.echo(
                        json.dumps(
                            {
                                "kind": "memory_reference_rationale",
                                "trace": reference_trace.to_dict(),
                                "target_rationale": target_payload,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                    return
                render_reference_rationale(
                    reference_trace,
                    target_report,
                    target_projection,
                    verbose=verbose,
                )
                return

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
        trace = rationale_memory_history(scope, target)
        granted_trace = (
            build_granted_memory_trace(
                target.access,
                target.candidate.uid,
                context=target.owner,
                display_name=target.owner.name,
            )
            if target.access.is_granted
            else None
        )
        report = build_rationale(
            target.access.store,
            target.owner,
            trace,
            None,
            recorded_evidence_available=not target.access.is_granted,
        )
        with progressing_provider_factory(
            "RATIONALE",
            "writing rationale",
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
        MemoryHistoryReconstructionError,
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
        if granted_trace is not None:
            payload["access_route"] = granted_trace.to_dict()["access_route"]
            payload["history"] = granted_trace.to_dict()["history"]
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
    render_rationale(
        report,
        projection,
        verbose=verbose,
        granted_trace=granted_trace,
    )
