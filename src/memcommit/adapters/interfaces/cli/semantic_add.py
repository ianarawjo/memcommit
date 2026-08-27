"""Human-first completion projection for semantic Memory additions."""

from __future__ import annotations

from collections.abc import Sequence

import typer

from memcommit.adapters.console.text import display_escape_text
from memcommit.adapters.console.theme import memory_object_color_rgb


APPLIED_MEMORY_PREVIEW_LIMIT = 20


def applied_memory_preview_lines(
    memory_uids: Sequence[str],
    contents: Sequence[str],
    *,
    limit: int = APPLIED_MEMORY_PREVIEW_LIMIT,
) -> tuple[str, ...]:
    """Show the exact added Memories while keeping large receipts scannable."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("Applied Memory preview limit must be positive.")
    if len(memory_uids) != len(contents):
        # UID/content position is the human-visible proof of what the atomic
        # Add published, so a partial or shifted pairing must never render.
        raise ValueError("Applied Memory identities and contents must align.")
    if not memory_uids:
        raise ValueError("Applied Memory preview requires at least one Memory.")

    lines: list[str] = []
    for uid, content in zip(memory_uids[:limit], contents[:limit], strict=True):
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError("Applied Memory identity must be nonblank text.")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Applied Memory content must be nonblank text.")
        one_line_content = display_escape_text(" ".join(content.split()))
        lines.append(f"  [memory {uid[:8]}] {one_line_content}")

    remaining = len(memory_uids) - min(len(memory_uids), limit)
    if remaining:
        lines.append(f"  … AND {remaining} MORE")
    return tuple(lines)


def render_applied_memory_preview(
    memory_uids: Sequence[str],
    contents: Sequence[str],
    *,
    limit: int = APPLIED_MEMORY_PREVIEW_LIMIT,
) -> None:
    """Print one visually separated completion block."""

    typer.echo("")
    for line in applied_memory_preview_lines(memory_uids, contents, limit=limit):
        typer.secho(line, fg=memory_object_color_rgb())
    typer.echo("")


__all__ = [
    "APPLIED_MEMORY_PREVIEW_LIMIT",
    "applied_memory_preview_lines",
    "render_applied_memory_preview",
]
