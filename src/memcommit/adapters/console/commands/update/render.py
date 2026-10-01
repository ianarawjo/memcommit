"""Pure terminal rendering for Update plans and report snapshots."""

from __future__ import annotations

from dataclasses import replace

import typer

from memcommit.application.authorization import ContextUse
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    render_resolution_workbench_snapshot,
)
from memcommit.application.operations.update.model import (
    UpdateContextInputs,
    UpdatePlan,
    required_update_context_uses,
)
from memcommit.adapters.console.commands.update.presentation import (
    UpdateResolutionWorkbenchAdapter,
)


def render_update_report_snapshot(inputs: UpdateContextInputs, plan: UpdatePlan) -> str:
    return render_resolution_workbench_snapshot(
        replace(
            UpdateResolutionWorkbenchAdapter(inputs, plan).view(),
            title=f"Impact: {inputs.source_name} -> {inputs.target_name}",
            status="PLANNED",
        )
    )


def render_plan(inputs: UpdateContextInputs, plan: UpdatePlan) -> None:
    """Render a process-local plan without persisting a reusable work slot."""
    edits, additions, removals = (
        sum(op.operation == kind for op in plan.operations)
        for kind in ("edit", "add", "remove")
    )
    view = replace(
        UpdateResolutionWorkbenchAdapter(inputs, plan).view(),
        title=f"Impact: {inputs.source_name} -> {inputs.target_name}",
        status="PLANNED",
    )
    typer.echo(render_resolution_workbench_snapshot(view))
    typer.echo(
        "\nSUMMARY · "
        f"{edits} edit{'s' if edits != 1 else ''}, "
        f"{additions} addition{'s' if additions != 1 else ''}, "
        f"{removals} removal{'s' if removals != 1 else ''}"
    )
    typer.echo(
        "SCOPE · SOURCE "
        f"{'INCLUDE DESCENDANTS' if inputs.source_include_descendants else 'SELECTED GRAPH ONLY'}"
        " · TARGET "
        f"{'INCLUDE DESCENDANTS' if inputs.target_include_descendants else 'SELECTED GRAPH ONLY'}"
    )
    if inputs.goal_focus is not None:
        typer.echo(
            "GOAL FOCUS · "
            f"{inputs.goal_focus.kind} · {inputs.goal_focus.label} · "
            f"{len(inputs.goal_focus.items)} ITEM"
            f"{'S' if len(inputs.goal_focus.items) != 1 else ''} · "
            "RELEVANCE ONLY"
        )
    if inputs.granted_target is not None:
        required_uses = required_update_context_uses(plan.operations)
        required = tuple(
            use.value
            for use in (
                ContextUse.READ,
                ContextUse.CREATE,
                ContextUse.UPDATE,
                ContextUse.DELETE,
            )
            if use in required_uses
        )
        granted = set(inputs.granted_target.permissions)
        ready = set(required).issubset(granted)
        typer.echo(
            "GRANTED TARGET · "
            f"{inputs.granted_target.access_name} · "
            f"grant {inputs.granted_target.grant_uid[:8]} "
            f"revision {inputs.granted_target.grant_revision}"
        )
        typer.echo("REQUIRED TO APPLY · " + " + ".join(required))
        typer.echo("GRANT PERMISSIONS · " + ("READY" if ready else "BLOCKED"))
    if not plan.operations:
        typer.echo("\n(no changes needed)")
    if view.items:
        typer.echo("\nEXACT PLANNED CHANGE DETAILS")
    for item in view.items:
        # ``title`` deliberately omits the kind because common interactive
        # rows supply it. The deterministic snapshot must add it once too.
        typer.echo(f"\n{item.kind} {item.title}")
        for block in item.blocks:
            typer.echo(f"  {block.heading}")
            for line in block.text.splitlines():
                typer.echo(f"    {line}")
    typer.echo()
    typer.echo("No changes applied.")
