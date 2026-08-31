"""Compact exact-name and transient Browse control for QUERY-granted views."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    Float,
    FloatContainer,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.menus import CompletionsMenu

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldView,
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import focused_control_style
from memcommit.application.operations.search_explain.retrieve_answer.query.granted_application import GrantedQueryTarget
from memcommit.adapters.console.terminal.components.selection.model import SelectionOption
from memcommit.adapters.console.terminal.components.selection.state import FlatSelectionState
from memcommit.adapters.console.terminal.components.selection import render_vertical_choice_rows


ScopeChanged = Callable[[str], None]
ScopeStatus = Callable[[str], None]
ScopeLocked = Callable[[], bool]


def _noop(_message: str) -> None:
    return None


class CompactQueryViewScopeControl:
    """One exact Query View fast path with a transient typed catalog."""

    def __init__(
        self,
        targets: Sequence[GrantedQueryTarget],
        *,
        initial_target: GrantedQueryTarget,
        federate_descendants: bool,
        on_change: ScopeChanged = _noop,
        on_status: ScopeStatus = _noop,
        locked: ScopeLocked = lambda: False,
    ) -> None:
        catalog = tuple(targets)
        if (
            not catalog
            or any(not isinstance(item, GrantedQueryTarget) for item in catalog)
            or len({item.grant_uid for item in catalog}) != len(catalog)
            or len({item.public_name for item in catalog}) != len(catalog)
            or initial_target not in catalog
        ):
            raise ValueError("Query View Browse requires a distinct typed catalog.")
        self.targets = catalog
        self.target_by_uid = {item.grant_uid: item for item in catalog}
        self.target_by_name = {item.public_name: item for item in catalog}
        self.on_change = on_change
        self.on_status = on_status
        self.locked = locked
        self.browser_open = False
        self._direct_dirty = False
        self._programmatic_edit = False

        self.selection = FlatSelectionState(
            tuple(
                SelectionOption(
                    target.grant_uid,
                    target.public_name,
                    "QUERY VIEW · ATTACHED TO " + target.attachment_name,
                )
                for target in catalog
            ),
            cursor_uid=initial_target.grant_uid,
            selected_uid=initial_target.grant_uid,
            allow_empty=False,
        )
        self.range_choice = HorizontalChoiceState(
            (
                HorizontalChoiceOption("EXACT", "EXACT VIEW"),
                HorizontalChoiceOption("FEDERATE", "FEDERATE DESCENDANTS"),
            ),
            "FEDERATE" if federate_descendants else "EXACT",
        )
        completer = WordCompleter(
            tuple(self.target_by_name),
            meta_dict={name: "QUERY VIEW" for name in self.target_by_name},
            sentence=True,
            match_middle=True,
        )
        self.name = ExactNameInputControl.create(
            ExactNameFieldView(
                value=initial_target.public_name,
                label="QUERY VIEW",
                detail="Enter one exact public Query View or use Browse.",
                validate=self._validate_name,
                value_label="Query View name",
            ),
            input_name="compact-query-view-name",
            prompt="› ",
            completer=completer,
            complete_while_typing=True,
            width=Dimension(min=18, preferred=44, max=64),
            dont_extend_width=True,
        )
        self.name.input.buffer.on_text_changed += self._direct_text_changed

        self.browse_control = FormattedTextControl(
            self._render_browse,
            focusable=True,
            show_cursor=False,
        )
        self.range_control = FormattedTextControl(
            self._render_range,
            focusable=True,
            show_cursor=False,
        )
        self.catalog_control = FormattedTextControl(
            self._render_catalog,
            focusable=True,
            show_cursor=False,
        )
        self.state_control = FormattedTextControl(
            self._render_state,
            focusable=False,
            show_cursor=False,
        )

        query_view_row = VSplit(
            [
                Window(
                    FormattedTextControl(" QUERY VIEW · "),
                    width=Dimension.exact(14),
                    dont_extend_height=True,
                ),
                self.name.input,
                Window(
                    self.browse_control,
                    width=Dimension.exact(12),
                    dont_extend_height=True,
                ),
                Window(
                    self.state_control,
                    width=Dimension(min=16, preferred=34, weight=1),
                    dont_extend_height=True,
                ),
            ],
            height=Dimension.exact(1),
        )
        catalog_detail = ConditionalContainer(
            HSplit(
                [
                    Window(
                        FormattedTextControl("  QUERY VIEWS · AUTHORIZED CATALOG"),
                        height=Dimension.exact(1),
                        dont_extend_height=True,
                    ),
                    Window(
                        self.catalog_control,
                        wrap_lines=False,
                        right_margins=[ScrollbarMargin(display_arrows=True)],
                        # Every unboxed option owns a label and description,
                        # plus a separator between options. Counting only
                        # targets would clip the next public View entirely.
                        height=Dimension.exact(
                            min(9, max(2, len(catalog) * 3 - 1))
                        ),
                        dont_extend_height=True,
                    ),
                ]
            ),
            filter=Condition(lambda: self.browser_open),
        )
        self.container = FloatContainer(
            content=HSplit(
                [
                    query_view_row,
                    Window(self.range_control, height=Dimension.exact(1)),
                    catalog_detail,
                ]
            ),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(
                        max_height=8,
                        scroll_offset=1,
                        display_arrows=True,
                    ),
                )
            ],
        )

    @property
    def input(self):
        return self.name.input

    @property
    def federate_descendants(self) -> bool:
        return self.range_choice.selected_uid == "FEDERATE"

    def selected_target(self) -> GrantedQueryTarget:
        if self._direct_dirty:
            self.commit_direct()
        uid = self.selection.selected_uid
        if uid is None:
            raise ValueError("Select one query-only View.")
        return self.target_by_uid[uid]

    def summary(self) -> str:
        target = self.selected_target()
        reach = "FEDERATE DESCENDANTS" if self.federate_descendants else "EXACT VIEW"
        return f"{target.public_name} · {reach}"

    def _validate_name(self, candidate: str) -> None:
        if candidate not in self.target_by_name:
            raise ValueError(
                f"Query View {safe_terminal_text(candidate)!r} is not authorized."
            )

    def _direct_text_changed(self, _buffer) -> None:
        if self._programmatic_edit:
            return
        self._direct_dirty = True
        self.on_change("QUERY VIEW DRAFT CHANGED · PRESS ENTER TO USE IT")

    def _set_direct_text(self, value: str) -> None:
        self._programmatic_edit = True
        try:
            self.name.set_text(value)
        finally:
            self._programmatic_edit = False
        self._direct_dirty = False

    def _locked(self) -> bool:
        if not self.locked():
            return False
        self.on_status("Wait for the current Query before changing Source.")
        return True

    def commit_direct(self) -> bool:
        if self._locked():
            return False
        candidate = self.name.validate_candidate()
        target = self.target_by_name[candidate]
        before = self.selection.selected_uid
        self.selection.selected_uid = target.grant_uid
        self.selection.cursor_uid = target.grant_uid
        self._direct_dirty = False
        changed = before != target.grant_uid
        if changed:
            self.on_change("QUERY VIEW CHANGED · PRESS ENTER TO QUERY")
        else:
            self.on_status(f"QUERY VIEW CONFIRMED · {candidate}")
        return True

    def _render_browse(self) -> StyleAndTextTuples:
        focused = get_app().layout.has_focus(self.browse_control)
        return [
            (
                focused_control_style(focused=focused, selected=self.browser_open),
                "[ BROWSE ]",
            )
        ]

    def _render_state(self) -> StyleAndTextTuples:
        if self._direct_dirty:
            return [("class:source-state", "PRESS ENTER TO USE")]
        target = self.selected_target()
        return [
            (
                "class:source-access",
                safe_terminal_text("ATTACHED TO " + target.attachment_name),
            )
        ]

    def _render_range(self) -> StyleAndTextTuples:
        return render_horizontal_choice(
            self.range_choice,
            title="RANGE",
            focused=get_app().layout.has_focus(self.range_control),
        )

    def _render_catalog(self) -> StyleAndTextTuples:
        width = max(30, get_app().output.get_size().columns - 8)
        return render_vertical_choice_rows(
            self.selection,
            focused=get_app().layout.has_focus(self.catalog_control),
            content_width=width,
            numbered=False,
        )

    def open_browser(self, event: KeyPressEvent) -> SurfaceActionResult:
        if self._locked():
            return "HANDLED"
        if self.name.input.buffer.complete_state is not None:
            self.name.input.buffer.cancel_completion()
        self.browser_open = True
        event.app.layout.focus(self.catalog_control)
        self.on_status("QUERY VIEW BROWSE · ENTER SELECTS · ESC CLOSES")
        return "HANDLED"

    def close_browser(self, event: KeyPressEvent) -> bool:
        if not self.browser_open:
            return False
        self.browser_open = False
        event.app.layout.focus(self.browse_control)
        self.on_status("QUERY VIEW STAGED · ENTER A QUESTION")
        return True

    def _move_direct(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        buffer = self.name.input.buffer
        if buffer.complete_state is None:
            return "BOUNDARY"
        if delta > 0:
            buffer.complete_next()
        else:
            buffer.complete_previous()
        return "CONSUMED"

    def _activate_direct(self, _event: KeyPressEvent) -> SurfaceActionResult:
        buffer = self.name.input.buffer
        if (
            buffer.complete_state is not None
            and buffer.complete_state.current_completion is not None
        ):
            buffer.apply_completion(buffer.complete_state.current_completion)
        try:
            self.commit_direct()
        except (TypeError, ValueError) as error:
            self.on_status(str(error))
        return "HANDLED"

    def _move_catalog(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        return "MOVED" if self.selection.move(delta) else "BOUNDARY"

    def _select_catalog(self, _event: KeyPressEvent) -> SurfaceActionResult:
        if self._locked():
            return "HANDLED"
        before = self.selection.selected_uid
        selected = self.selection.select_cursor(toggle=False)
        if selected is None:
            return "HANDLED"
        self._set_direct_text(self.target_by_uid[selected].public_name)
        if selected != before:
            self.on_change("QUERY VIEW CHANGED · PRESS ENTER TO QUERY")
        else:
            self.on_status("QUERY VIEW CONFIRMED")
        return "HANDLED"

    def _move_range(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        if self._locked():
            return "CONSUMED"
        if not self.range_choice.move(delta):
            return "BOUNDARY"
        self.on_change("QUERY VIEW RANGE CHANGED · PRESS ENTER TO QUERY")
        return "MOVED"

    def _toggle_range(self, event: KeyPressEvent) -> SurfaceActionResult:
        self._move_range(event, -1 if self.federate_descendants else 1)
        return "HANDLED"

    def normal_surfaces(
        self, *, uid_prefix: str = "query-view"
    ) -> tuple[FocusSurface, ...]:
        return (
            FocusSurface(
                f"{uid_prefix}:name",
                self.name.input,
                move_vertical=self._move_direct,
                activate=self._activate_direct,
            ),
            FocusSurface(
                f"{uid_prefix}:browse",
                self.browse_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self.open_browser,
            ),
            FocusSurface(
                f"{uid_prefix}:range",
                self.range_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=self._toggle_range,
            ),
        )

    def browser_surface(self, *, uid_prefix: str = "query-view") -> FocusSurface:
        return FocusSurface(
            f"{uid_prefix}:catalog",
            self.catalog_control,
            move_vertical=self._move_catalog,
            activate=self._select_catalog,
        )

    def bind_keybindings(self, bindings: KeyBindings) -> None:
        @bindings.add(" ", filter=has_focus(self.catalog_control), eager=True)
        def _catalog_space(event: KeyPressEvent) -> None:
            self._select_catalog(event)
            event.app.invalidate()

        @bindings.add("left", filter=has_focus(self.range_control), eager=True)
        def _range_left(event: KeyPressEvent) -> None:
            self._move_range(event, -1)
            event.app.invalidate()

        @bindings.add("right", filter=has_focus(self.range_control), eager=True)
        def _range_right(event: KeyPressEvent) -> None:
            self._move_range(event, 1)
            event.app.invalidate()


__all__ = ["CompactQueryViewScopeControl"]
