"""Plain command-line projection for one typed Fit result."""

from __future__ import annotations

import typer

from memcommit.fit_application import FitResult
from memcommit.interfaces.fit import fit_result_text


def render_fit_plain(result: FitResult) -> None:
    """Preserve Fit's stable non-interactive document."""

    typer.echo(fit_result_text(result))
