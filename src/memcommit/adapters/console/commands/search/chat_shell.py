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
from memcommit.adapters.console.shared.background_turn import BackgroundExecutorTurn
from memcommit.adapters.console.shared.command_progress import (
    BUSY_INTERVAL_SECONDS,
    busy_suffix,
)
from memcommit.adapters.console.shared.session_help import bind_session_help
from memcommit.adapters.interfaces.cli.search_results import (
    SearchResultViewRow,
    render_grouped_search_results,
)


FindChatRole = Literal["USER", "MEM", "STATUS"]
FindChatActionKind = Literal["SUBMIT", "CLOSE"]
FindChatResultKind = Literal["memory", "ref", "query", "artifact"]
FindChatRelevance = Literal["primary", "related"]
# Compatibility name remains patchable by focused shell tests while its
# default comes from the shared blocking-progress visual contract.
_FIND_BUSY_INTERVAL_SECONDS = BUSY_INTERVAL_SECONDS


def _processing_find_turn_label(frame_index: int) -> str:
    """Render one deterministic frame of the in-process busy indicator."""
    return " PROCESSING SEARCH TURN " + busy_suffix(frame_index)


@dataclass(frozen=True)
class FindChatMessage:
    """One already-visible dialogue block supplied by the Find controller."""

    role: FindChatRole
    text: str

    def __post_init__(self) -> None:
        if self.role not in {"USER", "MEM", "STATUS"}:
            raise ValueError("Invalid Find chat message role.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Find chat messages require nonblank text.")


@dataclass(frozen=True)
class FindChatResult:
    """One locally validated result rendered without provider-authored text."""

    alias: str
    context_name: str
    kind: FindChatResultKind
    uid: str
    content: str
    relevance: FindChatRelevance = "primary"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.alias, str)
            or not self.alias.startswith("m")
            or not self.alias[1:].isdigit()
            or self.alias[1:].startswith("0")
        ):
            raise ValueError("Find chat results require an alias like m1.")
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Find chat results require a Context name.")
        if self.kind not in {"memory", "ref", "query", "artifact"}:
            raise ValueError("Invalid Find chat result kind.")
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Find chat results require an item UID.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Find chat results require nonblank content.")
        if self.relevance not in {"primary", "related"}:
            raise ValueError("Invalid Find chat result relevance.")


@dataclass(frozen=True)
class FindPendingAnswerRequest:
    """One wider-scope answer waiting for a host-owned confirmation token."""

    user_text: str
    interpreted_request: str
    pending_clarification: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.user_text, str) or not self.user_text.strip():
            raise ValueError("Pending Find answers require user text.")
        if (
            not isinstance(self.interpreted_request, str)
            or not self.interpreted_request.strip()
        ):
            raise ValueError("Pending Find answers require an interpreted request.")
        if self.pending_clarification is not None and (
            not isinstance(self.pending_clarification, str)
            or not self.pending_clarification.strip()
        ):
            raise ValueError("Pending Find clarification must be nonblank text.")


@dataclass(frozen=True)
class FindChatState:
    """One immutable committed or transient view of the Find chat."""

    context_name: str
    current_query: str = ""
    messages: tuple[FindChatMessage, ...] = ()
    results: tuple[FindChatResult, ...] = ()
    related_query: str = ""
    kept_count: int = 0
    status: str = "READY"
    pending_answer: FindPendingAnswerRequest | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name.strip():
            raise ValueError("Find chat requires a Context name.")
        if not isinstance(self.current_query, str):
            raise ValueError("Find chat query must be text.")
        if isinstance(self.messages, (str, bytes)):
            raise ValueError("Find chat messages must be a sequence.")
        try:
            messages = tuple(self.messages)
        except TypeError as error:
            raise ValueError("Find chat messages must be a sequence.") from error
        if any(not isinstance(message, FindChatMessage) for message in messages):
            raise ValueError("Invalid Find chat message.")
        object.__setattr__(self, "messages", messages)
        if isinstance(self.results, (str, bytes)):
            raise ValueError("Find chat results must be a sequence.")
        try:
            results = tuple(self.results)
        except TypeError as error:
            raise ValueError("Find chat results must be a sequence.") from error
        if any(not isinstance(result, FindChatResult) for result in results):
            raise ValueError("Invalid Find chat result.")
        aliases = tuple(result.alias for result in results)
        if len(set(aliases)) != len(aliases):
            raise ValueError("Find chat result aliases must be unique.")
        object.__setattr__(self, "results", results)
        if not isinstance(self.related_query, str):
            raise ValueError("Find chat related query must be text.")
        related_query = self.related_query.strip()
        related = tuple(result for result in results if result.relevance == "related")
        primary = tuple(result for result in results if result.relevance == "primary")
        if primary and related:
            raise ValueError("Find chat cannot mix primary and related results.")
        if bool(related_query) != bool(related):
            raise ValueError("Related Find chat results require one related query.")
        object.__setattr__(self, "related_query", related_query)
        if type(self.kept_count) is not int or self.kept_count < 0:
            raise ValueError("Find chat kept count must be a nonnegative integer.")
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Find chat requires a nonblank status.")
        if self.pending_answer is not None and not isinstance(
            self.pending_answer,
            FindPendingAnswerRequest,
        ):
            raise ValueError("Invalid pending Find answer.")


@dataclass(frozen=True)
class FindChatAction:
    """The single controller-owned action returned by one shell invocation."""

    kind: FindChatActionKind
    text: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"SUBMIT", "CLOSE"}:
            raise ValueError("Invalid Find chat action.")
        if not isinstance(self.text, str):
            raise ValueError("Find chat action text must be text.")
        if self.kind == "SUBMIT" and not self.text.strip():
            raise ValueError("A submitted Find turn cannot be blank.")
        if self.kind == "CLOSE" and self.text:
            raise ValueError("A closed Find chat cannot carry submitted text.")


