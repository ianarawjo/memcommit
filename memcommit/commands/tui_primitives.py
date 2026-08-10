"""Small presentation primitives shared by memcommit terminal workbenches.

This module deliberately owns terminal mechanics, not semantic state,
provider prompts, persistence, or operation-specific key meanings.
"""
from __future__ import annotations

import asyncio
import sys
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import count
from time import monotonic
from typing import Callable, Literal

from prompt_toolkit.document import Document
from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, FilterOrBool
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
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
    VSplit,
)
from prompt_toolkit.layout.containers import AnyContainer, WindowRenderInfo
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.commands.tui_text_layout import (
    elide_terminal_text,
    pad_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)
from memcommit.commands.surface_focus import focus_in_order as _focus_in_order


ScrollAnchor = Literal["preserve", "start", "end"]
InlineEditSubmissionKind = Literal["NOOP", "DIRECT", "COMMENT", "BOTH"]

INLINE_DIRECT_EDIT_TITLE = "EDIT (DIRECTLY)"
INLINE_AGENT_COMMENT_TITLE = "COMMENT (FOR THE AGENT)"

_BUFFER_SERIAL = count(1)


def focus_in_order(app, controls: Sequence[object], delta: int, *, wrap: bool) -> bool:
    """Compatibility facade for the shared Surface focus controller."""

    return _focus_in_order(app, controls, delta, wrap=wrap)


def horizontal_rule() -> Window:
    """Return the shared fixed-height separator between terminal regions."""

    return Window(
        height=Dimension.exact(1),
        char="─",
        dont_extend_height=True,
    )


def bind_case_insensitive_key(
    bindings: KeyBindings,
    key: str,
    *,
    filter: FilterOrBool = True,
    eager: FilterOrBool = False,
) -> Callable[
    [Callable[[KeyPressEvent], None]],
    Callable[[KeyPressEvent], None],
]:
    """Bind one alphabetic shortcut in both lowercase and uppercase forms."""

    if len(key) != 1 or not key.isalpha():
        raise ValueError("Case-insensitive shortcuts require one alphabetic key.")
    lower, upper = key.lower(), key.upper()

    def decorator(
        handler: Callable[[KeyPressEvent], None],
    ) -> Callable[[KeyPressEvent], None]:
        # Read-only shortcuts should not change under Shift or Caps Lock. The
        # caller's focus filter still protects writable input from interception.
        bindings.add(lower, filter=filter, eager=eager)(handler)
        bindings.add(upper, filter=filter, eager=eager)(handler)
        return handler

    return decorator


