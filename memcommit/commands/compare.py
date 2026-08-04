"""Create or resume one targetless ordered peer-Context comparison."""

from __future__ import annotations

from collections import Counter
import shlex
import sys
from typing import Annotated, Optional

import typer

from memcommit.comparison import (
    COMPARISON_RULESET_VERSION,
    ComparisonAnalysis,
    ComparisonError,
    ComparisonInput,
    ComparisonRelation,
)
from memcommit.comparison_provider import (
    ComparisonProviderError,
    analyze_comparison,
)
from memcommit.comparison_store import (
    ConcurrentComparisonUpdateError,
    load_comparison_analysis,
    save_comparison_analysis,
)
from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.derived_policy import (
    AnalysisRetention,
    analysis_retention,
    authorize_combination,
)
from memcommit.granted_comparison_store import (
    load_granted_comparison_artifact,
    save_granted_comparison_artifact,
)
from memcommit.commands.compare_sessions import (
    choose_comparison_session,
    load_saved_comparison,
    revalidate_saved_comparison,
)
from memcommit.commands.compare_workbench import run_compare_workbench
from memcommit.commands.rationale import render_rationale
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.understanding_render import understanding_lines
from memcommit.query_provider import (
    CodexChatGPTProvider,
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.profile_config import ProfileConfigError
from memcommit.provenance import ProvenanceError
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.rationale import RationaleError, build_rationale
from memcommit.rationale_scope import (
    load_rationale_scope,
    rationale_trace,
    resolve_rationale_target,
)
from memcommit.store import MemoryStore


COMPARE_AGGREGATE_TIMEOUT_SECONDS = 300


class CompareCommandError(RuntimeError):
    """Safe user-facing Compare orchestration failure."""


def _single_line(value: str, *, limit: int = 110) -> str:
    normalized = " ".join(display_escape_text(value).split())
    return (
        normalized
        if len(normalized) <= limit
        else normalized[: limit - 1].rstrip() + "…"
    )


def _relation_lines(
    analysis: ComparisonAnalysis,
    relation: ComparisonRelation,
    *,
    number: int,
) -> list[str]:
    frame_by_uid = {frame.uid: frame for frame in analysis.frames}
    memory_by_key = {
        (frame.uid, memory.uid): memory
        for frame in analysis.frames
        for memory in frame.memories
    }
    marker = "?" if relation.status == "UNRESOLVED" else "✓"
    lines = [
        (f"  {marker} R{number}. {relation.kind} · {_single_line(relation.summary)}")
    ]
    for member in relation.members:
        frame = frame_by_uid[member.frame_uid]
        memory = memory_by_key[(member.frame_uid, member.memory_uid)]
        side = "REF" if frame.side == "REFERENCE" else "TO "
        lines.append(
            f"      {side} {display_escape_text(frame.context_name)} "
            f"#{memory.position + 1} [{memory.uid[:8]}] · "
            f"{display_escape_text(memory.content)}"
        )
    lines.append(f"      WHY · {display_escape_text(relation.reason)}")
    return lines


def _relation_groups(
    analysis: ComparisonAnalysis,
) -> dict[str, list[ComparisonRelation]]:
    reference, compared = analysis.frames
    return {
        "both": [
            relation
            for relation in analysis.relations
            if relation.kind in {"EQUIVALENT", "COMPATIBLE"}
        ],
        "differences": [
            relation
            for relation in analysis.relations
            if relation.kind in {"SCOPED", "CONFLICT", "UNCLEAR"}
        ],
        "reference_only": [
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == reference.uid for member in relation.members)
        ],
        "compared_only": [
            relation
            for relation in analysis.relations
            if relation.kind == "DISTINCT"
            and all(member.frame_uid == compared.uid for member in relation.members)
        ],
    }


