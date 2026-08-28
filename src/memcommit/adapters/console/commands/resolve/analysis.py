"""Plain terminal projection for typed Resolve analyses."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.resolve.application import ResolveAnalysis


def _line(label: str, value: str, *, color: str | None = None) -> None:
    typer.secho(
        f"{label} · {display_escape_text(value)}",
        fg=color,
    )


def _title(analysis: ResolveAnalysis) -> None:
    typer.secho(
        f"RESOLVE · {display_escape_text(analysis.frame.display_name)}",
        bold=True,
    )


def render_resolve_plain(analysis: ResolveAnalysis) -> None:
    """Render one compact outcome or externally replayable proposal."""

    _title(analysis)

    if analysis.status == "ALREADY_FIT":
        if analysis.initial_fit is None:
            raise TypeError("An already-Fit Resolve analysis requires its judgment.")
        _line("FIT", f"{analysis.initial_fit.verdict} · NO CHANGE")
        return

    if analysis.status in {"NEEDS_INPUT", "NEEDS_AUTHORITY"}:
        label = analysis.status.replace("_", " ")
        _line(label, analysis.question or "Resolve cannot continue.")
        return

    if analysis.status == "ASSUMED":
        candidate = analysis.candidates[0]
        _line("TEMPORARY INTERPRETATION", candidate.summary)
        for assumption in (
            assumption
            for issue in candidate.issues
            for assumption in issue.assumptions
        ):
            _line("ASSUMPTION", assumption, color=typer.colors.YELLOW)
        if analysis.question:
            _line("NEEDS INPUT", analysis.question)
        _line("NO CHANGE", "Grounding is required before Apply")
        return

    candidate = analysis.candidates[0]
    _line(
        "READY TO APPLY",
        f"{candidate.summary} · FIT {candidate.fit.verdict}",
    )
    _line("CANDIDATE", candidate.uid)
    _line(
        "APPLY",
        "rerun with --candidate <full-id> --expected-revision "
        f"{analysis.frame.revision} --apply",
    )


__all__ = ["render_resolve_plain"]
