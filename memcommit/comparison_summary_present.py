"""Stable plain-text presentation for lightweight Compare."""

from __future__ import annotations

from memcommit.comparison_summary import ComparisonSummary
from memcommit.interfaces.console.text import display_escape_text


def _scope_label(include_descendants: bool) -> str:
    return "CURRENT + DESCENDANTS" if include_descendants else "CURRENT ONLY"


def render_comparison_summary(summary: ComparisonSummary) -> str:
    if not isinstance(summary, ComparisonSummary):
        raise TypeError("Compare summary rendering requires a ComparisonSummary.")
    reference, compared = summary.frames
    lines = [
        "MEM COMPARE · SUMMARY",
        f"REFERENCE · {display_escape_text(reference.context_name)}",
        f"PEER · {display_escape_text(compared.context_name)}",
        "STATUS · READ-ONLY · TRANSIENT · NO RELATION LEDGER",
        (
            "SCOPE · "
            f"REFERENCE {_scope_label(summary.include_descendants[0])} · "
            f"PEER {_scope_label(summary.include_descendants[1])} · "
            f"SOURCES {summary.source_count:,}"
        ),
        "",
        "OVERVIEW",
        display_escape_text(summary.overview.text),
    ]
    for label, section in (
        ("BOTH", summary.reports.both),
        ("DIFFERENCES", summary.reports.differences),
        ("REFERENCE ONLY", summary.reports.reference_only),
        ("PEER ONLY", summary.reports.compared_only),
    ):
        if section.text:
            lines.extend(("", label, display_escape_text(section.text)))
    lines.extend(
        (
            "",
            (
                "Deep relation analysis is available with mem compare --ledger "
                "or when Meld requires an exhaustive basis."
            ),
        )
    )
    return "\n".join(lines)


__all__ = ["render_comparison_summary"]
