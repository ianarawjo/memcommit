"""Interactive Update Impact and exact report decision surfaces."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from memcommit.adapters.console.commands.update.render import _view
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    run_resolution_workbench_shell,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    update_operation_change,
)
from memcommit.application.operations.update.model import (
    UpdateSession,
)


def _impact_controller(
    view,
    session: UpdateSession,
    *,
    summary: str,
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


def decide_update_application(
    session: UpdateSession,
    *,
    analysis_origin: str | None = None,
) -> Literal["APPLY", "DECLINE"] | None:
    """Choose Apply or Decline against the exact report; never revise it."""

    view = replace(
        _view(session, staged=True, applied=False),
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
        capabilities=frozenset({"ACCEPT", "DECLINE"}),
        accept_enabled=True,
    )
    action = run_resolution_workbench_shell(
        view,
        terminal_label="Decide staged Update report",
        snapshot_hint=(
            "Run 'mem update --to TARGET' in a TTY to decide the staged report."
        ),
        split_viewer_items=True,
        report_decision=True,
        impact_controller=_impact_controller(
            view,
            session,
            summary=(
                "These exact target changes are staged. Choose Apply or Decline; "
                "this surface does not revise the proposal."
            ),
        ),
    )
    if action.kind == "ACCEPT":
        return "APPLY"
    if action.kind == "DECLINE":
        return "DECLINE"
    return None


__all__ = ["decide_update_application", "run_update_workbench"]
