"""Show one Memory with grounded natural-language provenance."""

from __future__ import annotations

import json

from typing import Annotated, Optional

import typer

from memcommit.persistence.command_ledger.attempts import annotate_command_outcome
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.history_target import (
    resolve_explicit_context_history_target,
)
from memcommit.adapters.console.terminal.components.memory_report_picker import (
    ScopedMemoryPickerItem,
    choose_history_report_target,
)
from memcommit.adapters.console.terminal.components.progress import (
    progressing_provider_factory,
)
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.capabilities.history.query.context_history_slicing import (
    ContextHistorySlice,
)
from memcommit.application.capabilities.history.verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.capabilities.memory_report_targeting import (
    ReadableMemoryTargetNotFoundError,
    freeze_memory_report_readable_catalog,
    parse_memory_report_locator,
    resolve_local_memory_report_target,
    resolve_readable_memory_target,
)
from memcommit.application.context_access.access import resolve_context_access
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
    try_resolve_existing_context_access,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.rationale.application import build_rationale
from memcommit.application.operations.rationale.narrative_length_validation import (
    validate_rationale_limit,
)
from memcommit.application.operations.rationale.model import (
    DEFAULT_RATIONALE_PROVENANCE_LIMIT,
    MAX_RATIONALE_PROVENANCE_LIMIT,
    RationaleError,
    RationaleLimitUnit,
    RationaleNarrativeStatus,
    RationaleReport,
    RationaleRulesError,
    RationaleSynthesisError,
)
from memcommit.application.operations.rationale.runtime import (
    load_context_rationale_history,
)
from memcommit.application.operations.rationale.scope import (
    freeze_rationale_profile_catalog,
    load_rationale_scope,
    rationale_candidates,
    rationale_memory_history,
    rationale_scope_from_catalog,
    resolve_rationale_target,
)
from memcommit.application.operations.rationale.skills.context_rationale.execution import (
    generate_context_rationale,
)
from memcommit.application.operations.rationale.skills.memory_rationale.execution import (
    generate_memory_rationale,
)
from memcommit.application.operations.rationale.skills.memory_rationale.response import (
    RationaleNarrativeProjection,
)

from memcommit.persistence.store import ProfileStore
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.connection import connect_semantic_provider


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
        typer.secho("\nPROVENANCE — unavailable", bold=True)
    elif projection.status is RationaleNarrativeStatus.EMPTY:
        typer.secho("\nPROVENANCE — no retained history", bold=True)
    else:
        typer.secho("\nPROVENANCE", bold=True)
        typer.echo("  " + safe_terminal_text(projection.text))
    if not report.trace.current_matches_last_checkpoint:
        typer.secho("\nATTENTION", bold=True)
        for warning in report.trace.warnings:
            typer.echo(f"  {display_escape_text(warning)}")


