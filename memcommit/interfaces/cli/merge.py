"""Plain command-line rendering for typed Merge results."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.merge_application import MergeResult
from memcommit.merge_runtime import merge_summary


def render_merge_plain(result: MergeResult) -> None:
    """Render the historical direct Merge success sentence."""

    typer.secho(
        f"Merged '{display_escape_text(result.source_name)}' into "
        f"'{display_escape_text(result.target_name)}': added "
        f"{merge_summary(result.additions)}.",
        fg=typer.colors.GREEN,
    )
