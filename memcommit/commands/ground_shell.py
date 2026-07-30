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
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import (
    DynamicContainer,
    FormattedTextControl,
    Layout,
    Window,
)
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from prompt_toolkit.widgets import Frame

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    format_exact_command,
    render_exact_command_blocks,
    render_exact_command_review,
)
from memcommit.commands.tui_primitives import (
    TuiRegion,
    anchored_fragments,
    build_framed_multiline_input,
    build_scrollable_text_pane,
    build_tui_frame,
    equal_pane_height,
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
    *,
    working_goal: str = "",
) -> str:
    """Render the compact unsaved Goal–Contexts–Rules–Cases state."""
    goal = (
        proposal.goal
        if proposal is not None
        else working_goal or "(not yet stated)"
    )
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
            "CONTEXTS",
            "  (not bound; not inferred)",
            "RULES",
            "  (none yet)",
            "CASES",
            "  (none yet)",
        ]
    )


def render_ground_goal_pane(
    proposal: GroundShellProposal | None = None,
    *,
    working_goal: str = "",
) -> str:
    """Render the complete blank-Ground Goal state for its own viewport."""
    if proposal is None:
        lines = [
            (
                "WORKING · NOT SAVED"
                if working_goal
                else "(not yet stated)"
            ),
        ]
        if working_goal:
            lines.append(safe_terminal_text(working_goal))
        lines.extend(["", "COMPLETION", "(not yet stated)"])
        return "\n".join(lines)

    lines = [
        "PROPOSED · NOT SAVED",
        safe_terminal_text(proposal.goal),
        "",
        "COMPLETION",
        safe_terminal_text(proposal.completion),
    ]
    if working_goal and working_goal != proposal.goal:
        lines.extend(
            [
                "",
                "STARTING REQUEST",
                safe_terminal_text(working_goal),
            ]
        )
    return "\n".join(lines)


def render_ground_contexts_pane() -> str:
    """Render the blank Ground's explicit absence of a Context frame."""
    return "\n".join(
        [
            "(not bound; not inferred)",
            "",
            "Contexts are bound only after this Ground is created.",
            "The current Context is not read or inferred.",
        ]
    )


def render_ground_rules_pane() -> str:
    """Render the initial slice's intentionally empty Rules component."""
    return "\n".join(
        [
            "(none yet)",
            "",
            "Rules can be proposed after this Ground is created.",
        ]
    )


