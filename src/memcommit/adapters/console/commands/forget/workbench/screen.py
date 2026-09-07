"""Forget's exact Impact report and Apply boundary over the shared session host."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.operations.forget.application import ForgetSessionSnapshot
from memcommit.adapters.console.commands.impact.projection import ImpactController
from memcommit.adapters.console.commands.forget.workbench.presentation import (
    forget_application_view,
    forget_memory_changes,
)
from memcommit.adapters.console.terminal.components.resolution import (
    run_resolution_workbench_shell,
)


def run_forget_review_workbench(
    snapshot: ForgetSessionSnapshot,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | None:
    """Inspect the frozen batch and return it only after Apply; never mutate it."""

    if not snapshot.review.changes():
        return snapshot
    # Only the presentation uses the public name. The returned snapshot keeps
    # its original owner identity and opaque authority/CAS binding unchanged.
    displayed_review = replace(
        snapshot.review, context_name=snapshot.source.display_name,
    )
    view = forget_application_view(displayed_review)
    ownership = "granted" if mutates_granted_authority else "local"
    action = run_resolution_workbench_shell(
        view,
        terminal_label="Interactive Forget",
        snapshot_hint="Run 'mem forget INSTRUCTION' in a terminal to inspect before Apply.",
        split_viewer_items=True,
        report_apply=True,
        impact_controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · FORGET · SAME SOURCE",
            detail=f"INSTRUCTION · {snapshot.review.instruction}",
            summary=(
                f"These exact changes will update the {ownership} Source. "
                "Apply accepts this batch; Escape cancels without changing the Source."
            ),
            changes=forget_memory_changes(displayed_review),
        ),
    )
    if action.kind == "ACCEPT":
        return snapshot
    if action.kind == "CLOSE":
        return None
    raise ValueError("Unsupported Forget application action.")


__all__ = ["run_forget_review_workbench"]
