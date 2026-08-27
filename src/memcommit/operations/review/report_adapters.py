"""Operation-owned projections into the common Review report contract."""

from __future__ import annotations

from dataclasses import replace

from memcommit.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.operations.atomize.resolution_adapter import AtomizeResolutionWorkbenchAdapter
from memcommit.operations.atomize.workbench import AtomizeWorkbenchSession
from memcommit.operations.compare.ledger.model import ComparisonAnalysis, comparison_canonical_digest
from memcommit.interfaces.presentation.comparison import render_comparison
from memcommit.operations.meld.model import MeldSession
from memcommit.operations.meld.resolution_adapter import MeldResolutionWorkbenchAdapter
from memcommit.application.reviewing.report import ReviewReportController
from memcommit.operations.sever.model import SeverSession
from memcommit.operations.sever.resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
)
from memcommit.operations.update.model import UpdateSession
from memcommit.operations.update.resolution_adapter import UpdateResolutionWorkbenchAdapter


def compare_review_report(analysis: ComparisonAnalysis) -> ReviewReportController:
    """Expose the exact saved Compare prose as a read-only Review report."""
    return ReviewReportController.from_text(
        operation="COMPARE",
        artifact_uid=analysis.uid,
        revision=comparison_canonical_digest(analysis.to_dict()),
        kind="READ_ONLY",
        title="MEM REVIEW · COMPARE",
        summary="Saved equal-authority comparison report. No review response is required.",
        report_text=render_comparison(analysis, reused=True, durable=True),
    )


def meld_review_report(session: MeldSession) -> ReviewReportController:
    """Expose Meld analysis, issues, and proposals without its Apply capability."""
    compare_text = ""
    if session.mode == "SYMMETRIC" and session.comparison_seed is not None:
        compare_text = (
            render_comparison(
                session.comparison_seed.analysis,
                reused=True,
                durable=True,
            )
            .partition("\nThe complete source-linked relation ledger")[0]
            .rstrip()
        )
    return ReviewReportController.from_resolution(
        MeldResolutionWorkbenchAdapter(session).view,
        kind="RESOLUTION",
        title="MEM REVIEW · MELD",
        summary=(
            "Review the saved Meld assessment and proposed target Memories. "
            "Applying the target remains outside Review."
        ),
        report_text=compare_text,
    )


def sever_review_report(session: SeverSession) -> ReviewReportController:
    """Expose content-severing decisions and the proposed local result."""
    result_boundary = (
        "The retained local Result has already been created; this Review "
        "does not create or apply it again."
        if session.state == "APPLIED"
        else "Review leaves the Source unchanged and creates no result Context."
    )
    return ReviewReportController.from_resolution(
        SeverResolutionWorkbenchAdapter(session).view,
        kind="CONTENT_SEVERING",
        title="MEM REVIEW · SEVER",
        summary=(
            "Review what the local result keeps, rewrites, or forgets. "
            + result_boundary
        ),
    )


def atomize_review_report(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> ReviewReportController:
    """Expose Atomize findings and saved clarification responses."""
    from memcommit.operations.atomize.result_adapter import AtomizeResultWorkbenchAdapter
    from memcommit.interfaces.tui.workbenches.result import (
        render_result_workbench_snapshot,
    )

    result_view = AtomizeResultWorkbenchAdapter(analysis).view()
    if workbench.application is not None:
        result_view = replace(result_view, status="APPLIED ANALYSIS")

    return ReviewReportController.from_resolution(
        AtomizeResolutionWorkbenchAdapter(analysis, workbench).view,
        kind="CLARIFICATION",
        title="MEM REVIEW · ATOMIZE",
        summary=(
            "Review uncertain findings and their saved clarifications. "
            "Context application remains outside Review."
        ),
        # Atomize's immutable result account and its actionable clarification
        # queue are different layers.  Preserve the former verbatim while the
        # common Review host supplies navigation and response controls for the
        # latter.
        report_text=render_result_workbench_snapshot(result_view),
    )


def update_review_report(session: UpdateSession) -> ReviewReportController:
    """Keep Update's existing exact change-detail report as Review material."""
    return ReviewReportController.from_resolution(
        UpdateResolutionWorkbenchAdapter(session).view,
        kind="CHANGE_PLAN",
        title="MEM REVIEW · UPDATE",
        summary=(
            "Review exact ADD, EDIT, and REMOVE details, reasons, owners, and "
            "source references. Applying the staged plan remains outside Review."
        ),
    )
