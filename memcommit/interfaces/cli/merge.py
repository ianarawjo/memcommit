"""Plain command-line rendering for typed Merge results."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.merge import (
    merge_conflict_summary_lines,
    merge_plan_summary_lines,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeDecision,
    MergeError,
    MergeResolution,
    MergeResult,
    merge_resolution_case,
)
from memcommit.merge_runtime import merge_summary


def render_merge_plain(result: MergeResult) -> None:
    """Report why Merge changed or retained each classified item set."""

    keep_count = sum(
        resolution.decision is MergeDecision.KEEP_TARGET
        for resolution in result.resolutions
    )
    take_count = len(result.resolutions) - keep_count
    created = sum(context.target_created for context in result.contexts)
    target_changed = bool(result.additions or take_count or created)
    new_detail = (
        f" ({merge_summary(result.additions)})" if result.additions else ""
    )
    typer.secho(
        "MERGE RECORDED · "
        f"'{display_escape_text(result.source_name)}' → "
        f"'{display_escape_text(result.target_name)}' · {result.reach.value} · "
        f"NEW {len(result.additions)}{new_detail} · "
        f"ALREADY PRESENT {len(result.unchanged)} · "
        f"KEPT TARGET {keep_count} · TOOK SOURCE {take_count} · "
        f"CREATED CONTEXTS {created} · "
        f"TARGET CHANGED {'YES' if target_changed else 'NO'} · "
        f"CHECKPOINTS {len(result.checkpoint_uids)}",
        fg=typer.colors.GREEN,
    )


def render_merge_conflicts_plain(plan: FrozenMergePlan) -> None:
    """Render stable conflict IDs for a noninteractive follow-up command."""

    for line in merge_plan_summary_lines(plan):
        typer.echo(line)
    for conflict in plan.conflicts:
        for line in merge_conflict_summary_lines(conflict):
            typer.echo(line)
    all_take_source = all(
        MergeDecision.TAKE_SOURCE in conflict.allowed_decisions
        for conflict in plan.conflicts
    )
    bulk = (
        "--keep-target-all / --take-source-all"
        if all_take_source
        else "--keep-target-all"
    )
    typer.echo(f"RESOLVE · repeat --resolve ID=<listed-allowed-value>, or use {bulk}.")


def parse_merge_resolutions(
    plan: FrozenMergePlan,
    values: tuple[str, ...],
) -> tuple[MergeResolution, ...]:
    """Parse repeatable CLI decisions against the exact frozen plan."""

    known = {
        requirement.item_uid for requirement in merge_resolution_case(plan).requirements
    }
    result: list[MergeResolution] = []
    for value in values:
        if not isinstance(value, str) or "=" not in value:
            raise MergeError(
                "Merge --resolve requires ID=keep-target or ID=take-source."
            )
        conflict_uid, raw_decision = value.split("=", 1)
        conflict_uid = conflict_uid.strip()
        if conflict_uid not in known:
            raise MergeError(
                f"Merge --resolve names an unknown conflict: '{conflict_uid}'."
            )
        normalized = raw_decision.strip().replace("-", "_").upper()
        try:
            decision = MergeDecision(normalized)
        except ValueError as error:
            raise MergeError(
                "Merge decisions are keep-target or take-source."
            ) from error
        result.append(MergeResolution(conflict_uid=conflict_uid, decision=decision))
    return tuple(result)
