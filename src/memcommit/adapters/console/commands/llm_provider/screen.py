"""One provider screen: use saved settings or edit a Codex configuration draft."""

from dataclasses import dataclass
from typing import Literal

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import FormattedTextControl, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin

from memcommit.adapters.console.commands.llm_provider.model_selection import (
    CodexModelAndReasoningSelectionState,
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
from memcommit.adapters.console.terminal.components.selection.state import (
    SingleSelectionState,
)
from memcommit.adapters.console.terminal.components.selection.rendering import (
    render_vertical_choice_rows,
    render_horizontal_choice_row,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.llm_provider.codex_configuration import (
    CodexConfiguration,
)
from memcommit.llm_providers.clients.codex_model_catalog import CodexModelOption


@dataclass(frozen=True)
class ProviderConfigurationAction:
    kind: Literal["USE", "CONFIGURE"]
    configuration: CodexConfiguration


def run_provider_configuration_screen(
    catalog: tuple[CodexModelOption, ...],
    *,
    saved_configuration: CodexConfiguration | None = None,
    active_provider: str | None = None,
    initial_focus: Literal["use", "model"] = "use",
    configuration_action_label: str = "Save Codex configuration",
    app_input=None,
    app_output=None,
) -> ProviderConfigurationAction | None:
    state = CodexModelAndReasoningSelectionState(
        catalog,
        last_selected_model=saved_configuration.model if saved_configuration else None,
        last_selected_reasoning_effort=saved_configuration.reasoning_effort
        if saved_configuration
        else None,
    )
    saved_selection = state.selection
    use_description = (
        "Current provider" if active_provider == "codex_chatgpt" else "Use OpenAI Codex"
    )
    use_state = SingleSelectionState(
        options=(
            SelectionOption(
                value="codex_chatgpt", label="OpenAI Codex", description=use_description
            ),
        ),
        cursor_value="codex_chatgpt",
        selected_value="codex_chatgpt",
        allow_empty=False,
    )
    save_state = SingleSelectionState(
        options=(SelectionOption(value="save", label=configuration_action_label),),
        cursor_value="save",
        selected_value="save",
        allow_empty=False,
    )
    use_control = FormattedTextControl(
        lambda: render_vertical_choice_rows(
            use_state,
            focused=layout.has_focus(use_control),
            content_width=100,
            numbered=False,
            blank_between=False,
        ),
        focusable=True,
        show_cursor=False,
    )
    model_control = FormattedTextControl(
        lambda: render_vertical_choice_rows(
            state.models,
            focused=layout.has_focus(model_control),
            content_width=100,
            numbered=False,
            blank_between=False,
        ),
        focusable=True,
        show_cursor=False,
    )
    reasoning_control = FormattedTextControl(
        lambda: render_horizontal_choice_row(
            state.reasoning, focused=layout.has_focus(reasoning_control)
        )
        if state.reasoning
        else [("", "Provider default; no selectable reasoning setting.")],
        focusable=True,
        show_cursor=False,
    )
    save_control = FormattedTextControl(
        lambda: render_vertical_choice_rows(
            save_state,
            focused=layout.has_focus(save_control),
            content_width=100,
            numbered=False,
            blank_between=False,
        ),
        focusable=True,
        show_cursor=False,
    )

    def frame(control, title, height):
        return build_focused_frame(
            Window(
                content=control,
                always_hide_cursor=True,
                right_margins=[ScrollbarMargin()],
            ),
            title=title,
            is_focused=lambda: layout.has_focus(control),
            height=height,
        )

    def details():
        selection = state.selection
        changed = saved_configuration is None or selection != saved_configuration
        effort_description = next(
            (
                option.description
                for option in state.selected_model.supported_reasoning_efforts
                if option.effort == selection.reasoning_effort
            ),
            "",
        )
        return safe_terminal_text(
            f" Model: {selection.model} · reasoning {selection.reasoning_effort or 'provider default'}\n {effort_description}\n {'Unsaved configuration' if changed else 'Selected configuration'} · USE selects saved settings; TO DO saves the draft."
        )

    configure_frame = build_focused_frame(
        HSplit(
            [
                frame(
                    model_control,
                    "MODEL",
                    Dimension(
                        min=4,
                        preferred=max(4, min(24, len(catalog) + 3)),
                        max=max(4, min(24, len(catalog) + 3)),
                    ),
                ),
                frame(
                    reasoning_control, "REASONING", Dimension(min=3, preferred=4, max=6)
                ),
                Window(
                    content=FormattedTextControl(details), height=3, wrap_lines=True
                ),
            ]
        ),
        title="CONFIGURE · OpenAI Codex",
        is_focused=lambda: False,
    )
    layout = Layout(
        build_tui_frame(
            Window(
                content=FormattedTextControl(
                    " mem · LLM Provider\n User settings · all Profiles and operations"
                ),
                height=3,
            ),
            # The common row renderer anchors after its trailing newline;
            # reserve that row so focus never scrolls the selected label away.
            frame(use_control, "USE", 5),
            configure_frame,
            frame(save_control, "TO DO", 4),
            Window(
                content=FormattedTextControl(
                    " Tab/Shift-Tab move · Up/Down model · Left/Right reasoning · Enter activate/continue · Esc cancel"
                ),
                height=2,
                wrap_lines=True,
            ),
        ),
        focused_element=use_control if initial_focus == "use" else model_control,
    )
    bindings = KeyBindings()

    def cancel(event):
        event.app.exit(result=None)
        return "HANDLED"

    def use_provider(event):
        event.app.exit(result=ProviderConfigurationAction("USE", saved_selection))
        return "HANDLED"

    def continue_editing(event):
        controller.focus_relative(event.app, 1, wrap=False)
        return "HANDLED"

    def save_configuration(event):
        event.app.exit(result=ProviderConfigurationAction("CONFIGURE", state.selection))
        return "HANDLED"

    controller = SurfaceFocusController(
        lambda: [
            FocusSurface(
                "use",
                use_control,
                move_vertical=lambda _e, _d: "BOUNDARY",
                activate=use_provider,
                back=cancel,
            ),
            FocusSurface(
                "model",
                model_control,
                move_vertical=lambda _e, delta: "MOVED"
                if state.move_model(delta)
                else "BOUNDARY",
                activate=continue_editing,
                back=cancel,
            ),
            *(
                [
                    FocusSurface(
                        "reasoning",
                        reasoning_control,
                        move_vertical=lambda _e, _d: "BOUNDARY",
                        activate=continue_editing,
                        back=cancel,
                    )
                ]
                if state.reasoning
                else []
            ),
            FocusSurface(
                "save",
                save_control,
                move_vertical=lambda _e, _d: "BOUNDARY",
                activate=save_configuration,
                back=cancel,
            ),
        ]
    )
    bind_surface_navigation(bindings=bindings, controller=controller, back=True)

    @bindings.add(
        "left",
        filter=Condition(
            lambda: layout.has_focus(reasoning_control) and state.reasoning is not None
        ),
        eager=True,
    )
    @bindings.add(
        "right",
        filter=Condition(
            lambda: layout.has_focus(reasoning_control) and state.reasoning is not None
        ),
        eager=True,
    )
    def move_reasoning(event):
        state.move_reasoning(-1 if event.key_sequence[-1].key == "left" else 1)
        event.app.invalidate()

    bindings.add("c-c", eager=True)(cancel)
    application = Application(
        layout=layout,
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        style=MEMCOMMIT_TUI_STYLE,
        input=app_input,
        output=app_output,
    )
    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return None