@dataclass
class NavigationAccelerator:
    """Increase held-arrow rate while keeping deliberate taps precise.

    Every accelerated pulse still visits each intermediate row. Terminals do
    not report key-up events, so hold detection requires the characteristic
    initial repeat delay followed by a sustained short cadence. Rapid taps that
    begin immediately, a pause, or a direction change retain one-unit
    navigation in every TUI that adopts it.
    """

    direction: int = 0
    streak: int = 0
    last_at: float | None = None
    repeat_candidate: bool = False
    repeat_interval: float = 0.08
    _animation_generation: int = 0
    _animation_task: asyncio.Task[None] | None = None

    _INITIAL_REPEAT_DELAY_MIN = 0.2
    _INITIAL_REPEAT_DELAY_MAX = 1.2
    _REPEAT_INTERVAL_MAX = 0.16
    _MIN_FRAME_INTERVAL = 1 / 60

    def reset(self) -> None:
        self._animation_generation += 1
        if self._animation_task is not None:
            self._animation_task.cancel()
            self._animation_task = None
        self.direction = 0
        self.streak = 0
        self.last_at = None
        self.repeat_candidate = False

    def step(self, direction: int, *, now: float | None = None) -> int:
        if direction not in {-1, 1}:
            raise ValueError("Navigation direction must be -1 or 1.")
        observed_at = monotonic() if now is None else now
        if self.last_at is None or direction != self.direction:
            self.direction = direction
            self.streak = 0
            self.last_at = observed_at
            self.repeat_candidate = False
            return 1

        interval = observed_at - self.last_at
        self.last_at = observed_at
        if interval < 0:
            self.streak = 0
            self.repeat_candidate = False
        elif self.repeat_candidate and interval <= self._REPEAT_INTERVAL_MAX:
            self.streak += 1
            self.repeat_interval = interval
        else:
            # A real held key normally emits one delayed first repeat. Fast
            # manual taps start with short intervals, so they never arm the
            # accelerator merely by arriving close together.
            self.repeat_candidate = (
                self._INITIAL_REPEAT_DELAY_MIN
                <= interval
                <= self._INITIAL_REPEAT_DELAY_MAX
            )
            self.streak = 0

        if self.streak >= 9:
            return 5
        if self.streak >= 4:
            return 2
        return 1

    def move(
        self,
        direction: int,
        *,
        app,
        move_one: Callable[[int], None],
        now: float | None = None,
    ) -> None:
        """Move now, then animate every additional held-key row in order."""

        multiplier = self.step(direction, now=now)
        self._animation_generation += 1
        generation = self._animation_generation
        if self._animation_task is not None:
            self._animation_task.cancel()
            self._animation_task = None

        move_one(direction)
        app.invalidate()
        if multiplier == 1:
            return

        interval = max(
            self._MIN_FRAME_INTERVAL,
            self.repeat_interval / multiplier,
        )

        async def animate_remaining() -> None:
            try:
                for _ in range(multiplier - 1):
                    await asyncio.sleep(interval)
                    if generation != self._animation_generation:
                        return
                    move_one(direction)
                    app.invalidate()
            finally:
                if generation == self._animation_generation:
                    self._animation_task = None

        self._animation_task = app.create_background_task(animate_remaining())

# Focus belongs to terminal chrome, not to the semantic panel title. A blue
# surface records a retained selection, while bold records the exact nested
# control that currently owns keyboard input. Keeping those signals orthogonal
# makes Tab movement visible without erasing a checked or selected value.
MEMCOMMIT_TUI_STYLE = Style.from_dict(
    {
        "memcommit.focused frame.border": "fg:#8bd5ff bold",
        "memcommit.focused frame.label": "fg:#8bd5ff bold",
        "memcommit.notification": "fg:#f5a97f bold",
        "memcommit.table.selected": "reverse bold",
        "memcommit.control.focused": "bold",
        # The blue surface persists after focus leaves. Bold is added only
        # while that same nested control is the immediate keyboard target.
        "memcommit.choice.active": "fg:#10242f bg:#8bd5ff",
        "memcommit.choice.active.focused": "fg:#10242f bg:#8bd5ff bold",
        "memcommit.choice.border.focused": "fg:#8bd5ff bold",
        # Source badges are available to every shared selector, not only to
        # semantic report viewers. Availability alone carries warning color.
        "source-access": "fg:#f4f5f7 bold",
        "source-reach": "fg:#f4f5f7",
        "source-state": "fg:#f5a97f bold",
    }
)


def focused_control_style(*, focused: bool, selected: bool = False) -> str:
    """Return the shared nested-control focus/selection presentation class."""

    if selected:
        return (
            "class:memcommit.choice.active.focused"
            if focused
            else "class:memcommit.choice.active"
        )
    return "class:memcommit.control.focused" if focused else ""

