"""Small setup screens composed from shared selection, input and focus controls."""

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, Layout, Window

from memcommit.adapters.console.terminal.components.exact_name import (
    ExactNameFieldControl,
    ExactNameFieldView,
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
    render_vertical_choice_cards,
)
from memcommit.adapters.console.terminal.components.selection.state import (
    FlatSelectionState,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.application.operations.setup.application import SETUP_PROVIDERS
from memcommit.providers.clients.completion import model_name


def choose_setup_action(
    title: str,
    description: str,
    options: tuple[SelectionOption, ...],
    *,
    with_model=False,
    initial_uid=None,
    initial_model=None,
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
    model = ExactNameFieldControl.create(
        ExactNameFieldView(
            value=initial_model
            or next(
                (
                    option.default_model
                    for option in SETUP_PROVIDERS
                    if option.uid == selected
                ),
                "",
            ),
            label="MODEL (OPTIONAL)",
            state="DEFAULT",
            detail="Use the default, or Tab to enter a different model ID.",
            value_label="Model",
            validate=model_name,
        ),
        input_name="setup-model",
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
        Window(control, always_hide_cursor=True),
        title=title,
        is_focused=lambda: layout.has_focus(control),
        height=min(30, len(options) * 5 + 2),
    )
    regions = [
        TuiRegion(
            Window(FormattedTextControl(" mem setup\n " + description + "\n"), height=3)
        ),
        TuiRegion(frame),
    ]
    if with_model:
        regions.append(TuiRegion(model.frame))
    error_message = ""
    regions.append(
        TuiRegion(
            Window(
                FormattedTextControl(
                    lambda: (
                        error_message
                        or (
                            " ↑/↓ choose · Enter continue · Tab model · Esc cancel"
                            if with_model
                            else " ↑/↓ choose · Enter continue · Esc cancel"
                        )
                    )
                ),
                height=1,
            )
        )
    )
    layout = Layout(build_tui_frame(*regions), focused_element=control)

    def move(event, delta):
        changed = state.move(delta)
        state.select_cursor(toggle=False)
        if changed and with_model:
            model.set_text(
                next(
                    option.default_model
                    for option in SETUP_PROVIDERS
                    if option.uid == state.selected_uid
                )
            )
        return "MOVED" if changed else "CONSUMED"

    def accept(event):
        nonlocal error_message
        try:
            result = (
                (state.selected_uid, model.validate_candidate())
                if with_model
                else state.selected_uid
            )
        except (ValueError, RuntimeError) as error:
            error_message = str(error)
            event.app.invalidate()
            return "HANDLED"
        event.app.exit(result=result)
        return "HANDLED"

    surfaces = [FocusSurface("choice", control, move_vertical=move, activate=accept)]
    if with_model:
        surfaces.append(FocusSurface("model", model.input, activate=accept))
    controller = SurfaceFocusController(surfaces)
    bind_surface_navigation(bindings, controller)

    @bindings.add("escape", eager=True)
    @bindings.add("c-c", eager=True)
    def cancel(event):
        event.app.exit(result=None)

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
