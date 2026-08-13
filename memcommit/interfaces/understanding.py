"""Shared plain-text projection for one understanding-summary unit."""

from memcommit.interfaces.console.text import display_escape_text
from memcommit.understanding import UnderstandingSummary


def understanding_lines(
    summary: UnderstandingSummary,
    *,
    heading: str = "WHAT MEM UNDERSTOOD",
) -> list[str]:
    """Render the common semantic unit without operation-specific sections."""

    return [heading, display_escape_text(summary.text)]
