from __future__ import annotations

import shlex
from dataclasses import dataclass

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.output import DummyOutput

from memcommit.commands.ground_shell import (
    GROUND_GOAL_FRAME_HEIGHT,
    GroundShellContextSuggestion,
    GroundShellProposal,
    _anchored_conversation_fragments,
    format_proposal_command,
    render_ground_cases_pane,
    render_ground_contexts_pane,
    render_ground_goal_pane,
    render_ground_rules_pane,
    render_ground_top_panel,
    render_proposal_review,
    run_ground_shell,
)


@dataclass(frozen=True)
class Ask:
    kind: str
    understanding: str
    question: str


@dataclass(frozen=True)
class Propose:
    kind: str
    understanding: str
    question: str
    ground_name: str
    goal: str
    command: str = "rm -rf ignored-raw-command"
    context_suggestions: tuple[GroundShellContextSuggestion, ...] = ()


def proposal(text: str = "Compare report coverage.") -> Propose:
    return Propose(
        kind="PROPOSE",
        understanding=f"Understood: {text}",
        question="Approve this initial Ground?",
        ground_name="task-1-report-coverage",
        goal="Find what was reported and what remains unclear.",
    )


def test_fixed_top_panel_and_effect_review_show_all_boundaries():
    frozen = GroundShellProposal(
        ground_name="task-1-report-coverage",
        goal="Find what was reported.",
        understanding="Review coverage.",
        question="Approve?",
    )

    blank = render_ground_top_panel()
    proposed = render_ground_top_panel(frozen)
    review = render_proposal_review(frozen)

    assert blank.startswith("MEM GROUND · WORKING · NOT SAVED")
    assert "GOAL\n  (not yet stated)" in blank
    assert "COMPLETION" not in blank
    assert "CONTEXTS\n  (no ordinary Context locators found)" in blank
    assert "RULES\n  (none yet)" in blank
    assert "CASES\n  (none yet)" in blank
    assert "Find what was reported." in proposed
    assert "COMPLETION" not in proposed
    assert "PROPOSED COMMAND · NOT RUN" in review
    assert "Ground: CREATE task-1-report-coverage" in review
    assert "Goal: SET" in review
    assert "Rules: unchanged (none)" in review
    assert "Cases: unchanged (none)" in review
    assert "Contexts: unchanged" in review
    assert "Memories: unchanged" in review
    assert "Checkpoints: unchanged" in review


def test_blank_ground_layers_render_as_complete_independent_components():
    frozen = GroundShellProposal(
        ground_name="task-1-report-coverage",
        goal="Find what was reported.",
        understanding="Review coverage.",
        question="Approve?",
    )

    assert render_ground_goal_pane() == "(not yet stated)"
    assert render_ground_goal_pane(
        working_goal="Split Task 1 into audience-facing fixtures."
    ) == "Split Task 1 into audience-facing fixtures."
    assert render_ground_goal_pane(frozen) == (
        "PROPOSED\nFind what was reported."
    )
    proposed_from_request = render_ground_goal_pane(
        frozen,
        working_goal="Check the report.",
    )
    assert "PROPOSED" in proposed_from_request
    assert "STARTING REQUEST\nCheck the report." in proposed_from_request
    assert "Rules can be proposed after" in render_ground_rules_pane()
    assert "Cases can be added after" in render_ground_cases_pane()
    contexts = render_ground_contexts_pane()
    assert "(no ordinary Context locators found)" in contexts
    assert "current Context was assumed or opened" in contexts
    suggested = render_ground_contexts_pane(
        (
            GroundShellContextSuggestion(
                context_name="temp/task-1",
                role="LIKELY_SOURCE",
                reason="The name matches Task 1.",
            ),
        ),
        catalog_count=4,
        discovery_complete=True,
    )
    assert "SUGGESTED · NOT BOUND" in suggested
    assert "1 of 4 ordinary Context locators" in suggested
    assert "SOURCE?  temp/task-1" in suggested
    assert "no Memory content was read" in suggested
    assert GROUND_GOAL_FRAME_HEIGHT.preferred == 5
    assert GROUND_GOAL_FRAME_HEIGHT.max == 5


