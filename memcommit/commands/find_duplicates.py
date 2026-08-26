"""Shared semantic-redundancy discovery for Find Redundancies and Dedun."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.authority.access import resolve_context_access
from memcommit.interfaces.cli.quality_findings import (
    render_cleanup_member,
    render_heading,
)
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.quality_find_workbench import (
    annotate_quality_find_attempt,
)
from memcommit.interfaces.console.text import (
    display_escape_text,
)
from memcommit.interfaces.console.identity import collision_safe_uid_prefixes
from memcommit.context import Memory
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_scope_preset,
)
from memcommit.findings import DuplicateFinding, DuplicateReport, FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.operations.dedup.application import (
    DEDUP_ELIGIBLE_RELATIONS,
    DedupRequest,
    apply_dedup,
    prepare_dedup,
    recommended_dedup_selections,
)
from memcommit.operations.dedup.runtime import MemoryStoreDedupPort
from memcommit.operations.dedun.scope import (
    DedunScopeReceipt,
    apply_recursive_dedun_scope,
    freeze_recursive_dedun_scope,
    prepare_recursive_dedun_scope,
)
from memcommit.quality_finding_handoff import (
    QualityFindingSource,
)
from memcommit.semantic_redundancy_evidence import (
    redundancy_evidence_json,
)
from memcommit.redundancy_scope import (
    RedundancyScopeAnalysis,
    analyze_independent_redundancy_scope,
    freeze_redundancy_scope,
)


_RELATION_COLORS = {
    "EXACT": typer.colors.GREEN,
    "SURFACE_EQUIVALENT": typer.colors.GREEN,
    "SEMANTIC_EQUIVALENT": typer.colors.YELLOW,
}

_RELATION_LABELS = {
    "EXACT": "EXACT",
    "SURFACE_EQUIVALENT": "SURFACE EQUIVALENT",
    "SEMANTIC_EQUIVALENT": "SEMANTIC EQUIVALENT",
}


def _count(value: int, singular: str, plural: str | None = None) -> str:
    return f"{value} {singular if value == 1 else plural or singular + 's'}"


def _connected_redundancy_groups(
    findings: tuple[DuplicateFinding, ...],
) -> tuple[tuple[tuple[Memory, ...], tuple[DuplicateFinding, ...]], ...]:
    """Group the evidence forest without repeating shared member Memories."""

    parent: dict[str, str] = {}
    memory_by_uid: dict[str, Memory] = {}
    order_by_uid: dict[str, int] = {}

    def add(memory: Memory) -> None:
        if memory.uid not in parent:
            parent[memory.uid] = memory.uid
            memory_by_uid[memory.uid] = memory
            order_by_uid[memory.uid] = len(order_by_uid)

    def root(uid: str) -> str:
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    for finding in findings:
        add(finding.left)
        add(finding.right)
        left_root = root(finding.left.uid)
        right_root = root(finding.right.uid)
        if left_root != right_root:
            parent[right_root] = left_root

    members_by_root: dict[str, list[Memory]] = {}
    evidence_by_root: dict[str, list[DuplicateFinding]] = {}
    for uid in sorted(order_by_uid, key=order_by_uid.__getitem__):
        members_by_root.setdefault(root(uid), []).append(memory_by_uid[uid])
    for finding in findings:
        evidence_by_root.setdefault(root(finding.left.uid), []).append(finding)

    roots = sorted(
        members_by_root,
        key=lambda group_root: min(
            order_by_uid[memory.uid] for memory in members_by_root[group_root]
        ),
    )
    return tuple(
        (tuple(members_by_root[group_root]), tuple(evidence_by_root[group_root]))
        for group_root in roots
    )


def _render_redundancy_groups(
    report: DuplicateReport,
) -> None:
    groups = _connected_redundancy_groups(report.findings)
    for group_index, (members, evidence) in enumerate(groups, start=1):
        relations = {finding.relation for finding in evidence}
        if relations == {"EXACT"}:
            layer = "DUP / EXACT"
        elif "EXACT" in relations:
            layer = "COMPLETE DUN"
        else:
            layer = "SEMANTIC DUN"
        typer.echo()
        typer.secho(
            f"  DUN GROUP  {group_index}/{report.group_count} · "
            f"{_count(len(members), 'Memory', 'Memories')} · {layer}",
            bold=True,
        )
        typer.echo("    CLEANUP MAP · READY FOR REVIEW")
        uid_prefixes = collision_safe_uid_prefixes(memory.uid for memory in members)
        for member_index, memory in enumerate(members):
            role = "SURVIVOR" if member_index == 0 else "ABSORB"
            render_cleanup_member(
                role,
                uid_prefixes[memory.uid],
                content=memory.content,
            )
        for evidence_index, finding in enumerate(evidence, start=1):
            typer.echo(f"    EVIDENCE {evidence_index} · ", nl=False)
            typer.secho(
                _RELATION_LABELS[finding.relation],
                fg=_RELATION_COLORS.get(finding.relation, typer.colors.YELLOW),
                bold=True,
                nl=False,
            )
            typer.echo(" · " + display_escape_text(finding.reason))

    for exact_index, group in enumerate(report.exact_item_groups, start=1):
        group_index = len(groups) + exact_index
        member_uids = (group.survivor_uid, *group.absorbed_uids)
        uid_prefixes = collision_safe_uid_prefixes(member_uids)
        typer.echo()
        typer.secho(
            f"  DUN GROUP  {group_index}/{report.group_count} · "
            f"{_count(len(member_uids), 'direct item')} · DUP / EXACT · "
            f"{group.item_kind}",
            bold=True,
        )
        typer.echo("    CLEANUP MAP · READY FOR REVIEW")
        render_cleanup_member(
            "SURVIVOR",
            uid_prefixes[group.survivor_uid],
            content=group.summary,
        )
        for uid in group.absorbed_uids:
            render_cleanup_member(
                "ABSORB",
                uid_prefixes[uid],
                content=group.summary,
            )
        typer.echo("    EVIDENCE 1 · ", nl=False)
        typer.secho("EXACT", fg=typer.colors.GREEN, bold=True, nl=False)
        typer.echo(" · Same role-specific identity.")


def _run(
    *,
    context_name: str | None,
    evidence_json: bool,
    dedun_handoff: bool,
    include_descendants: bool = False,
) -> None:
    """Run one shared analysis, optionally exposing Dedun's Apply handoff."""

    operation_name = "dedun" if dedun_handoff else "find-redundancies"
    operation_label = "Dedun" if dedun_handoff else "Find Redundancies"
    progress_label = "DEDUN" if dedun_handoff else "FIND REDUNDANCIES"
    store = MemoryStore(create=False)
    recursive_dedun = None
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        access = resolve_context_access(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
        if dedun_handoff and include_descendants:
            recursive_dedun = freeze_recursive_dedun_scope(store, access)
            source = recursive_dedun.source
        else:
            source = freeze_redundancy_scope(
                store,
                access,
                include_descendants=include_descendants,
            )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            f"{operation_label} error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    try:
        with CommandProgress(
            progress_label,
            "analyzing independent direct Context frames",
            total=len(source.contexts),
        ):
            analysis = analyze_independent_redundancy_scope(
                source,
                connect_codex_chatgpt_provider,
                operation=ops.find_redundancies,
            )
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            f"{operation_label} error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    annotate_quality_find_attempt(
        "duplicates",
        source,
        operation_name=operation_name,
    )

    if evidence_json:
        for handoff in analysis.handoffs:
            typer.echo(redundancy_evidence_json(handoff))
        return

    if dedun_handoff:
        if source.include_descendants:
            assert recursive_dedun is not None
            port = MemoryStoreDedupPort(
                store,
                current_name=context_snapshot.current_name,
                allow_grants=False,
            )
            prepared = prepare_recursive_dedun_scope(
                recursive_dedun,
                analysis,
                port=port,
            )
            receipt = apply_recursive_dedun_scope(store, prepared)
            _render_recursive_dedun_receipt(receipt)
            return
        frame = analysis.contexts[0]
        report = frame.report
        ctx = frame.source.contexts[0]
        applicable = tuple(
            handoff
            for handoff in frame.handoffs
            if handoff.classification in DEDUP_ELIGIBLE_RELATIONS
        )
        context_label = display_escape_text(access.display_name)
        if not applicable and not report.exact_item_groups:
            typer.echo(f"No redundancies in '{context_label}'.")
            return
        port = MemoryStoreDedupPort(
            store,
            current_name=context_snapshot.current_name,
        )
        plan = prepare_dedup(
            DedupRequest(
                applicable,
                exact_source=QualityFindingSource(
                    context_uid=ctx.uid,
                    display_name=access.display_name,
                    direct_memory_digest=source.context_digests[0],
                ),
                exact_source_frame_digest=source.digest,
            ),
            port=port,
        )
        receipt = apply_dedup(
            plan,
            recommended_dedup_selections(plan),
            port=port,
        )
        typer.secho(
            f"Dedun '{context_label}': absorbed {len(receipt.absorbed_uids)} "
            "redundant direct item(s); kept "
            f"{len(receipt.survivor_uids)} original UID(s).",
            fg=typer.colors.GREEN,
        )
        typer.echo(
            "DUN COMPOSITION · "
            f"{_count(report.redundancy_count, 'evidence link')} = "
            f"{_count(report.exact_duplicate_count, 'DUP / EXACT link')} + "
            f"{_count(report.semantic_redundancy_count, 'SEMANTIC DUN link')}"
        )
        typer.echo(
            f"Checkpoint [{receipt.checkpoint_uid[:8]}] · review: "
            f"mem review dedun --receipt {receipt.checkpoint_uid} · "
            "recovery: mem undo"
        )
        return

    if source.include_descendants:
        _render_redundancy_scope(analysis)
        return

    frame = analysis.contexts[0]
    report = frame.report
    ctx = frame.source.contexts[0]
    render_heading(
        operation_label="Find Redundancies",
        context_name=display_escape_text(ctx.name),
        facts=(
            _count(report.memory_count, "direct memory", "direct memories")
            + " checked",
            _count(report.group_count, "group"),
            _count(report.redundancy_count, "proposed absorption"),
        ),
    )
    if not report.findings and not report.exact_item_groups:
        return
    _render_redundancy_groups(report)


