"""Project a Summarize result into the shared semantic Viewer contract."""

from __future__ import annotations

from memcommit.interfaces.console.text import safe_terminal_text
from memcommit.interfaces.summarize import summarize_scope_label
from memcommit.interfaces.tui.viewers.semantic import (
    SemanticViewerBlock,
    SemanticViewerDocument,
    SemanticViewerSection,
)
from memcommit.summarize_application import SummarizeResult


def project_summarize_result(result: SummarizeResult) -> SemanticViewerDocument:
    """Return a typed read-only document without reparsing CLI output."""

    if not isinstance(result, SummarizeResult):
        raise TypeError("Summarize TUI requires a SummarizeResult.")
    return SemanticViewerDocument(
        (
            SemanticViewerSection(
                "SUMMARY:TITLE",
                "TITLE",
                SemanticViewerBlock(
                    (
                        (
                            "class:title",
                            f" SUMMARY · {safe_terminal_text(result.context_name)}\n",
                        ),
                    )
                ),
            ),
            SemanticViewerSection(
                "SUMMARY:STATUS",
                "STATUS",
                SemanticViewerBlock(
                    (
                        (
                            "class:report-label",
                            " STATUS · READ-ONLY · "
                            f"{summarize_scope_label(result)} · "
                            f"SOURCES {result.source_count:,}\n",
                        ),
                    )
                ),
            ),
            SemanticViewerSection(
                "SUMMARY:UNDERSTANDING",
                "UNDERSTANDING",
                SemanticViewerBlock(
                    (
                        ("class:section", "\n WHAT MEM UNDERSTOOD\n"),
                        (
                            "class:viewer-body",
                            f" {safe_terminal_text(result.understanding.text)}\n",
                        ),
                    ),
                    focus_indices=(0, 1),
                ),
            ),
        )
    )
