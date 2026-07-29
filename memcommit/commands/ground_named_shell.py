"""Persistent Goal–Rules–Cases TUI for one already named Ground."""
from __future__ import annotations

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
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import TextArea

from memcommit.commands.exact_command_review import (
    ExactCommandReview,
    render_exact_command_blocks,
)
from memcommit.commands.tui_primitives import (
    TuiRegion,
    anchored_fragments,
    build_tui_frame,
    require_interactive_terminal,
    safe_terminal_text,
)
from memcommit.ground import (
    GROUND_SCHEMA_VERSION,
    GroundItem,
    GroundSession,
)


class NamedGroundInterpreter(Protocol):
    def __call__(
        self,
        session: GroundSession,
        text: str,
    ) -> object:
        """Return an ASK object or one frozen command proposal."""


@dataclass(frozen=True)
class GroundCommandProposal:
    """One operation-specific action reduced to a frozen local argv."""

    kind: str
    understanding: str
    question: str
    review: ExactCommandReview
    expected_ground_uid: str
    expected_revision: int
    expected_state_digest: str
    expected_context_versions: tuple[str, ...] = ()


class NamedGroundApplier(Protocol):
    def __call__(
        self,
        session: GroundSession,
        proposal: GroundCommandProposal,
    ) -> tuple[GroundSession, str]:
        """Apply exactly one approved command and reload the Ground."""


class NamedGroundReloader(Protocol):
    def __call__(self, contract_name: str) -> GroundSession:
        """Reload one required named Ground from durable storage."""


@dataclass(frozen=True)
class NamedGroundShellResult:
    status: Literal["CLOSED"]
    session: GroundSession
    applied_argvs: tuple[tuple[str, ...], ...] = ()
    submitted_turns: tuple[str, ...] = ()


def _line(value: str, limit: int = 110) -> str:
    normalized = " ".join(safe_terminal_text(value).split())
    if sum(get_cwidth(character) for character in normalized) <= limit:
        return normalized
    kept: list[str] = []
    width = 0
    for character in normalized:
        character_width = get_cwidth(character)
        if width + character_width > limit - 1:
            break
        kept.append(character)
        width += character_width
    return "".join(kept).rstrip() + "…"


def _aliased_items(
    session: GroundSession,
    kind: str,
) -> tuple[tuple[str, GroundItem], ...]:
    prefix = "r" if kind == "RULE" else "c"
    return tuple(
        (f"{prefix}{number}", item)
        for number, item in enumerate(
            (item for item in session.items if item.kind == kind),
            start=1,
        )
    )


def _alias_range(
    items: tuple[tuple[str, GroundItem], ...],
) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return f" · ID {items[0][0]}"
    return f" · IDs {items[0][0]}–{items[-1][0]}"


def render_named_ground_top_panel(session: GroundSession) -> str:
    """Render a compact fixed Goal–Rules–Cases state panel."""
    state = (
        "BOUND"
        if session.schema_version == GROUND_SCHEMA_VERSION
        else "UNBOUND"
    )
    rules = _aliased_items(session, "RULE")
    cases = _aliased_items(session, "CASE")
    rule_summary = (
        "(none yet)"
        if not rules
        else (
            f"{rules[-1][0]} [{rules[-1][1].status}] "
            f"{_line(rules[-1][1].content)}"
        )
    )
    case_summary = (
        "(none yet)"
        if not cases
        else (
            f"{cases[-1][0]} [{cases[-1][1].status}] "
            f"{_line(cases[-1][1].content)}"
        )
    )
    return "\n".join(
        [
            (
                f"MEM GROUND · {safe_terminal_text(session.contract_name)} · "
                f"SAVED · {state} · REV {session.revision}"
            ),
            (
                "GOAL · completion: "
                f"{_line(session.completion_criterion, 80)}"
            ),
            f"  {_line(session.goal or '(not yet stated)')}",
            (
                f"RULES {len(rules)} · "
                f"{sum(item.status == 'PROPOSED' for _, item in rules)} "
                f"proposed{_alias_range(rules)}"
            ),
            f"  {rule_summary}",
            (
                f"CASES {len(cases)} · "
                f"{sum(item.status == 'PROPOSED' for _, item in cases)} "
                f"proposed{_alias_range(cases)}"
            ),
            f"  {case_summary}",
        ]
    )


