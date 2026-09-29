"""Attach navigation, focus and key grammar to caller-owned screen controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from prompt_toolkit.application.current import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceFocusController,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.navigation import (
    scroll_wrapped_page,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionItem,
    ResolutionWorkbenchAction,
)
from .screen_state import DecisionScreenState

if TYPE_CHECKING:
    from .intent import IntentEditor
    from memcommit.adapters.console.terminal.components.scrollable_pane.model import (
        ScrollableFormattedTextPane,
    )


FocusRole = Literal["navigation", "choices", "actions", "intent"]


@dataclass(frozen=True)
class CompactControls:
    """Focus targets supplied by the composing screen, independent of its layout."""

    navigation: object
    choices: object
    actions: object
    decisions: object
    intent: object | None = None

    def is_focused(self, role: FocusRole) -> bool:
        control = getattr(self, role)
        return control is not None and get_app().layout.has_focus(control)


class CompactInteraction:
    def __init__(
        self,
        state: DecisionScreenState,
        controls: CompactControls,
        *,
        build_continue_action: Callable[[str | None], ResolutionWorkbenchAction | None],
        stage_bulk_choice: Callable[[str], None] | None = None,
        intent: IntentEditor | None = None,
    ) -> None:
        if bool(state.bulk_options) != (stage_bulk_choice is not None):
            raise ValueError("Compact bulk choices require their operation callback.")
        self.state, self.controls, self.intent = state, controls, intent
        self.build_continue_action, self.stage_bulk_choice = (
            build_continue_action,
            stage_bulk_choice,
        )
        self.pending = Condition(
            lambda: self.intent is not None and self.intent.pending
        )
        editing = (
            has_focus(intent.area) if intent is not None else Condition(lambda: False)
        )
        self.decision_keys_active = ~editing & ~self.pending
        self.response_keys_active = editing & ~self.pending
        # The static title is deliberately absent from the focus topology. Keep the
        # existing choice/editor/action sequence inside its container so Tab restores
        # its prior cursor without submitting or discarding an intent draft.
        self.controller = SurfaceFocusController(
            (
                (
                    FocusSurface(
                        "navigation",
                        self.controls.navigation,
                        move_vertical=self.move_navigation,
                        on_vertical_enter=self.enter_navigation,
                        activate=self.activate_navigation,
                    ),
                )
                if self.state.navigation_visible
                else ()
            )
            + (
                FocusSurface(
                    "decisions",
                    self.controls.decisions,
                    move_vertical=self.move_decisions,
                    on_vertical_enter=self.enter_decisions,
                    activate=self.activate_decision,
                ),
            )
        )

    def response_choice_index(self, item: ResolutionItem | None) -> int | None:
        return (
            self.intent.response_choice_index(item) if self.intent is not None else None
        )

    def has_response_row(self) -> bool:
        return (
            self.intent is not None
            and self.intent.option_uid is None
            and self.intent.response_available(self.state.current_issue())
        )

    def action_rows(self):
        return self.state.action_rows(response_available=self.has_response_row())

    def row_count(self) -> int:
        return self.state.row_count(response_available=self.has_response_row())

    def focus_current_row(self, *, enter_choice_editor: bool = True) -> None:
        item = self.state.current_issue()
        option_count = len(item.options) if item is not None else 0
        response_index = self.response_choice_index(item)
        if (
            enter_choice_editor
            and self.intent is not None
            and response_index is not None
            and self.state.focused_row_index == response_index
        ):
            # Merely landing on choice 2 must not select it. The draft becomes
            # authoritative only after nonblank input is frozen by the caller.
            self.intent.sync_response_field()
            get_app().layout.focus(self.intent.area)
        elif (
            self.intent is not None
            and self.intent.option_uid is None
            and self.intent.response_available(item)
            and self.state.focused_row_index == option_count
        ):
            self.intent.sync_response_field()
            get_app().layout.focus(self.intent.area)
        elif self.state.focused_row_index < option_count:
            get_app().layout.focus(self.controls.choices)
        else:
            get_app().layout.focus(self.controls.actions)

    def move_item(self, delta: int) -> None:
        if not self.state.items:
            return
        self.state.current_issue_index = (self.state.current_issue_index + delta) % len(
            self.state.items
        )
        self.state.focus_selected_choice()
        if self.intent is not None:
            self.intent.sync_response_field()
        self.state.status_message = ""
        if not get_app().layout.has_focus(self.controls.navigation):
            self.focus_current_row()

    def move_row(self, delta: int) -> None:
        self.state.focused_row_index = max(
            0,
            min(self.state.focused_row_index + delta, max(self.row_count() - 1, 0)),
        )
        self.state.status_message = ""
        self.focus_current_row()

    def finish(self) -> None:
        if self.intent is not None and any(
            self.intent.response_needs_refresh(item) for item in self.state.items
        ):
            self.state.status_message = (
                "Your intent changed. Refresh its result before finalizing."
            )
            return
        item = self.state.current_issue()
        action = self.build_continue_action(item.uid if item is not None else None)
        if action is None:
            self.state.status_message = (
                "This action is not ready. Choose a required response."
                if self.state.require_all_decisions
                else "Choose at least one decision; submit any selected Intent before reviewing."
            )
            return
        get_app().exit(result=action)

    def select_choice(self, index: int) -> None:
        item = self.state.current_issue()
        if item is None or not 0 <= index < len(item.options):
            self.state.status_message = "That choice is unavailable."
            return
        option = item.options[index]
        self.state.stage_option(item.uid, option.uid)
        self.state.focused_row_index = index
        self.state.status_message = f"Selected · {safe_terminal_text(option.label)}"
        if (
            self.intent is not None
            and self.intent.option_uid is not None
            and option.uid == self.intent.option_uid(item.uid)
        ):
            self.intent.open_response()

    def activate(self) -> None:
        item = self.state.current_issue()
        option_count = len(item.options) if item is not None else 0
        if item is not None and self.state.focused_row_index < option_count:
            self.select_choice(self.state.focused_row_index)
            return
        action_uid = self.action_rows()[self.state.focused_row_index - option_count].uid
        if action_uid.startswith("bulk:"):
            assert self.stage_bulk_choice is not None
            self.stage_bulk_choice(action_uid.removeprefix("bulk:"))
            self.state.status_message = "Bulk choices staged; finalize to continue."
        elif action_uid == "action:CONTINUE":
            self.finish()
        elif action_uid == "action:RESPONSE" and self.intent is not None:
            self.intent.open_response()
        else:  # pragma: no cover - action rows are closed above
            self.state.status_message = "That action is unavailable."

    def leave_response(self, delta: int) -> None:
        self.state.focused_row_index = max(
            0,
            min(self.state.focused_row_index + delta, max(self.row_count() - 1, 0)),
        )
        self.state.status_message = ""
        item = self.state.current_issue()
        option_count = len(item.options) if item is not None else 0
        get_app().layout.focus(
            self.controls.choices
            if self.state.focused_row_index < option_count
            else self.controls.actions
        )

    def move_navigation(self, _event, _delta):
        # Both buttons occupy one row; vertical movement leaves the row.
        return "BOUNDARY"

    def enter_navigation(self, delta):
        self.state.navigation.cursor_uid = "PREV" if delta > 0 else "NEXT"

    def activate_navigation(self, _event):
        self.move_item(-1 if self.state.navigation.cursor_uid == "PREV" else 1)
        return "HANDLED"

    def move_decisions(self, _event, delta):
        if (self.state.focused_row_index == 0 and delta < 0) or (
            self.state.focused_row_index == self.row_count() - 1 and delta > 0
        ):
            return "BOUNDARY"
        self.move_row(delta)
        return "MOVED"

    def enter_decisions(self, _delta):
        self.state.focused_row_index = 0
        self.focus_current_row()

    def activate_decision(self, _event):
        self.activate()
        return "HANDLED"

    def bind_keys(self, bindings: KeyBindings) -> None:
        @bindings.add("tab", filter=self.decision_keys_active, eager=True)
        def _tab(event) -> None:
            self.controller.focus_relative(event.app, 1, wrap=True)
            event.app.invalidate()

        @bindings.add("s-tab", filter=self.decision_keys_active, eager=True)
        def _back_tab(event) -> None:
            self.controller.focus_relative(event.app, -1, wrap=True)
            event.app.invalidate()

        @bindings.add("left", filter=self.decision_keys_active, eager=True)
        def _left(event) -> None:
            if event.app.layout.has_focus(self.controls.navigation):
                if not self.state.navigation.move(-1):
                    self.move_item(-1)
            else:
                self.move_item(-1)
            event.app.invalidate()

        @bindings.add("right", filter=self.decision_keys_active, eager=True)
        def _right(event) -> None:
            if event.app.layout.has_focus(self.controls.navigation):
                if not self.state.navigation.move(1):
                    self.move_item(1)
            else:
                self.move_item(1)
            event.app.invalidate()

        @bindings.add("up", filter=self.decision_keys_active, eager=True)
        def _up(event) -> None:
            self.controller.move_vertical(event, -1)
            event.app.invalidate()

        @bindings.add("down", filter=self.decision_keys_active, eager=True)
        def _down(event) -> None:
            self.controller.move_vertical(event, 1)
            event.app.invalidate()

        @bindings.add("enter", filter=self.decision_keys_active, eager=True)
        def _enter(event) -> None:
            self.controller.activate(event)
            event.app.invalidate()

        def close_or_back(event) -> None:
            event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))

        @bindings.add("escape", filter=self.decision_keys_active, eager=True)
        @bindings.add("backspace", filter=self.decision_keys_active, eager=True)
        def _back(event) -> None:
            close_or_back(event)

        @bindings.add("escape", filter=self.response_keys_active, eager=True)
        def _response_back(event) -> None:
            self.leave_response(0)
            event.app.invalidate()

        @bindings.add("enter", filter=self.response_keys_active, eager=True)
        def _response_submit(event) -> None:
            self.intent.submit_response(
                0 if self.intent.option_uid is not None else 1,
                self.move_row,
                commit_unchanged=self.intent.option_uid is not None,
            )
            event.app.invalidate()

        @bindings.add("up", filter=self.response_keys_active, eager=True)
        @bindings.add("s-tab", filter=self.response_keys_active, eager=True)
        def _response_up(event) -> None:
            self.leave_response(-1)
            event.app.invalidate()

        @bindings.add("down", filter=self.response_keys_active, eager=True)
        @bindings.add("tab", filter=self.response_keys_active, eager=True)
        def _response_down(event) -> None:
            self.leave_response(1)
            event.app.invalidate()

        @bindings.add(Keys.Any, filter=self.pending, eager=True)
        def _pending_input(event) -> None:
            pass

        @bindings.add("escape", filter=self.pending, eager=True)
        def _cancel_pending(event) -> None:
            close_or_back(event)

        @bindings.add("c-c", eager=True)
        @bindings.add(Keys.SIGINT, eager=True)
        @bind_case_insensitive_key(
            bindings,
            "q",
            filter=self.decision_keys_active,
            eager=True,
        )
        def _close(event) -> None:
            event.app.exit(result=ResolutionWorkbenchAction(kind="CLOSE"))


def bind_scrolling(
    app,
    bindings: KeyBindings,
    interaction: CompactInteraction,
    choice_pane: ScrollableFormattedTextPane,
    response_preview: ScrollableFormattedTextPane | None = None,
    *,
    render_choices: Callable[[], list[tuple[str, str]]],
    render_result: Callable[[], list[tuple[str, str]]],
    has_result: Callable[[], bool],
) -> None:
    """Connect existing wrapped-pane paging without stealing the editor caret."""
    last_fragments = None
    last_position = None
    last_preview_fragments = None

    def refresh_choice_pane(_app):
        nonlocal last_fragments, last_position
        fragments = render_choices()
        position = (
            interaction.state.current_issue_index,
            interaction.state.focused_row_index,
        )
        if fragments != last_fragments:
            choice_pane.set_formatted_text(fragments)
            last_fragments = fragments
        if position != last_position:
            # Moving cards follows the card anchor. Reading a long card keeps
            # its independent wrapped-page position until the choice moves.
            offset = anchor = 0
            for style, text, *_ in fragments:
                if "[SetCursorPosition]" in style:
                    anchor = offset
                offset += len(text)
            choice_pane.text_area.buffer.cursor_position = anchor
            last_position = position

    app.before_render += refresh_choice_pane

    @bindings.add("pageup", filter=has_focus(interaction.controls.choices), eager=True)
    def _page_up(event):
        scroll_wrapped_page(event, direction=-1)

    @bindings.add(
        "pagedown", filter=has_focus(interaction.controls.choices), eager=True
    )
    def _page_down(event):
        scroll_wrapped_page(event, direction=1)

    if response_preview is None:
        return

    def refresh_response_preview(_app):
        nonlocal last_preview_fragments
        fragments = render_result()
        if fragments != last_preview_fragments:
            response_preview.set_formatted_text(fragments, anchor="start")
            last_preview_fragments = fragments

    app.before_render += refresh_response_preview

    def scroll_response_preview(event, direction):
        if not has_result():
            return
        original = event.app.layout.current_control
        event.app.layout.focus(response_preview.text_area)
        try:
            scroll_wrapped_page(event, direction=direction)
        finally:
            event.app.layout.focus(original)

    @bindings.add("pageup", filter=interaction.response_keys_active, eager=True)
    def _response_page_up(event):
        scroll_response_preview(event, -1)

    @bindings.add("pagedown", filter=interaction.response_keys_active, eager=True)
    def _response_page_down(event):
        scroll_response_preview(event, 1)
