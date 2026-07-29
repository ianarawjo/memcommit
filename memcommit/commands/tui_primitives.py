"""Small presentation primitives shared by memcommit terminal workbenches.

This module deliberately owns terminal mechanics, not semantic state,
provider prompts, persistence, or operation-specific key meanings.
"""
from __future__ import annotations

import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import count
from typing import Literal

from prompt_toolkit.document import Document
from prompt_toolkit.layout import (
    AnyDimension,
    HSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Frame, TextArea


ScrollAnchor = Literal["preserve", "start", "end"]

_BUFFER_SERIAL = count(1)


def _next_buffer_name(kind: str) -> str:
    """Return an app-safe buffer name when a caller does not supply one."""
    return f"memcommit-{kind}-{next(_BUFFER_SERIAL)}"


@dataclass(frozen=True)
class TuiRegion:
    """One vertical shell region and its presentation boundary."""

    container: AnyContainer
    separator_before: bool = False


@dataclass(frozen=True)
class ScrollableTextPane:
    """A framed, focusable, read-only text viewport with its own buffer.

    Keeping the :class:`~prompt_toolkit.widgets.TextArea` available lets an
    operation put the pane in its focus order without teaching this shared
    primitive what Tab, arrows, or PageUp mean for that operation.
    """

    frame: Frame
    text_area: TextArea

    @property
    def container(self) -> Frame:
        """Return the presentation container used in a layout."""
        return self.frame

    def set_text(self, text: str, *, anchor: ScrollAnchor = "preserve") -> None:
        """Safely replace visible text using the requested viewport anchor."""
        set_scrollable_pane_text(self, text, anchor=anchor)


@dataclass(frozen=True)
class FramedMultilineInput:
    """A bordered writable input region with an independently named buffer."""

    frame: Frame
    text_area: TextArea

    @property
    def container(self) -> Frame:
        """Return the presentation container used in a layout."""
        return self.frame


def equal_pane_height(
    *,
    minimum: int = 4,
    preferred: int | None = None,
    maximum: int | None = None,
    weight: int = 1,
) -> Dimension:
    """Return a height suitable for sibling panes that should share space.

    The dimension belongs on the outer :class:`Frame`, so its border counts
    toward the allocation. Giving sibling frames equivalent dimensions makes
    prompt-toolkit divide remaining rows evenly while still allowing each
    body to scroll independently.
    """
    return Dimension(
        min=minimum,
        preferred=preferred,
        max=maximum,
        weight=weight,
    )


def build_scrollable_text_pane(
    title: str,
    text: str = "",
    *,
    buffer_name: str | None = None,
    height: AnyDimension = None,
    wrap_lines: bool = True,
    focusable: bool = True,
    style: str = "",
    frame_style: str = "",
) -> ScrollableTextPane:
    """Build one independently scrollable, read-only framed component."""
    text_area = TextArea(
        text=safe_terminal_text(text),
        multiline=True,
        focusable=focusable,
        focus_on_click=focusable,
        wrap_lines=wrap_lines,
        read_only=True,
        scrollbar=True,
        style=style,
        name=buffer_name or _next_buffer_name("pane"),
    )
    frame = Frame(
        text_area,
        title=display_escape_text(title),
        style=frame_style,
        height=height if height is not None else equal_pane_height(),
    )
    return ScrollableTextPane(frame=frame, text_area=text_area)


def set_scrollable_pane_text(
    pane: ScrollableTextPane,
    text: str,
    *,
    anchor: ScrollAnchor = "preserve",
) -> None:
    """Replace pane text without accidentally resetting its reading position.

    ``preserve`` retains the cursor and both vertical viewport offsets,
    clamping the cursor if the new text is shorter. ``start`` and ``end`` are
    explicit semantic anchors for replacement content. The buffer is
    intentionally read-only to the person, so trusted rendering code uses
    ``bypass_readonly`` at this one update boundary.
    """
    if anchor not in {"preserve", "start", "end"}:
        raise ValueError("anchor must be 'preserve', 'start', or 'end'")

    safe_text = safe_terminal_text(text)
    buffer = pane.text_area.buffer
    window = pane.text_area.window
    old_cursor = buffer.cursor_position
    old_vertical_scroll = window.vertical_scroll
    old_vertical_scroll_2 = window.vertical_scroll_2
    old_horizontal_scroll = window.horizontal_scroll

    if anchor == "start":
        cursor_position = 0
    elif anchor == "end":
        cursor_position = len(safe_text)
    else:
        cursor_position = min(old_cursor, len(safe_text))

    buffer.set_document(
        Document(safe_text, cursor_position=cursor_position),
        bypass_readonly=True,
    )

    if anchor == "start":
        window.vertical_scroll = 0
        window.vertical_scroll_2 = 0
        window.horizontal_scroll = 0
    elif anchor == "end":
        # The next render clamps this logical-line anchor and, for a wrapped
        # last line, derives the in-line offset needed to expose the cursor.
        window.vertical_scroll = safe_text.count("\n")
        window.vertical_scroll_2 = 0
        window.horizontal_scroll = 0
    else:
        window.vertical_scroll = old_vertical_scroll
        window.vertical_scroll_2 = old_vertical_scroll_2
        window.horizontal_scroll = old_horizontal_scroll


def build_framed_multiline_input(
    title: str,
    *,
    text: str = "",
    prompt: str = "> ",
    buffer_name: str | None = None,
    height: AnyDimension = None,
    scrollbar: bool = True,
    style: str = "",
    frame_style: str = "",
) -> FramedMultilineInput:
    """Build a writable multiline input that reads as one bounded component."""
    text_area = TextArea(
        text=text,
        multiline=True,
        focusable=True,
        focus_on_click=True,
        wrap_lines=True,
        read_only=False,
        scrollbar=scrollbar,
        prompt=prompt,
        style=style,
        name=buffer_name or _next_buffer_name("input"),
    )
    frame = Frame(
        text_area,
        title=display_escape_text(title),
        style=frame_style,
        height=(
            height
            if height is not None
            else Dimension(min=5, preferred=6, max=9)
        ),
    )
    return FramedMultilineInput(frame=frame, text_area=text_area)


def build_tui_frame(*regions: TuiRegion) -> HSplit:
    """Compose operation-owned regions into one full-screen vertical frame."""
    children: list[AnyContainer] = []
    for region in regions:
        if region.separator_before:
            children.append(Window(height=1, char="─"))
        children.append(region.container)
    return HSplit(children)


def require_interactive_terminal(
    operation: str,
    *,
    snapshot_hint: str = "",
) -> None:
    """Fail before opening a full-screen application outside a TTY."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        return
    message = f"{operation} requires a TTY (interactive terminal)."
    if snapshot_hint:
        message += f" {snapshot_hint}"
    raise ValueError(message)


def safe_terminal_text(value: str) -> str:
    """Replace terminal controls while retaining explicit newline/tab layout."""
    result: list[str] = []
    for character in value:
        if character in {"\n", "\t"}:
            result.append(character)
        elif (
            unicodedata.category(character).startswith("C")
            or unicodedata.category(character) in {"Zl", "Zp"}
        ):
            result.append("�")
        else:
            result.append(character)
    return "".join(result)


def display_escape_text(value: str) -> str:
    """Return an injective, single-line representation of untrusted text.

    Exact-command receipts use this stricter boundary because preserving a
    newline, tab, bidi override, or zero-width format character there could
    make one argument look like a second command or a trusted UI heading.
    Backslashes are escaped first so every visible escape remains
    unambiguous; normal printable text, including Korean, stays readable.
    """
    escaped: list[str] = []
    named_controls = {
        "\n": r"\n",
        "\t": r"\t",
        "\r": r"\r",
        "\b": r"\b",
        "\f": r"\f",
        "\v": r"\v",
    }
    for character in value:
        if character == "\\":
            escaped.append(r"\\")
            continue
        if character in named_controls:
            escaped.append(named_controls[character])
            continue
        category = unicodedata.category(character)
        if category.startswith("C") or category in {"Zl", "Zp"}:
            codepoint = ord(character)
            if codepoint <= 0xFF:
                escaped.append(f"\\x{codepoint:02x}")
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
            continue
        escaped.append(character)
    return "".join(escaped)


def anchored_fragments(
    blocks: Sequence[str],
    *,
    anchor_index: int | None,
    anchor_at_end: bool = False,
) -> list[tuple[str, str]]:
    """Render text blocks with one prompt-toolkit viewport anchor.

    A caller chooses the semantically active block. Anchoring after an exact
    command keeps all of that command's wrapped logical line visible whenever
    it fits, while errors and selected issues normally anchor at their start.
    """
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
