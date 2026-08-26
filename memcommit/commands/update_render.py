"""Shared terminal rendering for impact and update plans."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import typer

from memcommit.application.review_policy import (
    ownership_aware_application_review,
)
from memcommit.interfaces.tui.workbenches.impact import ImpactController
from memcommit.memory_diff import update_operation_change
from memcommit.commands.resolution_workbench_shell import (
    ResolutionGlobalStrategy,
    render_resolution_workbench_snapshot,
    run_resolution_workbench_shell,
)
from memcommit.operations.update.model import (
    UpdateSession,
    count_operations,
    required_grant_permissions,
    update_session_record_digest,
)
from memcommit.application.interactive_command_review import update_turn_command_review
from memcommit.operations.update.resolution_adapter import (
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
        else "Undone update" if undone else ("Staged update" if staged else "Impact")
    )
    status = (
        "APPLIED"
        if applied
        else "UNDONE" if undone else ("STAGED" if staged else "IMPACT")
    )
    return replace(
        UpdateResolutionWorkbenchAdapter(session).view(),
        title=f"{heading}: {session.source_name} -> {session.target_name}",
        status=status,
    )


def _impact_controller(
    view, session: UpdateSession, *, summary: str
) -> ImpactController:
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


def review_update_application(
    session: UpdateSession,
    *,
    incorporate: Callable[[UpdateSession, str], UpdateSession],
    analysis_origin: str | None = None,
    allow_revision: bool = True,
) -> UpdateSession | None:
    """Return the exact accepted revision, or None when final Apply is closed.

    Normal local Update execution bypasses this surface.  Granted-target
    mutation uses ``allow_revision=False`` so this remains a narrow ownership
    approval instead of reopening semantic opinion submission.
    """

    current = session
    while True:
        view = replace(
            _view(current, staged=True, applied=False),
            status=(
                "STAGED · "
                + (
                    "EXACT PREWARM"
                    if analysis_origin == "EXACT_PREWARM"
                    else (
                        "PROJECTED PREWARM"
                        if analysis_origin == "PROJECTED_PREWARM"
                        else "EQUIVALENT SCOPE PREWARM"
                    )
                )
                + " · PROVIDER NOT CALLED"
                if analysis_origin is not None
                else "STAGED"
            ),
            capabilities=(
                frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"})
                if allow_revision
                else frozenset({"ACCEPT"})
            ),
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
            decision_free_behavior=ownership_aware_application_review(
                mutates_granted_authority=current.granted_target is not None,
                local_undo_available=True,
                publishes_context_mutation=bool(current.operations),
            ).decision_free_behavior,
            global_strategies=(
                (
                    ResolutionGlobalStrategy(
                        "Revise from comments",
                        "SUBMIT_ALL",
                        "Revise the complete Update proposal from saved comments.",
                    ),
                )
                if allow_revision
                else ()
            ),
            impact_controller=_impact_controller(
                view,
                current,
                summary=(
                    "These exact target changes are staged. Apply remains a separate "
                    "explicit action."
                ),
            ),
            turn_command_review=lambda action: (
                update_turn_command_review(
                    source_name=current.source_name,
                    target_name=current.target_name,
                    source_descendants=current.source_include_descendants,
                    target_descendants=current.target_include_descendants,
                    source_memory_uid=current.source_memory_uid,
                    target_memory_uid=current.target_memory_uid,
                    inline_source_content=current.inline_source_content,
                    comment=action.comment,
                    expected_session=update_session_record_digest(current),
                )
                if action.kind == "SUBMIT_ALL"
                else None
            ),
            compact_decisions=True,
        )
        if action.kind == "ACCEPT":
            return current
        if action.kind == "SUBMIT_ALL" and allow_revision:
            current = incorporate(current, action.comment)
            # The revised plan came from a new semantic turn, so the original
            # provider-free cache origin no longer describes what is visible.
            analysis_origin = None
            continue
        return None


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


def render_update_receipt(session: UpdateSession) -> str:
    """Render terminal Update success without reopening its full report."""

    if session.status != "applied" or session.application is None:
        raise ValueError("Update receipt requires an applied session.")
    edits, additions, removals = count_operations(session)
    checkpoints = session.application.checkpoints
    lines = [
        f"UPDATE APPLIED · {session.source_name} → {session.target_name}",
        f"EFFECTS · ADD {additions} · EDIT {edits} · REMOVE {removals}",
        f"RECEIPT · {session.uid}",
    ]
    if not session.operations:
        lines.insert(1, "OUTCOME · NO CHANGE · no Context checkpoint")
    if session.goal_focus is not None:
        lines.append(
            "GOAL FOCUS · "
            f"{session.goal_focus.kind} · {session.goal_focus.label} · "
            f"{len(session.goal_focus.items)} ITEM"
            f"{'S' if len(session.goal_focus.items) != 1 else ''}"
        )
    if checkpoints:
        lines.append(
            "CHECKPOINTS · "
            + " · ".join(
                f"{item.context_name} [{item.checkpoint_uid}]" for item in checkpoints
            )
        )
    lines.append(f"REVIEW · mem review update --session {session.uid}")
    if session.granted_target is None and checkpoints:
        lines.append("RECOVERY · mem undo")
    elif session.granted_target is not None:
        lines.append("RECOVERY · governed by the granted authority owner")
    return "\n".join(lines)


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
