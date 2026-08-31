"""Human-readable console receipt for a completed Embed."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.embed.application import (
    EmbedPlacement,
    EmbedResult,
    MemoryEmbedResult,
)


def _gap_description(placement: EmbedPlacement) -> str:
    if placement.previous_uid is not None and placement.next_uid is not None:
        return f"between [{placement.previous_uid[:8]}] and [{placement.next_uid[:8]}]"
    if placement.next_uid is not None:
        return f"before [{placement.next_uid[:8]}] at the start"
    if placement.previous_uid is not None:
        return f"after [{placement.previous_uid[:8]}] at the end"
    return "as the only direct item"


def render_embed_plain(result: EmbedResult | MemoryEmbedResult) -> None:
    """Render the established compact success line from a typed receipt."""

    if isinstance(result, MemoryEmbedResult):
        typer.secho(
            f"Embedded Memory [{result.memory_uid[:8]}] from "
            f"'{display_escape_text(result.source_name)}' as "
            f"[{result.embed_uid[:8]}] in "
            f"'{display_escape_text(result.into_name)}' "
            f"{_gap_description(result.placement)}.",
            fg=typer.colors.GREEN,
        )
        return
    typer.secho(
        f"Embedded '{display_escape_text(result.child_name)}' into "
        f"'{display_escape_text(result.into_name)}' "
        f"{_gap_description(result.placement)}.",
        fg=typer.colors.GREEN,
    )


__all__ = ["render_embed_plain"]