def test_approval_viewport_anchor_tracks_end_of_exact_proposed_command():
    command_block = (
        "PROPOSED COMMAND · NOT RUN\n  mem ground report-review"
    )
    fragments = _anchored_conversation_fragments(
        [
            "OLDER DIALOGUE\n  enough text to require scrolling",
            command_block,
            "EFFECTS · ONE COMMAND\n  Ground: CREATE report-review",
        ],
        anchor_index=1,
        anchor_at_end=True,
    )
    content = FormattedTextControl(fragments).create_content(
        width=80,
        height=10,
    )
    cursor_line = "".join(
        text for _style, text in content.get_line(content.cursor_position.y)
    )

    assert cursor_line == "  mem ground report-review"
    assert content.cursor_position.x == len("  mem ground report-review")


def test_ask_loops_to_another_input_without_applying():
    seen: list[str] = []
    applied: list[GroundShellProposal] = []

    def interpret(text: str):
        seen.append(text)
        if len(seen) == 1:
            return Ask(
                kind="ASK",
                understanding="You want to inspect a report.",
                question="Which report should define the source?",
            )
        return proposal(text)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("See what was reported.\rTask 1 notes.\rq")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        "See what was reported.",
        (
            "USER TURN 1\nSee what was reported.\n\n"
            "USER TURN 2\nTask 1 notes."
        ),
    ]
    assert applied == []
    assert result.status == "CANCELLED"
    assert result.submitted_turns == (
        "See what was reported.",
        "Task 1 notes.",
    )


def test_approval_applies_the_frozen_proposal_exactly_once():
    applied: list[GroundShellProposal] = []

    def apply(value: GroundShellProposal) -> str:
        applied.append(value)
        return "Grounding session created."

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Review the Task 1 report.\ra")
        result = run_ground_shell(
            interpret=proposal,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert len(applied) == 1
    assert applied[0] == result.proposal
    assert result.actual_output == "Grounding session created."
    # The provider's raw ``command`` field never reaches the frozen proposal.
    assert not hasattr(applied[0], "command")


def test_approval_is_modal_and_tab_cannot_detach_exact_apply():
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Review the Task 1 report.\r\ta")
        result = run_ground_shell(
            interpret=proposal,
            apply=lambda value: applied.append(value) or "created",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]


def test_tab_cycles_five_read_only_components_without_submitting():
    interpreted: list[str] = []
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        # MESSAGE → GOAL → CONTEXTS → RULES → CASES → DIALOGUE.
        pipe_input.send_text("\t\t\t\t\t\r\x03")
        result = run_ground_shell(
            interpret=lambda text: interpreted.append(text),
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert interpreted == []
    assert applied == []


def test_starting_request_is_already_submitted_before_tui_input():
    seen: list[str] = []

    def interpret(text: str):
        seen.append(text)
        return proposal(text)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request=(
                "Split Task 1 into wiki and user-facing Contexts."
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        "Split Task 1 into wiki and user-facing Contexts."
    ]
    assert result.status == "CANCELLED"
    assert result.submitted_turns == tuple(seen)


def test_starting_request_escape_closes_after_one_read_only_agent_turn():
    seen: list[str] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_ground_shell(
            interpret=lambda text: seen.append(text),
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="A Working Goal that is not sent yet.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.submitted_turns == (
        "A Working Goal that is not sent yet.",
    )
    assert seen == ["A Working Goal that is not sent yet."]


def test_initial_agent_question_leaves_message_empty_for_user_turn_two():
    seen: list[str] = []

    def interpret(text: str):
        seen.append(text)
        if len(seen) == 1:
            return Ask(
                kind="ASK",
                understanding="You want to separate Task 1 outputs.",
                question="Should the wiki be a target or a reference?",
            )
        return proposal(text)

    with create_pipe_input() as pipe_input:
        # There is no Ctrl-U here: the follow-up starts in an empty composer.
        pipe_input.send_text("Use it as the target.\rq")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Split Task 1 into wiki and user-facing outputs.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        "Split Task 1 into wiki and user-facing outputs.",
        (
            "USER TURN 1\n"
            "Split Task 1 into wiki and user-facing outputs.\n\n"
            "USER TURN 2\nUse it as the target."
        ),
    ]
    assert result.submitted_turns == (
        "Split Task 1 into wiki and user-facing outputs.",
        "Use it as the target.",
    )


def test_refine_requires_a_new_proposal_and_approval():
    seen: list[str] = []
    applied: list[GroundShellProposal] = []

    def interpret(text: str):
        seen.append(text)
        return proposal(text)

    with create_pipe_input() as pipe_input:
        # E restores the previous response. Ctrl-U clears it for a replacement.
        pipe_input.send_text("First wording.\re\x15Better wording.\ra")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda value: applied.append(value) or "created",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        "First wording.",
        "USER TURN 1\nFirst wording.\n\nUSER TURN 2\nBetter wording.",
    ]
    assert len(applied) == 1
    assert result.status == "APPLIED"
    assert result.submitted_turns == (
        "First wording.",
        "Better wording.",
    )


