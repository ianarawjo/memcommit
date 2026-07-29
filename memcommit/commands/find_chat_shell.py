"""Operation-neutral chat surface for interactive ``mem find``.

The shell deliberately returns one user action and exits.  The Find controller
interprets that turn, updates the in-process view, and reopens the shell without
putting provider calls or command execution inside prompt-toolkit handlers.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import TextArea

from memcommit.commands.tui_primitives import (
    TuiRegion,
    anchored_fragments,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)


FindChatRole = Literal["USER", "MEM", "STATUS"]
FindChatActionKind = Literal["SUBMIT", "CLOSE"]
FindChatResultKind = Literal["memory", "ref", "query"]


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
        if self.kind not in {"memory", "ref", "query"}:
            raise ValueError("Invalid Find chat result kind.")
        if not isinstance(self.uid, str) or not self.uid.strip():
            raise ValueError("Find chat results require an item UID.")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Find chat results require nonblank content.")


@dataclass(frozen=True)
class FindChatState:
    """Read-only presentation state for one invocation of the chat shell."""

    context_name: str
    current_query: str = ""
    messages: tuple[FindChatMessage, ...] = ()
    results: tuple[FindChatResult, ...] = ()
    kept_count: int = 0
    status: str = "READY"

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
        if (
            type(self.kept_count) is not int
            or self.kept_count < 0
        ):
            raise ValueError(
                "Find chat kept count must be a nonnegative integer."
            )
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Find chat requires a nonblank status.")


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
    """Final state after the person closes a repeatedly reopened chat."""

    status: Literal["CLOSED"]
    state: FindChatState
    submitted_turns: tuple[str, ...] = ()


def render_find_chat_header(state: FindChatState) -> str:
    """Render the stable portion of the Find chat frame."""
    query = state.current_query.strip() or "(not asked yet)"
    return "\n".join(
        [
            (
                "MEM FIND · INTERACTIVE · "
                f"{safe_terminal_text(state.context_name)}"
            ),
            f"QUERY · {safe_terminal_text(query)}",
            f"RESULTS {len(state.results)} · KEPT {state.kept_count}",
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


def _render_result(result: FindChatResult) -> str:
    label = (
        f"[{safe_terminal_text(result.alias)} "
        f"{result.kind:<7} {safe_terminal_text(result.uid[:8])}]"
    )
    lines = safe_terminal_text(result.content).splitlines() or [""]
    rendered = [f"{label} {lines[0]}"]
    continuation = " " * (len(label) + 1)
    rendered.extend(f"{continuation}{line}" for line in lines[1:])
    return "\n".join(rendered)


def _result_blocks(state: FindChatState) -> tuple[str, ...]:
    grouped: dict[str, list[FindChatResult]] = {}
    for result in state.results:
        grouped.setdefault(result.context_name, []).append(result)
    blocks: list[str] = []
    for index, (context_name, results) in enumerate(grouped.items()):
        lines = []
        if index == 0:
            lines.append("SEARCH RESULTS")
        lines.append(safe_terminal_text(context_name))
        lines.extend(_render_result(result) for result in results)
        blocks.append("\n".join(lines))
    return tuple(blocks)


def _dialogue_blocks(state: FindChatState) -> tuple[str, ...]:
    blocks = [_message_block(message) for message in state.messages]
    if not blocks:
        blocks.append(
            "\n".join(
                [
                    "OPEN QUESTION · FIND",
                    "  What are you trying to locate in this Context?",
                    "",
                    "Describe it in your own words. This shell only returns",
                    "the turn; the Find controller will own search and saving.",
                ]
            )
        )
    return tuple(blocks)


def _conversation_blocks(state: FindChatState) -> tuple[str, ...]:
    return (*_dialogue_blocks(state), *_result_blocks(state))


def _dialogue_fragments(state: FindChatState) -> list[tuple[str, str]]:
    blocks = _dialogue_blocks(state)
    return anchored_fragments(
        blocks,
        anchor_index=len(blocks) - 1,
        anchor_at_end=True,
    )


def _result_text(state: FindChatState) -> str:
    blocks = _result_blocks(state)
    return (
        "\n\n".join(blocks)
        if blocks
        else "SEARCH RESULTS\n  (no matching items)"
    )


def render_find_chat_snapshot(state: FindChatState) -> str:
    """Render a stable non-interactive representation for tests and fallback."""
    return "\n\n".join(
        [
            render_find_chat_header(state),
            "\n\n".join(_conversation_blocks(state)),
            "ASK OR REFINE THE FIND\n  (interactive input not shown)",
        ]
    )


def run_find_chat_shell(
    state: FindChatState,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindChatAction:
    """Collect one Find dialogue turn without searching or changing state."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Find chat",
            snapshot_hint="Use ordinary 'mem find' output outside a terminal.",
        )

    status_message = {"value": ""}
    bindings = KeyBindings()
    input_area = TextArea(
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, preferred=4, max=7),
        prompt="> ",
    )
    top_panel = Window(
        FormattedTextControl(lambda: render_find_chat_header(state)),
        height=Dimension.exact(4),
        dont_extend_height=True,
        wrap_lines=False,
    )
    conversation_control = FormattedTextControl(
        lambda: _dialogue_fragments(state),
        focusable=True,
        show_cursor=False,
    )
    conversation_panel = Window(
        conversation_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
        height=Dimension(min=3, preferred=6, max=8),
    )
    # A read-only BufferControl carries a real movable cursor. Window scroll
    # is cursor-relative, so mutating ``vertical_scroll`` on a cursorless
    # FormattedTextControl would be clamped back to its implicit first line.
    results_area = TextArea(
        text=_result_text(state),
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
                FormattedTextControl(" ASK OR REFINE THE FIND"),
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
                    " Enter · hand turn to Find controller    "
                    "Ctrl-J / Alt-Enter · newline    "
                    "Tab · dialogue/results/input    "
                    "↑/↓ · scroll results    Ctrl-C · close"
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(top_panel),
        TuiRegion(conversation_panel, separator_before=True),
        TuiRegion(results_panel, separator_before=True),
        TuiRegion(input_panel, separator_before=True),
        TuiRegion(footer),
    )
    application: Application[FindChatAction] = Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank Find turn first."
            event.app.invalidate()
            return
        event.app.exit(result=FindChatAction(kind="SUBMIT", text=text))

    @bindings.add("c-j", filter=has_focus(input_area), eager=True)
    @bindings.add(
        "escape",
        "enter",
        filter=has_focus(input_area),
        eager=True,
    )
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("tab", eager=True)
    def _toggle_focus(event) -> None:
        if event.app.layout.has_focus(input_area):
            event.app.layout.focus(conversation_control)
        elif event.app.layout.has_focus(conversation_control):
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

    def close(event) -> None:
        event.app.exit(result=FindChatAction(kind="CLOSE"))

    navigation_focus = (
        has_focus(conversation_control) | has_focus(results_control)
    )

    @bindings.add("q", filter=navigation_focus, eager=True)
    @bindings.add("escape", filter=navigation_focus, eager=True)
    def _close_from_transcript(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _close_anywhere(event) -> None:
        close(event)

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return FindChatAction(kind="CLOSE")


def run_find_chat_session(
    initial_state: FindChatState,
    *,
    handle_turn: FindChatTurnHandler,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FindChatSessionResult:
    """Reopen the shell after each controller-owned follow-up Find turn."""
    current = initial_state
    submitted_turns: list[str] = []
    while True:
        action = run_find_chat_shell(
            current,
            app_input=app_input,
            app_output=app_output,
            require_tty=require_tty,
        )
        if action.kind == "CLOSE":
            return FindChatSessionResult(
                status="CLOSED",
                state=current,
                submitted_turns=tuple(submitted_turns),
            )

        submitted_turns.append(action.text)
        try:
            updated = handle_turn(current, action.text)
            if not isinstance(updated, FindChatState):
                raise ValueError(
                    "Find chat controller returned an invalid next state."
                )
            current = updated
        except Exception as error:
            # A failed provider or controller turn must leave the current
            # results intact and return control to the person. Retrying is a
            # new visible turn rather than a hidden automatic action.
            current = replace(
                current,
                messages=(
                    *current.messages,
                    FindChatMessage(role="USER", text=action.text),
                    FindChatMessage(
                        role="STATUS",
                        text=(
                            f"Turn failed: {type(error).__name__}: {error}. "
                            "The existing results were not changed."
                        ),
                    ),
                ),
                status="TURN FAILED · RESULTS UNCHANGED",
            )