def render_ground_cases_pane() -> str:
    """Render the initial slice's intentionally empty Cases component."""
    return "\n".join(
        [
            "(none yet)",
            "",
            "Cases can be added after the Goal and working Rules exist.",
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
    initial_request: str = "",
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

    working_goal = initial_request.strip()
    mode = {"value": "INPUT"}
    review_view = {"value": "COMMAND"}
    pending: dict[str, GroundShellProposal | None] = {"value": None}
    error_message = {"value": ""}
    status_message = {"value": ""}
    last_submission = {"value": working_goal}
    submitted_turns: list[str] = []
    conversation: list[str] = (
        [
            "\n".join(
                [
                    "STARTING REQUEST · WORKING GOAL",
                    f"  {safe_terminal_text(working_goal)}",
                    "",
                    "Press Enter to begin the dialogue, or edit the",
                    "prefilled Message first.",
                ]
            )
        ]
        if working_goal
        else [
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
    )

    bindings = KeyBindings()
    # Five independent workbench panes must still fit a conventional 24-row
    # terminal. Other TUI users retain the shared four-row default.
    pane_height = equal_pane_height(minimum=3)
    action_height = Dimension(min=5, preferred=6, max=8)
    goal_pane = build_scrollable_text_pane(
        "GOAL",
        render_ground_goal_pane(working_goal=working_goal),
        buffer_name="ground-new-goal",
        height=pane_height,
    )
    contexts_pane = build_scrollable_text_pane(
        "CONTEXTS",
        render_ground_contexts_pane(),
        buffer_name="ground-new-contexts",
        height=pane_height,
    )
    rules_pane = build_scrollable_text_pane(
        "RULES",
        render_ground_rules_pane(),
        buffer_name="ground-new-rules",
        height=pane_height,
    )
    cases_pane = build_scrollable_text_pane(
        "CASES",
        render_ground_cases_pane(),
        buffer_name="ground-new-cases",
        height=pane_height,
    )

    def conversation_text() -> str:
        blocks = list(conversation)
        proposal = pending["value"]
        if proposal is not None:
            if review_view["value"] == "EFFECTS":
                blocks.append(_render_proposal_effects_block(proposal))
            else:
                blocks.append(
                    _render_proposal_command_block(proposal),
                )
        if error_message["value"]:
            blocks.append(
                "INTERPRETATION FAILED · NOTHING APPLIED\n"
                f"  {safe_terminal_text(error_message['value'])}"
            )
        return "\n\n".join(blocks)

    dialogue_pane = build_scrollable_text_pane(
        "DIALOGUE",
        conversation_text(),
        buffer_name="ground-new-dialogue",
        height=pane_height,
    )
    composer = build_framed_multiline_input(
        "MESSAGE",
        prompt="› ",
        buffer_name="ground-new-message",
        height=action_height,
    )
    input_area = composer.text_area
    if working_goal:
        # The command-line request is visible and editable before any provider
        # call. This preserves an immediate Escape path and makes sending it
        # an explicit dialogue action rather than hidden startup work.
        input_area.text = working_goal
        input_area.buffer.cursor_position = len(working_goal)

    header = Window(
        FormattedTextControl(" MEM GROUND · NEW · NOT SAVED"),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    approval_panel = Frame(
        Window(
            FormattedTextControl(
                " ↑ / ← · exact command    ↓ / → · effects\n"
                " A · approve once          E · refine\n"
                " Q / Esc / Ctrl-C · cancel"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=action_height,
    )
    error_panel = Frame(
        Window(
            FormattedTextControl(
                " R · retry interpretation    E · refine\n"
                " Q / Esc / Ctrl-C · quit"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=action_height,
    )
    apply_error_panel = Frame(
        Window(
            FormattedTextControl(
                " E · refine as a new proposal\n"
                " Q / Esc / Ctrl-C · quit"
            ),
            wrap_lines=True,
        ),
        title="ACTION",
        height=action_height,
    )
    action_panel = DynamicContainer(
        lambda: (
            approval_panel
            if mode["value"] == "APPROVAL"
            else apply_error_panel
            if mode["value"] == "APPLY_ERROR"
            else error_panel
            if mode["value"] == "ERROR"
            else composer.container
        )
    )
    footer = Window(
        FormattedTextControl(
            lambda: (
                f" {status_message['value']}"
                if status_message["value"]
                else " Enter · send / return    Ctrl-J · newline    Tab · pane"
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
        TuiRegion(header),
        TuiRegion(goal_pane.container),
        TuiRegion(contexts_pane.container),
        TuiRegion(rules_pane.container),
        TuiRegion(cases_pane.container),
        TuiRegion(dialogue_pane.container),
        TuiRegion(action_panel),
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

    def sync_panes(*, dialogue_anchor: str = "end") -> None:
        goal_pane.set_text(
            render_ground_goal_pane(
                pending["value"],
                working_goal=working_goal,
            ),
            anchor="preserve",
        )
        dialogue_pane.set_text(
            conversation_text(),
            anchor=dialogue_anchor,
        )

    def focus_conversation() -> None:
        application.layout.focus(dialogue_pane.text_area)

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
        sync_panes(dialogue_anchor="end")
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
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()
        except Exception as error:
            pending["value"] = None
            error_message["value"] = (
                f"{type(error).__name__}: {error}"
            )
            status_message["value"] = ""
            mode["value"] = "ERROR"
            sync_panes(dialogue_anchor="end")
            focus_conversation()
            application.invalidate()

    input_mode = Condition(lambda: mode["value"] == "INPUT")
    approval_mode = Condition(lambda: mode["value"] == "APPROVAL")
    error_mode = Condition(lambda: mode["value"] == "ERROR")
    action_mode = Condition(
        lambda: mode["value"] in {"APPROVAL", "ERROR", "APPLY_ERROR"}
    )
    read_panes = (
        goal_pane.text_area,
        contexts_pane.text_area,
        rules_pane.text_area,
        cases_pane.text_area,
        dialogue_pane.text_area,
    )
    read_pane_focus = (
        has_focus(goal_pane.text_area)
        | has_focus(contexts_pane.text_area)
        | has_focus(rules_pane.text_area)
        | has_focus(cases_pane.text_area)
        | has_focus(dialogue_pane.text_area)
    )
    focus_order = (input_area, *read_panes)

    def cycle_focus(step: int) -> None:
        current_index = next(
            (
                index
                for index, element in enumerate(focus_order)
                if application.layout.has_focus(element)
            ),
            0,
        )
        application.layout.focus(
            focus_order[(current_index + step) % len(focus_order)]
        )
        application.invalidate()

    @bindings.add("tab", filter=input_mode, eager=True)
    def _focus_next(_event) -> None:
        cycle_focus(1)

    @bindings.add(Keys.BackTab, filter=input_mode, eager=True)
    def _focus_previous(_event) -> None:
        cycle_focus(-1)

    @bindings.add("tab", filter=~input_mode, eager=True)
    @bindings.add(Keys.BackTab, filter=~input_mode, eager=True)
    def _keep_modal_focus(_event) -> None:
        """Approval and failure controls remain attached to Dialogue."""

    @bindings.add(
        "enter",
        filter=input_mode & read_pane_focus,
        eager=True,
    )
    def _return_to_message(event) -> None:
        event.app.layout.focus(input_area)
        event.app.invalidate()

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
    def _insert_newline(event) -> None:
        input_area.buffer.insert_text("\n")
        event.app.invalidate()

    @bindings.add("a", filter=approval_mode, eager=True)
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
            sync_panes(dialogue_anchor="end")
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

    @bindings.add("up", filter=approval_mode, eager=True)
    @bindings.add("left", filter=approval_mode, eager=True)
    def _show_command(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        review_view["value"] = "COMMAND"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("down", filter=approval_mode, eager=True)
    @bindings.add("right", filter=approval_mode, eager=True)
    def _show_effects(event) -> None:
        if mode["value"] != "APPROVAL":
            return
        review_view["value"] = "EFFECTS"
        sync_panes(dialogue_anchor="end")
        event.app.invalidate()

    @bindings.add("e", filter=action_mode, eager=True)
    def _refine(event) -> None:
        if mode["value"] not in {"APPROVAL", "ERROR", "APPLY_ERROR"}:
            return
        conversation.append(
            "REFINEMENT\n  Previous proposal or interpretation returned "
            "for revision."
        )
        focus_input(restore=True)

    @bindings.add("r", filter=error_mode, eager=True)
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

    @bindings.add("q", filter=action_mode, eager=True)
    def _cancel_from_action(event) -> None:
        cancel(event)

    @bindings.add("escape", eager=True)
    def _cancel_on_escape(event) -> None:
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
