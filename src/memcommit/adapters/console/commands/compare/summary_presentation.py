"""Console presentation for lightweight Compare."""

from __future__ import annotations

from memcommit.application.operations.compare.summary import ComparisonSummary
from memcommit.adapters.console.text import display_escape_text


def render_comparison_summary(summary: ComparisonSummary) -> str:
    """Render the bounded line-oriented result for lightweight Compare."""

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
