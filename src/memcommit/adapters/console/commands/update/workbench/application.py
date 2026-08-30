"""Interactive Update Impact and pre-Apply review surfaces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from memcommit.adapters.console.commands.update import (
    command_codec as update_command_review,
)
from memcommit.adapters.console.commands.update.render import _view
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    ResolutionGlobalStrategy,
    run_resolution_workbench_shell,
)
from memcommit.application.capabilities.review_policy import (
    ownership_aware_application_review,
)
from memcommit.application.capabilities.reviewing.memory_diff import (
    update_operation_change,
)
from memcommit.application.operations.update.model import (
    UpdateSession,
    update_session_record_digest,
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


def review_update_application(
    session: UpdateSession,
    *,
    incorporate: Callable[[UpdateSession, str], UpdateSession],
    analysis_origin: str | None = None,
    allow_revision: bool = True,
    require_final_review: bool = False,
) -> UpdateSession | None:
    """Return the exact accepted revision, or ``None`` without applying it.

    Direct interactive ``mem update`` uses ``require_final_review`` because no
    enclosing operation has already reviewed the change. Composing operations
    call Update's application boundary directly and never enter this adapter.
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
        policy = ownership_aware_application_review(
            mutates_granted_authority=current.granted_target is not None,
            local_undo_available=True,
            publishes_context_mutation=bool(current.operations),
        )
        action = run_resolution_workbench_shell(
            view,
            terminal_label="Review staged Update impact",
            snapshot_hint=(
                "Run 'mem update --to TARGET' in a TTY to review Impact before Apply."
            ),
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior=(
                "REPORT_FIRST"
                if require_final_review and current.operations
                else policy.decision_free_behavior
            ),
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
                update_command_review.build_turn_review(
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
            # Direct Update must show the exact plan and command projection,
            # not collapse its only review boundary to a bare APPLY ALL row.
            compact_decisions=not require_final_review,
        )
        if action.kind == "ACCEPT":
            return current
        if action.kind == "SUBMIT_ALL" and allow_revision:
            current = incorporate(current, action.comment)
            analysis_origin = None
            continue
        return None


__all__ = ["review_update_application", "run_update_workbench"]
