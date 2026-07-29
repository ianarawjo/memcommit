"""Interactive, fail-closed shell for starting one Ground from a blank page.

The dialogue provider may explain or propose, but it cannot supply a shell
command.  This module freezes the three structured creation fields, renders
their argv locally, and calls the supplied ``apply`` adapter only after one
explicit approval.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from prompt_toolkit.application import Application
from prompt_toolkit.filters import has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import TextArea

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
    render_exact_command_blocks,
    render_exact_command_review,
)
from memcommit.commands.tui_primitives import (
    TuiRegion,
    anchored_fragments,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.ground import validate_ground_contract_name


INITIAL_QUESTION = (
    "What are you trying to understand, decide, or make together?"
)


class GroundInterpreter(Protocol):
    """A semantic adapter that returns an ASK or PROPOSE object."""

    def __call__(self, text: str) -> object: ...


@dataclass(frozen=True)
class GroundShellProposal:
    """The immutable Ground creation fields displayed for approval."""

    ground_name: str
    goal: str
    completion: str
    understanding: str
    question: str


class GroundApplier(Protocol):
    """An execution adapter for one already-approved structured proposal."""

    def __call__(self, proposal: GroundShellProposal) -> object: ...


@dataclass(frozen=True)
class GroundShellResult:
    """Terminal outcome of one blank-Ground shell."""

    status: Literal["APPLIED", "CANCELLED"]
    proposal: GroundShellProposal | None = None
    actual_output: str | None = None
    submitted_turns: tuple[str, ...] = ()


def proposal_argv(proposal: GroundShellProposal) -> tuple[str, ...]:
    """Build the only command shape this initial shell can approve."""
    return (
        "mem",
        "ground",
        proposal.ground_name,
        "--goal",
        proposal.goal,
        "--completion",
        proposal.completion,
    )


def format_proposal_command(proposal: GroundShellProposal) -> str:
    """Render exact POSIX argv for review; never execute it as a shell line."""
    return format_exact_command(_proposal_review(proposal))


def render_ground_top_panel(
    proposal: GroundShellProposal | None = None,
) -> str:
    """Render the fixed Goal–Rules–Cases panel."""
    goal = proposal.goal if proposal is not None else "(not yet stated)"
    completion = (
        proposal.completion
        if proposal is not None
        else "(not yet stated)"
    )
    return "\n".join(
        [
            "MEM GROUND · NEW · NOT SAVED",
            "GOAL",
            f"  {safe_terminal_text(goal)}",
            f"  completion: {safe_terminal_text(completion)}",
            "RULES",
            "  (none yet)",
            "CASES",
            "  (none yet)",
        ]
    )


def render_proposal_review(proposal: GroundShellProposal) -> str:
    """Render the exact proposal and its complete first-slice effect boundary."""
    return render_exact_command_review(_proposal_review(proposal))


def _proposal_review(
    proposal: GroundShellProposal,
) -> ExactCommandReview:
    return ExactCommandReview(
        argv=proposal_argv(proposal),
        effects=(
            f"Ground: CREATE {proposal.ground_name}",
            "Goal: SET",
            "Rules: unchanged (none)",
            "Cases: unchanged (none)",
            "Contexts: unchanged",
            "Memories: unchanged",
            "Checkpoints: unchanged",
        ),
    )


def _render_proposal_command_block(
    proposal: GroundShellProposal,
) -> str:
    return render_exact_command_blocks(_proposal_review(proposal))[0]


def _render_proposal_effects_block(
    proposal: GroundShellProposal,
) -> str:
    return render_exact_command_blocks(_proposal_review(proposal))[1]


def _anchored_conversation_fragments(
    blocks: Sequence[str],
    *,
    anchor_index: int | None,
    anchor_at_end: bool = False,
) -> list[tuple[str, str]]:
    """Render dialogue blocks with the active content as the scroll anchor.

    ``FormattedTextControl`` uses ``[SetCursorPosition]`` as its viewport
    anchor. Approval anchors the end of the exact command so its wrapped text
    remains visible when it fits, rather than anchoring the end of a
    potentially long transcript and hiding the command before ``A`` applies.
    """
    return anchored_fragments(
        blocks,
        anchor_index=anchor_index,
        anchor_at_end=anchor_at_end,
    )


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Dialogue response has no {label}.")
    return value.strip()


def _command_text(value: object, label: str) -> str:
    text = _required_text(value, label)
    if any(unicodedata.category(character) == "Cc" for character in text):
        raise ValueError(
            f"Dialogue response {label} contains a control character."
        )
    return text


def _response_kind(value: object) -> str:
    raw = _field(value, "kind")
    raw = getattr(raw, "value", raw)
    if not isinstance(raw, str):
        raise ValueError("Dialogue response has no ASK or PROPOSE kind.")
    kind = raw.upper()
    if kind not in {"ASK", "PROPOSE"}:
        raise ValueError("Dialogue response kind must be ASK or PROPOSE.")
    return kind


def _freeze_proposal(response: object) -> GroundShellProposal:
    nested = _field(response, "proposal")
    source = nested if nested is not None else response
    understanding = _field(response, "understanding")
    if understanding is None:
        understanding = _field(source, "understanding")
    question = _field(response, "question")
    if question is None:
        question = _field(source, "question")
    ground_name = validate_ground_contract_name(
        _command_text(_field(source, "ground_name"), "Ground name")
    )
    return GroundShellProposal(
        ground_name=ground_name,
        goal=_command_text(_field(source, "goal"), "Goal"),
        completion=_command_text(
            _field(source, "completion"),
            "completion criterion",
        ),
        understanding=_required_text(understanding, "understanding"),
        question=_required_text(question, "question"),
    )


def _agent_block(*, understanding: str, question: str) -> str:
    return "\n".join(
        [
            "AGENT UNDERSTANDING",
            f"  {safe_terminal_text(understanding)}",
            "",
            "AGENT QUESTION",
            f"  {safe_terminal_text(question)}",
        ]
    )


def run_ground_shell(
    *,
    interpret: GroundInterpreter,
    apply: GroundApplier,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> GroundShellResult:
    """Run the blank-Ground dialogue until one command is applied or cancelled."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=(
                "Run 'mem ground' in a terminal or use a snapshot mode."
            ),
        )

    mode = {"value": "INPUT"}
    review_view = {"value": "COMMAND"}
    pending: dict[str, GroundShellProposal | None] = {"value": None}
    error_message = {"value": ""}
    status_message = {"value": ""}
    last_submission = {"value": ""}
    submitted_turns: list[str] = []
    conversation: list[str] = [
        "\n".join(
            [
                "OPEN QUESTION · GOAL",
                f"  {INITIAL_QUESTION}",
                "",
                "Start in your own words; a rough outcome, case, or",
                "uncertainty is enough.",
            ]
        )
    ]

    bindings = KeyBindings()
    input_area = TextArea(
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, preferred=4, max=7),
        prompt="> ",
    )

    def top_text() -> str:
        return render_ground_top_panel(pending["value"])

    top_panel = Window(
        FormattedTextControl(top_text),
        height=Dimension(min=8, preferred=10, max=14),
        dont_extend_height=True,
        wrap_lines=True,
    )

    def conversation_fragments() -> list[tuple[str, str]]:
        blocks = list(conversation)
        anchor_index: int | None = None
        anchor_at_end = False
        proposal = pending["value"]
        if proposal is not None:
            command_index = len(blocks)
            blocks.extend(
                [
                    _render_proposal_command_block(proposal),
                    _render_proposal_effects_block(proposal),
                ]
            )
            if mode["value"] == "APPROVAL":
                if review_view["value"] == "EFFECTS":
                    anchor_index = command_index + 1
                    anchor_at_end = False
                else:
                    anchor_index = command_index
                    anchor_at_end = True
        if error_message["value"]:
            anchor_index = len(blocks)
            blocks.append(
                "INTERPRETATION FAILED · NOTHING APPLIED\n"
                f"  {safe_terminal_text(error_message['value'])}"
            )
        elif mode["value"] == "APPLY_ERROR" and conversation:
            # The failed command is the newest conversation block. Keep that
            # failure visible instead of snapping back to the proposal.
            anchor_index = len(conversation) - 1
        return _anchored_conversation_fragments(
            blocks,
            anchor_index=anchor_index,
            anchor_at_end=anchor_at_end,
        )

    conversation_control = FormattedTextControl(
        conversation_fragments,
        focusable=True,
        show_cursor=False,
    )
    conversation_panel = Window(
        conversation_control,
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )
    input_label = Window(
        FormattedTextControl(
            lambda: (
                " REFINE YOUR DESCRIPTION"
                if last_submission["value"]
                else " DESCRIBE WHAT YOU HAVE SO FAR"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    input_panel = HSplit([input_label, input_area])
    approval_panel = Window(
        FormattedTextControl(
            " ↑ command  ↓ effects    A · approve    E · refine    "
            "Q / Esc / Ctrl-C · cancel"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    error_panel = Window(
        FormattedTextControl(
            " R · retry interpretation    E · refine    "
            "Q / Esc / Ctrl-C · quit"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    apply_error_panel = Window(
        FormattedTextControl(
            " E · refine as a new proposal    Q / Esc / Ctrl-C · quit"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    action_panel = DynamicContainer(
        lambda: (
            approval_panel
            if mode["value"] == "APPROVAL"
            else apply_error_panel
            if mode["value"] == "APPLY_ERROR"
            else error_panel
            if mode["value"] == "ERROR"
            else input_panel
        )
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status_message['value']}"
                if status_message["value"]
                else " Enter · send    Ctrl-J / Alt-Enter · newline"
                if mode["value"] == "INPUT"
                else " No command runs without A · exact approval"
                if mode["value"] == "APPROVAL"
                else " The exact command will not be applied again"
                if mode["value"] == "APPLY_ERROR"
                else " The failed interpretation cannot change Ground state"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )

    root = build_tui_frame(
        TuiRegion(top_panel),
        TuiRegion(conversation_panel, separator_before=True),
        TuiRegion(action_panel, separator_before=True),
        TuiRegion(footer),
    )
    application: Application[GroundShellResult] = Application(
        layout=Layout(root, focused_element=input_area),
        key_bindings=bindings,
        full_screen=True,
        erase_when_done=True,
        input=app_input,
        output=app_output,
        mouse_support=False,
    )

    def focus_conversation() -> None:
        application.layout.focus(conversation_control)

    def focus_input(*, restore: bool) -> None:
        mode["value"] = "INPUT"
        pending["value"] = None
        review_view["value"] = "COMMAND"
        error_message["value"] = ""
        status_message["value"] = ""
        if restore:
            input_area.text = last_submission["value"]
            input_area.buffer.cursor_position = len(input_area.text)
        else:
            input_area.text = ""
        application.layout.focus(input_area)
        application.invalidate()

    def interpret_submission(text: str, *, append_user: bool) -> None:
        if append_user:
            submitted_turns.append(text)
            conversation.append(
                f"YOU\n  {safe_terminal_text(text)}"
            )
        dialogue_text = (
            submitted_turns[0]
            if len(submitted_turns) == 1
            else "\n\n".join(
                f"USER TURN {index}\n{turn}"
                for index, turn in enumerate(
                    submitted_turns,
                    start=1,
                )
            )
        )
        try:
            response = interpret(dialogue_text)
            kind = _response_kind(response)
            understanding = _required_text(
                _field(response, "understanding"),
                "understanding",
            )
            question = _required_text(
                _field(response, "question"),
                "question",
            )
            if append_user:
                conversation.append(
                    _agent_block(
                        understanding=understanding,
                        question=question,
                    )
                )
            else:
                conversation.append(
                    "\n".join(
                        [
                            "AGENT RETRY",
                            f"  {safe_terminal_text(understanding)}",
                            "",
                            "AGENT QUESTION",
                            f"  {safe_terminal_text(question)}",
                        ]
                    )
                )
            error_message["value"] = ""
            status_message["value"] = ""
            if kind == "ASK":
                focus_input(restore=False)
                return
            pending["value"] = _freeze_proposal(response)
            review_view["value"] = "COMMAND"
            mode["value"] = "APPROVAL"
            input_area.text = ""
            focus_conversation()
            application.invalidate()
        except Exception as error:
            pending["value"] = None
            error_message["value"] = (
                f"{type(error).__name__}: {error}"
            )
            status_message["value"] = ""
            mode["value"] = "ERROR"
            focus_conversation()
            application.invalidate()

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank description first."
            event.app.invalidate()
            return
        status_message["value"] = ""
        last_submission["value"] = text
        input_area.text = ""
        interpret_submission(text, append_user=True)

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

    @bindings.add("a", filter=has_focus(conversation_control), eager=True)
    def _approve(event) -> None:
        if mode["value"] != "APPROVAL" or pending["value"] is None:
            return
        # Freeze the reference before calling out.  Repeated keypresses cannot
        # approve another command because a successful call exits this app.
        proposal = pending["value"]
        mode["value"] = "APPLYING"
        event.app.invalidate()
        try:
            actual_output = apply(proposal)
        except Exception as error:
            conversation.append(
                "\n".join(
                    [
                        "APPLY FAILED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                    ]
                )
            )
            error_message["value"] = ""
            mode["value"] = "APPLY_ERROR"
            focus_conversation()
            event.app.invalidate()
            return
        event.app.exit(
            result=GroundShellResult(
                status="APPLIED",
                proposal=proposal,
                actual_output=str(actual_output),
                submitted_turns=tuple(submitted_turns),
            )
        )

    @bindings.add("up", filter=has_focus(conversation_control), eager=True)
    @bindings.add("left", filter=has_focus(conversation_control), eager=True)
    def _show_command(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        review_view["value"] = "COMMAND"
        event.app.invalidate()

    @bindings.add("down", filter=has_focus(conversation_control), eager=True)
    @bindings.add("right", filter=has_focus(conversation_control), eager=True)
    def _show_effects(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        review_view["value"] = "EFFECTS"
        event.app.invalidate()

    @bindings.add("e", filter=has_focus(conversation_control), eager=True)
    def _refine(event) -> None:
        if mode["value"] not in {"APPROVAL", "ERROR", "APPLY_ERROR"}:
            return
        conversation.append(
            "REFINEMENT\n  Previous proposal or interpretation returned "
            "for revision."
        )
        focus_input(restore=True)

    @bindings.add("r", filter=has_focus(conversation_control), eager=True)
    def _retry(event) -> None:
        if mode["value"] != "ERROR":
            return
        mode["value"] = "INTERPRETING"
        error_message["value"] = ""
        interpret_submission(last_submission["value"], append_user=False)

    def cancel(event) -> None:
        event.app.exit(
            result=GroundShellResult(
                status="CANCELLED",
                proposal=pending["value"],
                submitted_turns=tuple(submitted_turns),
            )
        )

    @bindings.add("q", filter=has_focus(conversation_control), eager=True)
    @bindings.add("escape", filter=has_focus(conversation_control), eager=True)
    def _cancel_from_action(event) -> None:
        cancel(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _cancel_anywhere(event) -> None:
        cancel(event)

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return GroundShellResult(
            status="CANCELLED",
            proposal=pending["value"],
            submitted_turns=tuple(submitted_turns),
        )
