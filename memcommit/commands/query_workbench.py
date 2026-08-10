"""Interactive Question, Source, Scope, and Answer workbench for Query."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

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

from memcommit.commands.background_turn import BackgroundExecutorTurn
from memcommit.commands.command_progress import busy_suffix
from memcommit.commands.horizontal_choice import (
    HorizontalChoiceOption,
    HorizontalChoiceState,
    render_horizontal_choice,
)
from memcommit.commands.query_execution import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.commands.session_help import bind_session_help
from memcommit.commands.surface_focus import (
    FocusSurface,
    SurfaceActionResult,
    SurfaceFocusController,
    SurfaceMoveResult,
    bind_surface_navigation,
)
from memcommit.commands.tui_primitives import (
    MEMCOMMIT_TUI_STYLE,
    SEMANTIC_VIEWER_STYLE,
    bind_case_insensitive_key,
    bind_focused_frame_style,
    dispatch_tui_back,
    focused_control_style,
    require_interactive_terminal,
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
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    SourceDisplayValue,
    normalize_source_display_tokens,
    source_object_label,
)
from memcommit.find_answer_references import (
    FindAnswerReferenceDocument,
    render_numbered_find_answer_reference,
)


QueryWorkbenchResponse = OrdinaryQueryResponse | GrantedQueryResponse
OrdinaryQueryRunner = Callable[[OrdinaryQueryRequest], OrdinaryQueryResponse]
GrantedQueryRunner = Callable[[GrantedQueryRequest], GrantedQueryResponse]

_QUERY_VIEW_LABEL = source_object_label(SourceForm.QUERY_VIEW).upper()


@dataclass(frozen=True)
class SavedQueryTranscript:
    """Task-owned visible Q/A projected without reopening its Source."""

    name: str
    requested_name: str
    language: str
    revision: int
    turns: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.name or not self.requested_name or not self.language:
            raise ValueError("Saved Query transcript labels must be nonblank.")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            raise ValueError("Saved Query transcript revision is invalid.")
        if any(
            not isinstance(turn, tuple)
            or len(turn) != 2
            or not all(isinstance(value, str) and value for value in turn)
            for turn in self.turns
        ):
            raise ValueError("Saved Query transcript turns must be nonblank.")


def render_saved_query_transcript(transcript: SavedQueryTranscript) -> str:
    """Render only the durable, person-visible transcript projection."""

    lines = [
        f"QUERY SESSION · {safe_terminal_text(transcript.name)}",
        "VIEW · "
        + safe_terminal_text(transcript.requested_name)
        + " · LANGUAGE "
        + safe_terminal_text(transcript.language)
        + f" · REVISION {transcript.revision}",
    ]
    if not transcript.turns:
        lines.extend(("", "(no turns)"))
        return "\n".join(lines)
    for index, (question, answer) in enumerate(transcript.turns, start=1):
        lines.extend(
            (
                "",
                f"Q{index}",
                safe_terminal_text(question),
                f"A{index}",
                safe_terminal_text(answer),
            )
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class QueryWorkbenchResult:
    status: Literal["CLOSED"]
    response: QueryWorkbenchResponse | None = None


def _render_granted_catalog(response: GrantedQueryResponse) -> str:
    lines = [
        f"{_QUERY_VIEW_LABEL} MEMORIES · {response.request.target.public_name}",
        f"  {len(response.catalog)} queryable "
        f"Memor{'y' if len(response.catalog) == 1 else 'ies'}",
    ]
    for entry in response.catalog:
        lines.extend(("", f"  [{entry.handle}]"))
        lines.extend(f"    {line}" for line in entry.placeholder_lines)
    lines.extend(("", "Source text is not present in this catalog view."))
    return "\n".join(lines)


def render_query_answer(response: QueryWorkbenchResponse | None) -> str:
    if response is None:
        return "QUERY ANSWER\n  Enter a question for the selected Source and Scope."
    if isinstance(response, OrdinaryQueryResponse):
        return response.answer
    if response.answer is not None:
        return response.answer
    return _render_granted_catalog(response)


def _query_answer_reference_document(
    response: QueryWorkbenchResponse | None,
) -> FindAnswerReferenceDocument | None:
    if not isinstance(response, OrdinaryQueryResponse):
        return None
    return response.reference_document


def query_answer_stop_count(response: QueryWorkbenchResponse | None) -> int:
    """Return the answer body plus every independently navigable Reference."""

    document = _query_answer_reference_document(response)
    return 1 + (len(document.references) if document is not None else 0)


@dataclass
class QueryAnswerFocus:
    """Process-local cursor over the answer body and typed Reference blocks."""

    stop_index: int = 0

    def reset(self) -> None:
        self.stop_index = 0

    def move(self, response: QueryWorkbenchResponse | None, delta: int) -> bool:
        if delta not in {-1, 1}:
            raise ValueError("Query Answer focus direction must be -1 or 1.")
        last = query_answer_stop_count(response) - 1
        next_index = max(0, min(self.stop_index + delta, last))
        if next_index == self.stop_index:
            return False
        self.stop_index = next_index
        return True

    def enter(
        self,
        response: QueryWorkbenchResponse | None,
        delta: int,
    ) -> None:
        self.stop_index = 0 if delta > 0 else query_answer_stop_count(response) - 1


def render_query_answer_fragments(
    response: QueryWorkbenchResponse | None,
    *,
    focus: QueryAnswerFocus,
    focused: bool,
) -> list[tuple[str, str]]:
    """Render one Answer with shared blue focus over its active Reference."""

    document = _query_answer_reference_document(response)
    if document is None:
        return [("", safe_terminal_text(render_query_answer(response)))]

    active_stop = max(
        0,
        min(focus.stop_index, query_answer_stop_count(response) - 1),
    )
    fragments: list[tuple[str, str]] = []
    if active_stop == 0 and focused:
        fragments.append(("[SetCursorPosition]", ""))
    fragments.extend(
        [
            ("", safe_terminal_text(document.body)),
            ("", "\n\nReferences"),
        ]
    )
    for index, reference in enumerate(document.references, start=1):
        active = active_stop == index
        fragments.append(("", "\n" if index == 1 else "\n\n"))
        if active and focused:
            fragments.append(("[SetCursorPosition]", ""))
        fragments.append(
            (
                (
                    focused_control_style(focused=focused, selected=True)
                    if active
                    else ""
                ),
                safe_terminal_text(
                    render_numbered_find_answer_reference(reference)
                ),
            )
        )
    return fragments


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
        source_options.append(HorizontalChoiceOption("GRANTED", _QUERY_VIEW_LABEL))
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
                    _QUERY_VIEW_LABEL + " · ATTACHED TO "
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
    status = {"value": "READY · ENTER A QUESTION"}
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

    def render_header() -> str:
        if granted_mode():
            target = selected_query_target()
            scope = (
                "FEDERATE DESCENDANTS"
                if federate_choice.selected_uid == "FEDERATE"
                else "EXACT VIEW"
            )
            return (
                f" MEM QUERY · INTERACTIVE · {_QUERY_VIEW_LABEL}\n "
                f"{target.public_name} · {scope} · "
                f"LANGUAGE {safe_terminal_text(initial_language)}"
            )
        target_label = (
            f"PROFILE · {len(context_state.effective_names)} CONTEXTS"
            if context_state.profile_selected
            else f"CONTEXTS {len(context_state.effective_names)}"
        )
        reach = (
            "INCLUDE DESCENDANTS"
            if context_state.reach.include_descendants
            else "THIS CONTEXT ONLY"
        )
        embeds = "FOLLOW EMBEDS" if embed_choice.selected_uid == "FOLLOW" else "EXCLUDE EMBEDS"
        return f" MEM QUERY · INTERACTIVE · VISIBLE\n {target_label} · {reach} · {embeds}"

    header = Window(
        FormattedTextControl(render_header),
        height=Dimension.exact(2),
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
            f"SOURCES · {_QUERY_VIEW_LABEL}S · ENTER TO SELECT"
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

    def render_footer() -> str:
        if background_turn.busy:
            return (
                f" QUERYING {busy_suffix(background_turn.frame)} · "
                "scope frozen · H Help · Ctrl-C closes after query"
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
        nonlocal response, viewed_transcript
        response = None
        viewed_transcript = None
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
        nonlocal viewed_transcript
        if transcript_selection is None:
            status["value"] = "NO SAVED QUERY TRANSCRIPTS"
            return "HANDLED"
        selected_name = transcript_selection.select_cursor(toggle=False)
        assert selected_name is not None
        viewed_transcript = transcript_by_name[selected_name]
        answer_focus.reset()
        answer_window.vertical_scroll = 0
        status["value"] = (
            f"TRANSCRIPT {safe_terminal_text(selected_name)} · "
            f"{len(viewed_transcript.turns)} TURN(S) · READ ONLY"
        )
        event.app.invalidate()
        return "HANDLED"

    def _move_answer(_event, delta: int) -> SurfaceMoveResult:
        document = (
            None
            if viewed_transcript is not None
            else _query_answer_reference_document(response)
        )
        if document is not None:
            return "MOVED" if answer_focus.move(response, delta) else "BOUNDARY"

        render_info = answer_window.render_info
        if render_info is None:
            return "BOUNDARY"
        previous = answer_window.vertical_scroll
        maximum = max(0, render_info.content_height - render_info.window_height)
        answer_window.vertical_scroll = max(
            0,
            min(previous + delta, maximum),
        )
        return (
            "MOVED"
            if answer_window.vertical_scroll != previous
            else "BOUNDARY"
        )

    def _enter_answer(delta: int) -> None:
        if (
            viewed_transcript is None
            and _query_answer_reference_document(response) is not None
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
        nonlocal response, viewed_transcript
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
            nonlocal response, viewed_transcript
            response = next_response
            viewed_transcript = None
            answer_focus.reset()
            answer_window.vertical_scroll = 0
            status["value"] = "QUERY COMPLETE · SOURCE AND SCOPE FROZEN"

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
        status["value"] = "QUERYING · SOURCE AND SCOPE FROZEN"
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
    bind_session_help(
        bindings,
        filter=read_only_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="query",
    )

    @bindings.add("/", filter=read_only_focus, eager=True)
    def _question_shortcut(event) -> None:
        _focus_question(event)
        event.app.invalidate()

    @bindings.add("pageup", filter=has_focus(answer_control), eager=True)
    def _answer_page_up(event) -> None:
        document = (
            None
            if viewed_transcript is not None
            else _query_answer_reference_document(response)
        )
        if document is not None:
            answer_focus.stop_index = max(0, answer_focus.stop_index - 4)
        else:
            render_info = answer_window.render_info
            step = 1 if render_info is None else max(1, render_info.window_height - 1)
            answer_window.vertical_scroll = max(
                0,
                answer_window.vertical_scroll - step,
            )
        event.app.invalidate()

    @bindings.add("pagedown", filter=has_focus(answer_control), eager=True)
    def _answer_page_down(event) -> None:
        document = (
            None
            if viewed_transcript is not None
            else _query_answer_reference_document(response)
        )
        if document is not None:
            answer_focus.stop_index = min(
                query_answer_stop_count(response) - 1,
                answer_focus.stop_index + 4,
            )
        else:
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
