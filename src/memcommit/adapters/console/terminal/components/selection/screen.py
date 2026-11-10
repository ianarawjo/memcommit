"""Setup choices built from the shared selection grammar and focus controller."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame.rendering import (
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.components.selection.rendering import (
    render_vertical_choice_cards,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    SingleSelectionState,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)


def _run_screen(layout, bindings, *, app_input=None, app_output=None):
    app = Application(
        layout=layout,
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        style=MEMCOMMIT_TUI_STYLE,
        input=app_input,
        output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return None


def run_selection_screen(
    title: str,
    description: str,
    options: tuple[SelectionOption, ...],
    *,
    heading: str = "mem",
    app_input=None,
    app_output=None,
):
    selected = options[0].value
    state = SingleSelectionState(
        options=options,
        cursor_value=selected,
        selected_value=selected,
        allow_empty=False,
    )

    choices_control = FormattedTextControl(
        text=lambda: render_vertical_choice_cards(
            state, focused=layout.has_focus(choices_control), content_width=90
        ),
        focusable=True,
        show_cursor=False,
    )

    header_window = Window(
        content=FormattedTextControl(
            text=" " + heading + "\n " + description + "\n",
        ),
        height=3,
    )
    choices_frame = build_focused_frame(
        Window(
            content=choices_control,
            always_hide_cursor=True,
            right_margins=[ScrollbarMargin()],
        ),
        title=title,
        is_focused=lambda: layout.has_focus(choices_control),
        height=Dimension(
            min=4,
            preferred=min(30, len(options) * 5 + 2),
            max=min(30, len(options) * 5 + 2),
        ),
    )
    footer_window = Window(
        content=FormattedTextControl(text=" ↑/↓ choose · Enter continue · Esc cancel"),
        height=1,
    )

    layout = Layout(
        container=build_tui_frame(
            header_window,
            choices_frame,
            footer_window,
        ),
        focused_element=choices_control,
    )

    bindings = KeyBindings()

    def move(event, delta):
        changed = state.move(delta)
        state.select_cursor(toggle=False)
        return "MOVED" if changed else "BOUNDARY"

    def accept(event):
        event.app.exit(result=state.selected_value)
        return "HANDLED"

    def cancel(event):
        event.app.exit(result=None)
        return "HANDLED"

    controller = SurfaceFocusController(
        surfaces=[
            FocusSurface(
                uid="choice",
                control=choices_control,
                move_vertical=move,
                activate=accept,
                back=cancel,
            )
        ]
    )
    bind_surface_navigation(bindings=bindings, controller=controller, back=True)
    bindings.add("c-c", eager=True)(cancel)
    return _run_screen(
        layout=layout,
        bindings=bindings,
        app_input=app_input,
        app_output=app_output,
    )