def _header_lines(
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
    durable: bool,
    retention: AnalysisRetention | None,
) -> list[str]:
    reference, compared = analysis.frames
    counts = Counter(relation.kind for relation in analysis.relations)
    return [
        "MEM COMPARE · SYMMETRIC PEERS",
        (
            f"Reference: {display_escape_text(reference.context_name)} "
            "(layout only; no authority)"
        ),
        f"Compared:  {display_escape_text(compared.context_name)}",
        (
            f"Analysis: {analysis.uid[:8]} · "
            f"{'REUSED' if reused else 'NEW'}"
            + (
                " · SAVED · RETAINED"
                if retention == "RETAINED"
                else " · SAVED · GRANT-BOUND"
                if retention == "GRANT_BOUND"
                else ""
                if durable
                else " · NOT SAVED (GRANTED VIEW)"
            )
        ),
        (
            "METRICS · "
            f"MEMORIES {len(reference.memories)} + "
            f"{len(compared.memories)} · "
            f"RELATIONS {len(analysis.relations)} · "
            f"POTENTIAL CONFLICTS {len(analysis.issues)}"
        ),
        (
            f"EQUIVALENT {counts['EQUIVALENT']} · "
            f"COMPATIBLE {counts['COMPATIBLE']} · "
            f"SCOPED {counts['SCOPED']} · "
            f"CONFLICT {counts['CONFLICT']} · "
            f"DISTINCT {counts['DISTINCT']} · "
            f"UNCLEAR {counts['UNCLEAR']}"
        ),
    ]


def _potential_conflict_lines(
    analysis: ComparisonAnalysis,
    numbered: dict[str, int],
) -> list[str]:
    del numbered  # Stable relation numbers belong to the exhaustive ledger only.
    relation_by_uid = {relation.uid: relation for relation in analysis.relations}
    frame_by_uid = {frame.uid: frame for frame in analysis.frames}
    lines = [
        "",
        f"POTENTIAL CONFLICTS · {len(analysis.issues)}",
    ]
    if not analysis.issues:
        lines.append("  (none)")
        return lines

    for index, issue in enumerate(analysis.issues, start=1):
        source_names: list[str] = []
        relation_summaries: list[str] = []
        for relation_uid in issue.relation_uids:
            relation = relation_by_uid[relation_uid]
            relation_summaries.append(_single_line(relation.summary, limit=180))
            for member in relation.members:
                name = frame_by_uid[member.frame_uid].context_name
                if name not in source_names:
                    source_names.append(name)
        options = "; ".join(
            f"{display_escape_text(option.label)}: "
            f"{display_escape_text(option.text).rstrip(' .;')}"
            for option in issue.options
        )
        lines.extend(
            [
                "",
                (
                    f"{index}. {display_escape_text(issue.title).rstrip(' .')}. "
                    f"{' ↔ '.join(display_escape_text(name) for name in source_names)}: "
                    f"{' '.join(relation_summaries)} "
                    f"{display_escape_text(issue.why_it_matters)} "
                    f"{options}."
                ),
            ]
        )
    return lines


