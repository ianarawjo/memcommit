"""Layout assembly and runner for the decision screen."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.cursor_shapes import CursorShape, SimpleCursorShapeConfig
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles

from memcommit.adapters.console.terminal.core.activity import BUSY_INTERVAL_SECONDS
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.adapters.console.terminal.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.selection.input_card import (
    build_choice_input_card,
)
from memcommit.adapters.console.terminal.components.scrollable_pane.component import (
    build_scrollable_formatted_text_pane,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionWorkbenchAction,
    ResolutionWorkbenchView,
)

from .screen_state import DecisionScreenState
from .inputs import CompactDecisionInput, CompactScreenPresentation
from .intent import IntentEditor
from .components.header import render_header
from .components.navigation import render_navigation
from .components.issue_details import render_issue_details
from .components.choice_cards import render_choice_cards, has_trailing_choices
from .components.intent_result import (
    has_intent_result,
    render_intent_result_diff,
    render_intent_result_title,
)
from .components.decision_controls import render_decision_controls
from .components.footer import render_footer
from .interaction import CompactControls, CompactInteraction, bind_scrolling


def build_compact_application(
    state: DecisionScreenState,
    *,
    build_continue_action: Callable[[str | None], ResolutionWorkbenchAction | None],
    stage_bulk_choice: Callable[[str], None] | None = None,
    intent: IntentEditor | None = None,
    choice_previews: Mapping[str, tuple[tuple[str, str], ...]] | None = None,
    header_label: str | None = None,
    activation_hint: str = "select/apply",
    app_input: Input | None = None,
    app_output: Output | None = None,
) -> Application[ResolutionWorkbenchAction]:
    """Compose the existing layout; callers may instead assemble the parts directly."""

    def is_focused(role):
        return controls.is_focused(role)

    def content_width():
        return max(30, get_app().output.get_size().columns - 4)

    def choice_cards(*, after_response=False):
        return render_choice_cards(
            state,
            intent=intent,
            choice_previews=choice_previews,
            is_focused=is_focused,
            content_width=content_width,
            after_response=after_response,
        )

    header_control = FormattedTextControl(lambda: render_header(state, header_label))
    navigation_control = FormattedTextControl(
        lambda: render_navigation(state, is_focused=is_focused),
        focusable=state.navigation_visible,
        show_cursor=False,
    )
    choice_pane = build_scrollable_formatted_text_pane("RESOLVE CHOICES")
    body_control = choice_pane.text_area.control
    action_control = FormattedTextControl(
        lambda: render_decision_controls(state, intent=intent, is_focused=is_focused),
        focusable=True,
        show_cursor=False,
    )
    footer_control = FormattedTextControl(
        lambda: render_footer(
            state, intent=intent, is_focused=is_focused, activation_hint=activation_hint
        )
    )
    body_window = choice_pane.text_area.window
    body_window.dont_extend_height = Condition(lambda: True)
    # Read-only cursors anchor scrolling; only the editable field shows a caret.
    body_window.always_hide_cursor = Condition(lambda: True)
    children = [body_window]
    response_preview = None
    if intent is not None:
        response_preview = build_scrollable_formatted_text_pane(
            "INTENT RESULT", buffer_name="compact-resolution-result"
        )
        response_preview.text_area.window.always_hide_cursor = Condition(lambda: True)
        response_preview.text_area.window.height = Dimension(min=1, max=10)
        response_preview.text_area.window.dont_extend_height = Condition(lambda: True)
        editor = build_choice_input_card(
            intent.area,
            label=intent.title,
            selected=lambda: intent.response_selected(state.current_issue()),
            focused=lambda: controls.is_focused("intent")
            or (
                intent.response_choice_index(state.current_issue())
                == state.focused_row_index
                and controls.is_focused("choices")
            ),
            width=content_width,
            detail=response_preview.text_area.window,
            detail_title=lambda: render_intent_result_title(state, intent),
            detail_visible=Condition(
                lambda: has_intent_result(state, intent, choice_previews)
            ),
        )
        children.append(
            editor
            if intent.option_uid is None
            else ConditionalContainer(
                editor,
                filter=Condition(
                    lambda: intent.response_supported(state.current_issue())
                ),
            )
        )
    children.append(
        ConditionalContainer(
            Window(
                FormattedTextControl(
                    lambda: choice_cards(after_response=True),
                    show_cursor=False,
                ),
                wrap_lines=True,
                dont_extend_height=True,
            ),
            filter=Condition(lambda: has_trailing_choices(state, intent)),
        )
    )
    children.append(
        build_focused_frame(
            Window(action_control, wrap_lines=True, dont_extend_height=True),
            title="OTHER ACTIONS",
            is_focused=lambda: controls.is_focused("actions"),
        )
    )
    decision_body = HSplit(children)
    controls = CompactControls(
        navigation_control,
        body_control,
        action_control,
        decision_body,
        intent.area if intent else None,
    )
    root = build_tui_frame(
        TuiRegion(
            HSplit(
                [
                    Window(header_control, height=1, dont_extend_height=True),
                    ConditionalContainer(
                        Window(navigation_control, height=1, dont_extend_height=True),
                        filter=Condition(lambda: bool(state.items)),
                    ),
                    Window(height=1, char=" "),
                ]
            )
        ),
        TuiRegion(decision_body),
        TuiRegion(
            Window(footer_control, height=Dimension.exact(1), dont_extend_height=True)
        ),
    )
    initial_response_index = (
        intent.response_choice_index(state.current_issue())
        if intent is not None
        else None
    )
    initial_focus = (
        intent.area
        if intent is not None
        and initial_response_index is not None
        and state.focused_row_index == initial_response_index
        else body_control
    )
    bindings = KeyBindings()
    interaction = CompactInteraction(
        state,
        controls,
        intent=intent,
        build_continue_action=build_continue_action,
        stage_bulk_choice=stage_bulk_choice,
    )
    app: Application[ResolutionWorkbenchAction] = Application(
        layout=Layout(root, focused_element=initial_focus),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        refresh_interval=BUSY_INTERVAL_SECONDS
        if intent is not None and intent.prepare is not None
        else None,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
        cursor=SimpleCursorShapeConfig(CursorShape.BLINKING_BEAM)
        if intent is not None and intent.option_uid is not None
        else None,
    )
    bind_scrolling(
        app,
        bindings,
        interaction,
        choice_pane,
        response_preview,
        render_choices=lambda: render_issue_details(state) + choice_cards(),
        render_result=lambda: render_intent_result_diff(state, intent, choice_previews),
        has_result=lambda: has_intent_result(state, intent, choice_previews),
    )
    interaction.bind_keys(bindings)
    return app


def run_compact_resolution_decisions(
    view: ResolutionWorkbenchView | Callable[[], ResolutionWorkbenchView],
    *,
    decisions: CompactDecisionInput,
    presentation: CompactScreenPresentation,
    header_label: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
) -> ResolutionWorkbenchAction:
    """Stage choices in the default compact layout and return the caller's action."""
    supplier = view if callable(view) else lambda: view
    state = DecisionScreenState(
        supplier,
        decisions.selected_option,
        decisions.select_choice,
        lambda: presentation.continue_label,
        decisions.bulk_options,
        presentation.show_item_navigation,
        require_all_decisions=presentation.require_all_decisions,
    )
    state.initialize_selection()
    response = decisions.intent
    intent = (
        IntentEditor(
            state,
            read_text=response.response_text,
            stage_text=response.submit_intent,
            prepare=response.prepare_response,
            validator=response.validate_intent,
            option_uid=response.response_option_uid,
            title=presentation.response_title,
        )
        if response is not None
        else None
    )
    app = build_compact_application(
        state,
        intent=intent,
        choice_previews=decisions.choice_previews,
        header_label=header_label,
        activation_hint=presentation.activation_hint,
        build_continue_action=decisions.confirm,
        stage_bulk_choice=decisions.select_for_all if decisions.bulk_options else None,
        app_input=app_input,
        app_output=app_output,
    )
    try:
        return app.run()
    except (EOFError, KeyboardInterrupt):
        return ResolutionWorkbenchAction(kind="CLOSE")
