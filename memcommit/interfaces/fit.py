"""Presentation-neutral helpers shared by Fit interface adapters."""

from __future__ import annotations

from memcommit.fit import FitStatus
from memcommit.fit_application import (
    FitPropositionsResult,
    FitResult,
)
from memcommit.interfaces.console.text import safe_terminal_text


FIT_STATUS_ORDER: tuple[FitStatus, ...] = (
    "FIT",
    "CONTRADICTS",
    "UNDERDETERMINED",
    "NOT_APPLICABLE",
)


def proposition_fit_mark(result: FitPropositionsResult) -> str:
    """Project the stable mark for one general YES/MAY/NO verdict."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit marks require a typed result.")
    return {"YES": "✓", "MAY": "?", "NO": "!"}[
        result.analysis.assessment.verdict
    ]


def proposition_fit_summary_line(result: FitPropositionsResult) -> str:
    """Return the compact, role-neutral general Fit judgment."""

    if not isinstance(result, FitPropositionsResult):
        raise TypeError("General Fit summaries require a typed result.")
    assessment = result.analysis.assessment
    return (
        f"{proposition_fit_mark(result)} {assessment.verdict} · "
        f"{safe_terminal_text(assessment.reason)}"
    )


def proposition_fit_result_text(result: FitPropositionsResult) -> str:
    """Return the stable plain projection for one general Fit judgment."""

    return proposition_fit_summary_line(result)


def fit_status_counts(result: FitResult) -> tuple[tuple[FitStatus, int], ...]:
    """Count the stable Fit vocabulary without assigning interface styling."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit status counts require a typed Fit result.")
    return tuple(
        (
            status,
            sum(judgment.status == status for judgment in result.report.judgments),
        )
        for status in FIT_STATUS_ORDER
    )


def fit_mark(result: FitResult, *, status: FitStatus | None = None) -> str:
    """Project freshness and conformance into Fit's compact shared marks."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit marks require a typed Fit result.")
    # A stale judgment must not look currently passing or failing. Its stored
    # classification remains in the immutable receipt, while the public mark
    # asks the person or agent to run Fit again.
    if not result.current:
        return "◷"
    if status is None:
        return "✓" if result.report.issue_count == 0 else "!"
    return "✓" if status == "FIT" else "!"


def fit_fraction(result: FitResult) -> str:
    """Return the fitted Example count without exposing report machinery."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit fractions require a typed Fit result.")
    fitted = sum(
        judgment.status == "FIT" for judgment in result.report.judgments
    )
    return f"{fitted}/{len(result.report.judgments)}"


def fit_summary_line(result: FitResult) -> str:
    """Return Fit's stable one-line non-interactive result."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit summaries require a typed Fit result.")
    return (
        f"{fit_mark(result)} "
        f"{safe_terminal_text(result.report.ground_name)} · "
        f"{fit_fraction(result)}"
    )


def fit_result_lines(result: FitResult) -> tuple[str, ...]:
    """Project the intentionally compact plain result from typed Fit fields."""

    if not isinstance(result, FitResult):
        raise TypeError("Fit presentation requires a typed Fit result.")
    return (fit_summary_line(result),)


def fit_result_text(result: FitResult) -> str:
    """Return Fit's stable one-line plain text."""

    return "\n".join(fit_result_lines(result))
