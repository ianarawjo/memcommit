"""Compare-owned projection and loader for ``mem review compare``."""

from __future__ import annotations

from memcommit.adapters.console.commands.compare.presentation import render_comparison
from memcommit.adapters.console.commands.compare.sessions import (
    comparison_session_entries,
    load_saved_comparison,
    revalidate_saved_comparison,
)
from memcommit.adapters.console.commands.review.report import show_operation_review
from memcommit.adapters.console.commands.review.sessions import select_report_session
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.compare.ledger.model import (
    ComparisonAnalysis,
    comparison_canonical_digest,
)
from memcommit.persistence.store import MemoryStore


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


def open_compare_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    selected = select_report_session(
        comparison_session_entries(store),
        kind="compare",
        title="MEM REVIEW · COMPARE REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    analysis = load_saved_comparison(selected.key, store=store)
    revalidate_saved_comparison(store, analysis)
    show_operation_review(compare_review_report(analysis), snapshot=snapshot)


__all__ = ["compare_review_report", "open_compare_review"]
