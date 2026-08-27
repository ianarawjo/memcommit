"""Plain command-line projection for one typed Fit result."""

from __future__ import annotations

import typer

from memcommit.adapters.console.theme import (
    semantic_color_rgb,
    semantic_judgment_role,
)
from memcommit.adapters.console.commands.fit.presentation import (
    FitReceiptLine,
    fit_receipt_lines,
    proposition_fit_receipt_lines,
)
from memcommit.application.operations.fit.application import FitPropositionsResult, FitResult


def _render_receipt_line(
    line: FitReceiptLine,
    *,
    color: bool | None = None,
) -> None:
    """Style only the trusted judgment token in one typed receipt line."""

    typer.echo(line.before_judgment, nl=False)
    if line.judgment is not None:
        role = semantic_judgment_role(line.judgment)
        if role is None:
            typer.echo(line.judgment, nl=False)
        else:
            typer.secho(
                line.judgment,
                fg=semantic_color_rgb(role),
                bold=True,
                nl=False,
                color=color,
            )
    typer.echo(line.after_judgment)


def render_proposition_fit_plain(
    result: FitPropositionsResult,
    *,
    color: bool | None = None,
) -> None:
    """Print one stable general Fit receipt."""

    for line in proposition_fit_receipt_lines(result):
        _render_receipt_line(line, color=color)


def render_fit_plain(
    result: FitResult,
    *,
    color: bool | None = None,
) -> None:
    """Print Fit's compact summary and current issue relationship blocks."""

    for line in fit_receipt_lines(result):
        _render_receipt_line(line, color=color)
