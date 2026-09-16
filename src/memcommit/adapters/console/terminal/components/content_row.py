"""Shared one-logical-line projection for numbered terminal content."""

from __future__ import annotations


def render_numbered_content_row(
    number: int,
    content: str,
    *,
    suffix: str,
) -> str:
    """Render complete content before a compact metadata suffix.

    The renderer deliberately has no character-limit option. A terminal may
    wrap the returned logical row to its viewport, but operation content must
    not acquire an ellipsis merely to make a list visually shorter.
    """

    if (
        not isinstance(number, int)
        or isinstance(number, bool)
        or number < 1
    ):
        raise ValueError("Numbered content rows require a positive number.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Numbered content rows require nonblank content.")
    if not isinstance(suffix, str) or not suffix.strip():
        raise ValueError("Numbered content rows require a nonblank suffix.")
    folded_content = " ".join(content.split())
    folded_suffix = " ".join(suffix.split())
    return f"[{number}] {folded_content} — {folded_suffix}"


__all__ = ["render_numbered_content_row"]
