"""Operation-owned projections into the common Review report contract."""

from __future__ import annotations

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_resolution_adapter import AtomizeResolutionWorkbenchAdapter
from memcommit.atomize_workbench import AtomizeWorkbenchSession
from memcommit.comparison import ComparisonAnalysis, comparison_canonical_digest
from memcommit.comparison_present import render_comparison
from memcommit.meld import MeldSession
from memcommit.meld_resolution_adapter import MeldResolutionWorkbenchAdapter
from memcommit.review_report import ReviewReportController
from memcommit.sever import SeverSession
from memcommit.sever_resolution_adapter import SeverResolutionWorkbenchAdapter
from memcommit.update import UpdateSession
from memcommit.update_resolution_adapter import UpdateResolutionWorkbenchAdapter


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
    return ReviewReportController.from_resolution(
        SeverResolutionWorkbenchAdapter(session).view,
        kind="CONTENT SEVERING",
        title="MEM REVIEW · SEVER",
        summary=(
            "Review what the local result keeps, rewrites, or forgets. "
            "Review leaves the Source unchanged and creates no result Context."
        ),
    )


def atomize_review_report(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> ReviewReportController:
    """Expose Atomize findings and saved clarification responses."""
    from memcommit.atomize_result_adapter import AtomizeResultWorkbenchAdapter
    from memcommit.interfaces.tui.workbenches.result import (
        render_result_workbench_snapshot,
    )

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
        report_text=render_result_workbench_snapshot(
            AtomizeResultWorkbenchAdapter(analysis).view()
        ),
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
