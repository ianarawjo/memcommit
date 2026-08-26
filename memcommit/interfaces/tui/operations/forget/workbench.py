"""Forget-specific adapter over the shared Resolution Session shell."""

from __future__ import annotations

from memcommit.application.review_policy import (
    ownership_aware_application_review,
)
from memcommit.operations.forget.application import (
    ForgetSelectionRequest,
    ForgetSessionSnapshot,
    run_forget_selection,
)
from memcommit.operations.forget.review import ForgetSelection
from memcommit.interfaces.tui.workbenches.impact import ImpactController
from memcommit.interfaces.tui.operations.forget.resolution import (
    ForgetResolutionWorkbenchAdapter,
    forget_memory_changes,
)
from memcommit.interfaces.tui.workbenches.resolution import (
    run_resolution_workbench_shell,
)
from memcommit.resolution_workbench import ResolutionNavigation


def run_forget_review_workbench(
    snapshot: ForgetSessionSnapshot,
    *,
    mutates_granted_authority: bool = False,
) -> ForgetSessionSnapshot | None:
    """Review one complete process-local snapshot without provider or Apply."""

    if not snapshot.review.candidates:
        return snapshot
    navigation = ResolutionNavigation()
    current = snapshot
    while True:
        review = current.review
        active_view = ForgetResolutionWorkbenchAdapter(review).view()
        impact_controller = ImpactController.from_memory_changes(
            operation=active_view.operation,
            artifact_uid=active_view.artifact_uid,
            revision=active_view.revision,
            title="IMPACT · PROPOSED SOURCE REVISION",
            summary=(
                "These are the changes Apply would make to the selected "
                "Source. Nothing has changed yet."
            ),
            changes=forget_memory_changes(review),
        )
        action = run_resolution_workbench_shell(
            active_view,
            navigation=navigation,
            terminal_label="Interactive Forget",
            snapshot_hint=(
                "Run 'mem forget INSTRUCTION' in a terminal to review the batch."
            ),
            review_and_apply=True,
            decision_free_behavior=ownership_aware_application_review(
                mutates_granted_authority=mutates_granted_authority,
                local_undo_available=True,
                # An all-KEEP review crosses no Context mutation boundary,
                # even when the Source was reached through a Grant.
                publishes_context_mutation=bool(review.changes()),
            ).decision_free_behavior,
            split_viewer_items=True,
            impact_controller=impact_controller,
            compact_decisions=True,
        )
        if action.kind == "CLOSE":
            return None
        if action.kind == "ACCEPT":
            return current
        if action.kind != "SUBMIT_ITEM" or action.item_uid is None:
            raise ValueError("Unsupported Forget workbench action.")
        if action.comment.strip():
            current = run_forget_selection(
                ForgetSelectionRequest(
                    snapshot=current,
                    candidate_uid=action.item_uid,
                    selection="CUSTOM",
                    custom_content=action.comment.strip(),
                )
            )
            continue
        suffix = (action.option_uid or "").rpartition(":")[2]
        selection: ForgetSelection | None = {
            "recommended": "RECOMMENDED",
            "keep": "KEEP",
            "delete": "DELETE",
        }.get(suffix)  # type: ignore[assignment]
        if selection is None:
            raise ValueError("Unsupported Forget decision.")
        current = run_forget_selection(
            ForgetSelectionRequest(
                snapshot=current,
                candidate_uid=action.item_uid,
                selection=selection,
            )
        )


__all__ = ["run_forget_review_workbench"]
