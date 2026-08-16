"""Pure plain-text projection shared by semantic clipboard surfaces."""

from __future__ import annotations

from collections.abc import Sequence


FormattedFragments = Sequence[tuple[str, str]]


def plain_text_from_fragments(
    fragments: FormattedFragments,
    *,
    whole_document: bool,
) -> str:
    """Strip styles and project either all text or the anchored semantic unit.

    Two cursor anchors delimit a complete focused unit. A single anchor falls
    back to its visual line, which preserves older report renderers whose
    focus contract exposes only one viewport anchor.
    """

    if not isinstance(whole_document, bool):
        raise TypeError("Plain-text projection mode must be a boolean.")
    text_parts: list[str] = []
    anchors: list[int] = []
    offset = 0
    for fragment in fragments:
        if (
            not isinstance(fragment, tuple)
            or len(fragment) != 2
            or not isinstance(fragment[0], str)
            or not isinstance(fragment[1], str)
        ):
            raise TypeError("Plain-text projection fragments are invalid.")
        style, text = fragment
        if style == "[SetCursorPosition]":
            anchors.append(offset)
            continue
        text_parts.append(text)
        offset += len(text)
    complete = "".join(text_parts)
    if whole_document or not anchors:
        return complete.strip()
    if len(anchors) >= 2 and anchors[-1] > anchors[0]:
        focused = complete[anchors[0] : anchors[-1]].strip()
        if focused:
            return focused
    anchor = min(anchors[0], len(complete))
    line_start = complete.rfind("\n", 0, anchor) + 1
    line_end = complete.find("\n", anchor)
    return complete[line_start : line_end if line_end >= 0 else None].strip()


__all__ = ["FormattedFragments", "plain_text_from_fragments"]
