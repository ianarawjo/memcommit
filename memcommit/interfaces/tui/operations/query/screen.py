"""Interactive Question, Source, Scope, and Answer workbench for Query."""

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

from memcommit.interfaces.tui.components.background_turn import BackgroundExecutorTurn
from memcommit.interfaces.tui.components.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryTarget,
)
from memcommit.interfaces.tui.components.plain_text_clipboard import (
    PlainTextClipboardReceipt,
    clipboard_failure_receipt,
    copy_plain_text,
)
from memcommit.interfaces.tui.components.focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.interfaces.tui.core.theme import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
)
from memcommit.interfaces.tui.core.activity import busy_suffix
from memcommit.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.interfaces.tui.components.frame import (
    bind_focused_frame_style,
)
from memcommit.interfaces.console.terminal import (
    require_interactive_terminal,
)
from memcommit.interfaces.console.text import (
    safe_terminal_text,
)
from memcommit.context_targeting.tui.range_selection import (
    ContextRangeSelectionState,
)
from memcommit.context_targeting.tui.reach import render_context_reach
from memcommit.context_targeting.tui.selection import render_context_target_mode
from memcommit.selection.model import SelectionOption
from memcommit.selection.state import FlatSelectionState
from memcommit.selection.tui import render_vertical_choice_rows
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
)
from memcommit.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
)


from memcommit.interfaces.tui.operations.query.adapter import (
    QUERY_VIEW_LABEL,
    QueryAnswerFocus,
    project_query_answer_clipboard,
    query_answer_reference_document,
    query_answer_stop_count,
    render_query_answer_fragments,
    render_saved_query_transcript,
)
from memcommit.interfaces.tui.operations.query.model import (
    GrantedQueryRunner,
    OrdinaryQueryRunner,
    QueryWorkbenchResponse,
    QueryWorkbenchResult,
    SavedQueryTranscript,
)


