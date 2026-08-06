"""Shared terminal rendering for impact and update plans."""
from __future__ import annotations

from dataclasses import replace

import typer

from memcommit.impact_controller import ImpactController
from memcommit.memory_diff import update_operation_change
from memcommit.commands.resolution_workbench_shell import (
    render_resolution_workbench_snapshot,
    run_resolution_workbench_shell,
)
from memcommit.update import (
    UpdateSession,
    count_operations,
    required_grant_permissions,
)
from memcommit.update_resolution_adapter import (
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


def _impact_controller(view, session: UpdateSession, *, summary: str) -> ImpactController:
    """Keep Update Impact aligned with the same changes rendered by mem diff."""

    return ImpactController.from_memory_changes(
        operation=view.operation,
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · UPDATE",
        summary=summary,
        changes=tuple(update_operation_change(item) for item in session.operations),
    )


def run_update_workbench(session: UpdateSession) -> None:
    """Open provider-free drill-down over one already-saved Impact plan."""
    view = _view(session, staged=False, applied=False)
    run_resolution_workbench_shell(
        view,
        terminal_label="Interactive update impact",
        snapshot_hint=(
            "Run the same 'mem impact --to TARGET' command outside a TTY "
            "to render the saved plan."
        ),
        split_viewer_items=True,
        read_only=True,
        impact_controller=_impact_controller(
            view,
            session,
            summary="These are the exact planned target changes. Nothing is applied.",
        ),
    )


def review_update_application(session: UpdateSession) -> bool:
    """Return true only after explicit TTY acceptance of one staged Update."""
    view = replace(
        _view(session, staged=True, applied=False),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )
    action = run_resolution_workbench_shell(
        view,
        terminal_label="Review staged Update impact",
        snapshot_hint=(
            "Run 'mem update --to TARGET' in a TTY to review Impact before Apply."
        ),
        split_viewer_items=True,
        review_and_apply=True,
        impact_controller=_impact_controller(
            view,
            session,
            summary=(
                "These exact target changes are staged. Apply remains a separate "
                "explicit action."
            ),
        ),
    )
    return action.kind == "ACCEPT"


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
    view = _view(session, staged=staged, applied=applied, undone=undone)
    typer.echo(render_resolution_workbench_snapshot(view))
    typer.echo(
        "\nSUMMARY · "
        f"{edits} edit{'s' if edits != 1 else ''}, "
        f"{additions} addition{'s' if additions != 1 else ''}, "
        f"{removals} removal{'s' if removals != 1 else ''}"
    )
    if session.granted_target is not None:
        required = required_grant_permissions(session.operations)
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
            typer.echo(
                f"Updated granted authority target {session.target_name}."
            )
            typer.echo(
                "The participant source and fixed study baseline were not "
                "changed."
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
        typer.echo(
            f"The recorded Update to {session.target_name} remains undone."
        )
    else:
        typer.echo("No changes applied.")
