"""Read-only Atomize report adapter for ``mem review atomize``."""

from __future__ import annotations

import copy
from dataclasses import replace

from memcommit.adapters.console.commands.semantic_updates.derive.atomize.records import (
    load_saved_atomize_analysis,
    revalidate_saved_atomize_analysis,
)
from memcommit.adapters.console.commands.operation_lifecycle.review.report import show_operation_review
from memcommit.adapters.console.terminal.components.result import (
    render_result_workbench_snapshot,
)
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.semantic_updates.derive.atomize.resolution_adapter import (
    AtomizeResolutionWorkbenchAdapter,
)
from memcommit.application.operations.semantic_updates.derive.atomize.result_adapter import (
    AtomizeResultWorkbenchAdapter,
)
from memcommit.application.operations.semantic_updates.derive.atomize.records import (
    AtomizeReviewRecord,
    atomize_review_issue_projection,
    create_atomize_review_record,
)
from memcommit.application.operations.semantic_updates.derive.atomize.runtime import (
    atomize_application_checkpoint_uid,
)
from memcommit.application.operations.operation_lifecycle.review.model import ReviewError
from memcommit.persistence.store import MemoryStore


def atomize_review_report(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeReviewRecord,
) -> ReviewReportController:
    """Expose terminal Atomize evidence without response or Apply controls."""

    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    if workbench.application is not None:
        result_view = replace(result_view, status="APPLIED ANALYSIS")

    adapter = AtomizeResolutionWorkbenchAdapter(analysis, workbench)

    def review_view():
        projected = adapter.view()
        return replace(
            projected,
            title="MEM REVIEW · ATOMIZE",
            route=f"CONTEXT {analysis.context_name}",
            status="APPLIED RECORD · READ ONLY",
            context_locations=projected.context_locations[:1],
        )

    return ReviewReportController.from_resolution(
        review_view,
        kind="READ_ONLY",
        title="MEM REVIEW · ATOMIZE",
        summary=(
            "Inspect the completed atomization and its recorded issues. "
            "Review does not collect responses, reanalyze, or change Memories."
        ),
        report_text=render_result_workbench_snapshot(result_view),
    )


def _load_direct_context(
    store: MemoryStore,
    context_name: str | None,
    *,
    current_name: str | None,
):
    selected_name = context_name if context_name is not None else current_name
    if not selected_name:
        raise RuntimeError(
            "No current context. Pass --context or run 'mem init <name>' first."
        )
    return store.load_direct(selected_name)


def open_atomize_review(
    *,
    store: MemoryStore,
    context_name: str | None,
    current_name: str | None,
    snapshot: bool,
    expected_analysis_uid: str | None = None,
) -> None:
    """Open only the terminal evidence of one completed Atomize run."""

    if expected_analysis_uid is not None:
        selected_analysis = load_saved_atomize_analysis(store, expected_analysis_uid)
        expected_analysis_uid = selected_analysis.uid
        context_name = selected_analysis.context_name
    ctx = _load_direct_context(store, context_name, current_name=current_name)
    analysis = store.load_atomize_analysis(ctx.uid)
    if analysis is None:
        raise ReviewError(
            "No saved atomize analysis exists for this Context. Run "
            "'mem atomize' first."
        )
    if expected_analysis_uid is not None and analysis.uid != expected_analysis_uid:
        raise ReviewError(
            "The selected atomize analysis changed while the Review launcher "
            "was open. Reopen the launcher."
        )
    try:
        ctx, applied = revalidate_saved_atomize_analysis(store, analysis)
    except ValueError as error:
        raise ReviewError(str(error)) from error
    if not applied:
        raise ReviewError(
            "Atomize execution is not complete. Resume it with 'mem atomize'; "
            "Review opens only terminal application evidence."
        )

    workbench = store.load_atomize_workbench(analysis)
    if workbench is None:
        workbench = create_atomize_review_record(analysis)
    if workbench.application is None:
        checkpoint_uid = atomize_application_checkpoint_uid(store, ctx, analysis.uid)
        if checkpoint_uid is None:
            raise ReviewError(
                "The applied Atomize analysis has no recognized checkpoint."
            )
        # Some historical applied outputs have no workbench receipt. Rebuild a
        # process-local view without repairing or rewriting durable history.
        workbench = copy.deepcopy(workbench)
        workbench.record_application(
            output_context_name=analysis.context_name,
            checkpoint_uid=checkpoint_uid,
        )
    if not workbench.matches_analysis(
        analysis_uid=analysis.uid,
        context_uid=analysis.context_uid,
        context_name=analysis.context_name,
        context_digest=analysis.context_digest,
        issues=atomize_review_issue_projection(analysis),
    ):
        raise ReviewError("The saved atomize workbench does not match its analysis.")

    show_operation_review(
        atomize_review_report(analysis, workbench),
        snapshot=snapshot,
    )


__all__ = ["atomize_review_report", "open_atomize_review"]
