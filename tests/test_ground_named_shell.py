from __future__ import annotations

from dataclasses import dataclass, replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

from memcommit.commands.exact_command_review import ExactCommandReview
from memcommit.commands.ground_named_shell import (
    GroundCommandProposal,
    _line,
    render_named_ground_top_panel,
    render_named_ground_proposal_blocks,
    run_named_ground_shell,
)
from memcommit.ground import GroundItem, create_ground_session


@dataclass(frozen=True)
class Ask:
    kind: str
    understanding: str
    question: str


def proposal(session, text, *, kind="PROPOSE_RULE"):
    return GroundCommandProposal(
        kind=kind,
        understanding=f"Understood: {text}",
        question="Approve this exact Ground command?",
        review=ExactCommandReview(
            argv=(
                "mem",
                "ground",
                session.contract_name,
                "--propose-rule",
                text,
                "--rationale",
                "User supplied this Rule.",
            ),
            effects=("Rules: ADD one PROPOSED Rule",),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest="test-digest",
    )


def session_with_rule_and_case():
    rule = GroundItem(
        uid="11111111-1111-4111-8111-111111111111",
        kind="RULE",
        content="Publish only source-supported facts.",
        expected="",
        rationale="Preserve traceability.",
        status="PROPOSED",
        origin="AGENT",
        iteration=1,
        related_uids=("22222222-2222-4222-8222-222222222222",),
        rule_provenance="DISTILLED_FROM_GOAL",
    )
    case = GroundItem(
        uid="22222222-2222-4222-8222-222222222222",
        kind="CASE",
        content="The rear entrance closes during construction.",
        expected="Publish the rear-entrance closure.",
        rationale="The source directly supports the expected statement.",
        status="PROPOSED",
        origin="AGENT",
        iteration=2,
        related_uids=(rule.uid,),
        case_role="FIT",
        disposition="INCLUDE",
    )
    return replace(
        create_ground_session(
            "fixture-ground",
            goal="Build one verified fixture.",
            completion_criterion="Every required target has reviewed support.",
        ),
        revision=2,
        items=(rule, case),
    )


def review_proposal(session, item, *, action, response=""):
    argv = [
        "mem",
        "ground",
        session.contract_name,
        "--decide",
        item.uid,
        "--action",
        action,
    ]
    if response:
        argv.extend(["--response", response])
    return GroundCommandProposal(
        kind="REVIEW_ITEM",
        understanding=f"Review {item.kind}.",
        question="Approve this exact review?",
        review=ExactCommandReview(
            argv=tuple(argv),
            effects=(
                f"Selected Rule/Case: {action}",
                "One review Decision: RECORD",
                "Other Goal–Rules–Cases items: unchanged",
            ),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest="test-digest",
    )


def test_named_top_panel_keeps_goal_rules_and_cases_visible():
    session = create_ground_session(
        "fixture-ground",
        goal="Build one verified fixture.",
        completion_criterion="Every required target has reviewed support.",
    )

    rendered = render_named_ground_top_panel(session)

    assert "MEM GROUND · fixture-ground · SAVED · UNBOUND · REV 0" in rendered
    assert "GOAL · completion:" in rendered
    assert "Build one verified fixture." in rendered
    assert "RULES 0 · 0 proposed\n  (none yet)" in rendered
    assert "CASES 0 · 0 proposed\n  (none yet)" in rendered
    assert len(rendered.splitlines()) == 7


def test_named_top_panel_truncates_korean_by_terminal_cell_width():
    rendered = _line("한" * 100, limit=21)

    assert rendered.endswith("…")
    assert get_cwidth(rendered) <= 21


def test_named_top_panel_exposes_stable_rule_and_case_aliases():
    rendered = render_named_ground_top_panel(session_with_rule_and_case())

    assert "RULES 1 · 1 proposed · ID r1" in rendered
    assert "r1 [PROPOSED] Publish only source-supported facts." in rendered
    assert "CASES 1 · 1 proposed · ID c1" in rendered
    assert (
        "c1 [PROPOSED] The rear entrance closes during construction."
        in rendered
    )


def test_review_effects_identify_item_and_explain_rule_acceptance():
    session = session_with_rule_and_case()
    rule = session.items[0]
    command, effects = render_named_ground_proposal_blocks(
        session,
        review_proposal(session, rule, action="ACCEPT"),
    )

    assert rule.uid in command
    assert (
        "Selected item: r1 · Rule · PROPOSED · "
        "Publish only source-supported facts."
    ) in effects
    assert "ACCEPT: mark r1 ACCEPTED; its content remains unchanged" in effects
    assert "One review Decision record: ADD" in effects
    assert "Selected Rule/Case:" not in effects


def test_review_effects_explain_case_refine_as_expected_only():
    session = session_with_rule_and_case()
    case = session.items[1]
    _command, effects = render_named_ground_proposal_blocks(
        session,
        review_proposal(
            session,
            case,
            action="REFINE",
            response="Keep the closure unresolved pending exact dates.",
        ),
    )

    assert "REFINE: replace c1 expected output" in effects
    assert "c1 remains PROPOSED" in effects
    assert (
        "its source, linked Rule, role, disposition, and targets remain "
        "unchanged"
    ) in effects


def test_case_proposal_effects_name_new_alias_rule_targets_and_expected():
    session = session_with_rule_and_case()
    rule = session.items[0]
    proposed = GroundCommandProposal(
        kind="PROPOSE_CASE",
        understanding="Add one boundary Case.",
        question="Approve this exact Case proposal?",
        review=ExactCommandReview(
            argv=(
                "mem",
                "ground",
                session.contract_name,
                "--propose-source",
                "33333333-3333-4333-8333-333333333333",
                "--fit-rule",
                rule.uid,
                "--propose-target",
                "wiki",
                "--expected",
                "Keep the candidate unresolved.",
                "--rationale",
                "It tests the Rule boundary.",
                "--case-role",
                "BOUNDARY",
                "--disposition",
                "UNRESOLVED",
            ),
            effects=("Cases: ADD one traceable PROPOSED Case",),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest="test-digest",
    )

    _command, effects = render_named_ground_proposal_blocks(
        session,
        proposed,
    )

    assert "New c2 · PROPOSED BOUNDARY/UNRESOLVED Case" in effects
    assert (
        "Linked Rule: r1 · Publish only source-supported facts." in effects
    )
    assert "Targets: wiki" in effects
    assert "Expected output: Keep the candidate unresolved." in effects


def test_ask_accumulates_only_the_current_unresolved_turn_cycle():
    session = create_ground_session("fixture-ground", goal="Build a fixture.")
    seen = []

    def interpret(current, text):
        seen.append((current.revision, text))
        if len(seen) == 1:
            return Ask(
                kind="ASK",
                understanding="You want to bind evidence.",
                question="Which raw Context should be used?",
            )
        return proposal(current, text, kind="BIND")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Bind my evidence.\rtemp/task-1\rq")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        (0, "USER TURN 1\nBind my evidence."),
        (
            0,
            "USER TURN 1\nBind my evidence.\n\n"
            "AGENT TURN 1\n"
            "UNDERSTANDING\nYou want to bind evidence.\n"
            "QUESTION\nWhich raw Context should be used?\n\n"
            "USER TURN 2\ntemp/task-1",
        ),
    ]
    assert result.applied_argvs == ()
    assert result.submitted_turns == (
        "Bind my evidence.",
        "temp/task-1",
    )


def test_two_separate_approvals_apply_two_commands_and_refresh_state():
    session = create_ground_session("fixture-ground", goal="Initial Goal.")
    seen = []
    applied = []

    def interpret(current, text):
        seen.append((current.revision, text))
        return proposal(current, text)

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return (
            replace(
                current,
                goal=f"Goal after command {len(applied)}.",
                revision=current.revision + 1,
            ),
            f"command {len(applied)} applied",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("first rule\rasecond rule\ra\x03")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        (0, "USER TURN 1\nfirst rule"),
        (1, "USER TURN 1\nsecond rule"),
    ]
    assert len(applied) == 2
    assert result.session.revision == 2
    assert result.session.goal == "Goal after command 2."
    assert result.applied_argvs == tuple(applied)


def test_failed_apply_cannot_repeat_the_same_approval():
    session = create_ground_session("fixture-ground")
    calls = []

    def fail(_current, frozen):
        calls.append(frozen.review.argv)
        raise RuntimeError("CLI failed")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("one rule\raaq")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text: proposal(current, text),
            apply=fail,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(calls) == 1
    assert result.session == session
    assert result.applied_argvs == ()


def test_named_shell_refreshes_saved_state_before_interpreting_a_turn():
    session = create_ground_session("fixture-ground", goal="Old Goal.")
    refreshed = replace(session, goal="Current Goal.", revision=1)
    seen = []

    def interpret(current, text):
        seen.append((current, text))
        return Ask(
            kind="ASK",
            understanding="The current Goal is loaded.",
            question="What should change next?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("continue\r\x03")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            reload_session=lambda _name: refreshed,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [(refreshed, "USER TURN 1\ncontinue")]
    assert result.session == refreshed


def test_named_shell_refreshes_after_an_unconfirmed_apply():
    session = create_ground_session("fixture-ground", goal="Old Goal.")
    refreshed = replace(session, goal="Concurrent Goal.", revision=1)
    reloads = iter((session, refreshed))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("one rule\raq")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text: proposal(current, text),
            apply=lambda *_args: (_ for _ in ()).throw(
                RuntimeError("CLI outcome unavailable")
            ),
            reload_session=lambda _name: next(reloads),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.session == refreshed
    assert result.applied_argvs == ()


def test_retry_preserves_the_user_turn_when_refresh_clears_old_dialogue():
    session = create_ground_session("fixture-ground", goal="Old Goal.")
    refreshed = replace(session, goal="Current Goal.", revision=1)
    reloads = iter((session, refreshed))
    seen = []

    def interpret(current, text):
        seen.append((current, text))
        if len(seen) == 1:
            raise RuntimeError("temporary provider error")
        return Ask(
            kind="ASK",
            understanding="The refreshed Ground is loaded.",
            question="Continue?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("same user turn\rr\x03")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            reload_session=lambda _name: next(reloads),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert seen == [
        (session, "USER TURN 1\nsame user turn"),
        (refreshed, "USER TURN 1\nsame user turn"),
    ]
    assert result.submitted_turns == ("same user turn",)


def test_non_tty_named_shell_has_a_clear_error():
    with pytest.raises(ValueError, match="requires a TTY"):
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
        )
