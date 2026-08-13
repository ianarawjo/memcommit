"""Small presentation primitives shared by memcommit terminal workbenches.

This module deliberately owns terminal mechanics, not semantic state,
provider prompts, persistence, or operation-specific key meanings.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import count
from typing import Callable, Literal

from prompt_toolkit.application.current import get_app
from prompt_toolkit.layout import (
    AnyDimension,
    FormattedTextControl,
    HSplit,
    Window,
)
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.interfaces.tui.components.frame import build_focused_frame
from memcommit.interfaces.tui.components.scrollable_pane import ScrollableTextPane
from memcommit.interfaces.tui.core.text_layout import (
    elide_terminal_text,
    pad_terminal_text,
    single_line_terminal_text,
    terminal_cell_width,
    wrap_terminal_text,
)


InlineEditSubmissionKind = Literal["NOOP", "DIRECT", "COMMENT", "BOTH"]

INLINE_DIRECT_EDIT_TITLE = "EDIT (DIRECTLY)"
INLINE_AGENT_COMMENT_TITLE = "COMMENT (FOR THE AGENT)"

_BUFFER_SERIAL = count(1)


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
            section.text_area.buffer.read_only() and not section.allow_read_only
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
                        FormattedTextControl(display_escape_text(section.title)),
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
        height=(height if height is not None else Dimension(min=5, preferred=6, max=9)),
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
        height=(height if height is not None else Dimension(min=3, preferred=3, max=4)),
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


def boxed_lines(title: str, body: str, *, width: int = 72) -> list[str]:
    """Return one width-aware neutral report card for terminal surfaces."""

    if width < 6:
        raise ValueError("Terminal card width must be at least 6 cells.")
    inner_width = width - 2
    body_width = width - 4
    safe_title = single_line_terminal_text(safe_terminal_text(title))
    label = f"─ {elide_terminal_text(safe_title, inner_width - 3)} "
    lines = [f"╭{label}{'─' * max(0, inner_width - terminal_cell_width(label))}╮"]
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
