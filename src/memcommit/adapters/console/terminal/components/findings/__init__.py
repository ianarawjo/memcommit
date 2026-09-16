"""Compact read-only browser for model-assisted quality findings."""

from memcommit.adapters.console.terminal.components.findings.document import (
    quality_finding_item_document,
    quality_finding_item_sections,
    quality_find_report_header_text,
)
from memcommit.adapters.console.terminal.components.findings.issue_one_line_presentation import (
    echo_issue_one_line,
    issue_one_line_fragments,
    issue_one_line_text,
)
from memcommit.adapters.console.terminal.components.findings.screen import (
    run_quality_find_browser,
)

__all__ = [
    "echo_issue_one_line",
    "issue_one_line_fragments",
    "issue_one_line_text",
    "quality_finding_item_document",
    "quality_finding_item_sections",
    "quality_find_report_header_text",
    "run_quality_find_browser",
]
