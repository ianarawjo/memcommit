"""Interactive Profile provider selection and locked Study inspection."""

from __future__ import annotations

from prompt_toolkit.application import Application, get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import TextArea

from memcommit.exact_command_review import ExactCommandReview
from memcommit.interfaces.console.terminal import require_interactive_terminal
from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.interfaces.tui.components.exact_command_review import (
    render_exact_command_review,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.components.frame import (
    TuiRegion,
    build_focused_frame,
    build_tui_frame,
)
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    bind_tui_interrupt,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    focused_control_style,
)
from memcommit.provider_types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
)
from memcommit.selection import FlatSelectionState, SelectionOption
from memcommit.selection.tui import render_vertical_choice_rows

from memcommit.interfaces.tui.operations.provider.model import (
    ProviderRouteView,
    ProviderTuiAction,
    ProviderTuiSetup,
    ProviderUseDraft,
)


_PROVIDER_OPTIONS = (
    SelectionOption(
        CODEX_CHATGPT_PROVIDER,
        "CODEX CHATGPT",
        "Managed Codex session; an empty model keeps model selection managed.",
    ),
    SelectionOption(
        OLLAMA_PROVIDER,
        "OLLAMA",
        "Local Ollama runtime; an exact model name is required.",
    ),
    SelectionOption(
        OPENROUTER_PROVIDER,
        "OPENROUTER",
        "OpenRouter route; an exact provider/model slug is required.",
    ),
)


def _route_summary(route: ProviderRouteView) -> str:
    parts = [route.provider_id, f"model {route.model or 'Codex managed'}"]
    if route.provider_id == CODEX_CHATGPT_PROVIDER:
        parts.append(f"reasoning {route.reasoning_effort or 'none'}")
    parts.append(f"timeout {route.timeout_seconds:g}s")
    return " · ".join(parts)


def _normalized_optional(text: str) -> str | None:
    value = text.strip()
    return value or None


def provider_use_exact_command_review(
    setup: ProviderTuiSetup,
    draft: ProviderUseDraft,
) -> ExactCommandReview:
    """Project one complete route selection to its exact public command."""

    argv = ["mem", "provider", "use", draft.provider_id]
    if draft.model is not None:
        argv.extend(("--model", draft.model))
    if draft.provider_id == CODEX_CHATGPT_PROVIDER:
        assert draft.reasoning_effort is not None
        argv.extend(("--reasoning", draft.reasoning_effort))
    elif draft.provider_id == OLLAMA_PROVIDER:
        argv.extend(("--thinking", draft.ollama_thinking))
    elif draft.provider_id == OPENROUTER_PROVIDER:
        argv.append("--zdr" if draft.openrouter_zdr else "--no-zdr")
    if draft.operation is not None:
        argv.extend(("--operation", draft.operation))

    target = (
        f"operation {draft.operation!r}"
        if draft.operation is not None
        else "the Profile default"
    )
    effects = [
        f"Update {target} for Profile {setup.profile_name!r}.",
        "Store provider, model, reasoning, and timeout as one complete route.",
        "Do not contact the provider; mem provider probe remains a separate action.",
    ]
    if draft.provider_id == OLLAMA_PROVIDER:
        effects.append(
            "Retain the selected Ollama model and thinking mode as machine-local transport settings."
        )
    elif draft.provider_id == OPENROUTER_PROVIDER:
        effects.append(
            "Retain the displayed zero-data-retention choice as a machine-local transport setting."
        )
    return ExactCommandReview(tuple(argv), tuple(effects))


def provider_reset_exact_command_review(
    setup: ProviderTuiSetup,
    *,
    operation: str | None,
) -> ExactCommandReview:
    """Project removal of one authored Profile route to an exact command."""

    argv = ["mem", "provider", "reset"]
    if operation is not None:
        argv.extend(("--operation", operation))
    target = f"operation {operation!r}" if operation is not None else "the default"
    return ExactCommandReview(
        tuple(argv),
        (
            f"Remove {target} route authored by Profile {setup.profile_name!r}.",
            "Resume the inherited machine default or Profile default route.",
            "Do not contact a provider and do not change Context or Memory data.",
        ),
    )