def render_context_rationale(
    report: ContextHistorySlice,
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
        typer.secho("\nRATIONALE — unavailable", bold=True)
    elif projection.status is RationaleNarrativeStatus.EMPTY:
        typer.secho("\nRATIONALE — no retained history", bold=True)
    else:
        typer.secho("\nRATIONALE", bold=True)
        typer.echo("  " + safe_terminal_text(projection.text))


def _execute_context_rationale(
    store: ProfileStore,
    *,
    context_name: str,
    current_context_name: str | None,
    as_json: bool,
    verbose: bool,
    limit: int,
    unit: RationaleLimitUnit,
) -> None:
    """Run and present one exact Context rationale through its existing path."""

    context_report, history_available = load_context_rationale_history(
        store,
        context_name,
        current_context_name=current_context_name,
    )
    with progressing_provider_factory(
        "RATIONALE",
        "writing Context rationale",
        connect_semantic_provider,
    ) as provider_factory:
        context_projection = generate_context_rationale(
            context_report,
            provider_factory=provider_factory,
            history_available=history_available,
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
        return
    render_context_rationale(
        context_report,
        context_projection,
        verbose=verbose,
    )


def cmd(
    selector: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "browse the current readable subtree for one exact Context or "
                "Memory when omitted; otherwise accepts CONTEXT, "
                "Memory UID/prefix, or CONTEXT:UID"
            )
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Explain this exact Context; cannot be combined with SELECTOR",
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
    store = ProfileStore(create=False)
    try:
        include_descendants = False
        context_snapshot = ContextOperandSnapshot.capture(store)
        if selector is not None and context_name is not None:
            raise RationaleError(
                "--context selects a Context and cannot be combined with SELECTOR; "
                "use CONTEXT:UID for an exact Memory."
            )
        if selector is None and context_name is None and as_json:
            raise RationaleError(
                "JSON output requires an explicit Context or Memory target."
            )
        if context_name is not None:
            context_name = resolve_existing_context_access(
                store,
                context_name,
                current_name=context_snapshot.current_name,
            ).name
            _execute_context_rationale(
                store,
                context_name=context_name,
                current_context_name=context_snapshot.current_name,
                as_json=as_json,
                verbose=verbose,
                limit=limit,
                unit=unit,
            )
            return
        if selector is not None:
            context_identity = try_resolve_existing_context_access(
                store,
                selector,
                current_name=context_snapshot.current_name,
            )
            explicit_target = (
                context_identity.name
                if context_identity is not None
                else resolve_explicit_context_history_target(
                    selector,
                    current_context=context_snapshot.current_name,
                    available_context_names=store.list_context_names(),
                )
            )
            if isinstance(explicit_target, str):
                _execute_context_rationale(
                    store,
                    context_name=explicit_target,
                    current_context_name=context_snapshot.current_name,
                    as_json=as_json,
                    verbose=verbose,
                    limit=limit,
                    unit=unit,
                )
                return
        selected_from_profile = False
        if selector is None:
            name = context_snapshot.current_name
            if not name:
                raise RationaleError(
                    "No current context. Pass --context or run 'mem init <name>' first."
                )
            profile_catalog = freeze_rationale_profile_catalog(
                store,
                None,
                current_name=context_snapshot.current_name,
            )
            # The Switch-style browser starts at the current public name and
            # freezes its readable lexical subtree. Its final receipt remains
            # one exact Context or exact owner/Memory coordinate.
            picker_scope = rationale_scope_from_catalog(
                profile_catalog,
                name,
                include_descendants=True,
            )
            candidates, owners = rationale_candidates(picker_scope)
            scope_names = tuple(context.name for context in picker_scope.contexts)
            selected = choose_history_report_target(
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
            )
            if selected is None:
                annotate_command_outcome("CANCELLED")
                typer.echo("Rationale cancelled.")
                return
            if isinstance(selected, str):
                _execute_context_rationale(
                    store,
                    context_name=selected,
                    current_context_name=context_snapshot.current_name,
                    as_json=False,
                    verbose=verbose,
                    limit=limit,
                    unit=unit,
                )
                return
            if not isinstance(selected, tuple):
                raise RationaleError("Rationale browser returned an invalid target.")
            context_name = selected[0]
            selector = selected[1]
            selected_from_profile = True
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
            )
            try:
                resolved_target = resolve_local_memory_report_target(
                    store,
                    item_selector,
                    current=context_snapshot.current_name,
                    context_locator=access.context_name,
                )
            except ValueError as error:
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
                resolved_target = resolve_local_memory_report_target(
                    store,
                    readable_target.uid,
                    current=context_snapshot.current_name,
                    context_locator=readable_target.context_name,
                )
            else:
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

        if selected_from_profile:
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
        report = build_rationale(
            target.access.store,
            target.owner,
            trace,
            None,
            recorded_evidence_available=True,
        )
        with progressing_provider_factory(
            "RATIONALE",
            "writing rationale",
            connect_semantic_provider,
        ) as provider_factory:
            projection = generate_memory_rationale(
                report.trace,
                provider_factory=provider_factory,
                history_available=report.recorded_evidence_available,
                limit=limit,
                unit=unit,
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
    )