@pytest.mark.parametrize("cancel_key", ["q", "\x03"])
def test_cancel_and_ctrl_c_never_apply(cancel_key: str):
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(f"Draft a Goal.\r{cancel_key}")
        result = run_ground_shell(
            interpret=proposal,
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert applied == []


def test_escape_cancels_with_unsent_text_in_the_message_box():
    interpreted: list[str] = []
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("an unfinished Ground description\x1b")
        result = run_ground_shell(
            interpret=lambda text: interpreted.append(text),
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.submitted_turns == ()
    assert interpreted == []
    assert applied == []


def test_interpreter_error_is_fail_closed_and_can_retry():
    calls = {"count": 0}
    applied: list[GroundShellProposal] = []

    def interpret(text: str):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("provider unavailable")
        return proposal(text)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Draft a Goal.\rrq")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert calls["count"] == 2
    assert applied == []
    assert result.status == "CANCELLED"


def test_failed_apply_is_not_retried_by_repeated_approval():
    apply_calls: list[GroundShellProposal] = []

    def fail(value: GroundShellProposal):
        apply_calls.append(value)
        raise RuntimeError("CLI failed")

    with create_pipe_input() as pipe_input:
        # The second A is inert after an execution attempt; Q then closes.
        pipe_input.send_text("Draft a Goal.\raaq")
        result = run_ground_shell(
            interpret=proposal,
            apply=fail,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert len(apply_calls) == 1


def test_ctrl_j_inserts_a_newline_instead_of_submitting():
    seen: list[str] = []

    def interpret(text: str):
        seen.append(text)
        return proposal(text)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("first line\nsecond line\rq")
        run_ground_shell(
            interpret=interpret,
            apply=lambda value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == ["first line\nsecond line"]


def test_exact_command_is_quoted_from_structured_fields_not_raw_command():
    frozen = GroundShellProposal(
        ground_name="report-review",
        goal="Find what's missing; echo unsafe",
        understanding="Review the report.",
        question="Approve?",
    )

    command = format_proposal_command(frozen)

    assert shlex.split(command) == [
        "mem",
        "ground",
        "report-review",
        "--goal",
        "Find what's missing; echo unsafe",
    ]
    assert command == shlex.join(shlex.split(command))


def test_malformed_proposal_never_reaches_apply():
    applied: list[GroundShellProposal] = []

    def raw_only(_text: str):
        return {
            "kind": "PROPOSE",
            "understanding": "Run a command.",
            "question": "Approve?",
            "command": "mem ground injected --goal unsafe",
        }

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Create it.\rq")
        result = run_ground_shell(
            interpret=raw_only,
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert applied == []


def test_overlong_goal_from_custom_interpreter_never_reaches_apply():
    applied: list[GroundShellProposal] = []
    overlong = Propose(
        kind="PROPOSE",
        understanding="The requested Goal is too broad.",
        question="Approve?",
        ground_name="too-broad",
        goal=" ".join(f"word{index}" for index in range(41)),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Create it.\rq")
        result = run_ground_shell(
            interpret=lambda _text: overlong,
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert applied == []


def test_non_tty_entry_has_a_clear_error():
    with pytest.raises(ValueError, match="requires a TTY"):
        run_ground_shell(
            interpret=proposal,
            apply=lambda value: "unused",
            require_tty=True,
        )
