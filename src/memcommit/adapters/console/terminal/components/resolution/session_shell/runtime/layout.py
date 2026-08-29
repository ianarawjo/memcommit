"""Prompt-toolkit layout composition for the Resolution Session runtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.responses.model import (
    ResponseTarget,
)
from memcommit.adapters.console.terminal.components.responses.state import (
    ResponseFrameState,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)

from memcommit.adapters.console.terminal.components.resolution.session_shell.presentation import (
    RESOLUTION_WORKBENCH_STYLE,
)


@dataclass(frozen=True)
class ResolutionShellWidgets:
    """The already-configured controls composed into one shell layout."""

    body: Any
    body_control: Any
    legacy_inline_input: Any
    responses_window: Any
    responses_control: Any
    composer_frame: Frame
    items_window: Any
    items_control: Any
    destination_frame: Frame
    destination_control: Any
    todo_window: Any
    todo_control: Any
    footer: Any


@dataclass(frozen=True)
class ResolutionShellLayout:
    """Live Application plus the Viewer frame whose semantic title may change."""

    application: Application[ResolutionWorkbenchAction]
    viewer_frame: Frame


def build_resolution_shell_layout(
    widgets: ResolutionShellWidgets,
    *,
    frame_factory: Callable[..., Frame] = Frame,
    bindings: KeyBindings,
    session_navigation: SessionWorkbenchNavigation,
    response_state: ResponseFrameState,
    current_response_target: Callable[[], ResponseTarget | None],
    response_visible: Callable[[], bool],
    split_viewer_items: bool,
    destination_available: bool,
    app_input: Input | None,
    app_output: Output | None,
) -> ResolutionShellLayout:
    """Compose peer frames and their focus styling into one Application."""

    if split_viewer_items:
        viewer_frame = frame_factory(widgets.body, title="VIEWER")
        decision_container = ConditionalContainer(
            widgets.responses_window,
            filter=Condition(
                lambda: (
                    (target := current_response_target()) is not None
                    and target.has_decision
                )
            ),
        )
        responses_frame = frame_factory(
            HSplit([decision_container, widgets.composer_frame]),
            title="RESPONSES",
        )
        responses_container = ConditionalContainer(
            responses_frame,
            filter=Condition(response_visible),
        )
        items_frame = frame_factory(widgets.items_window, title="ITEMS")
        todo_frame = frame_factory(widgets.todo_window, title="TO DO")
        session_frames = [viewer_frame, responses_container, items_frame]
        if destination_available:
            session_frames.append(widgets.destination_frame)
        session_frames.extend([todo_frame, widgets.footer])
        # Semantic surfaces are peers in one top-to-bottom sequence; they are
        # not columns even though the historical flag calls the mode "split".
        root = build_tui_frame(*(TuiRegion(frame) for frame in session_frames))
        bind_focused_frame_style(
            viewer_frame,
            is_focused=lambda: session_navigation.pane == "viewer",
        )
        # Bind the nested box before its parent so one focus state never styles
        # both borders as the active control.
        bind_focused_frame_style(
            widgets.composer_frame,
            is_focused=lambda: (
                session_navigation.pane == "composer"
                or (
                    session_navigation.pane == "responses"
                    and response_state.section == "RESPONSE"
                )
            ),
        )
        bind_focused_frame_style(
            responses_frame,
            is_focused=lambda: session_navigation.pane in {"responses", "composer"},
        )
        bind_focused_frame_style(
            items_frame,
            is_focused=lambda: session_navigation.pane == "items",
        )
        if destination_available:
            bind_focused_frame_style(
                widgets.destination_frame,
                is_focused=lambda: session_navigation.pane == "save_location",
            )
        bind_focused_frame_style(
            todo_frame,
            is_focused=lambda: session_navigation.pane == "todo",
        )
        focused_element = {
            "viewer": widgets.body_control,
            "responses": widgets.responses_control,
            "items": widgets.items_control,
            "save_location": widgets.destination_control,
            "todo": widgets.todo_control,
        }[session_navigation.pane]
    else:
        viewer_frame = frame_factory(
            HSplit([widgets.body, widgets.legacy_inline_input]),
            title="VIEWER",
        )
        bind_focused_frame_style(viewer_frame, is_focused=lambda: True)
        root = build_tui_frame(
            TuiRegion(viewer_frame),
            TuiRegion(widgets.footer),
        )
        focused_element = widgets.body_control

    application: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=focused_element),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, RESOLUTION_WORKBENCH_STYLE]),
    )
    return ResolutionShellLayout(application, viewer_frame)