def render_comparison(
    analysis: ComparisonAnalysis,
    *,
    reused: bool,
    ledger: bool = False,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
) -> str:
    """Render a compact report, optionally followed by the complete ledger."""
    reference, compared = analysis.frames
    groups = _relation_groups(analysis)
    numbered = {
        relation.uid: index
        for index, relation in enumerate(analysis.relations, start=1)
    }
    lines = _header_lines(
        analysis,
        reused=reused,
        durable=durable,
        retention=retention,
    )
    lines.append("")
    lines.extend(understanding_lines(analysis.understanding))

    if not ledger:
        if analysis.reports is None:
            raise ComparisonError(
                "This saved comparison predates compact reports. "
                "Run 'mem compare --refresh --to NAME' to update it."
            )
        report_sections = [
            (
                f"WHAT BOTH CONTAIN · {len(groups['both'])}",
                analysis.reports.both,
                bool(groups["both"]),
            ),
            (
                f"WHAT DIFFERS · {len(groups['differences'])}",
                analysis.reports.differences,
                bool(groups["differences"]),
            ),
            (
                (
                    "ONLY IN "
                    + display_escape_text(reference.context_name)
                    + f" · {len(groups['reference_only'])}"
                    + " · not automatically a deficiency"
                ),
                analysis.reports.reference_only,
                bool(groups["reference_only"]),
            ),
            (
                (
                    "ONLY IN "
                    + display_escape_text(compared.context_name)
                    + f" · {len(groups['compared_only'])}"
                    + " · not automatically a deficiency"
                ),
                analysis.reports.compared_only,
                bool(groups["compared_only"]),
            ),
        ]
        for title, report, present in report_sections:
            if not present:
                continue
            lines.extend(
                [
                    "",
                    title,
                    display_escape_text(report),
                ]
            )
        if analysis.issues:
            lines.extend(_potential_conflict_lines(analysis, numbered))
        ledger_command = display_escape_text(
            shlex.join(
                [
                    "mem",
                    "compare",
                    "--to",
                    compared.context_name,
                    "--ledger",
                ]
            )
        )
        meld_command = display_escape_text(
            shlex.join(
                [
                    "mem",
                    "meld",
                    reference.context_name,
                    compared.context_name,
                    "--to",
                    "RESULT_CONTEXT",
                ]
            )
        )
        lines.extend(
            [
                "",
                (
                    "The complete source-linked relation ledger is saved. "
                    "Inspect it with:"
                    if durable
                    else "The complete source-linked relation ledger was not "
                    "saved. Re-run it with:"
                ),
                f"  {ledger_command}",
            ]
        )
        if durable:
            lines.extend(
                [
                    "",
                    (
                        "Create a new result Context and review both sources "
                        "with Meld:"
                    ),
                    f"  {meld_command}",
                ]
            )
        return "\n".join(lines)

    lines.extend(
        [
            "",
            f"RELATION LEDGER · {len(analysis.relations)}",
        ]
    )
    sections: list[tuple[str, list[ComparisonRelation]]] = [
        ("WHAT BOTH CONTAIN", groups["both"]),
        (
            "WHAT DIFFERS",
            [
                relation
                for relation in analysis.relations
                if relation.kind in {"SCOPED", "CONFLICT"}
            ],
        ),
        (
            (
                "ONLY IN "
                + display_escape_text(reference.context_name)
                + " · not automatically a deficiency"
            ),
            groups["reference_only"],
        ),
        (
            (
                "ONLY IN "
                + display_escape_text(compared.context_name)
                + " · not automatically a deficiency"
            ),
            groups["compared_only"],
        ),
        (
            "UNCLEAR",
            [relation for relation in analysis.relations if relation.kind == "UNCLEAR"],
        ),
    ]
    for title, relations in sections:
        lines.extend(["", title])
        if not relations:
            lines.append("  (none)")
            continue
        for relation in relations:
            lines.extend(
                _relation_lines(
                    analysis,
                    relation,
                    number=numbered[relation.uid],
                )
            )

    lines.extend(_potential_conflict_lines(analysis, numbered))
    return "\n".join(lines)


def _connect_compare_provider(provider_factory):
    provider = provider_factory()
    if isinstance(provider, CodexChatGPTProvider):
        provider.timeout = max(
            provider.timeout,
            COMPARE_AGGREGATE_TIMEOUT_SECONDS,
        )
    return provider


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
        ledger=ledger,
        snapshot=snapshot,
    )


def _render_meld_route(analysis: ComparisonAnalysis) -> None:
    reference, compared = analysis.frames
    typer.echo("Create a result Context and continue with Meld:")
    typer.echo(
        "  "
        + display_escape_text(
            shlex.join(
                [
                    "mem",
                    "meld",
                    reference.context_name,
                    compared.context_name,
                    "--to",
                    "RESULT_CONTEXT",
                ]
            )
        )
    )


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
        connect_codex_chatgpt_provider,
        cache_inference=not scope.granted,
        inference_contexts=scope.contexts,
        inference_scope_name=scope.root_name,
        recorded_evidence_available=not scope.granted,
    )
    render_rationale(report)


