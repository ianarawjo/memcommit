"""One shared SAVE frame for Find, Search, and Query outcomes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import cast

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.layout.containers import AnyContainer

from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameInputControl,
)
from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceMoveResult,
)
from memcommit.adapters.console.terminal.components.frame import build_focused_frame
from memcommit.adapters.console.terminal.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    ContextNameView,
    ContextParentLocatorState,
    context_name_tree_fragments,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.state.name_draft import (
    ContextNameDraftState,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    focused_control_style,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text


SavePanelStatus = Callable[[str], None]
SavePanelAction = Callable[[KeyPressEvent], SurfaceActionResult]
SavePanelSummary = Callable[[], str]
SavePanelActionLabel = Callable[[str | None], str]


class RetrieveAnswerSavePanel:
    """Compose common save mechanics without owning operation save meaning.

    CONTENT describes the already completed outcome. MODE is optional because
    Find/Search retain existing Memories while Query saves one generated
    answer. LOCATION is always one direct exact new Context name; BROWSE is a
    transient placement aid inside this same frame.
    """

    def __init__(
        self,
        *,
        content_summary: SavePanelSummary,
        action_label: SavePanelActionLabel,
        initial_location: str,
        context_names: Sequence[str],
        current_context: str | None,
        validate_location: Callable[[str], object] | None,
        input_name: str,
        on_status: SavePanelStatus,
        mode_options: Sequence[HorizontalChoiceOption] = (),
        initial_mode: str | None = None,
        browse_height: int = 5,
    ) -> None:
        catalog = tuple(context_names)
        options = tuple(mode_options)
        if not callable(content_summary) or not callable(action_label):
            raise TypeError("SAVE panel summaries must be callable.")
        if not callable(on_status):
            raise TypeError("SAVE panel status callback must be callable.")
        if len(set(catalog)) != len(catalog) or any(
            not isinstance(name, str) or not name for name in catalog
        ):
            raise ValueError("SAVE panel Context names must be distinct text.")
        if browse_height < 1:
            raise ValueError("SAVE panel Browse height must be positive.")
        if options and initial_mode is None:
            initial_mode = options[0].uid
        if not options and initial_mode is not None:
            raise ValueError("A SAVE panel without modes cannot select one.")

        self._content_summary = content_summary
        self._action_label = action_label
        self._on_status = on_status
        self.browser_open = False
        self._programmatic_edit = False
        if options:
            assert initial_mode is not None
            self.mode: HorizontalChoiceState | None = HorizontalChoiceState(
                options,
                selected_uid=initial_mode,
            )
        else:
            self.mode = None

        view = ContextNameView(
            value=initial_location,
            label="SAVE LOCATION",
            state="NEW CONTEXT",
            detail="Save into this exact new local Context.",
            validate=validate_location,
            value_label="Save location",
            context_names=catalog,
            current_context=current_context,
        )
        self.name = ExactNameInputControl.create(
            view,
            input_name=input_name,
            prompt="› ",
            width=Dimension(min=18, preferred=54),
        )
        self.locator = ContextParentLocatorState.create(view)
        self.draft = ContextNameDraftState(
            exact_name=initial_location,
            parent_name=(
                self.locator.selected_parent if self.locator is not None else None
            ),
        )

        def record_direct_edit(_buffer) -> None:
            if not self._programmatic_edit:
                self.draft.record_direct_edit(self.name.text)

        self.name.input.buffer.on_text_changed += record_direct_edit

        self.mode_control = (
            FormattedTextControl(
                self._render_mode,
                focusable=True,
                show_cursor=False,
            )
            if self.mode is not None
            else None
        )
        self.browse_control = FormattedTextControl(
            self._render_browse,
            focusable=self.locator is not None,
            show_cursor=False,
        )
        self.location_state_control = FormattedTextControl(
            lambda: [("class:source-state", "NEW CONTEXT")],
            focusable=False,
            show_cursor=False,
        )
        self.tree_control = FormattedTextControl(
            self._render_tree,
            focusable=self.locator is not None,
            show_cursor=False,
        )
        self.action_control = FormattedTextControl(
            self._render_action,
            focusable=True,
            show_cursor=False,
        )

        rows: list[AnyContainer] = [
            Window(
                FormattedTextControl(self._render_content),
                height=Dimension.exact(1),
                dont_extend_height=True,
            )
        ]
        if self.mode_control is not None:
            rows.append(
                Window(
                    self.mode_control,
                    height=Dimension.exact(1),
                    dont_extend_height=True,
                )
            )
        rows.append(
            VSplit(
                [
                    Window(
                        FormattedTextControl(" LOCATION · "),
                        width=Dimension.exact(12),
                        dont_extend_height=True,
                    ),
                    self.name.input,
                    Window(
                        self.browse_control,
                        width=Dimension.exact(12),
                        dont_extend_height=True,
                    ),
                    Window(
                        self.location_state_control,
                        width=Dimension(min=12, preferred=18, weight=1),
                        dont_extend_height=True,
                    ),
                ],
                height=Dimension.exact(1),
            )
        )
        rows.append(
            ConditionalContainer(
                HSplit(
                    [
                        Window(
                            FormattedTextControl(
                                "  SAVE LOCATION · EXISTING CONTEXTS"
                            ),
                            height=Dimension.exact(1),
                            dont_extend_height=True,
                        ),
                        Window(
                            self.tree_control,
                            wrap_lines=False,
                            right_margins=[ScrollbarMargin(display_arrows=True)],
                            height=Dimension.exact(
                                min(browse_height, len(catalog) + 1)
                            ),
                            dont_extend_height=True,
                        ),
                    ]
                ),
                filter=Condition(lambda: self.browser_open),
            )
        )
        rows.append(
            Window(
                self.action_control,
                height=Dimension.exact(1),
                dont_extend_height=True,
            )
        )
        self.container = build_focused_frame(
            HSplit(rows),
            title="SAVE",
            is_focused=self.is_focused,
        )

    @property
    def selected_mode(self) -> str | None:
        return None if self.mode is None else self.mode.selected_uid

    @property
    def location(self) -> str:
        return self.name.text

    def set_location(self, value: str) -> None:
        self.draft.replace_programmatically(value)
        self._programmatic_edit = True
        try:
            self.name.set_text(value)
        finally:
            self._programmatic_edit = False

    def validate_candidate(self) -> str:
        return self.name.validate_candidate()

    def is_focused(self) -> bool:
        app = get_app()
        return (
            app.layout.has_focus(self.name.input)
            or app.layout.has_focus(self.browse_control)
            or app.layout.has_focus(self.action_control)
            or (
                self.mode_control is not None
                and app.layout.has_focus(self.mode_control)
            )
            or (
                self.locator is not None
                and app.layout.has_focus(self.tree_control)
            )
        )

    def _render_content(self) -> list[tuple[str, str]]:
        return [
            ("class:report-label", " CONTENT · "),
            ("", safe_terminal_text(self._content_summary())),
        ]

    def _render_mode(self) -> StyleAndTextTuples:
        assert self.mode is not None
        assert self.mode_control is not None
        return render_horizontal_choice(
            self.mode,
            title="MODE",
            focused=get_app().layout.has_focus(self.mode_control),
            show_description=False,
        )

    def _render_browse(self) -> list[tuple[str, str]]:
        if self.locator is None:
            return [("class:source-state", "")]
        focused = get_app().layout.has_focus(self.browse_control)
        return [
            (
                focused_control_style(focused=focused, selected=self.browser_open),
                "[ BROWSE ]",
            )
        ]

    def _render_tree(self) -> list[tuple[str, str]]:
        if self.locator is None:
            return []
        return context_name_tree_fragments(
            self.locator,
            focused=get_app().layout.has_focus(self.tree_control),
        )

    def _render_action(self) -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(self.action_control)
        value = safe_terminal_text(self._action_label(self.selected_mode))
        fragments: list[tuple[str, str]] = []
        if focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                focused_control_style(focused=focused),
                f" ACTION · {'> ' if focused else '  '}{value}",
            )
        )
        return fragments

    def _move_mode(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        assert self.mode is not None
        return "MOVED" if self.mode.move(delta) else "BOUNDARY"

    def _activate_mode(self, event: KeyPressEvent) -> SurfaceActionResult:
        event.app.layout.focus(self.name.input)
        self.name.input.buffer.cursor_position = len(self.name.text)
        self._on_status(
            f"{self.selected_mode} · REVIEW THE EXACT SAVE LOCATION"
        )
        return "HANDLED"

    def _activate_location(self, event: KeyPressEvent) -> SurfaceActionResult:
        try:
            self.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            self._on_status(str(error))
            return "HANDLED"
        event.app.layout.focus(self.action_control)
        self._on_status("SAVE LOCATION VALID · ENTER TO SAVE")
        return "HANDLED"

    def _open_browser(self, event: KeyPressEvent) -> SurfaceActionResult:
        if self.locator is None:
            self._on_status("NO EXISTING LOCAL CONTEXTS TO BROWSE")
            return "HANDLED"
        self.browser_open = True
        event.app.layout.focus(self.tree_control)
        self._on_status(
            "BROWSE SAVE LOCATION · ENTER PLACES THE NAME · ESC CLOSES"
        )
        return "HANDLED"

    def close_browser(self, event: KeyPressEvent) -> bool:
        if not self.browser_open:
            return False
        self.browser_open = False
        event.app.layout.focus(self.browse_control)
        self._on_status("SAVE LOCATION STAGED")
        return True

    def _move_tree(
        self,
        _event: KeyPressEvent,
        delta: int,
    ) -> SurfaceMoveResult:
        if self.locator is None:
            return "BOUNDARY"
        before = self.locator.tree.selected_row_index()
        self.locator.tree.move(delta)
        return (
            "MOVED"
            if self.locator.tree.selected_row_index() != before
            else "BOUNDARY"
        )

    def _choose_tree_location(
        self,
        event: KeyPressEvent,
    ) -> SurfaceActionResult:
        if self.locator is None:
            return "HANDLED"
        try:
            parent = self.locator.tree.selected_name
            # Direct edits block silent suggestion inheritance, but Enter on a
            # Browse row is an explicit reparent request. Use a fresh draft so
            # the person's final name segment moves under the chosen Context.
            choice = ContextNameDraftState(
                exact_name=self.name.text,
                parent_name=self.draft.parent_name,
            )
            candidate = choice.choose_parent(parent)
            self.draft.parent_name = parent
            self.locator.selection.choose(parent)
            self.set_location(candidate)
        except (TypeError, ValueError) as error:
            self._on_status(str(error))
            return "HANDLED"
        self.browser_open = False
        event.app.layout.focus(self.name.input)
        self._on_status(f"SAVE LOCATION UPDATED · REVIEW {candidate}")
        return "HANDLED"

    def normal_surfaces(
        self,
        *,
        activate_action: SavePanelAction,
        uid_prefix: str,
    ) -> tuple[FocusSurface, ...]:
        surfaces: list[FocusSurface] = []
        if self.mode_control is not None:
            surfaces.append(
                FocusSurface(
                    f"{uid_prefix}:mode",
                    self.mode_control,
                    move_vertical=self._move_mode,
                    activate=self._activate_mode,
                )
            )
        surfaces.extend(
            (
                FocusSurface(
                    f"{uid_prefix}:location",
                    self.name.input,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=self._activate_location,
                ),
                FocusSurface(
                    f"{uid_prefix}:browse",
                    self.browse_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=self._open_browser,
                ),
                FocusSurface(
                    f"{uid_prefix}:action",
                    self.action_control,
                    move_vertical=lambda _event, _delta: "BOUNDARY",
                    activate=activate_action,
                ),
            )
        )
        return tuple(surfaces)

    def browser_surface(self, *, uid_prefix: str) -> FocusSurface:
        return FocusSurface(
            f"{uid_prefix}:tree",
            self.tree_control,
            move_vertical=self._move_tree,
            activate=self._choose_tree_location,
        )

    def bind_keybindings(self, bindings: KeyBindings) -> None:
        if self.mode_control is not None:

            @bindings.add("left", filter=has_focus(self.mode_control), eager=True)
            def _mode_left(event: KeyPressEvent) -> None:
                self._move_mode(event, -1)
                event.app.invalidate()

            @bindings.add("right", filter=has_focus(self.mode_control), eager=True)
            def _mode_right(event: KeyPressEvent) -> None:
                self._move_mode(event, 1)
                event.app.invalidate()

        if self.locator is not None:
            tree_focus = has_focus(self.tree_control)

            @bindings.add("left", filter=tree_focus, eager=True)
            def _tree_left(event: KeyPressEvent) -> None:
                cast(ContextParentLocatorState, self.locator).tree.collapse_selected()
                event.app.invalidate()

            @bindings.add("right", filter=tree_focus, eager=True)
            def _tree_right(event: KeyPressEvent) -> None:
                cast(ContextParentLocatorState, self.locator).tree.expand_selected()
                event.app.invalidate()

            @bindings.add(" ", filter=tree_focus, eager=True)
            def _tree_space(event: KeyPressEvent) -> None:
                self._choose_tree_location(event)
                event.app.invalidate()

            @bindings.add("tab", filter=tree_focus, eager=True)
            @bindings.add("s-tab", filter=tree_focus, eager=True)
            @bindings.add("backspace", filter=tree_focus, eager=True)
            def _leave_tree(event: KeyPressEvent) -> None:
                self.close_browser(event)
                event.app.invalidate()

        @bindings.add("c-j", filter=has_focus(self.name.input), eager=True)
        def _reject_newline(event: KeyPressEvent) -> None:
            self._on_status("SAVE LOCATION STAYS ON ONE LINE")
            event.app.invalidate()


__all__ = ["RetrieveAnswerSavePanel"]
