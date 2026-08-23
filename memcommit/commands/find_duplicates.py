"""Shared semantic-redundancy discovery for Find Redundancies and Dedun."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

import memcommit.ops as ops
from memcommit.commands.context_operand import (
    ContextOperandSnapshot,
    choose_context_operand,
)
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.commands.findings_render import (
    render_cleanup_member,
    render_finding_outcome,
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
from memcommit.findings import DuplicateFinding, DuplicateReport, FindingsError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.dedup_application import (
    DEDUP_ELIGIBLE_RELATIONS,
    DedupRequest,
    apply_dedup,
    prepare_dedup,
    recommended_dedup_selections,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.quality_find_workbench import (
    QualityFindSourceFrame,
    create_quality_find_workbench,
)
from memcommit.quality_finding_handoff import (
    QualityFindingSource,
    quality_finding_handoffs,
)
from memcommit.semantic_redundancy_evidence import (
    redundancy_evidence_json,
)


_RELATION_COLORS = {
    "EXACT": typer.colors.GREEN,
    "SURFACE_EQUIVALENT": typer.colors.GREEN,
    "SEMANTIC_EQUIVALENT": typer.colors.YELLOW,
    "OVERLAP": typer.colors.CYAN,
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
                finding.relation,
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
) -> None:
    """Run one shared analysis, optionally exposing Dedun's Apply handoff."""

    operation_name = "dedun" if dedun_handoff else "find-redundancies"
    operation_label = "Dedun" if dedun_handoff else "Find Redundancies"
    progress_label = "DEDUN" if dedun_handoff else "FIND REDUNDANCIES"
    store = MemoryStore(create=False)
    try:
        context_snapshot = ContextOperandSnapshot.capture(store)
        access = resolve_context_access(
            store,
            context_name,
            current_name=context_snapshot.current_name,
            required_permission="READ",
        )
        ctx = (
            GrantedReadStore(access).load_direct(access.display_name)
            if access.is_granted
            else store.load_direct(access.context_name)
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
            "analyzing direct memories",
            total=1,
        ):
            report = ops.find_redundancies(ctx, connect_codex_chatgpt_provider)
    except (FindingsError, QueryProviderError) as error:
        typer.secho(
            f"{operation_label} error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    source = QualityFindSourceFrame.create(
        (ctx,),
        context_names=(access.display_name,),
    )
    annotate_quality_find_attempt(
        "duplicates",
        source,
        operation_name=operation_name,
    )

    if evidence_json:
        session = create_quality_find_workbench("duplicates", source, report)
        for handoff in quality_finding_handoffs(session):
            typer.echo(redundancy_evidence_json(handoff))
        return

    if dedun_handoff:
        session = create_quality_find_workbench("duplicates", source, report)
        applicable = tuple(
            handoff
            for handoff in quality_finding_handoffs(session)
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

    render_heading(
        operation_label="Find Redundancies",
        context_name=display_escape_text(ctx.name),
        memory_count=report.memory_count,
    )
    render_finding_outcome(
        finding_count=report.redundancy_count,
        singular="redundancy finding",
        plural_form="redundancy findings",
        empty_message="No redundancies found",
    )
    if not report.findings and not report.exact_item_groups:
        return
    else:
        typer.echo()
        typer.secho(
            "  DUN = DUP / EXACT + SEMANTIC DUN",
            bold=True,
        )
        typer.echo(
            "    EVIDENCE  "
            f"{_count(report.redundancy_count, 'link')} = "
            f"{_count(report.exact_duplicate_count, 'DUP / EXACT link')} + "
            f"{_count(report.semantic_redundancy_count, 'SEMANTIC DUN link')}"
        )
        typer.echo(
            "    CLEANUP   "
            f"{_count(report.group_count, 'connected group')} · "
            f"{_count(report.redundancy_count, 'redundant direct item')}"
        )
        _render_redundancy_groups(report)


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
) -> None:
    """Report complete DUN evidence; never change Context content."""
    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
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
) -> None:
    """Analyze and immediately apply complete exact-plus-semantic DUN groups."""

    _run(
        context_name=context_name,
        evidence_json=evidence_json,
        dedun_handoff=True,
    )


__all__ = ["cmd", "run_dedun"]
