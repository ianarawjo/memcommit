"""Pure terminal rendering for Update plans and report snapshots."""

from __future__ import annotations

from dataclasses import replace

import typer

from memcommit.application.authorization import ContextUse
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    render_resolution_workbench_snapshot,
)
from memcommit.application.operations.update.model import (
    UpdateSession,
    count_operations,
    required_update_context_uses,
)
from memcommit.application.operations.update.resolution_adapter import (
    UpdateResolutionWorkbenchAdapter,
)


def _view(
    session: UpdateSession,
    *,
    staged: bool,
    applied: bool,
    undone: bool = False,
):
    if sum((staged, applied, undone)) > 1:
        raise ValueError("An Update view can have only one lifecycle status.")
    heading = (
        "Applied update"
        if applied
        else "Undone update"
        if undone
        else ("Staged update" if staged else "Impact")
    )
    status = (
        "APPLIED"
        if applied
        else "UNDONE"
        if undone
        else ("STAGED" if staged else "IMPACT")
    )
    return replace(
        UpdateResolutionWorkbenchAdapter(session).view(),
        title=f"{heading}: {session.source_name} -> {session.target_name}",
        status=status,
    )


def render_update_report_snapshot(
    session: UpdateSession,
    *,
    staged: bool = False,
    applied: bool = False,
    undone: bool = False,
) -> str:
    """Render the common Update report for read-only reuse by other shells."""

    return render_resolution_workbench_snapshot(
        _view(
            session,
            staged=staged,
            applied=applied,
            undone=undone,
        )
    )


def render_plan(
    session: UpdateSession,
    *,
    staged: bool = False,
    applied: bool = False,
    undone: bool = False,
) -> None:
    """Render a canonical local plan without trusting model-formatted prose."""
    if sum((staged, applied, undone)) > 1:
        raise ValueError("A plan can have only one lifecycle status.")
    edits, additions, removals = count_operations(session)
    view = _view(
        session,
        staged=staged,
        applied=applied,
        undone=undone,
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
        f"{'INCLUDE DESCENDANTS' if session.source_include_descendants else 'SELECTED GRAPH ONLY'}"
        " · TARGET "
        f"{'INCLUDE DESCENDANTS' if session.target_include_descendants else 'SELECTED GRAPH ONLY'}"
    )
    if session.goal_focus is not None:
        typer.echo(
            "GOAL FOCUS · "
            f"{session.goal_focus.kind} · {session.goal_focus.label} · "
            f"{len(session.goal_focus.items)} ITEM"
            f"{'S' if len(session.goal_focus.items) != 1 else ''} · "
            "RELEVANCE ONLY"
        )
    if session.granted_target is not None:
        required_uses = required_update_context_uses(session.operations)
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
        granted = set(session.granted_target.permissions)
        ready = set(required).issubset(granted)
        typer.echo(
            "GRANTED TARGET · "
            f"{session.granted_target.public_name} · "
            f"grant {session.granted_target.grant_uid[:8]} "
            f"revision {session.granted_target.grant_revision}"
        )
        typer.echo("REQUIRED TO APPLY · " + " + ".join(required))
        typer.echo("GRANT PERMISSIONS · " + ("READY" if ready else "BLOCKED"))
    elif applied and session.operations:
        typer.echo("RECOVERY · mem undo")
    if not session.operations:
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
    if applied:
        if session.granted_target is not None:
            typer.echo(f"Updated granted authority target {session.target_name}.")
            typer.echo(
                "The participant source and fixed study baseline were not changed."
            )
        else:
            typer.echo(f"Updated local working copy {session.target_name}.")
            typer.echo(
                "No shared origin was changed. Contribution still requires "
                "mem push or PR."
            )
    elif staged:
        typer.echo(f"Shared {session.target_name} is unchanged.")
    elif undone:
        typer.echo(f"The recorded Update to {session.target_name} remains undone.")
    else:
        typer.echo("No changes applied.")


def __getattr__(name: str):
    """Preserve historical renderer imports through narrow lazy facades."""

    if name == "render_update_receipt":
        from memcommit.adapters.console.commands.update.receipt import (
            render_update_receipt,
        )

        return render_update_receipt
    if name in {"decide_update_application", "run_update_workbench"}:
        from memcommit.adapters.console.commands.update.workbench.application import (
            decide_update_application,
            run_update_workbench,
        )

        return {
            "decide_update_application": decide_update_application,
            "run_update_workbench": run_update_workbench,
        }[name]
    raise AttributeError(name)