# Semantic workbenches share presentation vocabulary even when their state
# contracts differ.  A Result viewer is read-only, Compare owns report
# navigation, and Resolution owns choices; keeping these colors here avoids
# implying that one operation also owns another operation's semantics.
SEMANTIC_VIEWER_STYLE = Style.from_dict(
    {
        # Report chrome and explanatory prose stay neutral across semantic and
        # history viewers.  Screens should reuse these roles rather than copy
        # palette values into operation-specific style dictionaries.
        "report-neutral": "fg:#f4f5f7",
        "report-label": "fg:#f4f5f7 bold",
        "report-label.focused": "fg:#8bd5ff bold",
        "viewer-section": "fg:#8bd5ff bold",
        # A section may include its prose in the same focus stop without
        # making explanatory text look like another heading.
        "viewer-body": "fg:#f4f5f7",
        "viewer-body.focused": "fg:#8bd5ff",
        # Skeleton rows describe report shape while content is unavailable.
        # They are deliberately dimmer than prose and must never be confused
        # with a Memory object or a completed semantic result.
        "loading-label": "fg:#8bd5ff bold",
        "loading-status": "fg:#eed49f bold",
        "loading-placeholder": "fg:#5b6078",
        "detail-card": "fg:#ffffff",
        "detail-card.focused": "fg:#8bd5ff bold",
        # Lavender is reserved for actual Memory objects, not report prose.
        "memory-object": "fg:#cad3f5",
        "memory-object.focused": "fg:#8bd5ff bold",
        # Compact semantic references use purple rather than the blue focus
        # color. Memory-shaped reference rows still use memory-object lavender.
        "reference": "fg:#c6a0f6",
        # Impact treatment colors classify the operation applied to one
        # Memory; the surrounding Memory row owns the separate blue focus.
        "impact.keep": "fg:#a6da95 bold",
        "impact.keep.focused": "fg:#a6da95 bold",
        "impact.redact": "fg:#f5a97f bold",
        "impact.redact.focused": "fg:#f5a97f bold",
        "impact.summarize": "fg:#8aadf4 bold",
        "impact.summarize.focused": "fg:#8aadf4 bold",
        "impact.reframe": "fg:#c6a0f6 bold",
        "impact.reframe.focused": "fg:#c6a0f6 bold",
        "impact.forget": "fg:#ed8796 bold",
        "impact.forget.focused": "fg:#ed8796 bold",
        "impact.custom": "fg:#eed49f bold",
        "impact.custom.focused": "fg:#eed49f bold",
        "impact.other": "fg:#cad3f5 bold",
        "impact.other.focused": "fg:#cad3f5 bold",
        # Located mutation kinds use the same compact semantic-tag grammar as
        # Sever treatments without tinting their complete Memory bodies.
        "impact.edit": "fg:#a6da95 bold",
        "impact.edit.focused": "fg:#a6da95 bold",
        "impact.add": "fg:#8aadf4 bold",
        "impact.add.focused": "fg:#8aadf4 bold",
        "impact.remove": "fg:#ed8796 bold",
        "impact.remove.focused": "fg:#ed8796 bold",
        # Long before/after Memory content stays white. Only mechanically
        # removed or added spans receive directional color and an underline;
        # their line position never determines whether text is red or green.
        "memory-diff.remove": "fg:#ffffff",
        "memory-diff.remove.changed": "fg:#ed8796 underline",
        "memory-diff.add": "fg:#ffffff",
        "memory-diff.add.changed": "fg:#a6da95 underline",
        "memory-diff.equal": "fg:#ffffff",
        "memory-diff.equal.changed": "fg:#ffffff underline",
        # Compatibility names for older semantic fragments. Interactive flat
        # choices now use memcommit.selection's shared checked-card styles.
        "option-card": "fg:#ffffff",
        "option-card.focused": "fg:#8bd5ff bold underline",
        "option-card.selected": "fg:#8bd5ff bold",
        "option-card.other": "fg:#8bd5ff bold underline",
        "selection-badge": "fg:#8bd5ff bold",
        "case-title": "fg:#ffffff bold",
        "detail-heading": "fg:#ffffff bold",
        "block-heading": "fg:#ffffff bold",
        "trace": "fg:#8bd5ff",
    }
)


def _next_buffer_name(kind: str) -> str:
    """Return an app-safe buffer name when a caller does not supply one."""
    return f"memcommit-{kind}-{next(_BUFFER_SERIAL)}"