def _option_values(argv: tuple[str, ...], option: str) -> tuple[str, ...]:
    return tuple(
        argv[index + 1]
        for index, value in enumerate(argv[:-1])
        if value == option
    )


def _option_value(argv: tuple[str, ...], option: str) -> str:
    values = _option_values(argv, option)
    return values[0] if values else ""


def _item_aliases_by_uid(session: GroundSession) -> dict[str, str]:
    return {
        item.uid: alias
        for kind in ("RULE", "CASE")
        for alias, item in _aliased_items(session, kind)
    }


def _review_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    selector = _option_value(argv, "--decide")
    action = _option_value(argv, "--action").upper()
    target = next(
        (item for item in session.items if item.uid == selector),
        None,
    )
    if target is None or target.kind not in {"RULE", "CASE"}:
        return ()
    alias = _item_aliases_by_uid(session).get(target.uid, target.uid[:8])
    item_name = target.kind.title()
    details = [
        (
            f"Selected item: {alias} · {item_name} · {target.status} · "
            f"{_line(target.content)}"
        )
    ]
    if action == "REFINE":
        replacement = _option_value(argv, "--response")
        if target.kind == "RULE":
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} Rule content with "
                        f"'{_line(replacement)}'"
                    ),
                    (
                        f"{alias} remains PROPOSED; provenance becomes "
                        "JOINTLY_REVISED"
                    ),
                ]
            )
        else:
            details.extend(
                [
                    (
                        f"REFINE: replace {alias} expected output with "
                        f"'{_line(replacement)}'"
                    ),
                    (
                        f"{alias} remains PROPOSED; its source, linked Rule, "
                        "role, disposition, and targets remain unchanged"
                    ),
                ]
            )
    elif action in {"ACCEPT", "DEFER", "REJECT"}:
        status = {
            "ACCEPT": "ACCEPTED",
            "DEFER": "DEFERRED",
            "REJECT": "REJECTED",
        }[action]
        details.append(
            f"{action}: mark {alias} {status}; its content remains unchanged"
        )
    details.append("One review Decision record: ADD")
    return tuple(details)


def _proposal_item_effects(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, ...]:
    argv = proposal.review.argv
    if proposal.kind == "BIND":
        placements = _option_values(argv, "--placement-target")
        details = [
            f"Task binding: '{_line(_option_value(argv, '--description'))}'",
            (
                "Frames: raw="
                f"{_option_value(argv, '--raw-context')} · derived="
                f"{_option_value(argv, '--derived-context')}"
            ),
            (
                "Publication target: "
                f"{_option_value(argv, '--publication-target')}"
            ),
        ]
        if placements:
            details.append("Placement targets: " + ", ".join(placements))
        return tuple(details)
    if proposal.kind == "REVISE_GOAL":
        return (
            (
                "Replacement Goal: "
                f"'{_line(_option_value(argv, '--revise-goal'))}'"
            ),
            (
                "Reason: "
                f"{_line(_option_value(argv, '--change-reason'))}"
            ),
        )
    if proposal.kind == "PROPOSE_RULE":
        alias = f"r{len(_aliased_items(session, 'RULE')) + 1}"
        return (
            (
                f"New {alias} · PROPOSED Rule: "
                f"{_line(_option_value(argv, '--propose-rule'))}"
            ),
            (
                "Provenance: "
                f"{_option_value(argv, '--rule-provenance')}"
            ),
            f"Rationale: {_line(_option_value(argv, '--rationale'))}",
        )
    if proposal.kind == "PROPOSE_CASE":
        aliases = _item_aliases_by_uid(session)
        rule_uid = _option_value(argv, "--fit-rule")
        rule = next(
            (item for item in session.items if item.uid == rule_uid),
            None,
        )
        rule_alias = aliases.get(rule_uid, rule_uid[:8])
        alias = f"c{len(_aliased_items(session, 'CASE')) + 1}"
        details = [
            (
                f"New {alias} · PROPOSED "
                f"{_option_value(argv, '--case-role')}/"
                f"{_option_value(argv, '--disposition')} Case"
            ),
            (
                f"Linked Rule: {rule_alias}"
                + (f" · {_line(rule.content)}" if rule is not None else "")
            ),
            (
                "Targets: "
                + ", ".join(_option_values(argv, "--propose-target"))
            ),
            (
                "Expected output: "
                + (
                    _line(_option_value(argv, "--expected"))
                    or "(none for this disposition)"
                )
            ),
            "Source: exact Memory selected from the bound candidate Context",
        ]
        return tuple(details)
    if proposal.kind == "REVIEW_ITEM":
        return _review_item_effects(session, proposal)
    return ()


