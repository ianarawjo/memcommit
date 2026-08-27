from __future__ import annotations

from memcommit.commands.review.report import render_review_report_snapshot
from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionWorkbenchView,
)
from memcommit.application.reviewing.report import ReviewReportController


def test_review_report_snapshot_renders_typed_memory_rows() -> None:
    item = ResolutionItem(
        uid="atomize-split",
        kind="ATOMIZE_SPLIT",
        status="APPLIED",
        priority="REVIEW",
        title="SUGGESTED SPLIT 1",
        summary="A composite source was split.",
        role="CHANGE",
        blocks=(
            ResolutionDetailBlock(
                heading="APPLIED CHILD MEMORIES",
                text="",
                memory_rows=(
                    ResolutionMemoryRow(
                        ordinal=1,
                        content="First proposed Memory.",
                        evidence=("First source span.",),
                    ),
                    ResolutionMemoryRow(
                        ordinal=2,
                        content="Second proposed Memory.\nSecond line.",
                        evidence=("Second source span.", "Declared frame."),
                    ),
                ),
            ),
        ),
    )
    view = ResolutionWorkbenchView(
        operation="ATOMIZE",
        artifact_uid="atomize-analysis",
        revision="revision-1",
        title="MEM REVIEW · ATOMIZE",
        route="practice/greetings",
        status="APPLIED",
        metrics=(),
        overview="Applied Atomize analysis.",
        list_label="ITEMS",
        items=(item,),
        empty_message="No items.",
        results_label="RESULTS",
        results=(),
        capabilities=frozenset(),
        accept_enabled=False,
    )
    report = ReviewReportController.from_resolution(
        view,
        kind="RESOLUTION",
        title="MEM REVIEW · ATOMIZE",
        summary="Read-only applied evidence.",
    ).report()

    rendered = render_review_report_snapshot(report)

    assert "  APPLIED CHILD MEMORIES" in rendered
    assert "    MEMORY 1 · First proposed Memory." in rendered
    assert "Evidence ·" not in rendered
    assert "    MEMORY 2 · Second proposed Memory." in rendered
    assert "               Second line." in rendered
