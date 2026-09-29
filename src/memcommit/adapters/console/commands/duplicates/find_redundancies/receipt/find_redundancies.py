"""Render read-only redundancy analysis and evidence JSON."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.quality_find.rendering import (
    plural as _count,
    render_cleanup_member,
    render_heading,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_issue_analysis.model import (
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.memory_issue_analysis.redundancy_scope import (
    RedundancyScopeAnalysis,
)
from memcommit.application.capabilities.semantic.redundancy_evidence import (
    redundancy_evidence_json,
)
from memcommit.application.capabilities.semantic_execution.relations import (
    connected_relation_components,
)
from memcommit.core.context import Memory


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


def render_find_redundancies_receipt(
    analysis: RedundancyScopeAnalysis, *, evidence_json: bool = False
) -> None:
    """Print the complete direct or recursive report without executing work."""

    if evidence_json:
        for handoff in analysis.handoffs:
            typer.echo(redundancy_evidence_json(handoff))
        return

    source = analysis.source
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


def _connected_redundancy_groups(
    findings: tuple[DuplicateFinding, ...],
) -> tuple[tuple[tuple[Memory, ...], tuple[DuplicateFinding, ...]], ...]:
    """Group the evidence forest without repeating shared member Memories."""

    memory_by_uid: dict[str, Memory] = {}
    for finding in findings:
        memory_by_uid.setdefault(finding.left.uid, finding.left)
        memory_by_uid.setdefault(finding.right.uid, finding.right)
    components = connected_relation_components(
        tuple(memory_by_uid),
        ((finding.left.uid, finding.right.uid) for finding in findings),
    )
    return tuple(
        (
            tuple(memory_by_uid[uid] for uid in component),
            tuple(
                finding
                for finding in findings
                if {finding.left.uid, finding.right.uid}.issubset(component)
            ),
        )
        for component in components
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


def _render_redundancy_scope(analysis: RedundancyScopeAnalysis) -> None:
    source = analysis.source
    group_count = sum(frame.report.group_count for frame in analysis.contexts)
    absorption_count = sum(frame.report.redundancy_count for frame in analysis.contexts)
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