def _render_redundancy_scope(analysis: RedundancyScopeAnalysis) -> None:
    source = analysis.source
    group_count = sum(frame.report.group_count for frame in analysis.contexts)
    absorption_count = sum(
        frame.report.redundancy_count for frame in analysis.contexts
    )
    render_heading(
        operation_label="Find Redundancies",
        context_name=display_escape_text(source.target_names[0]),
        facts=(
            _count(len(analysis.contexts), "Context"),
            _count(analysis.memory_count, "direct memory", "direct memories")
            + " checked",
            _count(group_count, "group"),
            _count(absorption_count, "proposed absorption"),
        ),
    )
    for index, frame in enumerate(analysis.contexts, start=1):
        typer.echo()
        typer.secho(
            f"CONTEXT {index}/{len(analysis.contexts)} · "
            f"{display_escape_text(frame.context_name)}",
            bold=True,
        )
        typer.echo(
            "  "
            + _count(frame.report.memory_count, "direct memory", "direct memories")
            + " checked · "
            + _count(frame.report.group_count, "group")
            + " · "
            + _count(frame.report.redundancy_count, "proposed absorption")
        )
        if frame.report.findings or frame.report.exact_item_groups:
            _render_redundancy_groups(frame.report)
        else:
            typer.echo("  No redundancies.")