def render_named_ground_proposal_blocks(
    session: GroundSession,
    proposal: GroundCommandProposal,
) -> tuple[str, str]:
    """Render one Ground proposal with operation-aware approval context."""
    details = _proposal_item_effects(session, proposal)
    base_effects = proposal.review.effects
    if proposal.kind == "REVIEW_ITEM":
        base_effects = tuple(
            effect
            for effect in base_effects
            if not effect.startswith("Selected Rule/Case:")
            and not effect.startswith("One review Decision:")
        )
    informed_review = ExactCommandReview(
        argv=proposal.review.argv,
        effects=(*details, *base_effects),
    )
    return render_exact_command_blocks(informed_review)


def _initial_question(session: GroundSession) -> str:
    if session.schema_version != GROUND_SCHEMA_VERSION:
        return "\n".join(
            [
                "OPEN QUESTION · BINDING",
                "  Which explicit Task description, raw Context, derived",
                "  Context, and publication target should this Ground bind?",
                "",
                "No current Context is inferred. Placement or blocked targets",
                "can be supplied when they are part of the intended Ground.",
            ]
        )
    proposed = [
        item
        for item in session.items
        if item.kind in {"RULE", "CASE"} and item.status == "PROPOSED"
    ]
    if proposed:
        return "\n".join(
            [
                "OPEN QUESTION · REVIEW OR CONTINUE",
                "  Should the latest proposed Rule or Case be accepted,",
                "  refined, deferred, or rejected?",
            ]
        )
    return "\n".join(
        [
            "OPEN QUESTION · NEXT",
            "  Which one Ground layer should the next command change:",
            "  Goal, Rules, or Cases?",
        ]
    )


def _response_kind(response: object) -> str:
    raw = getattr(response, "kind", None)
    if not isinstance(raw, str):
        raise ValueError("Ground turn has no ASK or action kind.")
    return raw


def _response_text(response: object, field_name: str) -> str:
    value = getattr(response, field_name, None)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Ground turn has no {field_name}.")
    return value.strip()


