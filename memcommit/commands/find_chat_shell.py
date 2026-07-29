"""Operation-neutral chat surface for a future interactive ``mem find``.

The shell deliberately returns one user action and exits.  A Find controller
can later run semantic search, update a durable session, and reopen this view
without putting provider calls or persistence inside prompt-toolkit handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
class FindChatState:
    """Read-only presentation state for one invocation of the chat shell."""

    context_name: str
    current_query: str = ""
    messages: tuple[FindChatMessage, ...] = ()
    result_count: int = 0
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
        if (
            type(self.result_count) is not int
            or self.result_count < 0
            or type(self.kept_count) is not int
            or self.kept_count < 0
        ):
            raise ValueError("Find chat counts must be nonnegative integers.")
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
            f"RESULTS {state.result_count} · KEPT {state.kept_count}",
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


def _conversation_blocks(state: FindChatState) -> tuple[str, ...]:
    if state.messages:
        return tuple(_message_block(message) for message in state.messages)
    return (
        "\n".join(
            [
                "OPEN QUESTION · FIND",
                "  What are you trying to locate in this Context?",
                "",
                "Describe it in your own words. This shell only returns",
                "the turn; the Find controller will own search and saving.",
            ]
        ),
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
        lambda: anchored_fragments(
            _conversation_blocks(state),
            anchor_index=len(_conversation_blocks(state)) - 1,
            anchor_at_end=True,
        ),
        focusable=True,
        show_cursor=False,
    )
    conversation_panel = Window(
        conversation_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
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
                    "Tab · transcript    Ctrl-C · close"
                )
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    root = build_tui_frame(
        TuiRegion(top_panel),
        TuiRegion(conversation_panel, separator_before=True),
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
        else:
            event.app.layout.focus(input_area)
        event.app.invalidate()

    def close(event) -> None:
        event.app.exit(result=FindChatAction(kind="CLOSE"))

    @bindings.add("q", filter=has_focus(conversation_control), eager=True)
    @bindings.add("escape", filter=has_focus(conversation_control), eager=True)
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
