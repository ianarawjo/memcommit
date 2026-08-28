"""Prompt-toolkit cursor anchors for block-oriented viewports."""

from collections.abc import Sequence


def anchored_fragments(
    blocks: Sequence[str],
    *,
    anchor_index: int | None,
    anchor_at_end: bool = False,
) -> list[tuple[str, str]]:
    """Render text blocks with one prompt-toolkit viewport anchor."""
    fragments: list[tuple[str, str]] = []
    for index, block in enumerate(blocks):
        if index:
            fragments.append(("", "\n\n"))
        if index == anchor_index and not anchor_at_end:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(("", block))
        if index == anchor_index and anchor_at_end:
            fragments.append(("[SetCursorPosition]", ""))
    if anchor_index is None:
        fragments.append(("[SetCursorPosition]", ""))
    return fragments
