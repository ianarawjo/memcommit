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
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.styles import merge_styles
from prompt_toolkit.widgets import Frame, TextArea

from memcommit.context_targeting.tui.compact_scope import (
    CompactReadableScopeControl,
)
from memcommit.adapters.interfaces.console.terminal import require_interactive_terminal
from memcommit.adapters.interfaces.console.text import safe_terminal_text
from memcommit.adapters.interfaces.tui.components.background_turn import BackgroundExecutorTurn
from memcommit.adapters.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    bind_focused_frame_style,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.adapters.interfaces.tui.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.adapters.interfaces.tui.core.activity import busy_suffix
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.source_projection.presentation import SourceDisplayValue

from memcommit.adapters.interfaces.tui.operations.query.adapter import (
    QUERY_VIEW_LABEL,
    QueryAnswerFocus,
    project_query_answer_clipboard,
    query_answer_reference_document,
    query_answer_stop_count,
    render_query_answer_fragments,
)
from memcommit.adapters.interfaces.tui.operations.query.model import (
    GrantedQueryRunner,
    OrdinaryQueryRunner,
    QueryWorkbenchResponse,
    QueryWorkbenchResult,
)
from memcommit.adapters.interfaces.tui.operations.query.query_view_scope import (
    CompactQueryViewScopeControl,
)