def _present_comparison(
    *,
    store: MemoryStore,
    analysis: ComparisonAnalysis,
    reused: bool,
    ledger: bool,
    snapshot: bool,
    durable: bool = True,
    retention: AnalysisRetention | None = None,
) -> None:
    """Use the TTY workbench by default and preserve stable snapshot output."""
    if ledger or snapshot or not (sys.stdin.isatty() and sys.stdout.isatty()):
        typer.echo(
            render_comparison(
                analysis,
                reused=reused,
                ledger=ledger,
                durable=durable,
                retention=retention,
            )
        )
        return

    receipt = run_compare_workbench(
        analysis,
        report_text=render_comparison(
            analysis,
            reused=reused,
            durable=durable,
            retention=retention,
        ),
    )
    if receipt.action == "ledger":
        typer.echo(
            render_comparison(
                analysis,
                reused=True,
                ledger=True,
                durable=durable,
                retention=retention,
            )
        )
    elif receipt.action == "meld":
        _render_meld_route(analysis)
    elif receipt.action == "rationale":
        if receipt.context_name is None or receipt.memory_uid is None:
            raise CompareCommandError(
                "Compare workbench returned an incomplete Rationale selection."
            )
        _render_selected_rationale(
            store=store,
            context_name=receipt.context_name,
            memory_uid=receipt.memory_uid,
        )
    else:
        typer.echo("Compare view closed.")


def _recursive_compare_projection(root: Context) -> Context:
    """Flatten one loaded tree while retaining each Memory's public path."""

    if not any(isinstance(item, Context) for item in root.iter_items()):
        return root
    projected = Context(uid=root.uid, name=root.name)
    seen_contexts: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in seen_contexts:
            return
        seen_contexts.add(context.uid)
        for item in context.iter_items():
            if isinstance(item, Memory):
                projected.add(
                    Memory(
                        uid=item.uid,
                        content=f"[{context.name}] {item.content}",
                    )
                )
            elif isinstance(item, Context):
                visit(item)
            elif isinstance(item, QueryContextRef):
                # A nested query-only override is visible as a route but its
                # concealed content never enters ordinary comparison input.
                continue
            elif isinstance(item, MemoryRef):
                raise ComparisonError(
                    "Recursive Compare does not copy live Memory references; "
                    f"unsupported item [{item.uid[:8]}] in {context.name!r}."
                )

    visit(root)
    return projected


def _load_compare_context(access) -> Context:
    if access.is_granted:
        context = GrantedReadStore(access).load(access.display_name)
    else:
        context = access.store.load(access.context_name)
    return _recursive_compare_projection(context)


