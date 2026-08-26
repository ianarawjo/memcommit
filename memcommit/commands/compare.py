"""Create or resume one targetless ordered peer-Context comparison."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.operations.compare.ledger.model import (
    ComparisonAnalysis,
    ComparisonError,
    ComparisonInput,
)
from memcommit.operations.compare.summary import (
    ComparisonSummary,
    ComparisonSummaryError,
)
from memcommit.operations.compare.summary_application import run_comparison_summary
from memcommit.interfaces.cli.comparison_summary import render_comparison_summary
from memcommit.operations.compare.summary_provider import COMPARISON_SUMMARY_OPERATION
from memcommit.interfaces.presentation.comparison import (
    render_comparison,
    render_comparison_receipt,
)
from memcommit.operations.compare.ledger.provider import (
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.operations.compare.ledger.store import (
    ConcurrentComparisonUpdateError,
)
from memcommit.commands.comparison_execution import (
    COMPARISON_AGGREGATE_TIMEOUT_SECONDS as SHARED_COMPARISON_TIMEOUT_SECONDS,
    connect_comparison_provider,
    ensure_comparison_analysis,
    load_comparison_context,
)
from memcommit.authority.derived_policy import AnalysisRetention
from memcommit.commands.compare_sessions import (
    choose_comparison_session,
    load_saved_comparison,
    revalidate_saved_comparison,
)
from memcommit.commands.command_wait import run_command_wait
from memcommit.commands.compare_setup import choose_compare_setup
from memcommit.commands.compare_targeting import resolve_compare_cli_targets
from memcommit.commands.rationale import render_rationale
from memcommit.interfaces.tui.components.operation_launcher.session import SessionNewReceipt
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    legacy_root_only_option_alias,
    resolve_descendant_scopes,
    resolve_scope_preset,
)
from memcommit.context_targeting.model import DirectMemoryLocator
from memcommit.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
)
from memcommit.infrastructure.providers.profile_routes import (
    ProfileProviderRoutesError,
)
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.retained_history.provenance import ProvenanceError
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.operations.rationale.model import RationaleError, build_rationale
from memcommit.operations.rationale.semantic import synthesize_rationale_provenance
from memcommit.operations.rationale.scope import (
    load_rationale_scope,
    rationale_trace,
    resolve_rationale_target,
)
from memcommit.store import MemoryStore
from memcommit.semantic_provider import connect_operation_provider
from memcommit.study_prewarm.compare import (
    EquivalentComparePrewarmMatch,
    find_declared_equivalent_compare_analysis,
    installed_compare_prewarm_origin,
    project_declared_compare_analysis,
    record_equivalent_compare_prewarm,
    record_exact_compare_prewarm,
)
from memcommit.study_prewarm.registry import StudyPrewarmRegistryError


# A full Task 1 subtree Compare is one intentionally indivisible relation
# frame. The subscription-backed xhigh run can remain healthy beyond the
# configured ten-minute default, so match Meld's documented aggregate window
# instead of timing out a complete provider turn just before materialization.
COMPARE_AGGREGATE_TIMEOUT_SECONDS = SHARED_COMPARISON_TIMEOUT_SECONDS


class CompareCommandError(RuntimeError):
    """Safe user-facing Compare orchestration failure."""


def _connect_compare_provider(provider_factory):
    return connect_comparison_provider(provider_factory)


def _resume_selected_comparison(
    *,
    store: MemoryStore,
    analysis_uid: str,
    ledger: bool,
    snapshot: bool,
) -> None:
    """Open one exact saved analysis without provider or refresh fallback."""
    analysis = load_saved_comparison(analysis_uid, store=store)
    revalidate_saved_comparison(store, analysis)
    _present_comparison(
        store=store,
        analysis=analysis,
        reused=True,
        origin=installed_compare_prewarm_origin(store, analysis) or "SAVED_REUSE",
        ledger=ledger,
        snapshot=snapshot,
    )


def _start_new_comparison_from_setup(
    *,
    store: MemoryStore,
    refresh: bool,
    ledger: bool,
    snapshot: bool,
) -> None:
    """Collect one new Compare request without browsing saved analyses."""

    setup = choose_compare_setup(store)
    if setup is None:
        typer.echo("Compare setup cancelled; no analysis was opened.")
        return
    start_kwargs = {
        "from_": setup.reference_name,
        "to": setup.compared_name,
        "refresh": refresh,
        "ledger": ledger,
        "snapshot": snapshot,
        "reference_descendants": setup.reference_descendants,
        "compared_descendants": setup.compared_descendants,
    }
    if setup.reference_memory_uid is not None:
        start_kwargs["reference_memory"] = setup.reference_memory_uid
    if setup.compared_memory_uid is not None:
        start_kwargs["compared_memory"] = setup.compared_memory_uid
    # Re-enter only after the process-local setup has frozen explicit operands.
    # This keeps bare and launcher-New creation on the normal command boundary
    # without letting saved-session discovery choose an analysis implicitly.
    cmd(**start_kwargs)


def _start_meld_from_compare(
    *,
    store: MemoryStore,
    analysis: ComparisonAnalysis,
) -> None:
    """Collect one result target, then hand authority back to Meld."""
    from memcommit.commands.meld import (
        MeldCommandError,
        render_meld_session,
        start_reviewed_symmetric_meld,
    )
    from memcommit.commands.meld_target_picker import choose_meld_target

    reference, compared = analysis.frames
    receipt = choose_meld_target(
        store,
        source_names=(reference.context_name, compared.context_name),
    )
    if receipt is None:
        typer.echo("Meld target selection cancelled.")
        return
    try:
        session = start_reviewed_symmetric_meld(
            store=store,
            analysis=analysis,
            target_name=receipt.context_name,
            create_target=receipt.create,
        )
    except (MeldCommandError, OSError, RuntimeError, ValueError) as error:
        raise CompareCommandError(str(error)) from error
    typer.echo(render_meld_session(session))


def _render_selected_rationale(
    *,
    store: MemoryStore,
    context_name: str,
    memory_uid: str,
) -> None:
    """Explain one exact source selected from the immutable Compare ledger."""
    scope = load_rationale_scope(
        store,
        context_name,
        current_name=store.current_context_name(),
    )
    target = resolve_rationale_target(scope, memory_uid)
    trace = rationale_trace(scope, target)
    report = build_rationale(
        scope.access.store,
        target.owner,
        trace,
        None,
        recorded_evidence_available=not scope.granted,
    )
    projection = synthesize_rationale_provenance(
        report.trace,
        provider_factory=connect_codex_chatgpt_provider,
        history_available=report.recorded_evidence_available,
    )
    render_rationale(report, projection)


def _present_comparison(
    *,
    store: MemoryStore,
    analysis: ComparisonAnalysis,
    reused: bool,
    origin: str | None = None,
    ledger: bool,
    snapshot: bool,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
) -> None:
    """Return a compact receipt; full evidence is an explicit Review route."""
    if ledger or snapshot:
        typer.echo(
            render_comparison(
                analysis,
                reused=reused,
                origin=origin,
                ledger=ledger,
                durable=durable,
                retention=retention,
            )
        )
        return
    typer.echo(render_comparison_receipt(analysis, durable=durable))


def _present_comparison_summary(
    summary: ComparisonSummary,
    *,
    snapshot: bool,
) -> None:
    """Return the transient summary without an automatic full-screen viewer."""

    typer.echo(render_comparison_summary(summary))


def _resolve_endpoint_syntax(
    endpoints: list[str] | None,
    *,
    from_: str | None,
    to: str | None,
) -> tuple[str | None, str | None]:
    """Normalize the positional-first endpoint grammar before any store access."""

    positional = tuple(endpoints or ())
    if len(positional) > 2:
        raise CompareCommandError(
            "expected PEER or REFERENCE PEER (at most two positional endpoints)."
        )
    if positional and (from_ is not None or to is not None):
        raise CompareCommandError(
            "positional endpoints cannot be combined with --from or --to."
        )
    if len(positional) == 1:
        # A single operand preserves the established current-as-reference
        # behavior. Two operands are required to override that reference.
        return None, positional[0]
    if len(positional) == 2:
        return positional[0], positional[1]
    return from_, to


def cmd(
    contexts: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[ENDPOINT]...",
            help=(
                "One auto-typed PEER Context/Memory (REFERENCE defaults to "
                "current), or explicit REFERENCE and PEER endpoints"
            ),
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Compatibility alias for an explicit REFERENCE Context locator"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Compatibility alias for the PEER Context locator; REFERENCE "
                "defaults to current when --from is omitted"
            ),
        ),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Run a fresh aggregate analysis even when sources match",
        ),
    ] = False,
    ledger: Annotated[
        bool,
        typer.Option(
            "--ledger",
            help=(
                "Run, save, and show the exhaustive relation ledger used by Meld"
            ),
        ),
    ] = False,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the result instead of opening its read-only TTY viewer",
        ),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Compare session launcher",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Compare only the selected REFERENCE and PEER roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include readable descendants under both comparison roots",
        ),
    ] = False,
    reference_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--reference-descendants/--reference-root-only",
            legacy_root_only_option_alias("reference"),
            help="Include all readable descendants under REFERENCE A",
        ),
    ] = None,
    compared_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--compared-descendants/--compared-root-only",
            legacy_root_only_option_alias("compared"),
            help="Include all readable descendants under PEER B",
        ),
    ] = None,
    reference_memory: Annotated[
        Optional[str],
        typer.Option(
            "--reference-memory",
            metavar="UID/PREFIX",
            help=(
                "Compare one REFERENCE Memory; its neighbors remain "
                "non-actionable context"
            ),
        ),
    ] = None,
    compared_memory: Annotated[
        Optional[str],
        typer.Option(
            "--compared-memory",
            metavar="UID/PREFIX",
            help=(
                "Compare one PEER Memory; its neighbors remain non-actionable context"
            ),
        ),
    ] = None,
) -> None:
    """Summarize two peer Contexts; use --ledger for deep relation analysis."""
    try:
        from_, to = _resolve_endpoint_syntax(
            contexts,
            from_=from_,
            to=to,
        )
        auto_type_positionals = bool(contexts)
        reference_is_auto_memory = bool(
            auto_type_positionals
            and from_ is not None
            and isinstance(
                parse_auto_typed_context_memory_operand(from_),
                DirectMemoryLocator,
            )
        )
        compared_is_auto_memory = bool(
            auto_type_positionals
            and to is not None
            and isinstance(
                parse_auto_typed_context_memory_operand(to),
                DirectMemoryLocator,
            )
        )
        if reference_is_auto_memory and reference_memory is not None:
            raise CompareCommandError(
                "REFERENCE Memory was supplied both positionally and with "
                "--reference-memory."
            )
        if compared_is_auto_memory and compared_memory is not None:
            raise CompareCommandError(
                "PEER Memory was supplied both positionally and with "
                "--compared-memory."
            )
    except CompareCommandError as error:
        typer.secho(
            f"Compare error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    scope_flags_supplied = (
        direct
        or recursive
        or reference_descendants is not None
        or compared_descendants is not None
    )
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        reference_descendants, compared_descendants = resolve_descendant_scopes(
            preset=preset,
            explicit=(reference_descendants, compared_descendants),
        )
    except (TypeError, ValueError) as error:
        typer.secho(
            f"Compare error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if sessions and (
        from_ is not None
        or to is not None
        or scope_flags_supplied
        or reference_memory is not None
        or compared_memory is not None
    ):
        typer.secho(
            "Compare error: use either --sessions or explicit endpoints, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if from_ is not None and to is None:
        typer.secho(
            "Compare error: --from requires --to.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if to is None and (reference_descendants or compared_descendants):
        typer.secho(
            "Compare error: descendant scope flags require an explicit PEER Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if to is None and (
        reference_memory is not None or compared_memory is not None
    ):
        typer.secho(
            "Compare error: Memory scope flags require an explicit PEER Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if (
        reference_memory is not None or reference_is_auto_memory
    ) and reference_descendants:
        typer.secho(
            "Compare error: REFERENCE Memory selection cannot be combined "
            "with --reference-descendants.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if (
        compared_memory is not None or compared_is_auto_memory
    ) and compared_descendants:
        typer.secho(
            "Compare error: PEER Memory selection cannot be combined with "
            "--compared-descendants.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if refresh and to is None:
        typer.secho(
            "Compare error: --refresh requires an explicit PEER Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    try:
        if sessions:
            receipt = choose_comparison_session(store, ledger=ledger)
            if receipt is None:
                typer.echo("Compare selection ended; no analysis was opened.")
                return
            if isinstance(receipt, SessionNewReceipt):
                _start_new_comparison_from_setup(
                    store=store,
                    refresh=refresh,
                    # The session launcher is an explicit saved-analysis
                    # route. New must not fall through to the transient
                    # default and then leave the launcher with no row to open.
                    ledger=True,
                    snapshot=snapshot,
                )
                return
            _resume_selected_comparison(
                store=store,
                analysis_uid=receipt.key,
                ledger=ledger,
                snapshot=snapshot,
            )
            return
        if from_ is None and to is None:
            _start_new_comparison_from_setup(
                store=store,
                refresh=refresh,
                ledger=ledger,
                snapshot=snapshot,
            )
            return
        current_name = store.current_context_name()
        assert to is not None
        with authority_grant_snapshot_lock() as registry:
            targets = resolve_compare_cli_targets(
                store,
                reference_operand=from_,
                compared_operand=to,
                reference_is_auto_memory=reference_is_auto_memory,
                compared_is_auto_memory=compared_is_auto_memory,
                reference_is_auto_typed=auto_type_positionals,
                compared_is_auto_typed=auto_type_positionals,
                reference_memory_selector=reference_memory,
                compared_memory_selector=compared_memory,
                current_name=current_name,
                registry=registry,
            )
            reference_access = targets.reference_access
            compared_access = targets.compared_access
            reference_memory = targets.reference_memory_uid
            compared_memory = targets.compared_memory_uid
            if targets.reference_operand_is_memory and reference_descendants:
                raise CompareCommandError(
                    "REFERENCE Memory selection cannot be combined with "
                    "--reference-descendants."
                )
            if targets.compared_operand_is_memory and compared_descendants:
                raise CompareCommandError(
                    "PEER Memory selection cannot be combined with "
                    "--compared-descendants."
                )
            reference = load_comparison_context(
                reference_access,
                include_descendants=reference_descendants,
            )
            compared = load_comparison_context(
                compared_access,
                include_descendants=compared_descendants,
            )
            profile_registry = registry
        if reference.uid == compared.uid or reference.name == compared.name:
            raise CompareCommandError("Compare requires two distinct Contexts.")

        if not ledger and not refresh:
            def summarize_frames(progress):
                def provider_factory():
                    provider, policy = connect_operation_provider(
                        COMPARISON_SUMMARY_OPERATION
                    )
                    detail = policy.model or policy.provider_id
                    if policy.reasoning_effort is not None:
                        detail += f" · reasoning {policy.reasoning_effort}"
                    progress.update(f"summarizing · {detail}", step=2)
                    return provider

                return run_comparison_summary(
                    store=store,
                    reference_access=reference_access,
                    compared_access=compared_access,
                    reference=reference,
                    compared=compared,
                    current_name=current_name,
                    include_descendants=(
                        reference_descendants,
                        compared_descendants,
                    ),
                    memory_selectors=(reference_memory, compared_memory),
                    provider_factory=provider_factory,
                    context_loader=load_comparison_context,
                )

            summary = run_command_wait(
                "COMPARE",
                "connecting provider",
                total=2,
                work=summarize_frames,
            )
            _present_comparison_summary(summary, snapshot=snapshot)
            return

        def analyze_input(comparison_input: ComparisonInput) -> ComparisonAnalysis:
            def compare_frames(progress):
                provider = _connect_compare_provider(
                    connect_codex_chatgpt_provider
                )
                progress.update("analyzing relations", step=2)
                return analyze_comparison(comparison_input, provider)

            return run_command_wait(
                "COMPARE",
                "connecting provider",
                total=2,
                work=compare_frames,
            )

        equivalent_match: EquivalentComparePrewarmMatch | None = None

        def equivalent(comparison_input):
            nonlocal equivalent_match
            equivalent_match = find_declared_equivalent_compare_analysis(
                store=store,
                comparison_input=comparison_input,
                current_name=current_name,
                registry_snapshot=profile_registry,
            )
            return (
                equivalent_match.analysis
                if equivalent_match is not None
                else None
            )

        execution = ensure_comparison_analysis(
            store=store,
            reference_access=reference_access,
            compared_access=compared_access,
            reference=reference,
            compared=compared,
            current_name=current_name,
            include_descendants=(
                reference_descendants,
                compared_descendants,
            ),
            memory_selectors=(reference_memory, compared_memory),
            refresh=refresh,
            analyze=analyze_input,
            equivalent=(
                equivalent
                if reference_memory is None and compared_memory is None
                else None
            ),
            project=(
                (
                    lambda comparison_input: project_declared_compare_analysis(
                        store=store,
                        comparison_input=comparison_input,
                        current_name=current_name,
                        registry_snapshot=profile_registry,
                    )
                )
                if reference_memory is None and compared_memory is None
                else None
            ),
        )
        if (
            execution.origin == "EQUIVALENT_SCOPE_PREWARM"
            and equivalent_match is not None
        ):
            if equivalent_match.origin == "EXACT_PREWARM":
                record_exact_compare_prewarm(
                    store,
                    entry_key=equivalent_match.entry_key,
                    analysis=execution.analysis,
                )
            else:
                record_equivalent_compare_prewarm(
                    store,
                    entry_key=equivalent_match.entry_key,
                    analysis=execution.analysis,
                    prepared_context_names=(
                        equivalent_match.prepared_context_names
                    ),
                )
        _present_comparison(
            store=store,
            analysis=execution.analysis,
            reused=execution.reused,
            origin=(
                installed_compare_prewarm_origin(store, execution.analysis)
                or execution.origin
            ),
            ledger=ledger,
            snapshot=snapshot,
            durable=execution.durable,
            retention=execution.retention,
        )
    except (
        CompareCommandError,
        ComparisonError,
        ComparisonProviderError,
        ComparisonSummaryError,
        ConcurrentComparisonUpdateError,
        FileNotFoundError,
        OSError,
        ProvenanceError,
        ProfileConfigError,
        ProfileProviderRoutesError,
        ProfileError,
        QueryProviderError,
        RationaleError,
        StudyPrewarmRegistryError,
        ValueError,
    ) as error:
        typer.secho(
            f"Compare error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
