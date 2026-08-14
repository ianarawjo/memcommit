"""Plain command-line rendering for typed Merge results."""

from __future__ import annotations

import typer

from memcommit.interfaces.console.text import display_escape_text
from memcommit.merge_application import MergeReach, MergeResult
from memcommit.merge_runtime import merge_summary


def render_merge_plain(result: MergeResult) -> None:
    """Preserve direct output while reporting recursive tree reach explicitly."""

    if result.reach is MergeReach.DESCENDANTS:
        created = sum(context.target_created for context in result.contexts)
        context_count = len(result.contexts)
        checkpoint_count = len(result.checkpoint_uids)
        context_noun = "Context" if context_count == 1 else "Contexts"
        checkpoint_noun = "checkpoint" if checkpoint_count == 1 else "checkpoints"
        typer.secho(
            f"Recursively merged '{display_escape_text(result.source_name)}' into "
            f"'{display_escape_text(result.target_name)}': "
            f"{context_count} {context_noun}, {created} created; added "
            f"{merge_summary(result.additions)}; "
            f"{checkpoint_count} {checkpoint_noun}.",
            fg=typer.colors.GREEN,
        )
        return
    typer.secho(
        f"Merged '{display_escape_text(result.source_name)}' into "
        f"'{display_escape_text(result.target_name)}': added "
        f"{merge_summary(result.additions)}.",
        fg=typer.colors.GREEN,
    )
