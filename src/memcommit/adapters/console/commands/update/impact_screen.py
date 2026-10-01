"""Read-only interactive Update Impact."""

from __future__ import annotations

from memcommit.adapters.console.commands.update.effects import (
    update_effect_view,
    update_effect_report,
)
from memcommit.adapters.console.commands.impact.projection import ImpactController
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    run_resolution_workbench_shell,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    update_operation_change,
)
from memcommit.application.operations.update.model import (
    UpdateContextInputs,
    UpdatePlan,
)


def _impact_controller(
    view,
    plan: UpdatePlan,
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
        changes=tuple(update_operation_change(item) for item in plan.operations),
    )


def run_update_impact_screen(inputs: UpdateContextInputs, plan: UpdatePlan) -> None:
    """Open provider-free drill-down over one process-local Impact plan."""

    view = update_effect_view(inputs, plan)
    run_resolution_workbench_shell(
        view,
        terminal_label="Interactive update impact",
        snapshot_hint=(
            "Run the same 'mem impact --to TARGET' command outside a TTY "
            "to render the plan."
        ),
        split_viewer_items=True,
        read_only=True,
        effect_report=update_effect_report(plan),
        impact_controller=_impact_controller(
            view,
            plan,
            summary="These are the exact planned target changes. Nothing is applied.",
        ),
    )


__all__ = ["run_update_impact_screen"]
