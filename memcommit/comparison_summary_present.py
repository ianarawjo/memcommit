"""Stable plain-text presentation for lightweight Compare."""

from __future__ import annotations

from memcommit.comparison_summary import ComparisonSummary
from memcommit.interfaces.console.text import display_escape_text


def render_comparison_summary(summary: ComparisonSummary) -> str:
    if not isinstance(summary, ComparisonSummary):
        raise TypeError("Compare summary rendering requires a ComparisonSummary.")
    reference, compared = summary.frames
    lines = [
        (
            "Compare · "
            f"{display_escape_text(reference.context_name)} ↔ "
            f"{display_escape_text(compared.context_name)}"
        ),
        "",
        "COMPARISON",
        f"  {display_escape_text(summary.paragraph.text)}",
    ]
    return "\n".join(lines)


__all__ = ["render_comparison_summary"]