@dataclass(frozen=True)
class ExactNameFieldView:
    """Operation-neutral contract for one exact, single-line name.

    The caller supplies the label, validation, and eventual meaning.  This
    view deliberately does not know whether the value names a Context, Study
    Profile, session, or another domain object.
    """

    value: str
    label: str = "NAME"
    state: str = ""
    detail: str = "Enter to continue with this exact name."
    validate: Callable[[str], object] | None = None
    value_label: str = "Name"
    strip_candidate: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValueError(f"{self.value_label} must be text.")
        for value, label in (
            (self.label, "Name-field label"),
            (self.detail, "Name-field detail"),
            (self.value_label, "Name-field value label"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty text.")
        if any(character in self.value for character in "\r\n"):
            raise ValueError(f"{self.value_label} must stay on one line.")
        if any(character in self.label for character in "\r\n"):
            raise ValueError("Name-field label must stay on one line.")
        if not isinstance(self.state, str) or any(
            character in self.state for character in "\r\n"
        ):
            raise ValueError("Name-field state must be one-line text.")
        if self.validate is not None and not callable(self.validate):
            raise TypeError("Name-field validation must be callable.")
        if not isinstance(self.strip_candidate, bool):
            raise TypeError("Name-field strip policy must be boolean.")

    def validate_value(self, value: str) -> str:
        """Validate one candidate without deciding how it is persisted."""

        if not isinstance(value, str):
            raise ValueError(f"{self.value_label} must be nonempty text.")
        candidate = value.strip() if self.strip_candidate else value
        if not candidate.strip():
            raise ValueError(f"{self.value_label} must be nonempty text.")
        if any(character in candidate for character in "\r\n"):
            raise ValueError(f"{self.value_label} must stay on one line.")
        if self.validate is not None:
            self.validate(candidate)
        return candidate


@dataclass
class ExactNameInputControl:
    """Embeddable exact-name input without a surrounding layout frame."""

    view: ExactNameFieldView
    input: TextArea

    @classmethod
    def create(
        cls,
        view: ExactNameFieldView,
        *,
        input_name: str | None = None,
        prompt: str = "› ",
        input_style: str = "",
    ) -> "ExactNameInputControl":
        """Build the writable field without imposing box or host semantics."""

        input_area = TextArea(
            text=view.value,
            multiline=False,
            prompt=prompt,
            focusable=True,
            focus_on_click=True,
            wrap_lines=False,
            height=Dimension.exact(1),
            style=input_style,
            name=input_name or _next_buffer_name("exact-name"),
        )
        input_area.buffer.cursor_position = len(view.value)
        return cls(view=view, input=input_area)

    @property
    def text(self) -> str:
        return self.input.text

    def set_text(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("Exact name field text must be text.")
        self.input.text = value
        self.input.buffer.cursor_position = len(value)

    def validate_candidate(self) -> str:
        return self.view.validate_value(self.input.text)


@dataclass
class ExactNameFieldControl:
    """Exact-name input composed with common focused-frame chrome."""

    input_control: ExactNameInputControl
    frame: Frame

    @classmethod
    def create(
        cls,
        view: ExactNameFieldView,
        *,
        input_name: str | None = None,
        prompt: str = "› ",
        height: AnyDimension = None,
        input_style: str = "",
        frame_style: str = "",
        frame_title: str | None = None,
    ) -> "ExactNameFieldControl":
        """Compose the standalone input with one reusable focused frame."""

        input_control = ExactNameInputControl.create(
            view,
            input_name=input_name,
            prompt=prompt,
            input_style=input_style,
        )
        title = (
            view.label + (f" · {view.state}" if view.state else "")
            if frame_title is None
            else frame_title
        )
        frame = build_focused_frame(
            input_control.input,
            title=safe_terminal_text(title),
            is_focused=lambda: get_app().layout.has_focus(input_control.input),
            style=frame_style,
            height=height if height is not None else Dimension.exact(3),
        )
        return cls(input_control=input_control, frame=frame)

    @property
    def view(self) -> ExactNameFieldView:
        return self.input_control.view

    @property
    def input(self) -> TextArea:
        return self.input_control.input

    @property
    def text(self) -> str:
        return self.input_control.text

    def set_text(self, value: str) -> None:
        self.input_control.set_text(value)

    def validate_candidate(self) -> str:
        return self.input_control.validate_candidate()


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


class _MutableFormattedTextLexer(Lexer):
    """Keep trusted semantic styles aligned with a read-only text buffer."""

    def __init__(self) -> None:
        self._lines: tuple[StyleAndTextTuples, ...] = ([],)
        self._generation = 0

    def replace(self, value: str | StyleAndTextTuples) -> str:
        fragments = [
            (style, safe_terminal_text(text))
            for style, text, *_ in to_formatted_text(value)
        ]
        self._lines = tuple(
            [
                (style, text)
                for style, text, *_ in line
                if text
            ]
            for line in split_lines(fragments)
        ) or ([],)
        self._generation += 1
        return "\n".join(
            "".join(text for _style, text in line)
            for line in self._lines
        )

    def lex_document(self, document: Document):
        lines = self._lines

        def get_line(line_number: int) -> StyleAndTextTuples:
            if 0 <= line_number < len(lines):
                return list(lines[line_number])
            if 0 <= line_number < len(document.lines):
                return [("", document.lines[line_number])]
            return []

        return get_line

    def invalidation_hash(self):
        return self._generation


@dataclass(frozen=True)
class ScrollableFormattedTextPane:
    """The common read-only pane with dynamic formatted-text presentation."""

    pane: ScrollableTextPane
    lexer: _MutableFormattedTextLexer

    @property
    def frame(self) -> Frame:
        return self.pane.frame

    @property
    def text_area(self) -> TextArea:
        return self.pane.text_area

    @property
    def container(self) -> AnyContainer:
        return self.pane.container

    def set_formatted_text(
        self,
        value: str | StyleAndTextTuples,
        *,
        anchor: ScrollAnchor = "preserve",
    ) -> None:
        plain_text = self.lexer.replace(value)
        self.pane.set_text(plain_text, anchor=anchor)


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
    """Render focused chrome with light-blue styling and heavy box glyphs."""

    base_style = frame.container.style

    def focused_style() -> str:
        resolved = base_style() if callable(base_style) else base_style
        return (
            f"{resolved} class:memcommit.focused"
            if is_focused()
            else resolved
        )

    frame.container.style = focused_style

    # Terminal bold does not reliably increase a box glyph's stroke weight.
    # Swap the actual frame characters instead so focus stays visible across
    # fonts, while leaving the dynamic body and all semantic content untouched.
    heavy_border = {
        "┌": "┏",
        "─": "━",
        "┐": "┓",
        "│": "┃",
        "└": "┗",
        "┘": "┛",
        # prompt-toolkit uses ASCII separators around a Frame title.
        "|": "┃",
    }

    def bind_border_chars(container: AnyContainer) -> None:
        if isinstance(container, Window):
            normal = container.char
            if isinstance(normal, str) and normal in heavy_border:
                heavy = heavy_border[normal]
                container.char = (
                    lambda normal=normal, heavy=heavy: (
                        heavy if is_focused() else normal
                    )
                )
            return
        if isinstance(container, ConditionalContainer):
            bind_border_chars(container.content)
            return
        if isinstance(container, (HSplit, VSplit)):
            for child in container.children:
                bind_border_chars(child)

    bind_border_chars(frame.container)


def build_focused_frame(
    body: AnyContainer,
    *,
    title,
    is_focused: Callable[[], bool],
    height: AnyDimension = None,
    style: str = "",
) -> Frame:
    """Compose arbitrary content with the shared focused-frame presentation."""

    if not callable(is_focused):
        raise TypeError("Focused-frame state must be callable.")
    frame = Frame(body, title=title, height=height, style=style)
    bind_focused_frame_style(frame, is_focused=is_focused)
    return frame


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


def move_wrapped_read_cursor(event: object, *, direction: int) -> bool:
    """Move one visual row and anchor it in a wrapped read-only viewport.

    Buffer cursor movement alone waits until the cursor reaches the viewport
    edge before anything visibly scrolls.  Read-only report panes instead use
    the cursor as a trusted viewport anchor: every arrow press advances one
    visual row immediately, including inside a wrapped logical line.  The
    boolean result lets a ``SurfaceFocusController`` cross to the adjacent
    Surface only at the true document boundary.
    """

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    app = getattr(event, "app")
    window = app.layout.current_window
    buffer = app.current_buffer
    render_info = window.render_info if window is not None else None
    if render_info is None or window is None:
        before = buffer.cursor_position
        if direction > 0:
            buffer.cursor_down(count=1)
        else:
            buffer.cursor_up(count=1)
        moved = buffer.cursor_position != before
        if moved:
            app.invalidate()
        return moved

    line_heights = tuple(
        max(1, render_info.get_height_for_line(line_number))
        for line_number in range(render_info.content_height)
    )
    total_height = sum(line_heights)
    viewport_height = min(total_height, render_info.window_height)
    current_offset = (
        sum(line_heights[: window.vertical_scroll])
        + window.vertical_scroll_2
    )
    maximum_offset = max(0, total_height - viewport_height)
    target_offset = max(
        0,
        min(current_offset + direction, maximum_offset),
    )
    if target_offset == current_offset:
        return False

    row = 0
    row_offset = target_offset
    for line_number, line_height in enumerate(line_heights):
        if row_offset < line_height:
            row = line_number
            break
        row_offset -= line_height

    document = buffer.document
    column = 0
    if render_info.wrap_lines and row_offset and render_info.window_width > 0:
        visual_row = 0
        visual_width = 0
        for index, character in enumerate(document.lines[row]):
            character_width = terminal_cell_width(character)
            if visual_width + character_width > render_info.window_width:
                visual_row += 1
                visual_width = 0
                if visual_row == row_offset:
                    column = index
                    break
            visual_width += character_width
        else:
            column = len(document.lines[row])

    buffer.cursor_position = document.translate_row_col_to_index(row, column)
    window.vertical_scroll = row
    window.vertical_scroll_2 = row_offset if render_info.wrap_lines else 0
    app.invalidate()
    return True


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
    lexer: Lexer | None = None,
) -> ScrollableTextPane:
    """Build one independently scrollable, read-only framed component."""
    text_area = TextArea(
        text=safe_terminal_text(text),
        multiline=True,
        lexer=lexer,
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
                FormattedTextControl([("class:memcommit.notification", "●")]),
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


def build_scrollable_formatted_text_pane(
    title: str,
    value: str | StyleAndTextTuples = "",
    *,
    buffer_name: str | None = None,
    height: AnyDimension = None,
    wrap_lines: bool = True,
    focusable: bool = True,
    style: str = "",
    frame_style: str = "",
) -> ScrollableFormattedTextPane:
    """Build a styled report pane on the common cursor-backed viewport."""

    lexer = _MutableFormattedTextLexer()
    plain_text = lexer.replace(value)
    pane = build_scrollable_text_pane(
        title,
        plain_text,
        buffer_name=buffer_name,
        height=height,
        wrap_lines=wrap_lines,
        focusable=focusable,
        style=style,
        frame_style=frame_style,
        lexer=lexer,
    )
    return ScrollableFormattedTextPane(pane=pane, lexer=lexer)


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


def boxed_lines(title: str, body: str, *, width: int = 72) -> list[str]:
    """Return one width-aware neutral report card for terminal surfaces."""

    if width < 6:
        raise ValueError("Terminal card width must be at least 6 cells.")
    inner_width = width - 2
    body_width = width - 4
    safe_title = single_line_terminal_text(safe_terminal_text(title))
    label = f"─ {elide_terminal_text(safe_title, inner_width - 3)} "
    lines = [
        f"╭{label}{'─' * max(0, inner_width - terminal_cell_width(label))}╮"
    ]
    lines.extend(
        f"│ {pad_terminal_text(line, body_width)} │"
        for line in wrap_terminal_text(safe_terminal_text(body), body_width)
    )
    lines.append(f"╰{'─' * inner_width}╯")
    return lines


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


def navigable_tree_row_prefix(
    *,
    selected: bool,
    current: bool = False,
    depth: int = 0,
    branch: str = "·",
) -> str:
    """Return the shared Switch-style prefix for one navigable hierarchy row.

    Keeping the cursor, current marker, nesting indent, and branch marker in
    one primitive prevents long semantic-result lists from developing a
    second, subtly different navigation grammar.
    """
    if depth < 0:
        raise ValueError("Navigable tree row depth cannot be negative.")
    if not isinstance(branch, str) or not branch or "\n" in branch:
        raise ValueError("Navigable tree row branch must be one visible token.")
    pointer = "›" if selected else " "
    active = "*" if current else " "
    return f"{pointer} {active} {'  ' * depth}{branch} "
