"""Presentation-neutral projection helpers for Summarize adapters."""

from memcommit.application.operations.summarize.application import SummarizeResult


def summarize_scope_label(result: SummarizeResult) -> str:
    """Return the stable public label for the result's lexical Context reach."""

    if not result.include_descendants:
        return "DIRECT"
    return "RECURSIVE"
