"""Compact one-shot Source, Question, and Answer workbench for Query."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    ConditionalContainer,
    Dimension,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.adapters.console.terminal.components.operation_context_scope_editor.readable_scope_editor import (
    CompactReadableScopeControl,
)
from memcommit.adapters.console.terminal.components.retrieve_answer_save import (
    RetrieveAnswerSavePanel,
)
from memcommit.adapters.console.terminal.components.operation_context_scope_editor.new_context_editor import (
    suggest_fresh_context_name,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.adapters.console.terminal.components.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.terminal.components.focus.controller import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.console.terminal.components.frame import (
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.console.terminal.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.adapters.console.terminal.core.activity import busy_suffix
from memcommit.adapters.console.terminal.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.source_projection.presentation import SourceDisplayValue

from memcommit.adapters.console.commands.query.workbench.presentation import (
    QueryAnswerFocus,
    project_query_answer_clipboard,
    query_answer_reference_document,
    query_answer_stop_count,
    render_query_answer_fragments,
)
from memcommit.adapters.console.commands.query.workbench.model import (
    OrdinaryQueryRunner,
    QueryWorkbenchResponse,
    QueryWorkbenchResult,
)


def _query_save_location_stem(context_name: str, question: str) -> str:
    words = "-".join(question.strip().split()) or "query-answer"
    safe = "".join(
        "-" if character in "/\\:" or ord(character) < 32 else character
        for character in words
    ).strip("-.")
    if not safe:
        safe = "query-answer"
    return f"{context_name}/answers/{safe[:48].rstrip('-.') or 'query-answer'}"


def run_query_workbench(
    context_names: Sequence[str],
    *,
    current_context: str,
    initial_context: str,
    run_ordinary: OrdinaryQueryRunner,
    initial_include_descendants: bool = True,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    clipboard_writer: Callable[[str], None] | None = None,
    help_binder: Callable[..., object] | None = None,
    local_context_names: Sequence[str] | None = None,
    validate_save_location: Callable[[str], object] | None = None,
) -> QueryWorkbenchResult:
    """Open a process-local Query surface without connecting before Enter."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Query",
            snapshot_hint='Pass a question, for example: mem query "What changed?".',
        )
    if any(
        not isinstance(value, bool)
        for value in (
            initial_include_descendants,
            False,
        )
    ):
        raise ValueError("Initial Query scope choices must be booleans.")
    local_catalog = tuple(
        dict.fromkeys(
            context_names if local_context_names is None else local_context_names
        )
    )
    if any(not isinstance(name, str) or not name for name in local_catalog):
        raise ValueError("Query local Context names must be nonblank text.")

    response: QueryWorkbenchResponse | None = None
    answer_focus = QueryAnswerFocus()
    status = {"value": "ENTER A QUESTION"}
    copy_receipt: PlainTextClipboardReceipt | None = None
    background_turn: BackgroundExecutorTurn[QueryWorkbenchResponse] = (
        BackgroundExecutorTurn()
    )

    def clear_answer(message: str) -> None:
        nonlocal copy_receipt, response
        response = None
        copy_receipt = None
        answer_focus.reset()
        answer_window.vertical_scroll = 0
        status["value"] = message

    def update_status(message: str) -> None:
        status["value"] = message

    ordinary_scope = CompactReadableScopeControl(
        context_names,
        current_name=current_context,
        initial_targets=(initial_context,),
        include_descendants=initial_include_descendants,
        annotations=annotations,
        input_name="query-readable-scope-context",
        on_change=clear_answer,
        on_status=update_status,
        locked=lambda: background_turn.busy,
    )
    bindings = KeyBindings()
    question_area = TextArea(
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        read_only=Condition(lambda: background_turn.busy),
        name="query-question",
    )
    save_panel = RetrieveAnswerSavePanel(
        content_summary=lambda: "COMPLETE QUERY ANSWER",
        action_label=lambda _mode: "SAVE COMPLETE ANSWER",
        initial_location=suggest_fresh_context_name(
            _query_save_location_stem(initial_context, "query-answer"),
            local_catalog,
        ),
        context_names=local_catalog,
        current_context=(current_context if current_context in local_catalog else None),
        validate_location=validate_save_location,
        input_name="query-save-location",
        on_status=update_status,
    )
    save_location_edit = {"edited": False, "programmatic": False}

    def save_location_changed(_buffer) -> None:
        if not save_location_edit["programmatic"]:
            save_location_edit["edited"] = True

    save_panel.name.input.buffer.on_text_changed += save_location_changed

    scope_container = ordinary_scope.container

    def render_answer() -> list[tuple[str, str]]:
        return render_query_answer_fragments(
            response,
            focus=answer_focus,
            focused=app.layout.has_focus(answer_control),
        )

    answer_control = FormattedTextControl(
        render_answer,
        focusable=True,
        show_cursor=False,
    )
    answer_window = Window(
        answer_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    header = Window(
        FormattedTextControl(" MEM QUERY"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    scope_frame = Frame(scope_container, title="SCOPE")
    question_frame = Frame(
        question_area,
        title="QUESTION · ENTER TO ASK",
        height=Dimension.exact(3),
    )

    def answer_title() -> str:
        if background_turn.busy:
            return f"ANSWER · QUERYING {busy_suffix(background_turn.frame)}"
        return "ANSWER"

    answer_frame = Frame(
        answer_window,
        title=answer_title,
        height=Dimension(min=7, weight=2),
    )

    def render_footer() -> str | list[tuple[str, str]]:
        if background_turn.busy:
            return (
                f" QUERYING {busy_suffix(background_turn.frame)} · "
                "H Help · Ctrl-C closes after query"
            )
        if app.layout.has_focus(question_area):
            navigation = "Enter ask · Tab/Shift-Tab panes · Esc close"
        elif app.layout.has_focus(answer_control):
            navigation = (
                "↑/↓ answer/References · y copy focused · "
                "Y copy complete answer · / question · Esc back"
            )
        elif ordinary_scope.browser_open:
            navigation = (
                "↑/↓ move · ←/→ tree · Enter/Space check · "
                "A expand all · Esc close Browse"
            )
        elif save_panel.browser_open:
            navigation = "↑/↓ move · ←/→ tree · Enter place · Esc close Browse"
        else:
            navigation = (
                "↑/↓ move/cross · ←/→ adjust · Enter activate · "
                "/ question · Esc back · H Help · Q close"
            )
        if copy_receipt is not None and app.layout.has_focus(answer_control):
            return [
                (copy_receipt.style, " " + copy_receipt.message),
                ("", f" · {navigation}"),
            ]
        return f" {safe_terminal_text(status['value'])} · {navigation}"

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    save_container = ConditionalContainer(
        save_panel.container,
        filter=Condition(lambda: response is not None and not background_turn.busy),
    )
    root = build_tui_frame(
        header,
        scope_frame,
        question_frame,
        answer_frame,
        save_container,
        footer,
    )
    app: Application[QueryWorkbenchResult] = Application(
        layout=Layout(root, focused_element=question_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
        style=merge_styles([MEMCOMMIT_TUI_STYLE, SEMANTIC_VIEWER_STYLE]),
    )

    def scope_focused() -> bool:
        controls = [
            ordinary_scope.input,
            ordinary_scope.browse_control,
            ordinary_scope.range_control,
            ordinary_scope.tree_control,
        ]
        return any(app.layout.has_focus(control) for control in controls)

    bind_focused_frame_style(scope_frame, is_focused=scope_focused)
    bind_focused_frame_style(
        question_frame,
        is_focused=lambda: app.layout.has_focus(question_area),
    )
    bind_focused_frame_style(
        answer_frame,
        is_focused=lambda: app.layout.has_focus(answer_control),
    )

    def question_changed(_buffer) -> None:
        if response is not None and not background_turn.busy:
            clear_answer("QUESTION CHANGED · PRESS ENTER TO QUERY")
            app.invalidate()

    question_area.buffer.on_text_changed += question_changed

    def _move_question(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _enter_question(_delta: int) -> None:
        question_area.buffer.cursor_position = len(question_area.text)

    def _move_answer(_event, delta: int) -> SurfaceMoveResult:
        nonlocal copy_receipt
        document = query_answer_reference_document(response)
        if document is not None:
            moved = answer_focus.move(response, delta)
            if moved:
                copy_receipt = None
            return "MOVED" if moved else "BOUNDARY"
        render_info = answer_window.render_info
        if render_info is None:
            return "BOUNDARY"
        previous = answer_window.vertical_scroll
        maximum = max(0, render_info.content_height - render_info.window_height)
        answer_window.vertical_scroll = max(0, min(previous + delta, maximum))
        if answer_window.vertical_scroll != previous:
            copy_receipt = None
            return "MOVED"
        return "BOUNDARY"

    def _enter_answer(delta: int) -> None:
        if query_answer_reference_document(response) is not None:
            answer_focus.enter(response, delta)
            return
        render_info = answer_window.render_info
        maximum = (
            0
            if render_info is None
            else max(0, render_info.content_height - render_info.window_height)
        )
        answer_window.vertical_scroll = 0 if delta > 0 else maximum

    def _focus_question(event) -> SurfaceActionResult:
        event.app.layout.focus(question_area)
        question_area.buffer.cursor_position = len(question_area.text)
        return "HANDLED"

    def _query(event) -> SurfaceActionResult:
        nonlocal copy_receipt, response
        if background_turn.busy:
            status["value"] = "A Query is already running."
            return "HANDLED"
        try:
            request_targets, request_descendants = ordinary_scope.request_scope()
            ordinary_request = OrdinaryQueryRequest(
                question=question_area.text.strip(),
                target_names=request_targets,
                include_descendants=request_descendants,
            )

            def work() -> QueryWorkbenchResponse:
                next_response = run_ordinary(ordinary_request)
                if (
                    not isinstance(next_response, OrdinaryQueryResponse)
                    or next_response.request != ordinary_request
                ):
                    raise ValueError(
                        "Query inputs changed while the request was running. "
                        "Ask the question again."
                    )
                return next_response
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"

        def commit(next_response: QueryWorkbenchResponse) -> None:
            nonlocal copy_receipt, response
            response = next_response
            copy_receipt = None
            answer_focus.reset()
            answer_window.vertical_scroll = 0
            if not save_location_edit["edited"]:
                source_name = next_response.request.target_names[0]
                save_location_edit["programmatic"] = True
                try:
                    save_panel.set_location(
                        suggest_fresh_context_name(
                            _query_save_location_stem(
                                source_name,
                                next_response.request.question,
                            ),
                            local_catalog,
                        )
                    )
                finally:
                    save_location_edit["programmatic"] = False
            status["value"] = "ANSWER READY"

        def fail(error: Exception) -> None:
            detail = " ".join(safe_terminal_text(str(error)).split())
            if len(detail) > 240:
                detail = detail[:239].rstrip() + "…"
            status["value"] = f"QUERY FAILED · {type(error).__name__}: {detail}"

        def return_to_surface() -> None:
            app.layout.focus(answer_control if response is not None else question_area)

        def close_after_query() -> None:
            app.exit(result=QueryWorkbenchResult("CLOSED", response))

        background_turn.start(
            event.app,
            work=work,
            on_success=commit,
            on_error=fail,
            on_idle=return_to_surface,
            on_close=close_after_query,
        )
        status["value"] = "QUERYING"
        event.app.layout.focus(answer_control)
        return "HANDLED"

    def _apply_save(event) -> SurfaceActionResult:
        if background_turn.busy:
            status["value"] = "Wait for the current Query to finish."
            return "HANDLED"
        if response is None:
            status["value"] = "ASK A QUESTION BEFORE SAVING"
            return "HANDLED"
        try:
            destination = save_panel.validate_candidate()
        except (OSError, TypeError, ValueError) as error:
            status["value"] = str(error)
            event.app.layout.focus(save_panel.name.input)
            return "HANDLED"
        event.app.exit(
            result=QueryWorkbenchResult(
                "SAVE",
                response,
                destination,
            )
        )
        return "HANDLED"

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if ordinary_scope.browser_open:
            return (ordinary_scope.browser_surface(uid_prefix="query-scope"),)
        if save_panel.browser_open:
            return (save_panel.browser_surface(uid_prefix="query-save"),)
        scope_surfaces = ordinary_scope.normal_surfaces(uid_prefix="query-scope")
        surfaces = [
            *scope_surfaces,
            FocusSurface(
                "question",
                question_area,
                move_vertical=_move_question,
                activate=_query,
                on_vertical_enter=_enter_question,
            ),
            FocusSurface(
                "answer",
                answer_control,
                move_vertical=_move_answer,
                activate=_focus_question,
                on_vertical_enter=_enter_answer,
            ),
        ]
        if response is not None and not background_turn.busy:
            surfaces.extend(
                save_panel.normal_surfaces(
                    activate_action=_apply_save,
                    uid_prefix="query-save",
                )
            )
        return tuple(surfaces)

    surface_focus = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surface_focus)
    ordinary_scope.bind_keybindings(bindings)
    save_panel.bind_keybindings(bindings)

    @bindings.add("tab", filter=has_focus(ordinary_scope.tree_control), eager=True)
    @bindings.add("s-tab", filter=has_focus(ordinary_scope.tree_control), eager=True)
    @bindings.add(
        "backspace", filter=has_focus(ordinary_scope.tree_control), eager=True
    )
    def _leave_context_browser(event) -> None:
        ordinary_scope.close_browser(event)
        event.app.invalidate()

    scope_focus = (
        has_focus(ordinary_scope.input)
        | has_focus(ordinary_scope.browse_control)
        | has_focus(ordinary_scope.range_control)
        | has_focus(ordinary_scope.tree_control)
    )
    save_focus = (
        has_focus(save_panel.name.input)
        | has_focus(save_panel.browse_control)
        | has_focus(save_panel.tree_control)
        | has_focus(save_panel.action_control)
    )
    read_only_focus = (
        (scope_focus | has_focus(answer_control) | save_focus)
        & ~has_focus(ordinary_scope.input)
        & ~has_focus(save_panel.name.input)
    )
    if help_binder is not None:
        help_binder(
            bindings,
            filter=read_only_focus,
            app_input=app_input,
            app_output=app_output,
            study_surface="query",
        )

    def copy_answer(event, *, whole_document: bool) -> None:
        nonlocal copy_receipt
        try:
            projection = project_query_answer_clipboard(
                response,
                focus=answer_focus,
                whole_document=whole_document,
            )
        except ValueError as error:
            copy_receipt = clipboard_failure_receipt(error)
        else:
            copy_receipt = copy_plain_text(
                projection.text,
                success_message=projection.label,
                writer=clipboard_writer,
            )
        event.app.invalidate()

    @bindings.add("y", filter=has_focus(answer_control), eager=True)
    def _copy_focused_answer(event) -> None:
        copy_answer(event, whole_document=False)

    @bindings.add("Y", filter=has_focus(answer_control), eager=True)
    def _copy_complete_answer(event) -> None:
        copy_answer(event, whole_document=True)

    @bindings.add("/", filter=read_only_focus, eager=True)
    def _question_shortcut(event) -> None:
        _focus_question(event)
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(answer_control), eager=True)
    def _answer_page_up(event) -> None:
        nonlocal copy_receipt
        if query_answer_reference_document(response) is not None:
            previous = answer_focus.stop_index
            answer_focus.stop_index = max(0, previous - 4)
            if answer_focus.stop_index != previous:
                copy_receipt = None
        else:
            render_info = answer_window.render_info
            step = 1 if render_info is None else max(1, render_info.window_height - 1)
            previous = answer_window.vertical_scroll
            answer_window.vertical_scroll = max(0, previous - step)
            if answer_window.vertical_scroll != previous:
                copy_receipt = None
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(answer_control), eager=True)
    def _answer_page_down(event) -> None:
        nonlocal copy_receipt
        if query_answer_reference_document(response) is not None:
            previous = answer_focus.stop_index
            answer_focus.stop_index = min(
                query_answer_stop_count(response) - 1,
                previous + 4,
            )
            if answer_focus.stop_index != previous:
                copy_receipt = None
        else:
            render_info = answer_window.render_info
            step = 1 if render_info is None else max(1, render_info.window_height - 1)
            maximum = (
                answer_window.vertical_scroll + step
                if render_info is None
                else max(0, render_info.content_height - render_info.window_height)
            )
            previous = answer_window.vertical_scroll
            answer_window.vertical_scroll = min(maximum, previous + step)
            if answer_window.vertical_scroll != previous:
                copy_receipt = None
        event.app.invalidate()

    @bindings.add(
        "backspace",
        filter=read_only_focus
        & ~has_focus(ordinary_scope.tree_control)
        & ~has_focus(save_panel.tree_control)
        & (Condition(lambda: True)),
        eager=True,
    )
    def _back_to_question(event) -> None:
        _focus_question(event)
        event.app.invalidate()

    def close(event) -> None:
        if background_turn.request_close():
            status["value"] = "Closing after the current Query finishes."
            event.app.invalidate()
            return
        event.app.exit(result=QueryWorkbenchResult("CLOSED", response))

    def _return_to_question(event) -> bool:
        if event.app.layout.has_focus(question_area):
            return False
        _focus_question(event)
        return True

    @bindings.add("escape", eager=True)
    def _escape(event) -> None:
        if ordinary_scope.close_browser(event):
            event.app.invalidate()
            return
        if save_panel.close_browser(event):
            event.app.invalidate()
            return
        dispatch_tui_back(event, _return_to_question, close=close)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "q", filter=read_only_focus, eager=True)
    def _close_read_only(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bindings.add("c-d", eager=True)
    def _close_anywhere(event) -> None:
        close(event)

    try:
        result = app.run()
    except (EOFError, KeyboardInterrupt):
        return QueryWorkbenchResult("CLOSED", response)
    if not isinstance(result, QueryWorkbenchResult):
        raise ValueError("Query workbench returned an invalid result.")
    return result
