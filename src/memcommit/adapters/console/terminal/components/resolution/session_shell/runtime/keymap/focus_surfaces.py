"""Dynamic focus-Surface topology for the Resolution Session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus

from memcommit.adapters.console.terminal.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    WorkbenchPane,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.binding_state import (
    ResolutionKeyBindingState,
)


@dataclass(frozen=True)
class ResolutionSurfaceControls:
    """Focusable controls participating in the full session topology."""

    viewer: Any
    responses: Any
    items: Any
    save_location: Any
    todo: Any


@dataclass(frozen=True)
class ResolutionSurfaceHandlers:
    """Operation-aware movement supplied by the session runtime."""

    focus_pane: Callable[[WorkbenchPane], None]
    move_viewer: Callable[[Any, int], SurfaceMoveResult]
    enter_viewer: Callable[[int], None]
    move_responses: Callable[[Any, int], SurfaceMoveResult]
    enter_responses: Callable[[int], None]
    move_items: Callable[[Any, int], SurfaceMoveResult]
    enter_items: Callable[[int], None]
    move_single_row: Callable[[Any, int], SurfaceMoveResult]
    activate: Callable[[Any], SurfaceActionResult]


def bind_resolution_surface_navigation(
    bindings: KeyBindings,
    controls: ResolutionSurfaceControls,
    handlers: ResolutionSurfaceHandlers,
    *,
    response_visible: Callable[[], bool],
    destination_available: bool,
) -> SurfaceFocusController:
    """Bind the dynamic Viewer→Responses→Items→Save→To Do topology."""

    def visible_focus_surfaces() -> tuple[FocusSurface, ...]:
        surfaces = [
            FocusSurface(
                "viewer",
                controls.viewer,
                move_vertical=handlers.move_viewer,
                activate=handlers.activate,
                on_focus=lambda: handlers.focus_pane("viewer"),
                on_vertical_enter=handlers.enter_viewer,
            )
        ]
        if response_visible():
            surfaces.append(
                FocusSurface(
                    "responses",
                    controls.responses,
                    move_vertical=handlers.move_responses,
                    activate=handlers.activate,
                    on_focus=lambda: handlers.focus_pane("responses"),
                    on_vertical_enter=handlers.enter_responses,
                )
            )
        surfaces.append(
            FocusSurface(
                "items",
                controls.items,
                move_vertical=handlers.move_items,
                activate=handlers.activate,
                on_focus=lambda: handlers.focus_pane("items"),
                on_vertical_enter=handlers.enter_items,
            )
        )
        if destination_available:
            surfaces.append(
                FocusSurface(
                    "save-location",
                    controls.save_location,
                    move_vertical=handlers.move_single_row,
                    activate=handlers.activate,
                    on_focus=lambda: handlers.focus_pane("save_location"),
                )
            )
        surfaces.append(
            FocusSurface(
                "todo",
                controls.todo,
                move_vertical=handlers.move_single_row,
                activate=handlers.activate,
                on_focus=lambda: handlers.focus_pane("todo"),
            )
        )
        return tuple(surfaces)

    controller = SurfaceFocusController(visible_focus_surfaces)
    bind_surface_navigation(bindings, controller)
    return controller


def bind_focus_surfaces(
    state: ResolutionKeyBindingState,
    activate_current_surface: Callable[[Any], None],
) -> None:
    """Bind movement and activation across the visible Surface topology."""

    bindings = state.bindings
    controller = state.controller
    controls = state.controls
    options = state.options
    navigation_accelerator = state.navigation_accelerator
    viewer_controller = state.viewer_controller
    move = state.review_flow.move
    active_viewer_sections = controls.active_viewer_sections
    viewer_section_index = controls.viewer_section_index
    session_navigation = controller.session_navigation
    sync_response_state = controller.sync_response_state
    response_state = controller.response_state
    set_status = controller.set_status
    current_view = controller.current_view
    split_viewer_items = options.split_viewer_items
    body_control = controls.body_control
    responses_control = controls.responses_control
    items_control = controls.items_control
    destination_control = controls.destination_control
    todo_control = controls.todo_control
    _focus_surface_pane = state.review_flow.focus_surface_pane
    response_visible = controls.response_visible
    destination_available = options.destination_available
    writable_input_focused = controls.writable_input_focused
    _open_or_choose = activate_current_surface
    global_comment = controller.global_comment
    current_response_heading = state.editors.current_response_heading
    other_direction_editor = controller.other_direction_editor
    composer = controls.composer
    input_heading = controller.input_heading
    input_area = controls.input_area

    def _move_viewer_surface(event, delta: int) -> SurfaceMoveResult:
        sections = active_viewer_sections()
        if viewer_controller.nested_uid is not None:
            # Nested Memory reading deliberately keeps its own Escape boundary;
            # reaching the last wrapped line must not silently leave the reader.
            navigation_accelerator.move(delta, app=event.app, move_one=move)
            return "CONSUMED"
        index = viewer_section_index()
        if (delta < 0 and index == 0) or (delta > 0 and index == len(sections) - 1):
            navigation_accelerator.reset()
            return "BOUNDARY"
        navigation_accelerator.move(delta, app=event.app, move_one=move)
        return "MOVED"

    def _enter_viewer_surface(delta: int) -> None:
        sections = active_viewer_sections()
        if sections:
            session_navigation.section_uid = sections[0 if delta > 0 else -1].uid

    def _move_responses_surface(_event, delta: int) -> SurfaceMoveResult:
        target = sync_response_state()
        if target is None:
            return "BOUNDARY"
        before = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        response_state.move_focus(target, delta)
        after = (
            response_state.section,
            response_state.option_cursor_uid,
        )
        set_status("")
        return "MOVED" if after != before else "BOUNDARY"

    def _enter_responses_surface(delta: int) -> None:
        target = sync_response_state()
        if target is None:
            return
        if delta < 0 or not target.choices:
            response_state.focus_response()
            return
        response_state.open_options(target)
        choices = response_state.choice_state
        if choices is not None:
            choices.cursor_uid = choices.options[0].uid

    def _move_items_surface(_event, delta: int) -> SurfaceMoveResult:
        active_view = current_view()
        total_rows = len(active_view.items) + 1
        before = session_navigation.row_index
        if (delta < 0 and before == 0) or (delta > 0 and before == total_rows - 1):
            return "BOUNDARY"
        move(delta)
        return "MOVED" if session_navigation.row_index != before else "BOUNDARY"

    def _enter_items_surface(delta: int) -> None:
        # Entering a frame chooses its nearest edge without opening that row.
        # In particular, crossing out of final review must not close the review
        # until the person actually moves or activates an Items selection.
        session_navigation.row_index = 0 if delta > 0 else len(current_view().items)

    def _single_row_surface_move(
        _event,
        delta: int,
    ) -> SurfaceMoveResult:
        if session_navigation.pane == "todo" and controller.report_decision:
            return "MOVED" if controller.move_report_decision(delta) else "BOUNDARY"
        return "BOUNDARY"

    def _activate_surface(event) -> SurfaceActionResult:
        _open_or_choose(event)
        return "HANDLED"

    if split_viewer_items:
        bind_resolution_surface_navigation(
            bindings,
            ResolutionSurfaceControls(
                viewer=body_control,
                responses=responses_control,
                items=items_control,
                save_location=destination_control,
                todo=todo_control,
            ),
            ResolutionSurfaceHandlers(
                focus_pane=_focus_surface_pane,
                move_viewer=_move_viewer_surface,
                enter_viewer=_enter_viewer_surface,
                move_responses=_move_responses_surface,
                enter_responses=_enter_responses_surface,
                move_items=_move_items_surface,
                enter_items=_enter_items_surface,
                move_single_row=_single_row_surface_move,
                activate=_activate_surface,
            ),
            response_visible=response_visible,
            destination_available=destination_available,
        )
    else:

        @bindings.add("down", filter=~writable_input_focused)
        def _legacy_down(event) -> None:
            move(1)
            event.app.invalidate()

        @bindings.add("up", filter=~writable_input_focused)
        def _legacy_up(event) -> None:
            move(-1)
            event.app.invalidate()

        @bindings.add("enter", filter=~writable_input_focused)
        def _legacy_open_or_choose(event) -> None:
            _open_or_choose(event)

        @bindings.add("tab", filter=has_focus(body_control), eager=True)
        @bindings.add("s-tab", filter=has_focus(body_control), eager=True)
        def _legacy_focus_input(event) -> None:
            active_view = current_view()
            if active_view.input_locked:
                set_status("Resolution input is locked while analysis is pending.")
                event.app.invalidate()
                return
            if "SUBMIT_ITEM" not in active_view.capabilities:
                set_status("Item comments are unavailable here.")
                event.app.invalidate()
                return
            global_comment["value"] = False
            heading = current_response_heading()
            other_direction_editor["open"] = True
            composer.frame.title = heading
            input_heading["value"] = heading
            event.app.layout.focus(input_area)
            event.app.invalidate()
