"""Setup choices built from the shared selection grammar and focus controller."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.initial_setup.model_selection import (
    SetupModelSelectionState,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceFocusController,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame.model import TuiRegion
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
    FlatSelectionState,
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


def choose_setup_action(
    title: str,
    description: str,
    options: tuple[SelectionOption, ...],
    *,
    initial_uid=None,
    app_input=None,
    app_output=None,
):
    selected = (
        initial_uid
        if initial_uid in {option.uid for option in options}
        else options[0].uid
    )
    state = FlatSelectionState(
        options, cursor_uid=selected, selected_uid=selected, allow_empty=False
    )
    bindings = KeyBindings()
    control = FormattedTextControl(
        lambda: render_vertical_choice_cards(
            state, focused=layout.has_focus(control), content_width=90
        ),
        focusable=True,
        show_cursor=False,
    )
    frame = build_focused_frame(
        Window(control, always_hide_cursor=True, right_margins=[ScrollbarMargin()]),
        title=title,
        is_focused=lambda: layout.has_focus(control),
        height=Dimension(
            min=4,
            preferred=min(30, len(options) * 5 + 2),
            max=min(30, len(options) * 5 + 2),
        ),
    )
    layout = Layout(
        build_tui_frame(
            TuiRegion(
                Window(
                    FormattedTextControl(" mem · initial setup\n " + description + "\n"), height=3
                )
            ),
            TuiRegion(frame),
            TuiRegion(
                Window(
                    FormattedTextControl(" ↑/↓ choose · Enter continue · Esc cancel"),
                    height=1,
                )
            ),
        ),
        focused_element=control,
    )

    def move(event, delta):
        changed = state.move(delta)
        state.select_cursor(toggle=False)
        return "MOVED" if changed else "BOUNDARY"

    def accept(event):
        event.app.exit(result=state.selected_uid)
        return "HANDLED"

    def cancel(event):
        event.app.exit(result=None)
        return "HANDLED"

    controller = SurfaceFocusController(
        [
            FocusSurface(
                "choice", control, move_vertical=move, activate=accept, back=cancel
            )
        ]
    )
    bind_surface_navigation(bindings, controller, back=True)
    bindings.add("c-c", eager=True)(cancel)
    return _run_screen(layout, bindings, app_input=app_input, app_output=app_output)


def choose_setup_model(
    catalog: tuple[CodexModelOption, ...],
    *,
    initial_model: str | None = None,
    initial_reasoning_effort: str | None = None,
    app_input=None,
    app_output=None,
):
    state = SetupModelSelectionState(
        catalog,
        initial_model=initial_model,
        initial_reasoning_effort=initial_reasoning_effort,
    )
    bindings = KeyBindings()
    models = FormattedTextControl(
        lambda: render_vertical_choice_rows(
            state.models,
            focused=layout.has_focus(models),
            content_width=90,
            numbered=False,
            blank_between=False,
        ),
        focusable=True,
        show_cursor=False,
    )
    reasoning = FormattedTextControl(
        lambda: (
            render_horizontal_choice_row(
                state.reasoning, focused=layout.has_focus(reasoning)
            )
            if state.reasoning
            else [("", "No selectable reasoning settings for this model.")]
        ),
        focusable=True,
        show_cursor=False,
    )
    model_frame = build_focused_frame(
        Window(models, always_hide_cursor=True, right_margins=[ScrollbarMargin()]),
        title="MODEL",
        is_focused=lambda: layout.has_focus(models),
        # The shared renderer anchors after a row's newline. Reserve its
        # trailing row so final-model focus does not scroll a fitting list.
        height=Dimension(
            min=4,
            preferred=max(4, min(30, len(catalog) + 3)),
            max=max(4, min(30, len(catalog) + 3)),
        ),
    )
    reasoning_frame = build_focused_frame(
        Window(reasoning, always_hide_cursor=True, wrap_lines=True),
        title="REASONING",
        is_focused=lambda: layout.has_focus(reasoning),
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
            f" {state.reasoning_notice or description}"
        )

    layout = Layout(
        build_tui_frame(
            TuiRegion(
                Window(
                    FormattedTextControl(
                        " mem · initial setup · Codex login checked\n Choose a model and its supported reasoning setting.\n"
                    ),
                    height=3,
                )
            ),
            TuiRegion(model_frame),
            TuiRegion(reasoning_frame),
            TuiRegion(
                Window(
                    FormattedTextControl(selection_details), height=3, wrap_lines=True
                )
            ),
            TuiRegion(
                Window(
                    FormattedTextControl(
                        " ↑/↓ model · Tab reasoning · ←/→ effort · Enter check connection · Esc back"
                    ),
                    height=2,
                    wrap_lines=True,
                )
            ),
        ),
        focused_element=models,
    )

    def move_model(event, delta):
        return "MOVED" if state.move_model(delta) else "BOUNDARY"

    def accept(event):
        event.app.exit(result=state.selection)
        return "HANDLED"

    def cancel(event):
        event.app.exit(result=None)
        return "HANDLED"

    controller = SurfaceFocusController(
        lambda: [
            FocusSurface(
                "model", models, move_vertical=move_model, activate=accept, back=cancel
            ),
            *(
                [
                    FocusSurface(
                        "reasoning",
                        reasoning,
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
    bind_surface_navigation(bindings, controller, back=True)

    @bindings.add(
        "left",
        filter=Condition(
            lambda: layout.has_focus(reasoning) and state.reasoning is not None
        ),
        eager=True,
    )
    @bindings.add(
        "right",
        filter=Condition(
            lambda: layout.has_focus(reasoning) and state.reasoning is not None
        ),
        eager=True,
    )
    def move_reasoning(event):
        state.move_reasoning(-1 if event.key_sequence[-1].key == "left" else 1)
        event.app.invalidate()

    bindings.add("c-c", eager=True)(cancel)
    return _run_screen(layout, bindings, app_input=app_input, app_output=app_output)