def run_named_ground_shell(
    session: GroundSession,
    *,
    interpret: NamedGroundInterpreter,
    apply: NamedGroundApplier,
    reload_session: NamedGroundReloader | None = None,
    initial_receipt: str = "",
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> NamedGroundShellResult:
    """Run repeated one-command Ground turns until the person closes the TUI."""
    if require_tty:
        require_interactive_terminal(
            "Interactive Ground",
            snapshot_hint=(
                f"Use 'mem ground {session.contract_name} --snapshot' "
                "outside a terminal."
            ),
        )

    current = {"value": session}
    pending: dict[str, GroundCommandProposal | None] = {"value": None}
    mode = {"value": "INPUT"}
    review_view = {"value": "COMMAND"}
    error_message = {"value": ""}
    status_message = {"value": ""}
    last_submission = {"value": ""}
    cycle_dialogue: list[str] = []
    all_submitted_turns: list[str] = []
    applied_argvs: list[tuple[str, ...]] = []
    conversation = [_initial_question(session)]
    if initial_receipt:
        conversation.insert(
            0,
            "APPLIED\n  " + safe_terminal_text(initial_receipt),
        )

    bindings = KeyBindings()
    input_area = TextArea(
        multiline=True,
        wrap_lines=True,
        scrollbar=True,
        height=Dimension(min=3, preferred=4, max=7),
        prompt="> ",
    )
    top_panel = Window(
        FormattedTextControl(
            lambda: render_named_ground_top_panel(current["value"])
        ),
        height=Dimension.exact(7),
        dont_extend_height=True,
        # Every semantic layer owns a stable row. Wrapping long Korean or
        # Latin text must not push CASES below the fixed panel viewport.
        wrap_lines=False,
    )

    def conversation_fragments() -> list[tuple[str, str]]:
        blocks = list(conversation)
        anchor_index: int | None = None
        anchor_at_end = False
        proposal = pending["value"]
        if proposal is not None:
            command_block, effects_block = render_named_ground_proposal_blocks(
                current["value"],
                proposal,
            )
            command_index = len(blocks)
            blocks.extend([command_block, effects_block])
            if mode["value"] == "APPROVAL":
                if review_view["value"] == "EFFECTS":
                    anchor_index = command_index + 1
                    anchor_at_end = False
                else:
                    anchor_index = command_index
                    anchor_at_end = True
        if error_message["value"]:
            anchor_index = len(blocks)
            anchor_at_end = False
            blocks.append(
                "TURN FAILED · NOTHING NEW APPLIED\n"
                f"  {safe_terminal_text(error_message['value'])}"
            )
        elif mode["value"] == "APPLY_ERROR" and conversation:
            anchor_index = len(conversation) - 1
            anchor_at_end = False
        return anchored_fragments(
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
                else " DESCRIBE THE NEXT GROUND TURN"
            )
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    input_panel = HSplit([input_label, input_area])
    approval_panel = Window(
        FormattedTextControl(
            " ↑ command  ↓ effects    A · approve    E · refine    "
            "Q / Esc / Ctrl-C · close"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    error_panel = Window(
        FormattedTextControl(
            " R · retry interpretation    E · refine    "
            "Q / Esc / Ctrl-C · close"
        ),
        height=Dimension.exact(1),
        dont_extend_height=True,
    )
    apply_error_panel = Window(
        FormattedTextControl(
            " E · refine as a new proposal    Q / Esc / Ctrl-C · close"
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
                else " One approval applies one exact command"
                if mode["value"] == "APPROVAL"
                else " An unconfirmed command is never retried automatically"
                if mode["value"] == "APPLY_ERROR"
                else " No Ground state changed from the failed turn"
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
    application: Application[NamedGroundShellResult] = Application(
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

    def dialogue_text() -> str:
        return "\n\n".join(cycle_dialogue)

    def refresh_current(*, announce: bool) -> bool:
        if reload_session is None:
            return False
        previous = current["value"]
        refreshed = reload_session(previous.contract_name)
        if not isinstance(refreshed, GroundSession):
            raise ValueError("Named Ground reload returned invalid state.")
        if refreshed.contract_name != previous.contract_name:
            raise ValueError("Named Ground reload changed its storage key.")
        if refreshed == previous:
            return False
        current["value"] = refreshed
        cycle_dialogue.clear()
        if announce:
            conversation.append(
                "\n".join(
                    [
                        "GROUND REFRESHED",
                        "  Another saved change was found before this turn.",
                        (
                            "  The fixed panel and semantic turn now use the "
                            "latest Ground."
                        ),
                    ]
                )
            )
        application.invalidate()
        return True

    def interpret_current(*, append_user: bool, text: str) -> None:
        try:
            refresh_current(announce=True)
            if append_user or not cycle_dialogue:
                user_turn_number = (
                    sum(
                        block.startswith("USER TURN ")
                        for block in cycle_dialogue
                    )
                    + 1
                )
                cycle_dialogue.append(
                    f"USER TURN {user_turn_number}\n{text}"
                )
            if append_user:
                all_submitted_turns.append(text)
                conversation.append(f"YOU\n  {safe_terminal_text(text)}")
            response = interpret(current["value"], dialogue_text())
            kind = _response_kind(response)
            understanding = _response_text(response, "understanding")
            question = _response_text(response, "question")
            agent_turn_number = (
                sum(
                    block.startswith("AGENT TURN ")
                    for block in cycle_dialogue
                )
                + 1
            )
            cycle_dialogue.append(
                "\n".join(
                    [
                        f"AGENT TURN {agent_turn_number}",
                        f"UNDERSTANDING\n{understanding}",
                        f"QUESTION\n{question}",
                    ]
                )
            )
            conversation.append(
                "\n".join(
                    [
                        (
                            "AGENT UNDERSTANDING"
                            if append_user
                            else "AGENT RETRY"
                        ),
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
            if not isinstance(response, GroundCommandProposal):
                raise ValueError(
                    "Ground action was not reduced to an exact command."
                )
            pending["value"] = response
            review_view["value"] = "COMMAND"
            mode["value"] = "APPROVAL"
            input_area.text = ""
            focus_conversation()
            application.invalidate()
        except Exception as error:
            pending["value"] = None
            error_message["value"] = f"{type(error).__name__}: {error}"
            status_message["value"] = ""
            mode["value"] = "ERROR"
            focus_conversation()
            application.invalidate()

    @bindings.add("enter", filter=has_focus(input_area), eager=True)
    def _submit(event) -> None:
        text = input_area.text.strip()
        if not text:
            status_message["value"] = "Enter a nonblank Ground turn first."
            event.app.invalidate()
            return
        last_submission["value"] = text
        input_area.text = ""
        interpret_current(append_user=True, text=text)

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
        proposal = pending["value"]
        if mode["value"] != "APPROVAL" or proposal is None:
            return
        mode["value"] = "APPLYING"
        event.app.invalidate()
        try:
            updated, actual_output = apply(current["value"], proposal)
        except Exception as error:
            refresh_note = (
                "The saved Ground could not be reloaded; close and resume "
                "before proposing another command."
            )
            try:
                if refresh_current(announce=False):
                    refresh_note = (
                        "The fixed panel was refreshed from the latest saved "
                        "Ground before further input."
                    )
                else:
                    refresh_note = (
                        "The fixed panel already matches the latest saved "
                        "Ground."
                    )
            except Exception as refresh_error:
                refresh_note += (
                    " Reload error: "
                    f"{safe_terminal_text(type(refresh_error).__name__)}: "
                    f"{safe_terminal_text(str(refresh_error))}"
                )
            conversation.append(
                "\n".join(
                    [
                        "APPLY NOT CONFIRMED",
                        f"  {safe_terminal_text(type(error).__name__)}: "
                        f"{safe_terminal_text(str(error))}",
                        "",
                        "The same approval will not be retried automatically.",
                        refresh_note,
                    ]
                )
            )
            error_message["value"] = ""
            mode["value"] = "APPLY_ERROR"
            focus_conversation()
            event.app.invalidate()
            return
        current["value"] = updated
        applied_argvs.append(proposal.review.argv)
        conversation.append(
            "\n".join(
                [
                    f"APPLIED · {safe_terminal_text(proposal.kind)}",
                    f"  {safe_terminal_text(actual_output)}",
                    "",
                    (
                        "The fixed Goal–Rules–Cases panel now reflects the "
                        "saved Ground."
                    ),
                ]
            )
        )
        conversation.append(_initial_question(updated))
        cycle_dialogue.clear()
        last_submission["value"] = ""
        focus_input(restore=False)

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
            "REFINEMENT\n  The pending action returned for revision."
        )
        focus_input(restore=True)

    @bindings.add("r", filter=has_focus(conversation_control), eager=True)
    def _retry(event) -> None:
        if mode["value"] != "ERROR":
            return
        mode["value"] = "INTERPRETING"
        error_message["value"] = ""
        interpret_current(append_user=False, text=last_submission["value"])

    def close(event) -> None:
        event.app.exit(
            result=NamedGroundShellResult(
                status="CLOSED",
                session=current["value"],
                applied_argvs=tuple(applied_argvs),
                submitted_turns=tuple(all_submitted_turns),
            )
        )

    @bindings.add("q", filter=has_focus(conversation_control), eager=True)
    @bindings.add("escape", filter=has_focus(conversation_control), eager=True)
    def _close_from_review(event) -> None:
        close(event)

    @bindings.add("c-c", eager=True)
    @bindings.add(Keys.SIGINT, eager=True)
    def _close_anywhere(event) -> None:
        close(event)

    try:
        return application.run()
    except (EOFError, KeyboardInterrupt):
        return NamedGroundShellResult(
            status="CLOSED",
            session=current["value"],
            applied_argvs=tuple(applied_argvs),
            submitted_turns=tuple(all_submitted_turns),
        )