def _render_recursive_dedun_receipt(receipt: DedunScopeReceipt) -> None:
    root = display_escape_text(receipt.root_name)
    if not receipt.absorbed_uids:
        typer.echo(
            f"No redundancies under '{root}' "
            f"({_count(len(receipt.contexts), 'Context')} checked)."
        )
        return
    changed = tuple(frame for frame in receipt.contexts if frame.checkpoint_uid)
    typer.secho(
        f"Dedun '{root}' recursively: absorbed "
        f"{len(receipt.absorbed_uids)} redundant direct item(s) in "
        f"{len(changed)}/{len(receipt.contexts)} Context(s); kept "
        f"{len(receipt.survivor_uids)} original UID(s).",
        fg=typer.colors.GREEN,
    )
    for frame in changed:
        typer.echo(
            f"CONTEXT · {display_escape_text(frame.context_name)} · "
            f"{len(frame.absorbed_uids)} absorbed · checkpoint "
            f"[{frame.checkpoint_uid[:8]}] · review: "
            f"mem review dedun --receipt {frame.checkpoint_uid}"
        )
    assert receipt.operation_uid is not None
    typer.echo(
        f"Operation [{receipt.operation_uid[:8]}] · recovery: "
        "mem undo (one command unit)"
    )


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Context to inspect (defaults to current)",
        ),
    ] = None,
    evidence_json: Annotated[
        bool,
        typer.Option(
            "--evidence-json",
            help="Print one canonical redundancy evidence JSON per finding",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            "-d",
            help="Inspect the exact Context root only (default)",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "--recursive",
            "-r",
            help=(
                "Inspect each readable lexical descendant as an independent "
                "direct semantic frame"
            ),
        ),
    ] = False,
) -> None:
    """Report complete DUN evidence; never change Context content."""
    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
    except ValueError as error:
        typer.secho(
            "Find Redundancies error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        _run(
            context_name=context_name,
            evidence_json=evidence_json,
            dedun_handoff=False,
            include_descendants=preset is ContextScopePreset.RECURSIVE,
        )
    except typer.Exit:
        raise
    except ValueError as error:
        typer.secho(
            "Find Redundancies error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def run_dedun(
    *,
    context_name: str | None,
    evidence_json: bool,
    include_descendants: bool = False,
) -> None:
    """Analyze and immediately apply complete exact-plus-semantic DUN groups."""

    _run(
        context_name=context_name,
        evidence_json=evidence_json,
        dedun_handoff=True,
        include_descendants=include_descendants,
    )


__all__ = ["cmd", "run_dedun"]