def cmd(
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Existing PEER Context locator; canonical or explicitly "
                "relative to the active reference Context"
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
            help="Show every exact source-linked relation and explanation",
        ),
    ] = False,
    snapshot: Annotated[
        bool,
        typer.Option(
            "--snapshot",
            help="Print the compact report instead of opening the TTY workbench",
        ),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Interactively reopen a saved read-only comparison analysis",
        ),
    ] = False,
) -> None:
    """Compare the active Context with one equal-authority PEER Context."""
    if sessions and to is not None:
        typer.secho(
            "Compare error: use either --sessions or --to, not both.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    if refresh and to is None:
        typer.secho(
            "Compare error: --refresh requires an explicit --to Context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    store = MemoryStore(create=False)
    try:
        if sessions or to is None:
            receipt = choose_comparison_session(store, ledger=ledger)
            if receipt is None:
                typer.echo("Compare selection ended; no analysis was opened.")
                return
            _resume_selected_comparison(
                store=store,
                analysis_uid=receipt.key,
                ledger=ledger,
                snapshot=snapshot,
            )
            return
        reference_name = store.current_context_name()
        if not reference_name:
            raise CompareCommandError(
                "No current reference Context. Run 'mem switch NAME' first."
            )
        compared_name = resolve_context_locator(to, current=reference_name)
        with authority_grant_snapshot_lock() as registry:
            reference_access = resolve_context_access(
                store,
                reference_name,
                current_name=reference_name,
                required_permission="READ",
                registry=registry,
            )
            try:
                compared_access = resolve_context_access(
                    store,
                    to,
                    current_name=reference_name,
                    required_permission="READ",
                    registry=registry,
                )
            except FileNotFoundError as error:
                resolution = (
                    ""
                    if compared_name == to
                    else f" (resolved to '{compared_name}')"
                )
                raise CompareCommandError(
                    f"Compared Context '{to}'{resolution} does not exist."
                ) from error
            authorize_combination((reference_access, compared_access))
            reference = _load_compare_context(reference_access)
            compared = _load_compare_context(compared_access)
            reference_binding = (
                freeze_granted_context_binding(reference_access)
                if reference_access.is_granted
                else None
            )
            compared_binding = (
                freeze_granted_context_binding(compared_access)
                if compared_access.is_granted
                else None
            )
        if reference.uid == compared.uid or reference.name == compared.name:
            raise CompareCommandError("Compare requires two distinct Contexts.")

        granted = reference_binding is not None or compared_binding is not None
        granted_artifact = (
            load_granted_comparison_artifact(store, reference.uid, compared.uid)
            if granted
            else None
        )
        if granted:
            existing = (
                granted_artifact.analysis
                if granted_artifact is not None
                else None
            )
        else:
            existing = load_comparison_analysis(reference.uid, compared.uid)
        if (
            existing is not None
            and existing.matches(reference, compared)
            and existing.ruleset_version == COMPARISON_RULESET_VERSION
            and not refresh
        ):
            _present_comparison(
                store=store,
                analysis=existing,
                reused=True,
                ledger=ledger,
                snapshot=snapshot,
                retention=(
                    granted_artifact.retention
                    if granted_artifact is not None
                    else None
                ),
            )
            return

        comparison_input = ComparisonInput.from_contexts(
            reference,
            compared,
        )
        provider = _connect_compare_provider(connect_codex_chatgpt_provider)
        analysis = analyze_comparison(comparison_input, provider)
        if granted:
            with authority_grant_snapshot_lock() as registry:
                current_reference_access = (
                    revalidate_granted_context_binding(
                        reference_binding,
                        registry=registry,
                    )
                    if reference_binding is not None
                    else resolve_context_access(
                        store,
                        reference.name,
                        current_name=reference_name,
                        required_permission="READ",
                        registry=registry,
                    )
                )
                current_compared_access = (
                    revalidate_granted_context_binding(
                        compared_binding,
                        registry=registry,
                    )
                    if compared_binding is not None
                    else resolve_context_access(
                        store,
                        compared.name,
                        current_name=reference_name,
                        required_permission="READ",
                        registry=registry,
                    )
                )
                current_reference = _load_compare_context(
                    current_reference_access
                )
                current_compared = _load_compare_context(current_compared_access)
                if not analysis.matches(current_reference, current_compared):
                    raise ConcurrentComparisonUpdateError(
                        "A granted comparison source changed while Compare was "
                        "analyzing it; no result was published."
                    )
                retention = analysis_retention(
                    (current_reference_access, current_compared_access)
                )
                if retention is not None:
                    save_granted_comparison_artifact(
                        store,
                        analysis,
                        (current_reference_access, current_compared_access),
                        retention=retention,
                        expected_analysis_uid=(
                            existing.uid if existing is not None else None
                        ),
                    )
            _present_comparison(
                store=store,
                analysis=analysis,
                reused=False,
                ledger=ledger,
                snapshot=snapshot,
                durable=retention is not None,
                retention=retention,
            )
            return
        save_comparison_analysis(
            store,
            analysis,
            expected_analysis_uid=(existing.uid if existing is not None else None),
        )
        _present_comparison(
            store=store,
            analysis=analysis,
            reused=False,
            ledger=ledger,
            snapshot=snapshot,
        )
    except (
        CompareCommandError,
        ComparisonError,
        ComparisonProviderError,
        ConcurrentComparisonUpdateError,
        FileNotFoundError,
        OSError,
        ProvenanceError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RationaleError,
        ValueError,
    ) as error:
        typer.secho(
            f"Compare error: {display_escape_text(str(error))}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
