"""Presentation-neutral projection helpers for Summarize adapters."""

from memcommit.operations.summarize.application import SummarizeResult


def summarize_scope_label(result: SummarizeResult) -> str:
    """Return the stable public label for the result's two reach axes."""

    if result.include_descendants and result.follow_embeds:
        return "RECURSIVE"
    if not result.include_descendants and not result.follow_embeds:
        return "DIRECT"
    return "CUSTOM"