def run_query_workbench(
    context_names: Sequence[str],
    *,
    current_context: str,
    initial_context: str,
    query_targets: Sequence[GrantedQueryTarget],
    run_ordinary: OrdinaryQueryRunner,
    run_granted: GrantedQueryRunner,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    saved_transcripts: Sequence[SavedQueryTranscript] = (),
    initial_language: str = "en",
    initial_session_name: str | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
    clipboard_writer: Callable[[str], None] | None = None,
    help_binder: Callable[..., object] | None = None,
) -> QueryWorkbenchResult:
    """Open a read-only Query launcher without connecting before Enter."""

    if require_tty:
        require_interactive_terminal(
            "Interactive Query",
            snapshot_hint='Pass a question, for example: mem query "What changed?".',
        )
    targets = tuple(query_targets)
    transcripts = tuple(saved_transcripts)
    if (
        any(not isinstance(transcript, SavedQueryTranscript) for transcript in transcripts)
        or len({transcript.name for transcript in transcripts}) != len(transcripts)
    ):
        raise ValueError("Saved Query transcripts must have distinct names.")
    target_by_uid = {target.grant_uid: target for target in targets}
    if len(target_by_uid) != len(targets):
        raise ValueError("Query-only target identities must be distinct.")
    if not isinstance(initial_language, str) or not initial_language:
        raise ValueError("Query language must be nonblank.")
    initial_query_target = next(
        (target for target in targets if target.session_log_allowed),
        targets[0] if targets else None,
    )
    if initial_session_name is not None and (
        initial_query_target is None or not initial_query_target.session_log_allowed
    ):
        raise ValueError("No query-only View allows SESSION_LOG.")
    context_state = ContextRangeSelectionState.create(
        context_names,
        current_name=current_context,
        initial_target=initial_context,
        multiple=True,
        include_descendants=True,
    )
    source_options = [HorizontalChoiceOption("ORDINARY", "VISIBLE CONTEXTS")]
    if targets:
        source_options.append(HorizontalChoiceOption("GRANTED", QUERY_VIEW_LABEL))
    source_choice = HorizontalChoiceState(
        tuple(source_options),
        "GRANTED" if initial_session_name is not None else "ORDINARY",
    )
    embed_choice = HorizontalChoiceState(
        (
            HorizontalChoiceOption("EXCLUDE", "EXCLUDE"),
            HorizontalChoiceOption("FOLLOW", "FOLLOW"),
        ),
        "FOLLOW",
    )
    federate_choice = HorizontalChoiceState(
        (
            HorizontalChoiceOption("EXACT", "EXACT VIEW"),
            HorizontalChoiceOption("FEDERATE", "FEDERATE DESCENDANTS"),
        ),
        "EXACT" if initial_session_name is not None else "FEDERATE",
    )
    session_choice = HorizontalChoiceState(
        (
            HorizontalChoiceOption("OFF", "ONE SHOT"),
            HorizontalChoiceOption("ON", "SAVE VISIBLE Q/A"),
        ),
        "ON" if initial_session_name is not None else "OFF",
    )
    query_selection = (
        FlatSelectionState(
            tuple(
                SelectionOption(
                    target.grant_uid,
                    target.public_name,
                    QUERY_VIEW_LABEL + " · ATTACHED TO "
                    + target.attachment_name
                    + (" · SESSION LOG" if target.session_log_allowed else ""),
                )
                for target in targets
            ),
            cursor_uid=initial_query_target.grant_uid,
            selected_uid=initial_query_target.grant_uid,
            allow_empty=False,
        )
        if targets
        else None
    )
    labels = dict(annotations or {})
    if set(labels) - set(context_names):
        raise ValueError("Query Context annotations are outside the catalog.")
    try:
        for annotation in labels.values():
            normalize_source_display_tokens(annotation)
    except (TypeError, ValueError) as error:
        raise ValueError("Query received an invalid Context annotation.") from error
    scope_row = {"value": 0}
    response: QueryWorkbenchResponse | None = None
    viewed_transcript: SavedQueryTranscript | None = None
    answer_focus = QueryAnswerFocus()
    status = {"value": "ENTER A QUESTION"}
    copy_receipt: PlainTextClipboardReceipt | None = None
    background_turn: BackgroundExecutorTurn[QueryWorkbenchResponse] = (
        BackgroundExecutorTurn()
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
    session_area = TextArea(
        text=initial_session_name or "",
        multiline=False,
        prompt="› ",
        wrap_lines=False,
        height=Dimension.exact(1),
        read_only=Condition(lambda: background_turn.busy),
        name="query-session-name",
    )

    def granted_mode() -> bool:
        return source_choice.selected_uid == "GRANTED"

    def selected_query_target() -> GrantedQueryTarget:
        if query_selection is None or query_selection.selected_uid is None:
            raise ValueError("Select one query-only View.")
        return target_by_uid[query_selection.selected_uid]

    def render_sources() -> list[tuple[str, str]]:
        focused = app.layout.has_focus(sources_control)
        if not granted_mode():
            return context_state.render_rows(
                focused=focused,
                annotations=labels,
            )
        assert query_selection is not None
        width = max(30, app.output.get_size().columns - 8)
        return render_vertical_choice_rows(
            query_selection,
            focused=focused,
            content_width=width,
            numbered=False,
        )

    sources_control = FormattedTextControl(
        render_sources,
        focusable=True,
        show_cursor=False,
    )
    sources_window = Window(
        sources_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    def render_scope() -> list[tuple[str, str]]:
        focused = app.layout.has_focus(scope_control)
        fragments = render_horizontal_choice(
            source_choice,
            title="SOURCE TYPE",
            focused=focused and scope_row["value"] == 0,
        )
        fragments.append(("", "\n"))
        if not granted_mode():
            fragments.extend(
                render_context_target_mode(
                    context_state.target_mode,
                    focused=focused and scope_row["value"] == 1,
                )
            )
            fragments.append(("", "\n"))
            fragments.extend(
                render_context_reach(
                    context_state.reach,
                    title="CONTEXT RANGE",
                    focused=focused and scope_row["value"] == 2,
                )
            )
            fragments.append(("", "\n"))
            fragments.extend(
                render_horizontal_choice(
                    embed_choice,
                    title="EMBEDDED CONTEXTS",
                    focused=focused and scope_row["value"] == 3,
                )
            )
            return fragments
        fragments.extend(
            render_horizontal_choice(
                federate_choice,
                title="QUERY VIEW RANGE",
                focused=focused and scope_row["value"] == 1,
            )
        )
        fragments.append(("", "\n"))
        fragments.extend(
            render_horizontal_choice(
                session_choice,
                title="SESSION LOG",
                focused=focused and scope_row["value"] == 2,
            )
        )
        fragments.append(("", f"\n  LANGUAGE · {safe_terminal_text(initial_language)}"))
        return fragments

    scope_control = FormattedTextControl(render_scope, focusable=True, show_cursor=False)
    answer_control = FormattedTextControl(
        lambda: (
            [("", render_saved_query_transcript(viewed_transcript))]
            if viewed_transcript is not None
            else render_query_answer_fragments(
                response,
                focus=answer_focus,
                focused=app.layout.has_focus(answer_control),
            )
        ),
        focusable=True,
        show_cursor=False,
    )
    answer_window = Window(
        answer_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    transcript_selection = (
        FlatSelectionState(
            tuple(
                SelectionOption(
                    transcript.name,
                    transcript.name,
                    f"{transcript.requested_name} · {transcript.language} · "
                    f"{len(transcript.turns)} TURN(S) · REVISION "
                    f"{transcript.revision}",
                )
                for transcript in transcripts
            ),
            cursor_uid=transcripts[0].name,
            selected_uid=None,
            allow_empty=True,
        )
        if transcripts
        else None
    )
    transcript_by_name = {transcript.name: transcript for transcript in transcripts}

    def render_transcript_rows() -> list[tuple[str, str]]:
        if transcript_selection is None:
            return [("", "  No saved query transcripts.")]
        width = max(30, app.output.get_size().columns - 8)
        return render_vertical_choice_rows(
            transcript_selection,
            focused=app.layout.has_focus(transcripts_control),
            content_width=width,
            numbered=False,
        )

    transcripts_control = FormattedTextControl(
        render_transcript_rows,
        focusable=True,
        show_cursor=False,
    )
    transcripts_window = Window(
        transcripts_control,
        wrap_lines=False,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    header = Window(
        FormattedTextControl(" MEM QUERY"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    question_frame = Frame(
        question_area,
        title="QUESTION · ENTER TO ASK",
        height=Dimension.exact(3),
    )
    sources_frame = Frame(
        sources_window,
        title=lambda: (
            f"SOURCES · {QUERY_VIEW_LABEL}S · ENTER TO SELECT"
            if granted_mode()
            else "SOURCES · PROFILE/CONTEXT · ENTER/SPACE TO SELECT"
        ),
        height=Dimension(min=5, preferred=8, max=12, weight=1),
    )
    scope_frame = Frame(
        Window(scope_control, height=Dimension.exact(4), wrap_lines=False),
        title="SCOPE",
        height=Dimension.exact(6),
    )
    session_frame = Frame(
        session_area,
        title="SESSION NAME · VISIBLE Q/A ONLY",
        height=Dimension.exact(3),
    )
    transcripts_frame = Frame(
        transcripts_window,
        title="SAVED TRANSCRIPTS · ENTER TO VIEW",
        height=Dimension(min=3, preferred=5, max=7),
    )

    def answer_title() -> str:
        if background_turn.busy:
            return f"ANSWER · QUERYING {busy_suffix(background_turn.frame)}"
        if viewed_transcript is not None:
            return "ANSWER · SAVED TRANSCRIPT · READ ONLY"
        return "ANSWER"

    answer_frame = Frame(
        answer_window,
        title=answer_title,
        height=Dimension(min=5, weight=2),
    )

    def session_visible() -> bool:
        return granted_mode() and session_choice.selected_uid == "ON"

    def render_footer() -> str | list[tuple[str, str]]:
        if background_turn.busy:
            return (
                f" QUERYING {busy_suffix(background_turn.frame)} · "
                "H Help · Ctrl-C closes after query"
            )
        if app.layout.has_focus(question_area):
            navigation = "Enter ask · Tab switch · Esc close"
        elif app.layout.has_focus(session_area):
            navigation = "Enter ask · Tab switch · Esc question"
        else:
            navigation = (
                "↑/↓ move/cross · Tab switch · / question · "
                "Esc/Backspace question · H Help · Q close"
            )
        if app.layout.has_focus(answer_control):
            navigation = (
                "↑/↓ answer/References · y copy focused · "
                "Y copy complete answer · Tab switch · Esc question"
            )
        if copy_receipt is not None and app.layout.has_focus(answer_control):
            return [
                (copy_receipt.style, " " + copy_receipt.message),
                ("", f" · {navigation}"),
            ]
        return (
            f" {safe_terminal_text(status['value'])} · {navigation}"
        )

    footer = Window(
        FormattedTextControl(render_footer),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = HSplit(
        [
            header,
            question_frame,
            sources_frame,
            scope_frame,
            ConditionalContainer(
                session_frame,
                filter=Condition(session_visible),
            ),
            transcripts_frame,
            answer_frame,
            footer,
        ]
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
    bind_focused_frame_style(
        question_frame,
        is_focused=lambda: app.layout.has_focus(question_area),
    )
    bind_focused_frame_style(
        sources_frame,
        is_focused=lambda: app.layout.has_focus(sources_control),
    )
    bind_focused_frame_style(
        scope_frame,
        is_focused=lambda: app.layout.has_focus(scope_control),
    )
    bind_focused_frame_style(
        session_frame,
        is_focused=lambda: app.layout.has_focus(session_area),
    )
    bind_focused_frame_style(
        transcripts_frame,
        is_focused=lambda: app.layout.has_focus(transcripts_control),
    )
    bind_focused_frame_style(
        answer_frame,
        is_focused=lambda: app.layout.has_focus(answer_control),
    )

    def clear_answer(message: str) -> None:
        nonlocal copy_receipt, response, viewed_transcript
        response = None
        viewed_transcript = None
        copy_receipt = None
        answer_focus.reset()
        answer_window.vertical_scroll = 0
        status["value"] = message

    def text_changed(_buffer) -> None:
        if response is not None and not background_turn.busy:
            clear_answer("QUESTION CHANGED · PRESS ENTER TO QUERY")
            app.invalidate()

    question_area.buffer.on_text_changed += text_changed

    def _move_question(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _enter_question(_delta: int) -> None:
        question_area.buffer.cursor_position = len(question_area.text)

    def _move_sources(_event, delta: int) -> SurfaceMoveResult:
        if granted_mode():
            assert query_selection is not None
            return "MOVED" if query_selection.move(delta) else "BOUNDARY"
        return "MOVED" if context_state.move_cursor(delta) else "BOUNDARY"

    def _enter_sources(delta: int) -> None:
        if granted_mode():
            assert query_selection is not None
            query_selection.cursor_uid = (
                query_selection.options[0].uid
                if delta > 0
                else query_selection.options[-1].uid
            )
            return
        context_state.enter_from_boundary(delta)

    def _choose_source(event) -> SurfaceActionResult:
        if background_turn.busy:
            status["value"] = "Wait for the current Query before changing Sources."
        elif granted_mode():
            assert query_selection is not None
            before = query_selection.selected_uid
            query_selection.select_cursor(toggle=False)
            target = selected_query_target()
            if not target.session_log_allowed:
                session_choice.choose("OFF")
            if query_selection.selected_uid != before:
                clear_answer("SOURCE CHANGED · PRESS ENTER TO QUERY")
        else:
            if context_state.toggle_cursor():
                clear_answer("SOURCES CHANGED · PRESS ENTER TO QUERY")
        event.app.invalidate()
        return "HANDLED"

    @bindings.add("right", filter=has_focus(sources_control), eager=True)
    def _source_right(event) -> None:
        if not granted_mode():
            context_state.expand_cursor()
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(sources_control), eager=True)
    def _source_left(event) -> None:
        if not granted_mode():
            context_state.collapse_cursor()
        event.app.invalidate()

    @bindings.add(" ", filter=has_focus(sources_control), eager=True)
    def _source_space(event) -> None:
        _choose_source(event)

    @bindings.add("a", filter=has_focus(sources_control), eager=True)
    @bindings.add("A", filter=has_focus(sources_control), eager=True)
    def _source_expand_all(event) -> None:
        if not granted_mode():
            context_state.toggle_expand_all()
        event.app.invalidate()

    def scope_last_row() -> int:
        return 2 if granted_mode() else 3

    def _move_scope_vertical(_event, delta: int) -> SurfaceMoveResult:
        before = scope_row["value"]
        scope_row["value"] = max(0, min(before + delta, scope_last_row()))
        return "MOVED" if scope_row["value"] != before else "BOUNDARY"

    def _enter_scope(delta: int) -> None:
        scope_row["value"] = 0 if delta > 0 else scope_last_row()

    def move_scope(delta: int) -> None:
        if background_turn.busy:
            status["value"] = "Wait for the current Query before changing Scope."
            return
        row = scope_row["value"]
        if row == 0:
            if source_choice.move(delta):
                scope_row["value"] = 0
                clear_answer("SOURCE TYPE CHANGED · PRESS ENTER TO QUERY")
            return
        if not granted_mode():
            if row == 1:
                _changed, targets_changed = context_state.move_target_mode(delta)
                if targets_changed:
                    clear_answer("SOURCES CHANGED · PRESS ENTER TO QUERY")
                return
            if row == 2:
                if context_state.move_reach(delta):
                    clear_answer("CONTEXT RANGE CHANGED · PRESS ENTER TO QUERY")
                return
            if embed_choice.move(delta):
                clear_answer("EMBED SCOPE CHANGED · PRESS ENTER TO QUERY")
            return
        if row == 1:
            if session_choice.selected_uid == "ON":
                status["value"] = "Saved Query sessions remain exact to one View."
                return
            if federate_choice.move(delta):
                clear_answer("QUERY VIEW RANGE CHANGED · PRESS ENTER TO QUERY")
            return
        target = selected_query_target()
        if delta > 0 and not target.session_log_allowed:
            status["value"] = "The selected Query View does not allow SESSION_LOG."
            return
        if session_choice.move(delta):
            if session_choice.selected_uid == "ON":
                federate_choice.choose("EXACT")
            clear_answer("SESSION MODE CHANGED · PRESS ENTER TO QUERY")

    @bindings.add("right", filter=has_focus(scope_control), eager=True)
    def _scope_right(event) -> None:
        move_scope(1)
        event.app.invalidate()

    @bindings.add("left", filter=has_focus(scope_control), eager=True)
    def _scope_left(event) -> None:
        move_scope(-1)
        event.app.invalidate()

    def _move_session(_event, _delta: int) -> SurfaceMoveResult:
        return "BOUNDARY"

    def _enter_session(_delta: int) -> None:
        session_area.buffer.cursor_position = len(session_area.text)

    def _move_transcripts(_event, delta: int) -> SurfaceMoveResult:
        if transcript_selection is None:
            return "BOUNDARY"
        return "MOVED" if transcript_selection.move(delta) else "BOUNDARY"

    def _enter_transcripts(delta: int) -> None:
        if transcript_selection is None:
            return
        transcript_selection.cursor_uid = (
            transcript_selection.options[0].uid
            if delta > 0
            else transcript_selection.options[-1].uid
        )

    def _view_transcript(event) -> SurfaceActionResult:
        nonlocal copy_receipt, viewed_transcript
        if transcript_selection is None:
            status["value"] = "NO SAVED QUERY TRANSCRIPTS"
            return "HANDLED"
        selected_name = transcript_selection.select_cursor(toggle=False)
        assert selected_name is not None
        viewed_transcript = transcript_by_name[selected_name]
        copy_receipt = None
        answer_focus.reset()
        answer_window.vertical_scroll = 0
        status["value"] = (
            f"TRANSCRIPT {safe_terminal_text(selected_name)} · "
            f"{len(viewed_transcript.turns)} TURN(S) · READ ONLY"
        )
        event.app.invalidate()
        return "HANDLED"

    def _move_answer(_event, delta: int) -> SurfaceMoveResult:
        nonlocal copy_receipt
        document = (
            None
            if viewed_transcript is not None
            else query_answer_reference_document(response)
        )
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
        answer_window.vertical_scroll = max(
            0,
            min(previous + delta, maximum),
        )
        if answer_window.vertical_scroll != previous:
            copy_receipt = None
        return (
            "MOVED"
            if answer_window.vertical_scroll != previous
            else "BOUNDARY"
        )

    def _enter_answer(delta: int) -> None:
        if (
            viewed_transcript is None
            and query_answer_reference_document(response) is not None
        ):
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
        nonlocal copy_receipt, response, viewed_transcript
        if background_turn.busy:
            status["value"] = "A Query is already running."
            return "HANDLED"
        try:
            if granted_mode():
                target = selected_query_target()
                session_name = (
                    session_area.text.strip()
                    if session_choice.selected_uid == "ON"
                    else None
                )
                request = GrantedQueryRequest(
                    target=target,
                    question=question_area.text.strip() or None,
                    language=initial_language,
                    session_name=session_name,
                    federate_descendants=(
                        session_choice.selected_uid == "OFF"
                        and federate_choice.selected_uid == "FEDERATE"
                    ),
                )

                def work() -> QueryWorkbenchResponse:
                    return run_granted(request)

            else:
                request = OrdinaryQueryRequest(
                    question=question_area.text.strip(),
                    target_names=context_state.effective_names,
                    include_descendants=False,
                    follow_embeds=embed_choice.selected_uid == "FOLLOW",
                )

                def work() -> QueryWorkbenchResponse:
                    return run_ordinary(request)
        except ValueError as error:
            status["value"] = str(error)
            return "HANDLED"

        def commit(next_response: QueryWorkbenchResponse) -> None:
            nonlocal copy_receipt, response, viewed_transcript
            response = next_response
            viewed_transcript = None
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

    def visible_surfaces():
        surfaces = [
            FocusSurface(
                "question",
                question_area,
                move_vertical=_move_question,
                activate=_query,
                on_vertical_enter=_enter_question,
            ),
            FocusSurface(
                "sources",
                sources_control,
                move_vertical=_move_sources,
                activate=_choose_source,
                on_vertical_enter=_enter_sources,
            ),
            FocusSurface(
                "scope",
                scope_control,
                move_vertical=_move_scope_vertical,
                activate=_focus_question,
                on_vertical_enter=_enter_scope,
            ),
        ]
        if session_visible():
            surfaces.append(
                FocusSurface(
                    "session",
                    session_area,
                    move_vertical=_move_session,
                    activate=_focus_question,
                    on_vertical_enter=_enter_session,
                )
            )
        if transcript_selection is not None:
            surfaces.append(
                FocusSurface(
                    "transcripts",
                    transcripts_control,
                    move_vertical=_move_transcripts,
                    activate=_view_transcript,
                    on_vertical_enter=_enter_transcripts,
                )
            )
        surfaces.append(
            FocusSurface(
                "answer",
                answer_control,
                move_vertical=_move_answer,
                activate=_focus_question,
                on_vertical_enter=_enter_answer,
            )
        )
        return tuple(surfaces)

    surface_focus = SurfaceFocusController(visible_surfaces)
    bind_surface_navigation(bindings, surface_focus)

    read_only_focus = (
        has_focus(sources_control)
        | has_focus(scope_control)
        | has_focus(transcripts_control)
        | has_focus(answer_control)
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
                viewed_transcript=viewed_transcript,
                whole_document=whole_document,
            )
        except ValueError as error:
            copy_receipt = clipboard_failure_receipt(error)
        else:
            # Answer copies are plain OS text only. They do not create the
            # typed single-source clipboard stage used by mutating commands.
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
        document = (
            None
            if viewed_transcript is not None
            else query_answer_reference_document(response)
        )
        if document is not None:
            previous_stop = answer_focus.stop_index
            answer_focus.stop_index = max(0, answer_focus.stop_index - 4)
            if answer_focus.stop_index != previous_stop:
                copy_receipt = None
        else:
            previous_scroll = answer_window.vertical_scroll
            render_info = answer_window.render_info
            step = 1 if render_info is None else max(1, render_info.window_height - 1)
            answer_window.vertical_scroll = max(
                0,
                answer_window.vertical_scroll - step,
            )
            if answer_window.vertical_scroll != previous_scroll:
                copy_receipt = None
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(answer_control), eager=True)
    def _answer_page_down(event) -> None:
        nonlocal copy_receipt
        document = (
            None
            if viewed_transcript is not None
            else query_answer_reference_document(response)
        )
        if document is not None:
            previous_stop = answer_focus.stop_index
            answer_focus.stop_index = min(
                query_answer_stop_count(response) - 1,
                answer_focus.stop_index + 4,
            )
            if answer_focus.stop_index != previous_stop:
                copy_receipt = None
        else:
            previous_scroll = answer_window.vertical_scroll
            render_info = answer_window.render_info
            step = 1 if render_info is None else max(1, render_info.window_height - 1)
            maximum = (
                answer_window.vertical_scroll + step
                if render_info is None
                else max(
                    0,
                    render_info.content_height - render_info.window_height,
                )
            )
            answer_window.vertical_scroll = min(
                maximum,
                answer_window.vertical_scroll + step,
            )
            if answer_window.vertical_scroll != previous_scroll:
                copy_receipt = None
        event.app.invalidate()

    @bindings.add("backspace", filter=read_only_focus, eager=True)
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
        dispatch_tui_back(event, _return_to_question, close=close)

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
