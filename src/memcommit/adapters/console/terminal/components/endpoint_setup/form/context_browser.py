"""Open a role's frozen Context catalog and return its choice to the input row."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text

from .endpoint_editor import EndpointEditor


class ContextBrowser:
    """Own the transient catalog and its return focus; editors own chosen values."""

    def __init__(
        self,
        editors: Mapping[str, EndpointEditor],
        *,
        set_status: Callable[[str], None],
        before_open: Callable[[], None],
        on_context_selected: Callable[[], None],
    ) -> None:
        self.editors = editors
        self.set_status = set_status
        self.before_open = before_open
        self.on_context_selected = on_context_selected
        self.active_role_uid: str | None = None

    @property
    def is_open(self) -> bool:
        return self.active_role_uid is not None

    def reset(self) -> None:
        self.active_role_uid = None

    def prepare(self, role_uid: str) -> None:
        self.before_open()
        buffer = self.editors[role_uid].input.buffer
        if buffer.complete_state is not None:
            buffer.cancel_completion()

    def open(self, event, role_uid: str) -> bool:
        editor = self.editors[role_uid]
        selector = editor.selector
        if selector is None:
            self.set_status(
                f"{editor.label()} has no eligible existing Context; type one new exact name."
            )
            return False
        self.prepare(role_uid)
        candidate = editor.catalog_initial_name()
        selected = (
            candidate if candidate in selector.selectable else selector.view.names[0]
        )
        selector.select_name(selected)
        self.active_role_uid = role_uid
        self.set_status("")
        event.app.layout.focus(selector.control)
        return True

    def activate(self, event, role_uid: str) -> SurfaceActionResult:
        self.open(event, role_uid)
        return "HANDLED"

    def move(self, _event, delta: int) -> SurfaceMoveResult:
        selector = self.editors[self.active_role_uid].selector
        before = selector.tree.selected_name
        selector.move(delta)
        return "MOVED" if selector.tree.selected_name != before else "BOUNDARY"

    def close(self, event, *, choose: bool) -> SurfaceActionResult:
        if not self.is_open:
            return "IGNORED"
        editor = self.editors[self.active_role_uid]
        if choose:
            editor.selector.choose_cursor()
            message = editor.select_catalog_name(editor.selector.tree.selected_name)
            if editor.role.new_parent_locator:
                self.set_status(message)
            else:
                self.on_context_selected()
        self.reset()
        if not editor.role.new_parent_locator:
            self.set_status("")
        event.app.layout.focus(editor.browse_control)
        return "HANDLED"

    def dismiss(self, event) -> bool:
        return self.close(event, choose=False) == "HANDLED"

    def surface(self) -> FocusSurface:
        editor = self.editors[self.active_role_uid]
        return FocusSurface(
            f"CATALOG:{editor.uid}",
            editor.selector.control,
            move_vertical=self.move,
            activate=lambda event: self.close(event, choose=True),
        )

    def build_details(self) -> list[ConditionalContainer]:
        containers = []
        for role_uid, editor in self.editors.items():
            selector = editor.selector
            if selector is None:
                continue
            containers.append(
                ConditionalContainer(
                    HSplit(
                        [
                            Window(
                                FormattedTextControl(
                                    lambda editor=editor: (
                                        "  PARENT CONTEXTS · "
                                        if editor.role.new_parent_locator
                                        else "  CONTEXTS · "
                                    )
                                    + safe_terminal_text(editor.label())
                                    + (
                                        " · LOCAL LOCATIONS"
                                        if editor.role.new_parent_locator
                                        else " · ALL ALLOWED"
                                    )
                                ),
                                height=Dimension.exact(1),
                                dont_extend_height=True,
                            ),
                            Window(
                                selector.control,
                                wrap_lines=False,
                                right_margins=[ScrollbarMargin(display_arrows=True)],
                                height=Dimension.exact(
                                    min(8, len(selector.view.names))
                                ),
                                dont_extend_height=True,
                            ),
                        ]
                    ),
                    filter=Condition(lambda uid=role_uid: self.active_role_uid == uid),
                )
            )
        return containers
