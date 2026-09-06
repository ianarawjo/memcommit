"""Present temporary Memory choices or read-only evidence for one endpoint."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.terminal.components.focus import SurfaceActionResult
from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)

from .endpoint_editor import EndpointEditor


class MemoryPicker:
    """Keep list visibility separate from the endpoint's selected Memory value."""

    def __init__(
        self,
        editors: Mapping[str, EndpointEditor],
        *,
        set_status: Callable[[str], None],
    ) -> None:
        self.editors = editors
        self.set_status = set_status
        self.active_role_uid: str | None = None

    def reset(self) -> None:
        self.active_role_uid = None

    def reset_for(self, role_uid: str) -> None:
        if self.active_role_uid == role_uid:
            self.reset()

    def dismiss(self, _event) -> bool:
        if self.active_role_uid is None:
            return False
        self.reset()
        self.set_status("")
        return True

    def open(self, role_uid: str) -> bool:
        try:
            self.editors[role_uid].prepare_memory_selection()
        except (OSError, TypeError, ValueError) as error:
            self.set_status(str(error))
            return False
        self.active_role_uid = role_uid
        self.set_status("")
        return True

    def move(self, delta: int) -> bool:
        return self.editors[self.active_role_uid].memory_focus.move(delta)

    def activate(self, _event, role_uid: str) -> SurfaceActionResult:
        if self.active_role_uid != role_uid:
            self.open(role_uid)
            return "HANDLED"
        editor = self.editors[role_uid]
        if editor.role.memory_preview_only:
            self.set_status(
                "Memory rows are read-only evidence; the whole Context remains selected."
            )
            return "HANDLED"
        selected = editor.select_memory()
        self.reset()
        self.set_status(
            f"{editor.label()} uses Memory {selected[:8]}."
            if selected is not None
            else f"{editor.label()} uses the whole Context."
        )
        return "HANDLED"

    def render(self) -> StyleAndTextTuples:
        if self.active_role_uid is None:
            return []
        editor = self.editors[self.active_role_uid]
        fragments: StyleAndTextTuples = [
            (
                "class:report-neutral",
                ("  " if editor.role.memory_required else "  MEMORY · ")
                + safe_terminal_text(editor.label())
                + f" · {display_escape_text(editor.selected_memory_context())}\n",
            )
        ]
        fragments.extend(
            editor.memory_focus.render(focused=True, include_descendants=False)
        )
        return fragments

    def build_detail(self) -> ConditionalContainer:
        return ConditionalContainer(
            Window(
                FormattedTextControl(self.render, focusable=False, show_cursor=False),
                wrap_lines=True,
                right_margins=[ScrollbarMargin(display_arrows=True)],
                height=Dimension(min=3, preferred=7, max=9),
            ),
            filter=Condition(lambda: self.active_role_uid is not None),
        )