class FindChatTurnHandler(Protocol):
    """Controller boundary for one read-only follow-up Find turn."""

    def __call__(
        self,
        state: FindChatState,
        text: str,
    ) -> FindChatState:
        """Return the complete next view after handling one submitted turn."""


@dataclass(frozen=True)
class FindChatSessionResult:
    """Final committed state after the person closes one continuous chat."""

    status: Literal["CLOSED"]
    state: FindChatState
    submitted_turns: tuple[str, ...] = ()


def render_find_chat_header(state: FindChatState) -> str:
    """Render the stable portion of the Find chat frame."""
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


def _message_block(message: FindChatMessage) -> str:
    label = {
        "USER": "YOU",
        "MEM": "MEM",
        "STATUS": "STATUS",
    }[message.role]
    content = safe_terminal_text(message.text).replace("\n", "\n  ")
    return f"{label}\n  {content}"


def _result_view_row(result: FindChatResult) -> SearchResultViewRow:
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


def _result_blocks(state: FindChatState) -> tuple[str, ...]:
    if not state.results:
        return ()
    return (
        render_grouped_search_results(
            tuple(_result_view_row(result) for result in state.results),
            related_query=state.related_query,
        ),
    )


def _dialogue_blocks(state: FindChatState) -> tuple[str, ...]:
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


def _body_blocks(state: FindChatState) -> tuple[str, ...]:
    return (*_result_blocks(state), *_dialogue_blocks(state))


def _dialogue_text(state: FindChatState) -> str:
    return "\n\n".join(_dialogue_blocks(state))


def _result_text(state: FindChatState) -> str:
    blocks = _result_blocks(state)
    return "\n\n".join(blocks) if blocks else "SEARCH RESULTS\n  (no matching items)"


def render_find_chat_snapshot(state: FindChatState) -> str:
    """Render a stable non-interactive representation for tests and fallback."""
    return "\n\n".join(
        [
            render_find_chat_header(state),
            "\n\n".join(_body_blocks(state)),
            "ASK OR REFINE THE SEARCH\n  (interactive input not shown)",
        ]
    )


def _failed_turn_state(
    state: FindChatState,
    text: str,
    error: Exception,
) -> FindChatState:
    """Preserve the committed view and append one visible failure receipt."""
    return replace(
        state,
        messages=(
            *state.messages,
            FindChatMessage(role="USER", text=text),
            FindChatMessage(
                role="STATUS",
                text=(
                    f"Turn failed: {type(error).__name__}: {error}. "
                    "The existing results were not changed."
                ),
            ),
        ),
        status="TURN FAILED · PREVIOUS RESULTS KEPT",
    )


def _run_find_chat_application(
    initial_state: FindChatState,
    *,
    handle_turn: FindChatTurnHandler | None,
    app_input: Input | None,
    app_output: Output | None,
    require_tty: bool,
) -> FindChatAction | FindChatSessionResult:
    """Run one shell action or one long-lived controller-backed session."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Search chat",
            snapshot_hint="Use ordinary 'mem search' output outside a terminal.",
        )

    committed_state = initial_state
    display_state = initial_state
    submitted_turns: list[str] = []
    background_turn: BackgroundExecutorTurn[FindChatState] = BackgroundExecutorTurn(
        interval_seconds=_FIND_BUSY_INTERVAL_SECONDS,
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
        FormattedTextControl(lambda: render_find_chat_header(display_state)),
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
                        _processing_find_turn_label(background_turn.frame)
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
    application: Application[FindChatAction | FindChatSessionResult] = Application(
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

    def refresh(next_state: FindChatState) -> None:
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

    def session_result() -> FindChatSessionResult:
        return FindChatSessionResult(
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
            event.app.exit(result=FindChatAction(kind="SUBMIT", text=text))
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
                    FindChatMessage(role="USER", text=text),
                ),
                status="THINKING",
            )
        )
        event.app.layout.focus(conversation_control)

        def work() -> FindChatState:
            assert handle_turn is not None
            updated = handle_turn(base_state, text)
            if not isinstance(updated, FindChatState):
                raise ValueError("Find chat controller returned an invalid next state.")
            return updated

        def commit(updated: FindChatState) -> None:
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
        result: FindChatAction | FindChatSessionResult = (
            FindChatAction(kind="CLOSE") if handle_turn is None else session_result()
        )
        event.app.exit(result=result)

    navigation_focus = has_focus(conversation_control) | has_focus(results_control)
    bind_session_help(
        bindings,
        filter=navigation_focus,
        app_input=app_input,
        app_output=app_output,
        study_surface="find-chat",
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
        return FindChatAction(kind="CLOSE") if handle_turn is None else session_result()
    if not isinstance(result, (FindChatAction, FindChatSessionResult)):
        raise ValueError("Find chat application returned an invalid result.")
    return result


def run_find_chat_shell(
    state: FindChatState,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindChatAction:
    """Collect one Find dialogue turn without controller work."""
    result = _run_find_chat_application(
        state,
        handle_turn=None,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(result, FindChatAction):  # pragma: no cover - invariant
        raise ValueError("Find shell returned an invalid result.")
    return result


def run_find_chat_session(
    initial_state: FindChatState,
    *,
    handle_turn: FindChatTurnHandler,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindChatSessionResult:
    """Run repeated controller turns without recreating the full-screen UI."""
    result = _run_find_chat_application(
        initial_state,
        handle_turn=handle_turn,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if not isinstance(
        result,
        FindChatSessionResult,
    ):  # pragma: no cover - invariant
        raise ValueError("Find session returned an invalid result.")
    return result