def run_query_workbench(
    context_names: Sequence[str],
    *,
    current_context: str,
    initial_context: str,
    query_targets: Sequence[GrantedQueryTarget],
    run_ordinary: OrdinaryQueryRunner,
    run_granted: GrantedQueryRunner,
    initial_query_target: GrantedQueryTarget | None = None,
    initial_include_descendants: bool = True,
    initial_follow_embeds: bool = True,
    initial_federate_descendants: bool = True,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    initial_language: str = "en",
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    clipboard_writer: Callable[[str], None] | None = None,
    help_binder: Callable[..., object] | None = None,
) -> QueryWorkbenchResult:
    """Open a process-local Query surface without connecting before Enter."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Query",
            snapshot_hint='Pass a question, for example: mem query "What changed?".',
        )
    targets = tuple(query_targets)
    if len({target.grant_uid for target in targets}) != len(targets):
        raise ValueError("Query-only target identities must be distinct.")
    if initial_query_target is not None and initial_query_target not in targets:
        raise ValueError("The initial Query View is outside the authorized catalog.")
    if any(
        not isinstance(value, bool)
        for value in (
            initial_include_descendants,
            initial_follow_embeds,
            initial_federate_descendants,
        )
    ):
        raise ValueError("Initial Query scope choices must be booleans.")
    if not isinstance(initial_language, str) or not initial_language:
        raise ValueError("Query language must be nonblank.")

    source_options = [HorizontalChoiceOption("ORDINARY", "VISIBLE CONTEXTS")]
    if targets:
        source_options.append(HorizontalChoiceOption("GRANTED", QUERY_VIEW_LABEL))
    source_choice = HorizontalChoiceState(
        tuple(source_options),
        "GRANTED" if initial_query_target is not None else "ORDINARY",
    )
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
        follow_embeds=initial_follow_embeds,
        annotations=annotations,
        input_name="query-readable-scope-context",
        on_change=clear_answer,
        on_status=update_status,
        locked=lambda: background_turn.busy,
    )
    query_view_scope = (
        CompactQueryViewScopeControl(
            targets,
            initial_target=initial_query_target or targets[0],
            federate_descendants=initial_federate_descendants,
            on_change=clear_answer,
            on_status=update_status,
            locked=lambda: background_turn.busy,
        )
        if targets
        else None
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

    def granted_mode() -> bool:
        return source_choice.selected_uid == "GRANTED"

    source_type_control: FormattedTextControl

    def render_source_type() -> list[tuple[str, str]]:
        return render_horizontal_choice(
            source_choice,
            title="SOURCE",
            focused=app.layout.has_focus(source_type_control),
        )

    source_type_control = FormattedTextControl(
        render_source_type,
        focusable=True,
        show_cursor=False,
    )
    scope_container = HSplit(
        [
            Window(
                source_type_control,
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            ConditionalContainer(
                ordinary_scope.container,
                filter=Condition(lambda: not granted_mode()),
            ),
            ConditionalContainer(
                query_view_scope.container
                if query_view_scope is not None
                else Window(),
                filter=Condition(granted_mode),
            ),
        ]
    )

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
        elif query_view_scope is not None and query_view_scope.browser_open:
            navigation = "↑/↓ move · Enter/Space select · Esc close Browse"
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
    root = build_tui_frame(
        TuiRegion(header),
        TuiRegion(scope_frame),
        TuiRegion(question_frame),
        TuiRegion(answer_frame),
        TuiRegion(footer),
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
            source_type_control,
            ordinary_scope.input,
            ordinary_scope.browse_control,
            ordinary_scope.range_control,
            ordinary_scope.embed_control,
            ordinary_scope.tree_control,
        ]
        if query_view_scope is not None:
            controls.extend(
                [
                    query_view_scope.input,
                    query_view_scope.browse_control,
                    query_view_scope.range_control,
                    query_view_scope.catalog_control,
                ]
            )
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

    def _move_source_type(_event, delta: int) -> SurfaceMoveResult:
        if background_turn.busy:
            status["value"] = "Wait for the current Query before changing Source."
            return "CONSUMED"
        if not source_choice.move(delta):
            return "BOUNDARY"
        clear_answer("SOURCE TYPE CHANGED · PRESS ENTER TO QUERY")
        return "MOVED"

    def _activate_source_type(event) -> SurfaceActionResult:
        if granted_mode():
            assert query_view_scope is not None
            event.app.layout.focus(query_view_scope.input)
        else:
            event.app.layout.focus(ordinary_scope.input)
        return "HANDLED"

    @bindings.add("left", filter=has_focus(source_type_control), eager=True)
    def _source_type_left(event) -> None:
        _move_source_type(event, -1)
        event.app.invalidate()

    @bindings.add("right", filter=has_focus(source_type_control), eager=True)
    def _source_type_right(event) -> None:
        _move_source_type(event, 1)
        event.app.invalidate()

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
            if granted_mode():
                assert query_view_scope is not None
                request = GrantedQueryRequest(
                    target=query_view_scope.selected_target(),
                    question=question_area.text.strip(),
                    language=initial_language,
                    federate_descendants=query_view_scope.federate_descendants,
                )

                def work() -> QueryWorkbenchResponse:
                    next_response = run_granted(request)
                    if (
                        not isinstance(next_response, GrantedQueryResponse)
                        or next_response.request != request
                    ):
                        raise ValueError(
                            "Query inputs changed while the request was running. "
                            "Ask the question again."
                        )
                    return next_response

            else:
                request_targets, request_descendants = ordinary_scope.request_scope()
                request = OrdinaryQueryRequest(
                    question=question_area.text.strip(),
                    target_names=request_targets,
                    include_descendants=request_descendants,
                    follow_embeds=ordinary_scope.follow_embeds,
                )

                def work() -> QueryWorkbenchResponse:
                    next_response = run_ordinary(request)
                    if (
                        not isinstance(next_response, OrdinaryQueryResponse)
                        or next_response.request != request
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

    def visible_surfaces() -> tuple[FocusSurface, ...]:
        if not granted_mode() and ordinary_scope.browser_open:
            return (ordinary_scope.browser_surface(uid_prefix="query-scope"),)
        if (
            granted_mode()
            and query_view_scope is not None
            and query_view_scope.browser_open
        ):
            return (query_view_scope.browser_surface(uid_prefix="query-view"),)
        scope_surfaces = (
            query_view_scope.normal_surfaces(uid_prefix="query-view")
            if granted_mode() and query_view_scope is not None
            else ordinary_scope.normal_surfaces(uid_prefix="query-scope")
        )
        return (
            FocusSurface(
                "source-type",
                source_type_control,
                move_vertical=lambda _event, _delta: "BOUNDARY",
                activate=_activate_source_type,
            ),
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
        )

    surface_focus = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surface_focus)
    ordinary_scope.bind_keybindings(bindings)
    if query_view_scope is not None:
        query_view_scope.bind_keybindings(bindings)

    @bindings.add("tab", filter=has_focus(ordinary_scope.tree_control), eager=True)
    @bindings.add("s-tab", filter=has_focus(ordinary_scope.tree_control), eager=True)
    @bindings.add(
        "backspace", filter=has_focus(ordinary_scope.tree_control), eager=True
    )
    def _leave_context_browser(event) -> None:
        ordinary_scope.close_browser(event)
        event.app.invalidate()

    if query_view_scope is not None:

        @bindings.add(
            "tab",
            filter=has_focus(query_view_scope.catalog_control),
            eager=True,
        )
        @bindings.add(
            "s-tab",
            filter=has_focus(query_view_scope.catalog_control),
            eager=True,
        )
        @bindings.add(
            "backspace",
            filter=has_focus(query_view_scope.catalog_control),
            eager=True,
        )
        def _leave_query_view_browser(event) -> None:
            query_view_scope.close_browser(event)
            event.app.invalidate()

    scope_focus = (
        has_focus(source_type_control)
        | has_focus(ordinary_scope.input)
        | has_focus(ordinary_scope.browse_control)
        | has_focus(ordinary_scope.range_control)
        | has_focus(ordinary_scope.embed_control)
        | has_focus(ordinary_scope.tree_control)
    )
    if query_view_scope is not None:
        scope_focus = (
            scope_focus
            | has_focus(query_view_scope.input)
            | has_focus(query_view_scope.browse_control)
            | has_focus(query_view_scope.range_control)
            | has_focus(query_view_scope.catalog_control)
        )
    read_only_focus = (scope_focus | has_focus(answer_control)) & ~has_focus(
        ordinary_scope.input
    )
    if query_view_scope is not None:
        read_only_focus = read_only_focus & ~has_focus(query_view_scope.input)
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
        & (
            ~has_focus(query_view_scope.catalog_control)
            if query_view_scope is not None
            else Condition(lambda: True)
        ),
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
        if query_view_scope is not None and query_view_scope.close_browser(event):
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
