"""Setup choices built from the shared selection grammar and focus controller."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.initial_setup.model_selection import (
    SetupModelAndReasoningSelectionState,
)
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
    render_horizontal_choice_row,
    render_vertical_choice_cards,
    render_vertical_choice_rows,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    SingleSelectionState,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.providers.clients.codex_model_catalog import CodexModelOption


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


def run_setup_selection_screen(
    title: str,
    description: str,
    options: tuple[SelectionOption, ...],
    *,
    app_input=None,
    app_output=None,
):
    selected = options[0].value
    state = SingleSelectionState(
        options=options, cursor_value=selected, selected_value=selected, allow_empty=False
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
            text=" memcommit initial setup\n " + description + "\n",
        ),
        height=3,
    )
    choices_frame = build_focused_frame(
        Window(content=choices_control, always_hide_cursor=True, right_margins=[ScrollbarMargin()]),
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
                uid="choice", control=choices_control, move_vertical=move, activate=accept, back=cancel
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


def run_setup_model_selection_screen(
    catalog: tuple[CodexModelOption, ...],
    *,
    last_selected_model: str | None = None,
    last_selected_reasoning_effort: str | None = None,
    app_input=None,
    app_output=None,
):
    state = SetupModelAndReasoningSelectionState(
        catalog=catalog,
        last_selected_model=last_selected_model,
        last_selected_reasoning_effort=last_selected_reasoning_effort,
    )

    model_choices_control = FormattedTextControl(
        text=lambda: render_vertical_choice_rows(
            state.models,
            focused=layout.has_focus(model_choices_control),
            content_width=90,
            numbered=False,
            blank_between=False,
        ),
        focusable=True,
        show_cursor=False,
    )
    reasoning_choices_control = FormattedTextControl(
        text=lambda: (
            render_horizontal_choice_row(
                state.reasoning, focused=layout.has_focus(reasoning_choices_control)
            )
            if state.reasoning
            else [("", "No selectable reasoning settings for this model.")]
        ),
        focusable=True,
        show_cursor=False,
    )

    header_window = Window(
        content=FormattedTextControl(
            text=" mem · initial setup · Codex login checked\n Choose a model and its supported reasoning setting.\n"
        ),
        height=3,
    )
    model_frame = build_focused_frame(
        Window(
            content=model_choices_control,
            always_hide_cursor=True,
            right_margins=[ScrollbarMargin()],
        ),
        title="MODEL",
        is_focused=lambda: layout.has_focus(model_choices_control),
        # The shared renderer anchors after a row's newline. Reserve its
        # trailing row so final-model focus does not scroll a fitting list.
        height=Dimension(
            min=4,
            preferred=max(4, min(30, len(catalog) + 3)),
            max=max(4, min(30, len(catalog) + 3)),
        ),
    )
    reasoning_frame = build_focused_frame(
        Window(content=reasoning_choices_control, always_hide_cursor=True, wrap_lines=True),
        title="REASONING",
        is_focused=lambda: layout.has_focus(reasoning_choices_control),
        height=Dimension(min=3, preferred=4, max=6),
    )

    def selection_details():
        effort = state.selection.reasoning_effort
        description = next(
            (
                option.description
                for option in state.selected_model.supported_reasoning_efforts
                if option.effort == effort
            ),
            "",
        )
        return safe_terminal_text(
            f" Selected: {state.selected_model.model} · reasoning {effort or 'provider default'}\n"
            f" Model default: {state.selected_model.default_reasoning_effort or 'provider default'}\n"
            f" {description}"
        )

    selection_details_window = Window(
        content=FormattedTextControl(text=selection_details),
        height=3,
        wrap_lines=True,
    )
    footer_window = Window(
        content=FormattedTextControl(
            text=" ↑/↓ model · Tab reasoning · ←/→ effort · Enter check connection · Esc back"
        ),
        height=2,
        wrap_lines=True,
    )

    layout = Layout(
        container=build_tui_frame(
            header_window,
            model_frame,
            reasoning_frame,
            selection_details_window,
            footer_window,
        ),
        focused_element=model_choices_control,
    )

    bindings = KeyBindings()

    def move_model(event, delta):
        return "MOVED" if state.move_model(delta) else "BOUNDARY"

    def accept(event):
        event.app.exit(result=state.selection)
        return "HANDLED"

    def cancel(event):
        event.app.exit(result=None)
        return "HANDLED"

    controller = SurfaceFocusController(
        surfaces=lambda: [
            FocusSurface(
                uid="model",
                control=model_choices_control,
                move_vertical=move_model,
                activate=accept,
                back=cancel,
            ),
            *(
                [
                    FocusSurface(
                        uid="reasoning",
                        control=reasoning_choices_control,
                        move_vertical=lambda _event, _delta: "BOUNDARY",
                        activate=accept,
                        back=cancel,
                    )
                ]
                if state.reasoning
                else []
            ),
        ]
    )
    bind_surface_navigation(bindings=bindings, controller=controller, back=True)

    @bindings.add(
        "left",
        filter=Condition(
            lambda: layout.has_focus(reasoning_choices_control) and state.reasoning is not None
        ),
        eager=True,
    )
    @bindings.add(
        "right",
        filter=Condition(
            lambda: layout.has_focus(reasoning_choices_control) and state.reasoning is not None
        ),
        eager=True,
    )
    def move_reasoning(event):
        state.move_reasoning(-1 if event.key_sequence[-1].key == "left" else 1)
        event.app.invalidate()

    bindings.add("c-c", eager=True)(cancel)
    return _run_screen(
        layout=layout,
        bindings=bindings,
        app_input=app_input,
        app_output=app_output,
    )
