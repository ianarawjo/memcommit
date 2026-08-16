"""Plain command-line rendering for typed Merge results."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.merge_application import (
    FrozenMergePlan,
    MergeDecision,
    MergeError,
    MergeReach,
    MergeResolution,
    MergeResult,
    merge_resolution_case,
)
from memcommit.merge_runtime import merge_summary


def render_merge_plain(result: MergeResult) -> None:
    """Preserve direct output while reporting recursive tree reach explicitly."""

    resolution_phrase = (
        f"; resolved {len(result.resolutions)} conflict(s)"
        if result.resolutions
        else ""
    )
    unchanged_phrase = (
        f"; {len(result.unchanged)} unchanged" if result.unchanged else ""
    )
    no_change = (
        not result.additions
        and not any(
            resolution.decision is MergeDecision.TAKE_SOURCE
            for resolution in result.resolutions
        )
        and not any(context.target_created for context in result.contexts)
    )
    status = "NO TARGET CHANGE · " if no_change else ""
    if result.reach is MergeReach.DESCENDANTS:
        created = sum(context.target_created for context in result.contexts)
        context_count = len(result.contexts)
        checkpoint_count = len(result.checkpoint_uids)
        context_noun = "Context" if context_count == 1 else "Contexts"
        checkpoint_noun = "checkpoint" if checkpoint_count == 1 else "checkpoints"
        typer.secho(
            f"{status}Recursively merged "
            f"'{display_escape_text(result.source_name)}' into "
            f"'{display_escape_text(result.target_name)}': "
            f"{context_count} {context_noun}, {created} created; added "
            f"{merge_summary(result.additions)}; "
            f"{checkpoint_count} {checkpoint_noun}"
            f"{resolution_phrase}{unchanged_phrase}.",
            fg=typer.colors.GREEN,
        )
        return
    typer.secho(
        f"{status}Merged '{display_escape_text(result.source_name)}' into "
        f"'{display_escape_text(result.target_name)}': added "
        f"{merge_summary(result.additions)}"
        f"{resolution_phrase}{unchanged_phrase}; checkpoint recorded.",
        fg=typer.colors.GREEN,
    )


def render_merge_conflicts_plain(plan: FrozenMergePlan) -> None:
    """Render stable conflict IDs for a noninteractive follow-up command."""

    typer.echo(
        f"MERGE PLAN · {display_escape_text(plan.source_name)} → "
        f"{display_escape_text(plan.target_name)} · {plan.request.reach.value}"
    )
    typer.echo(
        f"CLASSIFICATION · NEW {len(plan.additions)} · "
        f"UNCHANGED {len(plan.unchanged)} · CONFLICT {len(plan.conflicts)}"
    )
    for conflict in plan.conflicts:
        typer.echo(
            f"CONFLICT · {conflict.uid} · {conflict.kind.value} · "
            f"{display_escape_text(conflict.source_name)} → "
            f"{display_escape_text(conflict.target_name)}"
        )
        typer.echo(f"  SOURCE · {display_escape_text(conflict.source.description)}")
        for target in conflict.targets:
            typer.echo(f"  TARGET · {display_escape_text(target.description)}")
        typer.echo(f"  WHY · {display_escape_text(conflict.reason)}")
        typer.echo(
            "  ALLOWED · "
            + " / ".join(decision.value for decision in conflict.allowed_decisions)
        )
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
