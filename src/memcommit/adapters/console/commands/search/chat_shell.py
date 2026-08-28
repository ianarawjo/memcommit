"""Operation-neutral, long-lived chat surface for interactive Search.

The production session keeps one prompt-toolkit application alive while a
controller handles submitted turns in a worker thread. A one-turn wrapper
remains for focused shell tests and callers that need only input collection.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from prompt_toolkit.application import Application
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_page_down,
    scroll_page_up,
)
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import TextArea

from memcommit.adapters.interfaces.tui.components.frame import (
    TuiRegion,
    build_tui_frame,
)
from memcommit.adapters.interfaces.tui.core.keybindings import (
    bind_case_insensitive_key,
    dispatch_tui_back,
)
from memcommit.adapters.console.terminal import (
    require_interactive_terminal,
)
from memcommit.adapters.console.text import (
    safe_terminal_text,
)
from memcommit.adapters.console.shared.background_turn import (
    BackgroundExecutorTurn,
)
from memcommit.adapters.console.shared.command_progress import (
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)
from memcommit.adapters.console.shared.session_help import bind_session_help
from memcommit.adapters.console.commands.search.result_present import (
    SearchResultViewRow,
    render_grouped_search_results,
)


SearchChatRole = Literal["USER", "MEM", "STATUS"]
SearchChatActionKind = Literal["SUBMIT", "CLOSE"]
SearchChatResultKind = Literal["memory", "ref", "query", "artifact"]
SearchChatRelevance = Literal["primary", "related"]
# Compatibility name remains patchable by focused shell tests while its
# default comes from the shared blocking-progress visual contract.
_SEARCH_BUSY_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS


def _processing_search_turn_label(frame_index: int) -> str:
    """Render one deterministic frame of the in-process busy indicator."""
    return " PROCESSING SEARCH TURN " + busy_suffix(frame_index)


@dataclass(frozen=True)
class SearchChatMessage:
    """One already-visible dialogue block supplied by the Search controller."""

    role: SearchChatRole
    text: str

    def __post_init__(self) -> None:
        if self.role not in {"USER", "MEM", "STATUS"}:
            raise ValueError("Invalid Search chat message role.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Search chat messages require nonblank text.")


@dataclass(frozen=True)
class SearchChatResult:
    """One locally validated result rendered without provider-authored text."""

    alias: str
    context_name: str
    kind: SearchChatResultKind
    uid: str
    content: str
    relevance: SearchChatRelevance = "primary"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.alias, str)
            or not self.alias.startswith("m")
            or not self.alias[1:].isdigit()
            or self.alias[1:].startswith("0")
        ):
            raise ValueError("Search chat results require an alias like m1.")
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Search chat results require a Context name.")
        if self.kind not in {"memory", "ref", "query", "artifact"}:
            raise ValueError("Invalid Search chat result kind.")
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Search chat results require an item UID.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Search chat results require nonblank content.")
        if self.relevance not in {"primary", "related"}:
            raise ValueError("Invalid Search chat result relevance.")


@dataclass(frozen=True)
class SearchPendingAnswerRequest:
    """One wider-scope answer waiting for a host-owned confirmation token."""

    user_text: str
    interpreted_request: str
    pending_clarification: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.user_text, str) or not self.user_text.strip():
            raise ValueError("Pending Search answers require user text.")
        if (
            not isinstance(self.interpreted_request, str)
            or not self.interpreted_request.strip()
        ):
            raise ValueError("Pending Search answers require an interpreted request.")
        if self.pending_clarification is not None and (
            not isinstance(self.pending_clarification, str)
            or not self.pending_clarification.strip()
        ):
            raise ValueError("Pending Search clarification must be nonblank text.")


@dataclass(frozen=True)
class SearchChatState:
    """One immutable committed or transient view of the Search chat."""

    context_name: str
    current_query: str = ""
    messages: tuple[SearchChatMessage, ...] = ()
    results: tuple[SearchChatResult, ...] = ()
    related_query: str = ""
    kept_count: int = 0
    status: str = "READY"
    pending_answer: SearchPendingAnswerRequest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Search chat requires a Context name.")
        if not isinstance(self.current_query, str):
            raise ValueError("Search chat query must be text.")
        if isinstance(self.messages, (str, bytes)):
            raise ValueError("Search chat messages must be a sequence.")
        try:
            messages = tuple(self.messages)
        except TypeError as error:
            raise ValueError("Search chat messages must be a sequence.") from error
        if any(not isinstance(message, SearchChatMessage) for message in messages):
            raise ValueError("Invalid Search chat message.")
        object.__setattr__(self, "messages", messages)
        if isinstance(self.results, (str, bytes)):
            raise ValueError("Search chat results must be a sequence.")
        try:
            results = tuple(self.results)
        except TypeError as error:
            raise ValueError("Search chat results must be a sequence.") from error
        if any(not isinstance(result, SearchChatResult) for result in results):
            raise ValueError("Invalid Search chat result.")
        aliases = tuple(result.alias for result in results)
        if len(set(aliases)) != len(aliases):
            raise ValueError("Search chat result aliases must be unique.")
        object.__setattr__(self, "results", results)
        if not isinstance(self.related_query, str):
            raise ValueError("Search chat related query must be text.")
        related_query = self.related_query.strip()
        related = tuple(result for result in results if result.relevance == "related")
        primary = tuple(result for result in results if result.relevance == "primary")
        if primary and related:
            raise ValueError("Search chat cannot mix primary and related results.")
        if bool(related_query) != bool(related):
            raise ValueError("Related Search chat results require one related query.")
        object.__setattr__(self, "related_query", related_query)
        if type(self.kept_count) is not int or self.kept_count < 0:
            raise ValueError("Search chat kept count must be a nonnegative integer.")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Search chat requires a nonblank status.")
        if self.pending_answer is not None and not isinstance(
            self.pending_answer,
            SearchPendingAnswerRequest,
        ):
            raise ValueError("Invalid pending Search answer.")


@dataclass(frozen=True)
class SearchChatAction:
    """The single controller-owned action returned by one shell invocation."""

    kind: SearchChatActionKind
    text: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"SUBMIT", "CLOSE"}:
            raise ValueError("Invalid Search chat action.")
        if not isinstance(self.text, str):
            raise ValueError("Search chat action text must be text.")
        if self.kind == "SUBMIT" and not self.text.strip():
            raise ValueError("A submitted Search turn cannot be blank.")
        if self.kind == "CLOSE" and self.text:
            raise ValueError("A closed Search chat cannot carry submitted text.")


class SearchChatTurnHandler(Protocol):
    """Controller boundary for one read-only follow-up Search turn."""

    def __call__(
        self,
        state: SearchChatState,
        text: str,
    ) -> SearchChatState:
        """Return the complete next view after handling one submitted turn."""


@dataclass(frozen=True)
class SearchChatSessionResult:
    """Final committed state after the person closes one continuous chat."""

    status: Literal["CLOSED"]
    state: SearchChatState
    submitted_turns: tuple[str, ...] = ()


def render_search_chat_header(state: SearchChatState) -> str:
    """Render the stable portion of the Search chat frame."""
    query = state.current_query.strip() or "(not asked yet)"
    related_count = sum(result.relevance == "related" for result in state.results)
    result_summary = (
        f"PRIMARY MATCHES 0 · RELATED {related_count} · KEPT {state.kept_count}"
        if related_count
        else f"RESULTS {len(state.results)} · KEPT {state.kept_count}"
    )
    return "\n".join(
        [
            (f"MEM SEARCH · {safe_terminal_text(state.context_name)}"),
            f"QUERY · {safe_terminal_text(query)}",
            result_summary,
            f"STATUS · {safe_terminal_text(state.status)}",
        ]
    )


def _message_block(message: SearchChatMessage) -> str:
    label = {
        "USER": "YOU",
        "MEM": "MEM",
        "STATUS": "STATUS",
    }[message.role]
    content = safe_terminal_text(message.text).replace("\n", "\n  ")
    return f"{label}\n  {content}"


def _result_view_row(result: SearchChatResult) -> SearchResultViewRow:
    if result.relevance == "related":
        label = (
            f"[{safe_terminal_text(result.alias)} related "
            f"{result.kind:<7} {safe_terminal_text(result.uid[:8])}]"
        )
    else:
        label = (
            f"[{safe_terminal_text(result.alias)} "
            f"{result.kind:<7} {safe_terminal_text(result.uid[:8])}]"
        )
    return SearchResultViewRow(
        context_name=result.context_name,
        label=label,
        content=result.content,
    )


def _result_blocks(state: SearchChatState) -> tuple[str, ...]:
    if not state.results:
        return ()
    return (
        render_grouped_search_results(
            tuple(_result_view_row(result) for result in state.results),
            related_query=state.related_query,
        ),
    )


def _dialogue_blocks(state: SearchChatState) -> tuple[str, ...]:
    blocks = [_message_block(message) for message in state.messages]
    if not blocks:
        blocks.append(
            "\n".join(
                [
                    "OPEN QUESTION · SEARCH",
                    "  What are you trying to locate in this Context?",
                    "",
                    "Describe it in your own words. The Search controller handles",
                    "the turn while this view remains open.",
                ]
            )
        )
    return tuple(blocks)


def _body_blocks(state: SearchChatState) -> tuple[str, ...]:
    return (*_result_blocks(state), *_dialogue_blocks(state))


def _dialogue_text(state: SearchChatState) -> str:
    return "\n\n".join(_dialogue_blocks(state))


def _result_text(state: SearchChatState) -> str:
    blocks = _result_blocks(state)
    return "\n\n".join(blocks) if blocks else "SEARCH RESULTS\n  (no matching items)"


def render_search_chat_snapshot(state: SearchChatState) -> str:
    """Render a stable non-interactive representation for tests and fallback."""
    return "\n\n".join(
        [
            render_search_chat_header(state),
            "\n\n".join(_body_blocks(state)),
            "ASK OR REFINE THE SEARCH\n  (interactive input not shown)",
        ]
    )


def _failed_turn_state(
    state: SearchChatState,
    text: str,
    error: Exception,
) -> SearchChatState:
    """Preserve the committed view and append one visible failure receipt."""
    return replace(
        state,
        messages=(
            *state.messages,
            SearchChatMessage(role="USER", text=text),
            SearchChatMessage(
                role="STATUS",
                text=(
                    f"Turn failed: {type(error).__name__}: {error}. "
                    "The existing results were not changed."
                ),
            ),
        ),
        status="TURN FAILED · PREVIOUS RESULTS KEPT",
    )


def _run_search_chat_application(
    initial_state: SearchChatState,
    *,
    handle_turn: SearchChatTurnHandler | None,
    app_input: Input | None,
    app_output: Output | None,
    require_tty: bool,
) -> SearchChatAction | SearchChatSessionResult:
    """Run one shell action or one long-lived controller-backed session."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Search chat",
            snapshot_hint="Use ordinary 'mem search' output outside a terminal.",
        )

    committed_state = initial_state
    display_state = initial_state
    submitted_turns: list[str] = []
    background_turn: BackgroundExecutorTurn[SearchChatState] = BackgroundExecutorTurn(
        interval_seconds=_SEARCH_BUSY_INTERVAL_SECONDS,
    )
    status_message = {"value": ""}
    bindings = KeyBindings()
    input_area = TextArea(
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, preferred=4, max=7),
        prompt="> ",
        # While a turn is in flight, keystrokes must not accumulate into a
        # hidden second submission that would race the frozen controller view.
        read_only=Condition(lambda: background_turn.busy),
    )
    top_panel = Window(
        FormattedTextControl(lambda: render_search_chat_header(display_state)),
        height=Dimension.exact(4),
        dont_extend_height=True,
        wrap_lines=False,
    )
    conversation_area = TextArea(
        text=_dialogue_text(display_state),
        multiline=True,
        read_only=True,
        focusable=True,
        wrap_lines=True,
        scrollbar=True,
    )
    conversation_area.buffer.cursor_position = len(conversation_area.text)
    conversation_control = conversation_area.control
    conversation_panel = conversation_area.window
    conversation_panel.height = Dimension(min=3, preferred=6, max=8)
    # Read-only buffers carry real cursors. Window scrolling is cursor-relative,
    # so this keeps long results and References inspectable without allowing
    # the user to edit their locally validated content.
    results_area = TextArea(
        text=_result_text(display_state),
        multiline=True,
        read_only=True,
        focusable=True,
        wrap_lines=True,
        scrollbar=True,
    )
    results_control = results_area.control
    results_panel = results_area.window
    input_panel = HSplit(
        [
            Window(
                FormattedTextControl(
                    lambda: (
                        _processing_search_turn_label(background_turn.frame)
                        if background_turn.busy
                        else " ASK OR REFINE THE SEARCH"
                    )
                ),
                height=Dimension.exact(1),
                dont_extend_height=True,
            ),
            input_area,
        ]
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status_message['value']}"
                if status_message["value"]
                else (
                    " Working · current results remain visible    "
                    "Ctrl-C · close after this turn"
                    if background_turn.busy
                    else (
                        " Enter · submit    Ctrl-J · newline    "
                        "Tab · results/dialogue/input    "
                        "↑/↓ or PgUp/PgDn · scroll    H · Help    "
                        "Esc/Ctrl-C · close"
                    )
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(top_panel),
        TuiRegion(results_panel, separator_before=True),
        TuiRegion(conversation_panel, separator_before=True),
        TuiRegion(input_panel, separator_before=True),
        TuiRegion(footer),
    )
    application: Application[SearchChatAction | SearchChatSessionResult] = Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=bindings,
        full_screen=True,
        # The alternate screen is left only when the person closes the
        # whole session, never between controller turns.
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )

    def refresh(next_state: SearchChatState) -> None:
        """Replace display buffers from the event-loop thread."""
        nonlocal display_state
        display_state = next_state
        next_results = _result_text(next_state)
        if results_area.buffer.text != next_results:
            results_area.buffer.set_document(
                Document(next_results, cursor_position=0),
                bypass_readonly=True,
            )
        next_dialogue = _dialogue_text(next_state)
        conversation_area.buffer.set_document(
            Document(next_dialogue, cursor_position=len(next_dialogue)),
            bypass_readonly=True,
        )
        application.invalidate()

    def session_result() -> SearchChatSessionResult:
        return SearchChatSessionResult(
            status="CLOSED",
            state=committed_state,
            submitted_turns=tuple(submitted_turns),
        )

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    def _submit(event) -> None:
        nonlocal committed_state
        if background_turn.busy:
            status_message["value"] = "A Search turn is already running."
            event.app.invalidate()
            return
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank Search turn first."
            event.app.invalidate()
            return
        if handle_turn is None:
            event.app.exit(result=SearchChatAction(kind="SUBMIT", text=text))
            return

        base_state = committed_state
        submitted_turns.append(text)
        input_area.buffer.set_document(Document("", cursor_position=0))
        status_message["value"] = ""
        refresh(
            replace(
                base_state,
                messages=(
                    *base_state.messages,
                    SearchChatMessage(role="USER", text=text),
                ),
                status="THINKING",
            )
        )
        event.app.layout.focus(conversation_control)

        def work() -> SearchChatState:
            assert handle_turn is not None
            updated = handle_turn(base_state, text)
            if not isinstance(updated, SearchChatState):
                raise ValueError(
                    "Search chat controller returned an invalid next state."
                )
            return updated

        def commit(updated: SearchChatState) -> None:
            nonlocal committed_state
            committed_state = updated
            refresh(updated)

        def fail(error: Exception) -> None:
            nonlocal committed_state
            committed_state = _failed_turn_state(base_state, text, error)
            refresh(committed_state)

        def return_to_input() -> None:
            status_message["value"] = ""
            application.layout.focus(input_area)

        background_turn.start(
            event.app,
            work=work,
            on_success=commit,
            on_error=fail,
            on_idle=return_to_input,
            on_close=lambda: application.exit(result=session_result()),
        )
        event.app.invalidate()

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    def _insert_newline(event) -> None:
        if background_turn.busy:
            status_message["value"] = "Wait for the current Search turn."
        else:
            input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("tab", eager=True)
    def _toggle_focus(event) -> None:
        if event.app.layout.has_focus(input_area):
            event.app.layout.focus(results_control)
        elif event.app.layout.has_focus(results_control):
            event.app.layout.focus(conversation_control)
        elif background_turn.busy:
            event.app.layout.focus(results_control)
        else:
            event.app.layout.focus(input_area)
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(results_control), eager=True)
    def _scroll_results_down(event) -> None:
        results_area.buffer.cursor_down()
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(results_control), eager=True)
    def _scroll_results_up(event) -> None:
        results_area.buffer.cursor_up()
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(conversation_control), eager=True)
    def _scroll_dialogue_down(event) -> None:
        conversation_area.buffer.cursor_down()
        event.app.invalidate()

    @bindings.add("up", filter=has_focus(conversation_control), eager=True)
    def _scroll_dialogue_up(event) -> None:
        conversation_area.buffer.cursor_up()
        event.app.invalidate()

    def close(event) -> None:
        if handle_turn is not None and background_turn.request_close():
            # The synchronous controller may own a child process. A cancelled
            # executor future cannot terminate that process safely, so finish
            # the reviewed turn before leaving the alternate screen.
            status_message["value"] = "Closing after the current turn finishes."
            event.app.invalidate()
            return
        result: SearchChatAction | SearchChatSessionResult = (
            SearchChatAction(kind="CLOSE") if handle_turn is None else session_result()
        )
        event.app.exit(result=result)

    navigation_focus = has_focus(conversation_control) | has_focus(results_control)
    bind_session_help(
        bindings,
        filter=navigation_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="search-chat",
    )

    @bindings.add("pageup", filter=navigation_focus, eager=True)
    def _scroll_page_up(event) -> None:
        scroll_page_up(event)
        event.app.invalidate()

    @bindings.add("pagedown", filter=navigation_focus, eager=True)
    def _scroll_page_down(event) -> None:
        scroll_page_down(event)
        event.app.invalidate()

    @bind_case_insensitive_key(bindings, "q", filter=navigation_focus, eager=True)
    def _close_from_transcript(event) -> None:
        close(event)

    @bindings.add("escape", eager=True)
    def _close_on_escape(event) -> None:
        dispatch_tui_back(event, close=close)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    @bindings.add("c-d", eager=True)
    def _close_anywhere(event) -> None:
        close(event)

    try:
        result = application.run()
    except (EOFError, KeyboardInterrupt):
        return (
            SearchChatAction(kind="CLOSE") if handle_turn is None else session_result()
        )
    if not isinstance(result, (SearchChatAction, SearchChatSessionResult)):
        raise ValueError("Search chat application returned an invalid result.")
    return result


def run_search_chat_shell(
    state: SearchChatState,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SearchChatAction:
    """Collect one Search dialogue turn without controller work."""
    result = _run_search_chat_application(
        state,
        handle_turn=None,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(result, SearchChatAction):  # pragma: no cover - invariant
        raise ValueError("Search shell returned an invalid result.")
    return result


def run_search_chat_session(
    initial_state: SearchChatState,
    *,
    handle_turn: SearchChatTurnHandler,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> SearchChatSessionResult:
    """Run repeated controller turns without recreating the full-screen UI."""
    result = _run_search_chat_application(
        initial_state,
        handle_turn=handle_turn,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(
        result,
        SearchChatSessionResult,
    ):  # pragma: no cover - invariant
        raise ValueError("Search session returned an invalid result.")
    return result
