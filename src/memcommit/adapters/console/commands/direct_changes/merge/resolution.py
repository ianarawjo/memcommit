"""Noninteractive conflict reporting and decision parsing for Merge."""

from __future__ import annotations

import typer

from memcommit.adapters.console.commands.direct_changes.merge.presentation import (
    merge_conflict_summary_lines,
    merge_plan_summary_lines,
)
from memcommit.application.operations.direct_changes.merge.application import (
    FrozenMergePlan,
    MergeDecision,
    MergeError,
    MergeResolution,
    merge_resolution_case,
)


def render_merge_conflicts(plan: FrozenMergePlan) -> None:
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