def _provider_routes_text(setup: ProviderTuiSetup) -> str:
    lines = [
        f"DEFAULT · {_route_summary(setup.default_route)}",
        f"SOURCE · {setup.route_source.lower()}",
        "",
        "OPERATION ROUTES",
    ]
    if setup.operation_routes:
        width = max(len(operation) for operation, _route in setup.operation_routes)
        lines.extend(
            f"{operation:<{width}} · {_route_summary(route)}"
            for operation, route in setup.operation_routes
        )
    else:
        lines.append("none configured · all operations use the default")
    return "\n".join(lines)


def _run_general_provider_tui(
    setup: ProviderTuiSetup,
    *,
    app_input: Input | None,
    app_output: Output | None,
) -> ProviderTuiAction | None:
    bindings = KeyBindings()
    selected = FlatSelectionState(
        _PROVIDER_OPTIONS,
        cursor_uid=setup.default_route.provider_id,
        selected_uid=setup.default_route.provider_id,
        allow_empty=False,
    )
    models = {
        provider: setup.known_model(provider) or ""
        for provider in (
            CODEX_CHATGPT_PROVIDER,
            OLLAMA_PROVIDER,
            OPENROUTER_PROVIDER,
        )
    }
    if setup.default_route.model is not None:
        models[setup.default_route.provider_id] = setup.default_route.model
    model_area = TextArea(
        text=models[selected.selected_uid or CODEX_CHATGPT_PROVIDER],
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="provider-model",
    )
    operation_area = TextArea(
        text="",
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        name="provider-operation",
    )
    reasoning = HorizontalChoiceState(
        tuple(
            HorizontalChoiceOption(value, value.upper(), "")
            for value in CODEX_REASONING_EFFORTS
        ),
        selected_uid=(
            setup.default_route.reasoning_effort
            if setup.default_route.provider_id == CODEX_CHATGPT_PROVIDER
            and setup.default_route.reasoning_effort in CODEX_REASONING_EFFORTS
            else "none"
        ),
    )
    status = {"value": ""}
    action_kind = {"value": "USE"}
    changing_model = {"value": False}

    def active_provider() -> str:
        assert selected.selected_uid is not None
        return selected.selected_uid

    def provider_rows() -> list[tuple[str, str]]:
        width = max(40, get_app().output.get_size().columns - 8)
        return render_vertical_choice_rows(
            selected,
            focused=get_app().layout.has_focus(provider_control),
            content_width=width,
            numbered=False,
            blank_between=False,
        )

    provider_control = FormattedTextControl(
        provider_rows,
        focusable=True,
        show_cursor=False,
    )
    provider_frame = build_focused_frame(
        Window(provider_control, wrap_lines=True),
        title="DEFAULT PROVIDER · ↑/↓ SELECT",
        is_focused=lambda: get_app().layout.has_focus(provider_control),
        height=Dimension.exact(8),
    )
    model_frame = build_focused_frame(
        model_area,
        title=lambda: (
            "MODEL · EMPTY = CODEX MANAGED"
            if active_provider() == CODEX_CHATGPT_PROVIDER
            else "MODEL · REQUIRED"
        ),
        is_focused=lambda: get_app().layout.has_focus(model_area),
        height=Dimension.exact(3),
    )
    reasoning_control = FormattedTextControl(
        lambda: render_horizontal_choice(
            reasoning,
            title="REASONING",
            focused=get_app().layout.has_focus(reasoning_control),
        ),
        focusable=True,
        show_cursor=False,
    )
    reasoning_frame = build_focused_frame(
        Window(reasoning_control, wrap_lines=True),
        title="CODEX REASONING",
        is_focused=lambda: get_app().layout.has_focus(reasoning_control),
        height=Dimension.exact(3),
    )
    operation_frame = build_focused_frame(
        operation_area,
        title="OPERATION · OPTIONAL · EMPTY = PROFILE DEFAULT",
        is_focused=lambda: get_app().layout.has_focus(operation_area),
        height=Dimension.exact(3),
    )
    routes_control = FormattedTextControl(
        lambda: [("class:report-neutral", _provider_routes_text(setup))],
        focusable=False,
        show_cursor=False,
    )
    routes_frame = build_focused_frame(
        Window(routes_control, wrap_lines=True),
        title="CURRENT EFFECTIVE ROUTES · NOT CONTACTED",
        is_focused=lambda: False,
        height=Dimension(min=5, preferred=7, max=10),
    )

    def current_draft() -> ProviderUseDraft:
        provider_id = active_provider()
        model = _normalized_optional(model_area.text)
        operation = _normalized_optional(operation_area.text)
        return ProviderUseDraft(
            provider_id=provider_id,
            model=model,
            reasoning_effort=(
                reasoning.selected_uid
                if provider_id == CODEX_CHATGPT_PROVIDER
                else None
            ),
            operation=operation,
            ollama_thinking=setup.ollama_thinking,
            openrouter_zdr=setup.openrouter_zdr,
        )

    def current_review() -> ExactCommandReview:
        operation = _normalized_optional(operation_area.text)
        if action_kind["value"] == "RESET":
            configured = dict(setup.operation_routes)
            if operation is None and not setup.has_profile_default:
                raise ValueError("This Profile has no authored default route to reset.")
            if operation is not None and operation not in configured:
                raise ValueError(
                    f"Operation {operation!r} has no authored Profile route to reset."
                )
            return provider_reset_exact_command_review(setup, operation=operation)
        return provider_use_exact_command_review(setup, current_draft())

    def todo_rows() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        try:
            review_text = render_exact_command_review(current_review())
            action = (
                "PRESS ENTER TO RESET THE EXACT ROUTE"
                if action_kind["value"] == "RESET"
                else "PRESS ENTER TO APPLY THE EXACT ROUTE"
            )
        except (TypeError, ValueError) as error:
            review_text = "ROUTE INCOMPLETE · " + display_escape_text(str(error))
            action = "COMPLETE THE ROUTE FIRST"
        button_style = focused_control_style(focused=focused)
        return [
            ("class:report-neutral", review_text + "\n\n"),
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (button_style, f"[ {action} ]"),
        ]

    todo_control = FormattedTextControl(todo_rows, focusable=True, show_cursor=False)
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title=lambda: "TO DO · EXACT " + action_kind["value"] + " COMMAND",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension(min=10, preferred=12, max=14),
    )
    header = Window(
        FormattedTextControl(
            " MEM PROVIDER · PROFILE-AWARE ROUTING\n"
            f" PROFILE · {safe_terminal_text(setup.profile_name)} · GENERAL · EDITABLE · NOT CONTACTED"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )

    def footer_text() -> str:
        if status["value"]:
            return " " + display_escape_text(status["value"])
        if get_app().layout.has_focus(provider_control):
            return " ↑/↓ choose · Enter/Tab model · R reset · P probe current route · Esc close"
        if get_app().layout.has_focus(model_area):
            return (
                " Type exact model · Enter/Tab continue · Esc back · Backspace deletes"
            )
        if get_app().layout.has_focus(reasoning_control):
            return " ←/→ reasoning · Enter/Tab operation · R reset · P probe · Esc back"
        if get_app().layout.has_focus(operation_area):
            return " Optional operation key · Enter/Tab review · Esc back · Backspace deletes"
        return " Enter apply exact command · R reset instead · P probe current route · Esc back"

    footer = Window(
        FormattedTextControl(footer_text),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(provider_frame),
        TuiRegion(model_frame),
        TuiRegion(
            ConditionalContainer(
                content=reasoning_frame,
                filter=Condition(lambda: active_provider() == CODEX_CHATGPT_PROVIDER),
            )
        ),
        TuiRegion(operation_frame),
        TuiRegion(routes_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[ProviderTuiAction | None] = Application(
        layout=Layout(root, focused_element=provider_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def mark_use() -> None:
        action_kind["value"] = "USE"
        status["value"] = ""

    def replace_model(text: str) -> None:
        changing_model["value"] = True
        try:
            model_area.text = text
            model_area.buffer.cursor_position = len(text)
        finally:
            changing_model["value"] = False

    def move_provider(_event, delta: int) -> SurfaceMoveResult:
        models[active_provider()] = model_area.text
        if not selected.move(delta):
            return "BOUNDARY"
        selected.select_cursor(toggle=False)
        replace_model(models[active_provider()])
        mark_use()
        return "MOVED"

    def enter_model(event) -> SurfaceActionResult:
        event.app.layout.focus(model_area)
        model_area.buffer.cursor_position = len(model_area.text)
        return "HANDLED"

    def enter_operation(event) -> SurfaceActionResult:
        event.app.layout.focus(operation_area)
        operation_area.buffer.cursor_position = len(operation_area.text)
        return "HANDLED"

    def submit(event) -> SurfaceActionResult:
        try:
            current_review()
            if action_kind["value"] == "RESET":
                result = ProviderTuiAction(
                    "RESET",
                    operation=_normalized_optional(operation_area.text),
                )
            else:
                result = ProviderTuiAction("USE", draft=current_draft())
        except (TypeError, ValueError) as error:
            status["value"] = str(error)
            return "HANDLED"
        event.app.exit(result=result)
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        return (
            FocusSurface(
                "PROVIDER",
                provider_control,
                move_vertical=move_provider,
                activate=enter_model,
            ),
            FocusSurface("MODEL", model_area),
            *(
                (
                    FocusSurface(
                        "REASONING",
                        reasoning_control,
                        activate=enter_operation,
                    ),
                )
                if active_provider() == CODEX_CHATGPT_PROVIDER
                else ()
            ),
            FocusSurface("OPERATION", operation_area),
            FocusSurface("TO_DO", todo_control, activate=submit),
        )

    surfaces = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surfaces, vertical=True)

    @bindings.add("enter", filter=has_focus(model_area), eager=True)
    def _model_continue(event) -> None:
        if active_provider() == CODEX_CHATGPT_PROVIDER:
            event.app.layout.focus(reasoning_control)
        else:
            event.app.layout.focus(operation_area)
        event.app.invalidate()

    @bindings.add("enter", filter=has_focus(operation_area), eager=True)
    def _operation_continue(event) -> None:
        event.app.layout.focus(todo_control)
        event.app.invalidate()

    reasoning_focus = has_focus(reasoning_control)

    @bindings.add("left", filter=reasoning_focus, eager=True)
    def _previous_reasoning(event) -> None:
        reasoning.move(-1)
        mark_use()
        event.app.invalidate()

    @bindings.add("right", filter=reasoning_focus, eager=True)
    def _next_reasoning(event) -> None:
        reasoning.move(1)
        mark_use()
        event.app.invalidate()

    def changed_input(_buffer) -> None:
        if not changing_model["value"]:
            mark_use()
        try:
            get_app().invalidate()
        except RuntimeError:
            pass

    model_area.buffer.on_text_changed += changed_input
    operation_area.buffer.on_text_changed += changed_input

    read_only_focus = (
        has_focus(provider_control)
        | has_focus(reasoning_control)
        | has_focus(todo_control)
    )

    @bind_case_insensitive_key(bindings, "r", filter=read_only_focus, eager=True)
    def _stage_reset(event) -> None:
        action_kind["value"] = "RESET"
        status["value"] = ""
        event.app.layout.focus(todo_control)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "p", filter=read_only_focus, eager=True)
    def _probe(event) -> None:
        event.app.exit(
            result=ProviderTuiAction(
                "PROBE",
                operation=_normalized_optional(operation_area.text),
            )
        )

    def close(event) -> None:
        event.app.exit(result=None)

    def return_to_provider(event) -> bool:
        if event.app.layout.has_focus(provider_control):
            return False
        action_kind["value"] = "USE"
        status["value"] = ""
        event.app.layout.focus(provider_control)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        dispatch_tui_back(event, return_to_provider, close=close)
        event.app.invalidate()

    def _interrupt(event) -> None:
        close(event)

    bind_tui_interrupt(bindings, _interrupt)

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return None
    if result is not None and not isinstance(result, ProviderTuiAction):
        raise ValueError("Provider TUI returned an invalid action.")
    return result


def _run_study_provider_tui(
    setup: ProviderTuiSetup,
    *,
    app_input: Input | None,
    app_output: Output | None,
) -> ProviderTuiAction | None:
    bindings = KeyBindings()
    route_text = _provider_routes_text(setup)
    route_text += (
        "\n\nPINNED STUDY POLICY\n"
        f"version · {setup.study_policy_version}\n"
        f"digest  · {setup.study_policy_digest}"
    )
    routes_control = FormattedTextControl(
        [("class:report-neutral", route_text)],
        focusable=False,
        show_cursor=False,
    )
    routes_frame = build_focused_frame(
        Window(routes_control, wrap_lines=True),
        title="STUDY PROVIDER ROUTES · LOCKED · NOT CONTACTED",
        is_focused=lambda: False,
        height=Dimension(min=14, preferred=18, max=24),
    )

    def todo_rows() -> list[tuple[str, str]]:
        focused = get_app().layout.has_focus(todo_control)
        style = focused_control_style(focused=focused)
        return [
            (
                "class:report-neutral",
                "Provider routing is fixed for Study reproducibility.\n"
                "Switch to an ordinary Profile to edit routes.\n\n",
            ),
            ("[SetCursorPosition]", "") if focused else ("", ""),
            (style, "[ PRESS ENTER TO PROBE THE PINNED DEFAULT ROUTE ]"),
        ]

    todo_control = FormattedTextControl(todo_rows, focusable=True, show_cursor=False)
    todo_frame = build_focused_frame(
        Window(todo_control, wrap_lines=True),
        title="TO DO · READ-ONLY VERIFICATION",
        is_focused=lambda: get_app().layout.has_focus(todo_control),
        height=Dimension.exact(7),
    )
    header = Window(
        FormattedTextControl(
            " MEM PROVIDER · PROFILE-AWARE ROUTING\n"
            f" PROFILE · {safe_terminal_text(setup.profile_name)} · STUDY · LOCKED"
        ),
        height=Dimension.exact(2),
        dont_extend_height=True,
    )
    footer = Window(
        FormattedTextControl(
            " Enter/P probe pinned default · Esc/Q close · use mem profile to switch"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(routes_frame),
        TuiRegion(todo_frame),
        TuiRegion(footer),
    )
    app: Application[ProviderTuiAction | None] = Application(
        layout=Layout(root, focused_element=todo_control),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    @bindings.add("enter", eager=True)
    @bind_case_insensitive_key(bindings, "p", eager=True)
    def _probe(event) -> None:
        event.app.exit(result=ProviderTuiAction("PROBE"))

    @bindings.add("escape", eager=True)
    @bind_case_insensitive_key(bindings, "q", eager=True)
    def _close(event) -> None:
        event.app.exit(result=None)

    def _interrupt(event) -> None:
        event.app.exit(result=None)

    bind_tui_interrupt(bindings, _interrupt)

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return None
    if result is not None and not isinstance(result, ProviderTuiAction):
        raise ValueError("Study Provider TUI returned an invalid action.")
    return result


def run_provider_tui(
    setup: ProviderTuiSetup,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ProviderTuiAction | None:
    """Run editable general setup or read-only locked Study inspection."""

    if not isinstance(setup, ProviderTuiSetup):
        raise TypeError("Provider TUI requires a typed setup.")
    if require_tty:
        require_interactive_terminal(
            "Interactive Provider configuration",
            snapshot_hint="Use mem provider status outside a terminal.",
        )
    if setup.mode == "STUDY":
        return _run_study_provider_tui(
            setup,
            app_input=app_input,
            app_output=app_output,
        )
    return _run_general_provider_tui(
        setup,
        app_input=app_input,
        app_output=app_output,
    )


__all__ = [
    "provider_reset_exact_command_review",
    "provider_use_exact_command_review",
    "run_provider_tui",
]
