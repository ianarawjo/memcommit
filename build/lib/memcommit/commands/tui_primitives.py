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
from typing import Callable, Literal

from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_page_down,
    scroll_page_up,
)
from prompt_toolkit.layout import (
    AnyDimension,
    ConditionalContainer,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer, WindowRenderInfo
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea


ScrollAnchor = Literal["preserve", "start", "end"]
InlineEditSubmissionKind = Literal["NOOP", "DIRECT", "COMMENT", "BOTH"]

INLINE_DIRECT_EDIT_TITLE = "EDIT (DIRECTLY)"
INLINE_AGENT_COMMENT_TITLE = "COMMENT (FOR THE AGENT)"

_BUFFER_SERIAL = count(1)

# Focus belongs to terminal chrome, not to the semantic panel title. Nested
# selectors color only the frame border/label and leave its content unchanged.
MEMCOMMIT_TUI_STYLE = Style.from_dict(
    {
        "memcommit.focused frame.border": "fg:#8bd5ff bold",
        "memcommit.focused frame.label": "fg:#8bd5ff bold",
        "memcommit.notification": "fg:#f5a97f bold",
        "memcommit.table.selected": "reverse bold",
    }
)


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
    scrollbar_margin: WrappedScrollbarMargin | None = None
    presentation_container: AnyContainer | None = None

    @property
    def container(self) -> AnyContainer:
        """Return the presentation container used in a layout."""
        return self.presentation_container or self.frame

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


@dataclass(frozen=True)
class InFrameInputSection:
    """One labeled field embedded below a pane's read surface.

    ``allow_read_only`` is reserved for visibly locked direct-edit fields; a
    normal conversational composer must remain writable.
    """

    title: str
    text_area: TextArea
    height: AnyDimension = None
    allow_read_only: bool = False


@dataclass(frozen=True)
class _PaneBaseLayout:
    body: AnyContainer
    height: AnyDimension


class InFrameInputManager:
    """Move writable fields among read panes without nesting another Frame.

    One manager owns one set of live pane containers. Attaching a field first
    restores the previous host, because prompt-toolkit must not see the same
    writable ``TextArea`` through two live layout branches at once. This lets
    operation shells reuse a single Message buffer while keeping each
    conversation visually inside the semantic pane it currently concerns.
    """

    def __init__(self, *panes: ScrollableTextPane) -> None:
        if not panes:
            raise ValueError("at least one pane is required")
        if len({id(pane) for pane in panes}) != len(panes):
            raise ValueError("panes must be distinct")
        self._panes = {id(pane): pane for pane in panes}
        self._base = {
            id(pane): _PaneBaseLayout(
                body=pane.frame.body,
                height=pane.frame.container.height,
            )
            for pane in panes
        }
        self._active_pane: ScrollableTextPane | None = None
        self._active_sections: tuple[InFrameInputSection, ...] = ()

    @property
    def active_pane(self) -> ScrollableTextPane | None:
        """Return the pane currently hosting writable fields, if any."""
        return self._active_pane

    @property
    def active_sections(self) -> tuple[InFrameInputSection, ...]:
        """Return the currently embedded fields in display order."""
        return self._active_sections

    def show(
        self,
        pane: ScrollableTextPane,
        *sections: InFrameInputSection,
        height: AnyDimension = None,
    ) -> None:
        """Show zero or more labeled inputs inside ``pane``'s outer Frame.

        Passing no sections is equivalent to :meth:`clear`. ``height``
        temporarily replaces the pane's outer height and is restored exactly
        when the inputs move or close.
        """
        if id(pane) not in self._panes:
            raise ValueError("pane is not registered with this manager")
        if not sections:
            self.clear()
            return

        text_areas = [section.text_area for section in sections]
        if len({id(text_area) for text_area in text_areas}) != len(text_areas):
            raise ValueError("input TextAreas must be distinct")
        if any(
            section.text_area.buffer.read_only()
            and not section.allow_read_only
            for section in sections
        ):
            raise ValueError("embedded input TextAreas must be writable")
        if pane.text_area in text_areas:
            raise ValueError("a pane's read TextArea cannot be its input")

        self.clear()
        children: list[AnyContainer] = [pane.text_area]
        for section in sections:
            children.extend(
                [
                    Window(
                        FormattedTextControl(
                            display_escape_text(section.title)
                        ),
                        height=1,
                        char="─",
                        style="class:embedded-input.separator",
                    ),
                    HSplit(
                        [section.text_area],
                        height=section.height,
                    ),
                ]
            )
        pane.frame.body = HSplit(children)
        if height is not None:
            pane.frame.container.height = height
        self._active_pane = pane
        self._active_sections = tuple(sections)

    def clear(self) -> None:
        """Detach all inputs and restore the active pane's original layout."""
        pane = self._active_pane
        if pane is None:
            return
        base = self._base[id(pane)]
        pane.frame.body = base.body
        pane.frame.container.height = base.height
        self._active_pane = None
        self._active_sections = ()


class WrappedScrollbarMargin(ScrollbarMargin):
    """A scrollbar whose thumb follows wrapped visual rows.

    prompt-toolkit's stock margin measures logical lines, so the thumb stays
    at the top when a single long line is paged within its wrapped rows. Ground
    panes are prose surfaces, where that misleading motion is common.
    """

    def __init__(self, *, display_arrows: bool = True) -> None:
        super().__init__(display_arrows=display_arrows)
        self._revision = 0
        self._height_cache: dict[
            tuple[int, int, int], tuple[int, ...]
        ] = {}

    def invalidate(self) -> None:
        """Forget cached visual heights after trusted pane text changes."""
        self._revision += 1
        self._height_cache.clear()

    def _line_heights(
        self,
        render_info: WindowRenderInfo,
    ) -> tuple[int, ...]:
        key = (
            self._revision,
            render_info.window_width,
            render_info.content_height,
        )
        cached = self._height_cache.get(key)
        if cached is not None:
            return cached
        heights = tuple(
            max(1, render_info.get_height_for_line(line_number))
            for line_number in range(render_info.content_height)
        )
        self._height_cache[key] = heights
        return heights

    def create_margin(
        self,
        window_render_info: WindowRenderInfo,
        width: int,
        height: int,
    ) -> StyleAndTextTuples:
        """Render a visual-row-aware thumb for wrapped read-only prose."""
        del width, height
        display_arrows = self.display_arrows()
        track_height = window_render_info.window_height
        if display_arrows:
            track_height -= 2
        if track_height <= 0:
            return []

        line_heights = self._line_heights(window_render_info)
        total_height = sum(line_heights)
        viewport_height = min(
            total_height,
            window_render_info.window_height,
        )
        logical_start = window_render_info.vertical_scroll
        visual_offset = (
            sum(line_heights[:logical_start])
            + window_render_info.window.vertical_scroll_2
        )
        scrollable_height = max(0, total_height - viewport_height)
        visual_offset = min(max(0, visual_offset), scrollable_height)
        thumb_height = min(
            track_height,
            max(1, int(track_height * viewport_height / total_height)),
        )
        thumb_top = (
            0
            if scrollable_height == 0
            else round(
                (track_height - thumb_height)
                * visual_offset
                / scrollable_height
            )
        )

        result: StyleAndTextTuples = []
        if display_arrows:
            result.extend(
                [
                    ("class:scrollbar.arrow", self.up_arrow_symbol),
                    ("class:scrollbar", "\n"),
                ]
            )
        for row in range(track_height):
            in_thumb = thumb_top <= row < thumb_top + thumb_height
            next_in_thumb = thumb_top <= row + 1 < thumb_top + thumb_height
            if in_thumb:
                style = (
                    "class:scrollbar.button"
                    if next_in_thumb
                    else "class:scrollbar.button,scrollbar.end"
                )
            else:
                style = (
                    "class:scrollbar.background,scrollbar.start"
                    if next_in_thumb
                    else "class:scrollbar.background"
                )
            result.extend([(style, " "), ("", "\n")])
        if display_arrows:
            result.append(
                ("class:scrollbar.arrow", self.down_arrow_symbol)
            )
        return result


def bind_focused_frame_style(
    frame: Frame,
    *,
    is_focused: Callable[[], bool],
) -> None:
    """Render one focused border in bold light blue without changing labels."""

    base_style = frame.container.style

    def focused_style() -> str:
        resolved = base_style() if callable(base_style) else base_style
        return (
            f"{resolved} class:memcommit.focused"
            if is_focused()
            else resolved
        )

    frame.container.style = focused_style


def scroll_wrapped_page(event: object, *, direction: int) -> None:
    """Move one visual page in the currently focused wrapped read pane.

    prompt-toolkit's stock PageUp/PageDown operates on logical document rows.
    A long wrapped paragraph is one such row, so the stock binding cannot move
    inside it. The last render already exposes visual-row-to-document
    coordinates, including the next/previous off-screen page; use those first
    and retain the stock behavior as a logical-line fallback.
    """
    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    app = getattr(event, "app")
    window = app.layout.current_window
    buffer = app.current_buffer
    render_info = window.render_info if window is not None else None
    if render_info is None:
        return

    page_height = max(1, render_info.window_height)
    mapping = render_info.visible_line_to_row_col
    if direction > 0:
        candidates = [row for row in mapping if row >= page_height]
        visual_row = min(candidates) if candidates else None
    else:
        candidates = [row for row in mapping if row <= -page_height]
        visual_row = max(candidates) if candidates else None

    if visual_row is not None:
        row, column = mapping[visual_row]
        target = buffer.document.translate_row_col_to_index(row, column)
        if target != buffer.cursor_position:
            buffer.cursor_position = target
            app.invalidate()
            return

    if direction > 0:
        scroll_page_down(event)
    else:
        scroll_page_up(event)
    app.invalidate()


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
    notification: Callable[[], bool] | None = None,
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
    scrollbar_margin = WrappedScrollbarMargin(display_arrows=True)
    text_area.window.right_margins = [scrollbar_margin]
    frame = Frame(
        text_area,
        title=display_escape_text(title),
        style=frame_style,
        height=height if height is not None else equal_pane_height(),
    )
    presentation_container: AnyContainer | None = None
    if notification is not None:
        # Frame centers its title between flexible border fills. A one-cell
        # float keeps the notification at the physical right edge without
        # padding the title, so terminal resizes and wide glyphs cannot move
        # it. The semantic unread state remains owned by the calling shell.
        badge = ConditionalContainer(
            Window(
                FormattedTextControl(
                    [("class:memcommit.notification", "●")]
                ),
                width=Dimension.exact(1),
                height=Dimension.exact(1),
                dont_extend_width=True,
                dont_extend_height=True,
            ),
            filter=Condition(notification),
        )
        presentation_container = FloatContainer(
            content=frame,
            floats=[
                Float(
                    content=badge,
                    top=0,
                    right=2,
                    width=1,
                    height=1,
                )
            ],
        )
    return ScrollableTextPane(
        frame=frame,
        text_area=text_area,
        scrollbar_margin=scrollbar_margin,
        presentation_container=presentation_container,
    )


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
    if pane.scrollbar_margin is not None:
        pane.scrollbar_margin.invalidate()

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


def build_inline_direct_edit_input(
    *,
    text: str = "",
    buffer_name: str | None = None,
    height: AnyDimension = None,
) -> FramedMultilineInput:
    """Build the exact-text half of a pane-local edit/comment exchange.

    The companion comment field is the operation's existing Message composer,
    temporarily moved next to this field and retitled. Reusing that composer
    keeps the interaction visually conversational without adding enough rows
    to hide another workbench pane on a 24-row terminal.
    """
    return build_framed_multiline_input(
        INLINE_DIRECT_EDIT_TITLE,
        text=text,
        prompt="> ",
        buffer_name=buffer_name,
        height=(
            height
            if height is not None
            else Dimension(min=3, preferred=3, max=4)
        ),
    )


def classify_inline_edit_submission(
    *,
    original: str,
    edited: str,
    comment: str,
) -> InlineEditSubmissionKind:
    """Classify one pane-local exchange without inferring user intent.

    The prefilled edit buffer is not itself a direct edit. Only a byte-level
    change to that field counts; this prevents a comment-only turn from
    accidentally freezing a redundant mutation command.
    """
    direct = edited != original
    agent_comment = bool(comment.strip())
    if direct and agent_comment:
        return "BOTH"
    if direct:
        return "DIRECT"
    if agent_comment:
        return "COMMENT"
    return "NOOP"


def build_tui_frame(*regions: TuiRegion) -> HSplit:
    """Compose operation-owned regions into one full-screen vertical frame."""
    children: list[AnyContainer] = []
    for region in regions:
        if region.separator_before:
            children.append(Window(height=1, char="─"))
        children.append(region.container)
    return HSplit(children)


def dispatch_tui_back(
    event: object,
    *steps: Callable[[object], bool],
    close: Callable[[object], None],
) -> None:
    """Unwind one visible UI layer, or delegate closing to the operation.

    The shared layer deliberately owns neither persistence nor the result
    returned by ``Application.exit``. Each callback is tried deepest-first;
    the first callback returning true consumes this Escape press. When no
    presentation layer can retreat, the operation-owned ``close`` callback
    preserves that command's cancellation and concurrency semantics.
    """
    for step in steps:
        if step(event):
            getattr(event, "app").invalidate()
            return
    close(event)


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
