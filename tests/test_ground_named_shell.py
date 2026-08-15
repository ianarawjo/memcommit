from __future__ import annotations

from dataclasses import dataclass, replace
import threading
import time

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

import memcommit.commands.ground_named_shell as ground_named_shell_module
from memcommit.commands.exact_command_review import ExactCommandReview
from memcommit.commands.ground_named_shell import (
    GroundCommandProposal,
    _line,
    render_named_ground_cases_pane,
    render_named_ground_contexts_pane,
    render_named_ground_goal_pane,
    render_named_ground_header,
    render_named_ground_top_panel,
    render_named_ground_proposal_blocks,
    render_named_ground_rules_pane,
    run_named_ground_shell,
)
from memcommit.ground import (
    GROUND_SCHEMA_VERSION,
    GroundFrame,
    GroundItem,
    create_ground_session,
)
from memcommit.ground_turn_dialogue import (
    GroundTurnDraft,
    GroundTurnDraftBatch,
)
from memcommit.fit import FitExample, FitJudgment, FitReport, FitRule
from memcommit.fit_store import GroundFitReceipt


class SizedDummyOutput(DummyOutput):
    def __init__(self, *, rows: int, columns: int) -> None:
        super().__init__()
        self._size = Size(rows=rows, columns=columns)

    def get_size(self) -> Size:
        return self._size


@dataclass(frozen=True)
class Ask:
    kind: str
    understanding: str
    question: str


def draft_batch(
    *drafts: GroundTurnDraft,
    raw_source: str = "The submitted comment.",
) -> GroundTurnDraftBatch:
    return GroundTurnDraftBatch(
        understanding="The comment contains independently reviewable units.",
        question="Review the classified drafts.",
        drafts=drafts,
        raw_source=raw_source,
    )


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


def fit_receipt_for(
    session,
    *,
    status="FIT",
    current=True,
) -> GroundFitReceipt:
    rule = session.items_of_kind("RULE")[0]
    case = session.items_of_kind("CASE")[0]
    fit_rule = FitRule(rule.uid, "r1", rule.content)
    example = FitExample(
        case.uid,
        "e1",
        f"{case.content} -> {case.expected}",
        "EXACT_OUTPUT",
        (rule.uid,),
        input_text=case.content,
        expected_output=case.expected,
    )
    report = FitReport(
        uid="55555555-5555-4555-8555-555555555555",
        ground_uid=session.uid,
        ground_name=session.contract_name,
        ground_revision=session.revision,
        ground_digest="a" * 64,
        rules=(fit_rule,),
        examples=(example,),
        judgments=(
            FitJudgment(
                example_uid=case.uid,
                status=status,
                rule_uids=(rule.uid,),
                reason="The Rule reproduces the reviewed expected result.",
                observed=case.expected if status == "FIT" else "different",
            ),
        ),
        overview="The fitted Example is exhaustively accounted for.",
        created_at="2026-08-15T12:00:00Z",
    )
    return GroundFitReceipt(report=report, current=current)


def session_with_two_cases():
    session = session_with_rule_and_case()
    rule, first = session.items
    second = replace(
        first,
        uid="33333333-3333-4333-8333-333333333333",
        content="The east elevator remains in service.",
        expected="Publish the continued elevator service.",
        rationale="Preserve the operating exception.",
    )
    return replace(
        session,
        items=(
            replace(rule, related_uids=(first.uid, second.uid)),
            first,
            second,
        ),
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
                f"Selected Rule/Ground Memory: {action}",
                "One review Decision: RECORD",
                "Other Goal–Rules–Memories items: unchanged",
            ),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest="test-digest",
    )


def test_named_goal_inline_direct_edit_freezes_one_command_before_apply():
    session = replace(
        create_ground_session(
            "fixture-ground",
            goal="Build one verified fixture.",
        ),
        schema_version=GROUND_SCHEMA_VERSION,
    )
    prepared = []
    interpreted = []
    applied = []

    def prepare(current, target, selector, edited, comment):
        prepared.append((target, selector, edited, comment))
        return proposal(current, edited, kind="REVISE_GOAL")

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return (
            replace(
                current,
                goal="Build one verified fixture. Revised.",
                revision=current.revision + 1,
            ),
            "revised",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\te Revised.\ra\x03")
        result = run_named_ground_shell(
            session,
            interpret=lambda *args: interpreted.append(args),
            prepare_direct_edit=prepare,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared == [
        (
            "GOAL",
            "",
            "Build one verified fixture. Revised.",
            "",
        )
    ]
    assert interpreted == []
    assert len(applied) == 1
    assert result.session.goal == "Build one verified fixture. Revised."
    assert len(result.applied_argvs) == 1


def test_applied_goal_change_marks_goal_and_chat_as_unseen(monkeypatch):
    session = replace(
        create_ground_session(
            "fixture-ground",
            goal="Build one verified fixture.",
        ),
        schema_version=GROUND_SCHEMA_VERSION,
    )
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    notifications = {}

    def capturing_pane(title, *args, **kwargs):
        notifications[title] = kwargs.get("notification")
        return original_pane_builder(title, *args, **kwargs)

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )

    def prepare(current, _target, _selector, edited, _comment):
        return proposal(current, edited, kind="REVISE_GOAL")

    def apply(current, _frozen):
        return (
            replace(
                current,
                goal="Build one verified fixture. Revised.",
                revision=current.revision + 1,
            ),
            "revised",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\te Revised.\ra\x03")
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            prepare_direct_edit=prepare,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.session.goal == "Build one verified fixture. Revised."
    assert notifications["GOAL"]()
    assert notifications["CHAT"]()
    assert not notifications["CONTEXTS"]()
    assert not notifications["RULES"]()
    assert not notifications["MEMORIES"]()


def test_named_goal_inline_comment_is_a_focused_agent_turn_not_an_edit():
    seen = []
    prepared = []

    def interpret(current, dialogue_text, source_text):
        seen.append((current, dialogue_text, source_text))
        return Ask(
            kind="ASK",
            understanding="The comment concerns the Goal.",
            question="What exact outcome should be retained?",
        )

    with create_pipe_input() as pipe_input:
        # An unbound saved scaffold opens the same pane-local surface with
        # Direct locked and Comment focused first.
        pipe_input.send_text("\t\rExplain the audience.\r\x1b")
        result = run_named_ground_shell(
            create_ground_session(
                "fixture-ground",
                goal="Build one verified fixture.",
            ),
            interpret=interpret,
            prepare_direct_edit=lambda *args: prepared.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(seen) == 1
    _session, dialogue_text, source_text = seen[0]
    assert "FOCUS · GOAL" in dialogue_text
    assert source_text == "Explain the audience."
    assert prepared == []
    assert result.applied_argvs == ()


def test_named_context_focused_comment_can_prepare_goal_proposal_without_apply():
    session = replace(
        session_with_rule_and_case(),
        schema_version=GROUND_SCHEMA_VERSION,
    )
    comment = "Use the Context discussion to narrow the overall Goal."
    seen = []
    prepared = []
    applied = []

    def interpret(current, dialogue_text, source_text):
        seen.append((current, dialogue_text, source_text))
        frozen = GroundCommandProposal(
            kind="REVISE_GOAL",
            understanding="The Context comment changes the Goal boundary.",
            question="Approve this exact Goal revision?",
            review=ExactCommandReview(
                argv=(
                    "mem",
                    "ground",
                    current.contract_name,
                    "--revise-goal",
                    "Build one Context-aligned fixture.",
                ),
                effects=("Goal: REVISE",),
            ),
            expected_ground_uid=current.uid,
            expected_revision=current.revision,
            expected_state_digest="test-digest",
        )
        prepared.append(frozen)
        return frozen

    with create_pipe_input() as pipe_input:
        # MESSAGE -> GOAL -> CONTEXTS. C opens a Context-focused semantic
        # comment; Escape closes the still-unapproved cross-layer proposal.
        pipe_input.send_text(f"\t\tc{comment}\r\x1b")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=lambda *_args: applied.append(_args),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(seen) == 1
    _current, dialogue_text, source_text = seen[0]
    assert "FOCUS · CONTEXTS" in dialogue_text
    assert source_text == comment
    assert len(prepared) == 1
    assert prepared[0].kind == "REVISE_GOAL"
    assert "--revise-goal" in prepared[0].review.argv
    assert applied == []
    assert result.applied_argvs == ()


def test_named_focused_comment_escape_collapses_before_second_escape_closes():
    interpreted = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\tcunsent context comment\x1b\x1b")
        result = run_named_ground_shell(
            create_ground_session(
                "fixture-ground",
                goal="Build one verified fixture.",
            ),
            interpret=lambda *args: interpreted.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert interpreted == []
    assert result.applied_argvs == ()


@pytest.mark.parametrize(
    ("tabs", "focus"),
    [
        (1, "GOAL"),
        (2, "CONTEXTS"),
        (3, "RULE r1"),
        (4, "MEMORY c1"),
    ],
)
def test_named_enter_opens_conversation_inside_each_semantic_pane(
    tabs,
    focus,
):
    seen = []
    comment = f"Discuss {focus.lower()} here."

    def interpret(current, dialogue_text, source_text):
        seen.append((current, dialogue_text, source_text))
        return Ask(
            kind="ASK",
            understanding="The focused pane comment was received.",
            question="What should happen next?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(("\t" * tabs) + f"\r{comment}\r\x1b")
        result = run_named_ground_shell(
            session_with_rule_and_case(),
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(seen) == 1
    _current, dialogue_text, source_text = seen[0]
    assert f"FOCUS · {focus}" in dialogue_text
    assert source_text == comment
    assert result.applied_argvs == ()


@pytest.mark.parametrize(
    ("tabs", "target", "selector", "suffix"),
    [
        (3, "RULE", "r1", " Revised."),
        (4, "MEMORY", "c1", " Clarified."),
    ],
)
def test_named_rule_and_memory_edit_only_one_selected_item(
    tabs,
    target,
    selector,
    suffix,
):
    session = replace(
        session_with_rule_and_case(),
        schema_version=GROUND_SCHEMA_VERSION,
    )
    prepared = []

    def prepare(current, actual_target, actual_selector, edited, comment):
        prepared.append(
            (actual_target, actual_selector, edited, comment)
        )
        return proposal(current, edited, kind="REVIEW_ITEM")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(("\t" * tabs) + "e" + suffix + "\rq")
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            prepare_direct_edit=prepare,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(prepared) == 1
    actual_target, actual_selector, edited, comment = prepared[0]
    assert (actual_target, actual_selector, comment) == (
        target,
        selector,
        "",
    )
    original = (
        session.items[0].content
        if target == "RULE"
        else session.items[1].expected
    )
    assert edited == original + suffix
    assert result.applied_argvs == ()


@pytest.mark.parametrize(
    ("target", "kind", "tabs", "pane_title", "alias"),
    [
        ("RULE", "RULE", 3, "RULES", "r11"),
        ("MEMORY", "CASE", 4, "MEMORIES", "c11"),
    ],
)
def test_saved_item_selection_scrolls_marker_before_editing(
    monkeypatch,
    target,
    kind,
    tabs,
    pane_title,
    alias,
):
    base = session_with_rule_and_case()
    rule, memory = base.items
    if kind == "RULE":
        items = tuple(
            replace(
                rule,
                uid=f"{number:08d}-1111-4111-8111-111111111111",
                content=f"Saved Rule {number}.",
                related_uids=(),
            )
            for number in range(1, 16)
        )
    else:
        items = (
            rule,
            *tuple(
                replace(
                    memory,
                    uid=f"{number:08d}-2222-4222-8222-222222222222",
                    content=f"Source Memory {number}.",
                    expected=f"Expected output {number}.",
                    related_uids=(rule.uid,),
                )
                for number in range(1, 16)
            ),
        )
    session = replace(
        base,
        schema_version=GROUND_SCHEMA_VERSION,
        items=items,
    )
    original_builder = ground_named_shell_module.build_scrollable_text_pane
    panes = {}
    prepared = []
    visible_scroll = []
    feeder_errors = []

    def capture_pane(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def prepare(current, actual_target, selector, edited, comment):
        prepared.append((actual_target, selector, edited, comment))
        return proposal(current, edited, kind="REVIEW_ITEM")

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capture_pane,
    )
    with create_pipe_input() as pipe_input:
        def select_then_edit() -> None:
            try:
                pipe_input.send_text(
                    ("\t" * tabs) + ("\x1b[B" * 10)
                )
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    pane = panes.get(pane_title)
                    if (
                        pane is not None
                        and pane.text_area.window.render_info is not None
                        and pane.text_area.buffer.document.cursor_position_row
                        > 0
                        and pane.text_area.window.vertical_scroll > 0
                    ):
                        visible_scroll.append(
                            pane.text_area.window.vertical_scroll
                        )
                        pipe_input.send_text("e revised\rq")
                        return
                    time.sleep(0.01)
                raise AssertionError("selected marker never became visible")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                pipe_input.send_text("\x03")

        feeder = threading.Thread(target=select_then_edit)
        feeder.start()
        run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            prepare_direct_edit=prepare,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=40),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert prepared and prepared[0][0:2] == (target, alias)
    pane = panes[pane_title].text_area
    assert pane.buffer.document.cursor_position_row > 0
    assert visible_scroll and visible_scroll[0] > 0


def test_named_inline_escape_collapses_before_second_escape_closes():
    prepared = []
    interpreted = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\teunsubmitted\x1b\x1b")
        result = run_named_ground_shell(
            create_ground_session(
                "fixture-ground",
                goal="Build one fixture.",
            ),
            interpret=lambda *args: interpreted.append(args),
            prepare_direct_edit=lambda *args: prepared.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared == []
    assert interpreted == []
    assert result.applied_argvs == ()


def test_refining_direct_edit_reopens_exact_fields_and_stales_old_drafts():
    session = replace(
        create_ground_session(
            "fixture-ground",
            goal="Build one fixture.",
        ),
        schema_version=GROUND_SCHEMA_VERSION,
    )
    draft = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep all fixture areas separate.",
        classification_reason="This is an independently reviewable Rule.",
        source_spans=("Keep the areas separate.",),
        proposal_rationale="The user stated this boundary.",
        rule_provenance="USER_STATED",
    )
    direct_prepared = []
    draft_prepared = []

    def prepare_direct(current, target, selector, edited, comment):
        direct_prepared.append((target, selector, edited, comment))
        return proposal(current, edited, kind="REVISE_GOAL")

    with create_pipe_input() as pipe_input:
        def drive_refinement() -> None:
            pipe_input.send_text(
                "classify this\r"
                "\x1b[Z\x1b[Z"
                "e Revised.\r"
                "e\r"
                "e"
            )
            # A literal Escape must be distinguishable from the following
            # Tab sequence; this mirrors a person releasing the key.
            time.sleep(0.1)
            pipe_input.send_text("\x1b")
            time.sleep(0.1)
            pipe_input.send_text("\t\tr")
            time.sleep(0.1)
            pipe_input.send_text("\x1b")

        feeder = threading.Thread(target=drive_refinement)
        feeder.start()
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: draft_batch(
                draft,
                raw_source="classify this",
            ),
            prepare_rule_draft=lambda *args: draft_prepared.append(args),
            prepare_direct_edit=prepare_direct,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert not feeder.is_alive()
    assert direct_prepared == [
        ("GOAL", "", "Build one fixture. Revised.", ""),
        ("GOAL", "", "Build one fixture. Revised.", ""),
    ]
    assert draft_prepared == []
    assert result.applied_argvs == ()


def test_named_inline_editor_keeps_all_panes_visible_at_24_rows(
    monkeypatch,
):
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    original_message_builder = (
        ground_named_shell_module.build_framed_multiline_input
    )
    original_edit_builder = (
        ground_named_shell_module.build_inline_direct_edit_input
    )
    panes = {}
    composers = []
    editors = []
    observed = []
    feeder_errors = []

    def capture_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def capture_message(title, *args, **kwargs):
        value = original_message_builder(title, *args, **kwargs)
        composers.append(value)
        return value

    def capture_editor(*args, **kwargs):
        value = original_edit_builder(*args, **kwargs)
        editors.append(value)
        return value

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capture_pane,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_framed_multiline_input",
        capture_message,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_inline_direct_edit_input",
        capture_editor,
    )

    with create_pipe_input() as pipe_input:
        def inspect_expanded_layout() -> None:
            try:
                pipe_input.send_text("\te")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if panes and composers and editors:
                        infos = [
                            pane.text_area.window.render_info
                            for pane in panes.values()
                        ]
                        edit_info = editors[0].text_area.window.render_info
                        comment_info = composers[0].text_area.window.render_info
                        if (
                            all(info is not None for info in infos)
                            and edit_info is not None
                            and comment_info is not None
                            and composers[0].frame.title
                            == "COMMENT (FOR THE AGENT)"
                        ):
                            observed.append(
                                (
                                    [info.window_height for info in infos],
                                    edit_info.window_height,
                                    comment_info.window_height,
                                    editors[0].frame.title,
                                    composers[0].frame.title,
                                )
                            )
                            pipe_input.send_text("\x1b\x1b")
                            return
                    time.sleep(0.01)
                raise AssertionError("expanded Goal editor was not rendered")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                pipe_input.send_text("\x03")

        feeder = threading.Thread(target=inspect_expanded_layout)
        feeder.start()
        run_named_ground_shell(
            create_ground_session(
                "fixture-ground",
                goal="Build one fixture.",
            ),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert len(observed) == 1
    pane_heights, edit_height, comment_height, edit_title, comment_title = (
        observed[0]
    )
    assert all(height >= 1 for height in pane_heights)
    assert edit_height >= 1
    assert comment_height >= 1
    assert edit_title == "EDIT (DIRECTLY)"
    assert comment_title == "COMMENT (FOR THE AGENT)"


def test_named_top_panel_keeps_goal_rules_and_memories_visible():
    session = create_ground_session(
        "fixture-ground",
        goal="Build one verified fixture.",
        completion_criterion="Every required target has reviewed support.",
    )

    rendered = render_named_ground_top_panel(session)

    assert (
        "MEM GROUND · fixture-ground · WORKING · SAVED · UNBOUND · REV 0"
        in rendered
    )
    assert "\nGOAL\n  Build one verified fixture." in rendered
    assert "Every required target has reviewed support." not in rendered
    assert "Build one verified fixture." in rendered
    assert "RULES 0 · 0 proposed\n  (none yet)" in rendered
    assert "MEMORIES 0 · 0 proposed\n  (none yet)" in rendered
    assert len(rendered.splitlines()) == 7


def test_named_top_panel_truncates_korean_by_terminal_cell_width():
    rendered = _line("한" * 100, limit=21)

    assert rendered.endswith("…")
    assert get_cwidth(rendered) <= 21


def test_named_top_panel_exposes_stable_rule_and_memory_aliases():
    rendered = render_named_ground_top_panel(session_with_rule_and_case())

    assert "RULES 1 · 1 proposed · ID r1" in rendered
    assert "r1 [PROPOSED] Publish only source-supported facts." in rendered
    assert "MEMORIES 1 · 1 proposed · ID c1" in rendered
    assert (
        "c1 [PROPOSED] The rear entrance closes during construction."
        in rendered
    )


def test_named_ground_components_render_all_items_without_summary_truncation():
    original = session_with_rule_and_case()
    first_rule, first_case = original.items
    second_rule = replace(
        first_rule,
        uid="33333333-3333-4333-8333-333333333333",
        content="Preserve exceptions and continued service.",
        rationale="Otherwise the fixture overstates closures.",
    )
    second_case = replace(
        first_case,
        uid="44444444-4444-4444-8444-444444444444",
        content="The east elevator remains in service.",
        expected="Publish the continued elevator service.",
        related_uids=(second_rule.uid,),
    )
    session = replace(
        original,
        items=(first_rule, first_case, second_rule, second_case),
    )

    assert "MEM GROUND · fixture-ground" in render_named_ground_header(session)
    assert render_named_ground_goal_pane(session) == (
        "Build one verified fixture."
    )
    assert (
        "Every required target has reviewed support."
        not in render_named_ground_goal_pane(session)
    )
    rules = render_named_ground_rules_pane(session)
    cases = render_named_ground_cases_pane(session)
    assert "r1 [PROPOSED]" in rules
    assert "r2 [PROPOSED]" in rules
    assert "Preserve exceptions and continued service." in rules
    assert "Otherwise the fixture overstates closures." in rules
    assert "c1 [PROPOSED · FIT / INCLUDE]" in cases
    assert "c2 [PROPOSED · FIT / INCLUDE]" in cases
    assert (
        "The east elevator remains in service. → "
        "Publish the continued elevator service."
    ) in cases
    assert "NOTES · The source directly supports" in cases
    assert "LINKED RULES" not in cases

    selected = ground_named_shell_module.render_named_ground_memories_pane(
        session,
        selected_memory_index=1,
    )
    assert "› c2 [PROPOSED · FIT / INCLUDE]" in selected
    assert "DETAILS\nLINKED RULES · r2" in selected


def test_ground_memory_renders_as_multiline_case_with_non_output_notes():
    original = session_with_rule_and_case()
    rule, memory = original.items
    ticker_case = replace(
        memory,
        content="North Star Energy Inc.\nClass B",
        expected="NSE.B",
        rationale=(
            "Ignore the legal suffix and append .B for the share class."
        ),
    )

    rendered = render_named_ground_cases_pane(
        replace(original, items=(rule, ticker_case))
    )

    assert "c1 [PROPOSED · FIT / INCLUDE]" in rendered
    assert (
        "North Star Energy Inc. ↵ Class B → NSE.B\n"
        "NOTES · Ignore the legal suffix and append .B for the share "
        "class."
        in rendered
    )
    assert rendered.count("\n") == 2
    assert "EXPECTED" not in rendered
    assert "WHY" not in rendered


def test_ground_memory_projects_current_and_stale_fit_receipts() -> None:
    session = session_with_rule_and_case()
    current = ground_named_shell_module.render_named_ground_memories_pane(
        session,
        selected_memory_index=0,
        fit_receipt=fit_receipt_for(session),
    )
    stale = ground_named_shell_module.render_named_ground_memories_pane(
        session,
        selected_memory_index=0,
        fit_receipt=fit_receipt_for(session, current=False),
    )

    assert "c1 [PROPOSED · FIT / INCLUDE · FIT FIT]" in current
    assert "FIT RECEIPT · CURRENT · 55555555" in current
    assert "FIT RULES · r1" in current
    assert "FIT WHY · The Rule reproduces" in current
    assert "FIT STALE · FIT" in stale
    assert "FIT RECEIPT · STALE · 55555555" in stale


def test_named_ground_runs_fit_from_cases_without_shelling_out(monkeypatch) -> None:
    session = session_with_rule_and_case()
    receipt = fit_receipt_for(session)
    latest = {"value": None}
    ran = []
    completed = threading.Event()
    panes = {}
    original_builder = ground_named_shell_module.build_scrollable_text_pane

    def capture_pane(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def run_fit(active):
        ran.append(active.revision)
        latest["value"] = receipt
        completed.set()
        return receipt.report

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capture_pane,
    )
    with create_pipe_input() as pipe_input:
        def drive() -> None:
            pipe_input.send_text("\t\t\t\tf")
            assert completed.wait(timeout=2)
            time.sleep(0.05)
            pipe_input.send_text("q")

        feeder = threading.Thread(target=drive)
        feeder.start()
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            run_fit=run_fit,
            lookup_fit=lambda _active: latest["value"],
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert result.status == "CLOSED"
    assert ran == [session.revision]
    assert "FIT FIT" in panes["MEMORIES"].text_area.text


def test_named_ground_memory_table_exposes_fields_as_cells():
    rendered = ground_named_shell_module.render_named_ground_memories_pane(
        session_with_two_cases(),
        view="TABLE",
        selected_memory_index=1,
        selected_memory_column=5,
    )

    assert "TABLE · 2 MEMORIES · ROW 2/2 · COLUMN EXPECTED" in rendered
    assert "ID" in rendered
    assert "STATUS" in rendered
    assert "ROLE" in rendered
    assert "DECISION" in rendered
    assert "INPUT" in rendered
    assert "EXPECTED" in rendered
    assert "NOTES" in rendered
    assert "RULES" in rendered
    assert "SOURCES" in rendered
    assert "TARGETS" in rendered
    assert "CELL · c2 · EXPECTED" in rendered
    assert "Publishthecontinuedelevatorservice." in "".join(rendered.split())


def test_ground_memory_without_notes_keeps_the_three_line_card_shape():
    original = session_with_rule_and_case()
    rule, memory = original.items
    rendered = render_named_ground_cases_pane(
        replace(original, items=(rule, replace(memory, rationale="")))
    )

    assert "NOTES · (none)" in rendered
    assert rendered.count("\n") == 2


def test_saved_directional_provenance_is_presented_as_neutral_distillation():
    session = session_with_rule_and_case()
    rule, memory = session.items
    rendered = render_named_ground_rules_pane(
        replace(
            session,
            items=(
                replace(rule, rule_provenance="INDUCED_FROM_CASES"),
                memory,
            ),
        )
    )

    assert "DISTILLED" in rendered
    assert "INDUCED_FROM_CASES" not in rendered


def test_named_contexts_pane_distinguishes_unbound_and_recorded_frames():
    unbound = create_ground_session(
        "fixture-ground",
        goal="Build one verified fixture.",
    )
    assert render_named_ground_contexts_pane(unbound) == (
        "UNBOUND\n\n"
        "Name the raw evidence, working candidates,\n"
        "publication target, and placement targets.\n"
        "No current Context is inferred."
    )
    hinted = render_named_ground_contexts_pane(
        unbound,
        context_hints=("temp/task-1", "campus-wiki"),
        new_context_hint="test/ground/ticker-rule-examples",
    )
    assert "UNBOUND · LOCAL CONTEXT PLAN" in hinted
    assert "MAIN · temp/task-1 · NOT BOUND" in hinted
    assert "ADDITIONAL · campus-wiki · NOT BOUND" in hinted
    assert (
        "NEW CONTEXT · test/ground/ticker-rule-examples · "
        "LOCAL ONLY · NOT CREATED"
        in hinted
    )
    assert "separately reviewed commands" in hinted

    frames = (
        GroundFrame(
            role="RAW_EVIDENCE",
            context_uid="11111111-1111-4111-8111-111111111111",
            context_name="temp/task-1",
            context_digest="1" * 64,
            direct_memory_count=51,
            direct_item_count=51,
        ),
        GroundFrame(
            role="WORKING_CANDIDATES",
            context_uid="22222222-2222-4222-8222-222222222222",
            context_name="temp/task-1-atomized",
            context_digest="2" * 64,
            direct_memory_count=61,
            direct_item_count=62,
        ),
        GroundFrame(
            role="PUBLICATION_TARGET",
            context_uid="33333333-3333-4333-8333-333333333333",
            context_name="campus-wiki",
            context_digest="3" * 64,
            direct_memory_count=0,
            direct_item_count=0,
        ),
    )
    bound = replace(
        unbound,
        schema_version=GROUND_SCHEMA_VERSION,
        frames=frames,
    )

    rendered = render_named_ground_contexts_pane(
        bound,
        context_hints=("ignored-local-hint",),
        new_context_hint="ignored-new-context",
    )

    assert "RAW EVIDENCE\ntemp/task-1 · 51 direct Memories" in rendered
    assert (
        "WORKING CANDIDATES\n"
        "temp/task-1-atomized · 61 direct Memories · 62 direct items"
        in rendered
    )
    assert "PUBLICATION TARGET\ncampus-wiki" in rendered
    assert "freshness is rechecked before mutation" in rendered
    assert frames[0].context_uid not in rendered
    assert frames[0].context_digest not in rendered
    assert "ignored-local-hint" not in rendered
    assert "ignored-new-context" not in rendered


def test_process_local_context_hints_are_not_sent_to_named_interpreter():
    seen = []

    def interpret(session, dialogue_text, source_text):
        seen.append((session, dialogue_text, source_text))
        return Ask(
            kind="ASK",
            understanding="Continue refining the unbound Ground.",
            question="Which frame roles should be assigned?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Continue.\r\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            context_hints=("temp/task-1", "campus-wiki"),
            new_context_hint="test/ground/ticker-rule-examples",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(seen) == 1
    _session, dialogue_text, source_text = seen[0]
    assert source_text == "Continue."
    assert "temp/task-1" not in dialogue_text
    assert "campus-wiki" not in dialogue_text
    assert "test/ground/ticker-rule-examples" not in dialogue_text


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
    assert "Selected Rule/Ground Memory:" not in effects


def test_review_effects_explain_ground_memory_refine_as_expected_only():
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

    assert (
        "Selected item: c1 · Ground Memory · PROPOSED · "
        "The rear entrance closes during construction."
    ) in effects
    assert "· Case ·" not in effects
    assert "REFINE: replace c1 expected output" in effects
    assert "c1 remains PROPOSED" in effects
    assert (
        "its source, linked Rule, role, disposition, and targets remain "
        "unchanged"
    ) in effects


def test_ground_memory_proposal_effects_name_alias_rule_targets_and_expected():
    session = session_with_rule_and_case()
    rule = session.items[0]
    proposed = GroundCommandProposal(
        kind="PROPOSE_CASE",
        understanding="Add one boundary Ground Memory.",
        question="Approve this exact Ground Memory proposal?",
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
            effects=(
                "Ground Memories: ADD one traceable PROPOSED Ground Memory",
            ),
        ),
        expected_ground_uid=session.uid,
        expected_revision=session.revision,
        expected_state_digest="test-digest",
    )

    _command, effects = render_named_ground_proposal_blocks(
        session,
        proposed,
    )

    assert (
        "New c2 · PROPOSED BOUNDARY/UNRESOLVED Ground Memory"
        in effects
    )
    assert (
        "Linked Rule: r1 · Publish only source-supported facts." in effects
    )
    assert "Targets: wiki" in effects
    assert "Expected output: Keep the candidate unresolved." in effects
    assert (
        "Source: exact Context Memory selected from the bound candidate "
        "Context"
    ) in effects


def test_ask_accumulates_only_the_current_unresolved_turn_cycle():
    session = create_ground_session("fixture-ground", goal="Build a fixture.")
    seen = []
    sources = []

    def interpret(current, text, source_text):
        seen.append((current.revision, text))
        sources.append(source_text)
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
    assert sources == ["Bind my evidence.", "temp/task-1"]
    assert result.applied_argvs == ()
    assert result.submitted_turns == (
        "Bind my evidence.",
        "temp/task-1",
    )


def test_two_separate_approvals_apply_two_commands_and_refresh_state():
    session = create_ground_session("fixture-ground", goal="Initial Goal.")
    seen = []
    applied = []

    def interpret(current, text, _source_text):
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


def test_named_approval_is_modal_and_tab_cannot_detach_exact_apply():
    session = create_ground_session("fixture-ground")
    applied = []

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return replace(current, revision=1), "applied"

    with create_pipe_input() as pipe_input:
        # Approval starts on Dialogue. Tab reaches Goal, but Enter must remain
        # read-only and cannot replace the already frozen proposal.
        pipe_input.send_text("one rule\r\t\ra\x03")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text, _source: proposal(current, text),
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(applied) == 1
    assert result.applied_argvs == tuple(applied)


def test_modal_scrolled_dialogue_allows_tab_round_trip_before_same_approval(
    monkeypatch,
):
    original_builder = ground_named_shell_module.build_scrollable_text_pane
    panes = {}
    focused_at_apply = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    session = create_ground_session("fixture-ground")

    def apply(current, frozen):
        focused_at_apply.update(
            {
                title: "class:memcommit.focused" in pane.frame.container.style()
                for title, pane in panes.items()
            }
        )
        return replace(current, revision=1), "applied"

    with create_pipe_input() as pipe_input:
        # Approval starts on CHAT. Page it, visit GOAL, return, then apply.
        pipe_input.send_text(
            ("long requirement " * 80)
            + "\r"
            + "\x1b[6~"
            + "\t"
            + "\x1b[Z"
            + "a"
            + "\x03"
        )
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text, _source: proposal(current, text),
            apply=apply,
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=50),
            require_tty=False,
        )

    assert result.applied_argvs
    assert panes["CHAT"].text_area.buffer.cursor_position > 0
    assert focused_at_apply["CHAT"]
    assert sum(focused_at_apply.values()) == 1


def test_named_approval_down_arrow_stays_in_focused_memories(monkeypatch):
    original_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    session = session_with_rule_and_case()

    with create_pipe_input() as pipe_input:
        # The submitted turn enters APPROVAL on CHAT. Four Tabs reach
        # MEMORIES; Down must remain local to that focused read viewport.
        pipe_input.send_text("Propose another Rule.\r\t\t\t\t\x1b[B\x1b")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text, _source: proposal(current, text),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert (
        panes["MEMORIES"].text_area.buffer.document.cursor_position_row == 1
    )
    dialogue = panes["CHAT"].text_area.text
    assert "PROPOSED COMMAND · NOT RUN" in dialogue
    assert "EFFECTS · ONE COMMAND" not in dialogue


@pytest.mark.parametrize(
    ("key", "expected_status"),
    [("b", "BACK_TO_PICKER"), ("q", "CLOSED")],
)
def test_named_read_pane_backs_to_picker_or_quits_without_a_turn(
    key,
    expected_status,
):
    interpreted = []
    applied = []

    with create_pipe_input() as pipe_input:
        # The general Message composer keeps ordinary letters. One Tab enters
        # a collapsed read pane where B/Q become navigation commands.
        pipe_input.send_text(f"\t{key}")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *args: interpreted.append(args),
            apply=lambda *args: applied.append(args),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == expected_status
    assert interpreted == []
    assert applied == []


def test_named_back_discards_pending_receipt_without_applying_it():
    applied = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Propose one Rule.\rb")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda current, text, _source: proposal(current, text),
            apply=lambda *args: applied.append(args),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "BACK_TO_PICKER"
    assert result.applied_argvs == ()
    assert applied == []


def test_named_message_keeps_lowercase_b_and_q_as_user_text():
    seen = []

    def interpret(_current, _dialogue, source_text):
        seen.append(source_text)
        return Ask(
            kind="ASK",
            understanding="The letters are ordinary Message text.",
            question="Continue?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("bring back q safely\r\x03")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=interpret,
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    assert seen == ["bring back q safely"]


def test_named_focused_comment_key_is_disabled_during_approval():
    session = session_with_rule_and_case()
    interpreted = []
    applied = []

    def interpret(current, dialogue_text, source_text):
        interpreted.append((dialogue_text, source_text))
        return proposal(current, source_text)

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return current, "applied"

    with create_pipe_input() as pipe_input:
        # The first Enter opens exact approval on CHAT. C must not open a
        # comment editor or start a second provider turn; A applies the same
        # frozen receipt once.
        pipe_input.send_text("Propose one Rule.\rca\x03")
        result = run_named_ground_shell(
            session,
            interpret=interpret,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(interpreted) == 1
    assert len(applied) == 1
    assert result.applied_argvs == tuple(applied)


def test_named_memory_table_toggles_back_to_selected_list_card(monkeypatch):
    original_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\tv\x1b[B\x1b[Cv\x1b")
        result = run_named_ground_shell(
            session_with_two_cases(),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CLOSED"
    memories = panes["MEMORIES"].text_area
    assert "TABLE ·" not in memories.text
    assert "› c2 [PROPOSED · FIT / INCLUDE]" in memories.text
    assert memories.window.wrap_lines()


def test_named_approval_table_navigation_keeps_the_exact_receipt(monkeypatch):
    original_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    panes = {}
    applied = []

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )

    def apply(current, frozen):
        applied.append(frozen.review.argv)
        return current, "applied"

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "Propose another Rule.\r\t\t\t\tv\x1b[B\x1b[Ca\x03"
        )
        result = run_named_ground_shell(
            session_with_two_cases(),
            interpret=lambda current, text, _source: proposal(current, text),
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.applied_argvs == tuple(applied)
    assert len(applied) == 1
    memories = panes["MEMORIES"].text_area
    assert "TABLE · 2 MEMORIES · ROW 2/2 · COLUMN STATUS" in memories.text
    assert "CELL · c2 · STATUS" in memories.text
    assert not memories.window.wrap_lines()


def test_named_tab_cycles_five_components_without_starting_a_turn():
    session = create_ground_session("fixture-ground")
    interpreted = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\t\r\x03")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text, _source: interpreted.append(
                (current, text)
            ),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert interpreted == []
    assert result.applied_argvs == ()


def test_named_tab_focuses_and_page_scrolls_a_long_rules_component(
    monkeypatch,
):
    original_builder = ground_named_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    base = session_with_rule_and_case()
    first_rule = base.items[0]
    rules = tuple(
        replace(
            first_rule,
            uid=f"{number:08d}-1111-4111-8111-111111111111",
            content=f"Rule {number}: retain independently reviewable detail.",
            rationale=f"Rationale {number}: preserve the stated boundary.",
            related_uids=(),
        )
        for number in range(1, 21)
    )
    session = replace(base, items=rules)

    with create_pipe_input() as pipe_input:
        # MESSAGE → GOAL → CONTEXTS → RULES, then browse one real page.
        pipe_input.send_text("\t\t\t\x1b[6~\x1b")
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    rules_area = panes["RULES"].text_area
    assert result.applied_argvs == ()
    assert rules_area.buffer.document.cursor_position_row > 0
    assert panes["RULES"].frame.title == "RULES"
    assert callable(panes["RULES"].frame.container.style)
    assert (
        "class:memcommit.focused"
        in panes["RULES"].frame.container.style()
    )
    assert panes["GOAL"].frame.title == "GOAL"


def test_wrapped_goal_pages_visually_and_keeps_tab_navigation(
    monkeypatch,
):
    original_builder = ground_named_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    session = create_ground_session("fixture-ground", goal="가" * 500)

    with create_pipe_input() as pipe_input:
        # MESSAGE → GOAL → one visual page → CONTEXTS → GOAL.
        pipe_input.send_text("\t\x1b[6~\t\x1b[Z\x1b")
        run_named_ground_shell(
            session,
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )

    goal = panes["GOAL"].text_area
    assert goal.buffer.document.cursor_position_row == 0
    assert goal.buffer.cursor_position > 0
    assert goal.window.vertical_scroll_2 > 0
    assert (
        "class:memcommit.focused"
        in panes["GOAL"].frame.container.style()
    )


def test_wrapped_goal_page_up_returns_to_the_visual_start(monkeypatch):
    original_builder = ground_named_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\x1b[6~\x1b[5~\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground", goal="가" * 500),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )

    goal = panes["GOAL"].text_area
    assert goal.buffer.cursor_position == 0
    assert goal.window.vertical_scroll == 0
    assert goal.window.vertical_scroll_2 == 0


def test_named_ground_keeps_every_pane_and_message_body_visible_at_24_rows(
    monkeypatch,
):
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    original_input_builder = (
        ground_named_shell_module.build_framed_multiline_input
    )
    panes = {}
    composers = []

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def capturing_input(title, *args, **kwargs):
        composer = original_input_builder(title, *args, **kwargs)
        composers.append(composer)
        return composer

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_framed_multiline_input",
        capturing_input,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=100),
            require_tty=False,
        )

    assert set(panes) == {
        "GOAL",
        "CONTEXTS",
        "RULES",
        "MEMORIES",
        "CHAT",
    }
    assert all(
        pane.text_area.window.render_info is not None
        and pane.text_area.window.render_info.window_height >= 1
        for pane in panes.values()
    )
    assert len(composers) == 1
    message_info = composers[0].text_area.window.render_info
    assert message_info is not None
    assert message_info.window_height >= 1
    chat_body = panes["CHAT"].frame.body
    assert chat_body.children[0] is panes["CHAT"].text_area.window
    assert chat_body.children[2].children[0] is composers[0].text_area.window


def test_named_ground_prefers_five_context_body_rows_at_30_rows(monkeypatch):
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    panes = {}

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=30, columns=100),
            require_tty=False,
        )

    context_info = panes["CONTEXTS"].text_area.window.render_info
    assert context_info is not None
    assert context_info.window_height == 5
    assert all(
        pane.text_area.window.render_info is not None
        and pane.text_area.window.render_info.window_height >= 1
        for title, pane in panes.items()
        if title != "CONTEXTS"
    )


def test_named_ground_flexible_panes_fill_a_tall_terminal(monkeypatch):
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    original_input_builder = (
        ground_named_shell_module.build_framed_multiline_input
    )
    panes = {}
    composers = []

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def capturing_input(title, *args, **kwargs):
        composer = original_input_builder(title, *args, **kwargs)
        composers.append(composer)
        return composer

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_framed_multiline_input",
        capturing_input,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=60, columns=100),
            require_tty=False,
        )

    heights = {
        title: pane.text_area.window.render_info.window_height
        for title, pane in panes.items()
    }
    flexible = [
        heights["RULES"],
        heights["MEMORIES"],
        heights["CHAT"],
    ]
    message_height = composers[0].text_area.window.render_info.window_height
    assert heights["GOAL"] <= 3
    assert heights["CONTEXTS"] <= 8
    assert min(flexible) > 4
    # CHAT uses part of the same outer pane for its always-attached Message
    # field, so its read viewport may be two rows shorter than a read-only
    # sibling even though the semantic pane itself remains peer-sized.
    assert max(flexible) - min(flexible) <= 2
    # Five outer borders + header/footer + one in-frame Message divider.
    assert sum(heights.values()) + message_height + 13 == 60


def test_named_action_panels_are_content_sized_and_fit_narrow_terminals(
    monkeypatch,
):
    original_frame = ground_named_shell_module.Frame
    action_frames = []

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    monkeypatch.setattr(
        ground_named_shell_module,
        "Frame",
        capturing_frame,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=40, columns=30),
            require_tty=False,
        )

    assert len(action_frames) == 3
    assert [
        frame.container.height.preferred for frame in action_frames
    ] == [4, 3, 3]
    assert [
        frame.container.height.max for frame in action_frames
    ] == [4, 3, 3]
    texts = [frame.body.content.text for frame in action_frames]
    assert [len(text.splitlines()) for text in texts] == [2, 1, 1]
    assert all(
        get_cwidth(line) <= 28
        for text in texts
        for line in text.splitlines()
    )


def test_named_approval_action_renders_two_body_rows_at_24_by_30(
    monkeypatch,
):
    original_frame = ground_named_shell_module.Frame
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    action_frames = []
    panes = {}
    feeder_errors: list[Exception] = []
    rendered_height: list[int] = []
    dialogue_height: list[int] = []
    dialogue_text: list[str] = []
    applied = threading.Event()

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "Frame",
        capturing_frame,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )

    def apply(current, _proposal):
        applied.set()
        return replace(current, revision=current.revision + 1), "applied"

    with create_pipe_input() as pipe_input:
        def approve_after_render() -> None:
            try:
                pipe_input.send_text("Propose one Rule.\r")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if action_frames:
                        render_info = action_frames[0].body.render_info
                        dialogue_info = (
                            panes["CHAT"].text_area.window.render_info
                            if "CHAT" in panes
                            else None
                        )
                        if render_info is not None and dialogue_info is not None:
                            rendered_height.append(render_info.window_height)
                            dialogue_height.append(
                                dialogue_info.window_height
                            )
                            dialogue_text.append(
                                panes["CHAT"].text_area.text
                            )
                            pipe_input.send_text("a")
                            if not applied.wait(2):
                                raise AssertionError(
                                    "approved command was not applied"
                                )
                            pipe_input.send_text("\x03")
                            return
                    time.sleep(0.01)
                raise AssertionError("approval Action was not rendered")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                pipe_input.send_text("\x1b")

        feeder = threading.Thread(target=approve_after_render)
        feeder.start()
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda current, text, _source: proposal(current, text),
            apply=apply,
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert result.applied_argvs
    assert rendered_height == [2]
    assert dialogue_height and dialogue_height[0] >= 1
    assert (
        "mem ground fixture-ground --propose-rule"
        in dialogue_text[0]
    )


def test_comment_is_classified_once_and_one_ready_rule_is_proposed(
    monkeypatch,
):
    rendered_rules = []
    original_renderer = ground_named_shell_module.render_named_ground_rules_pane

    def capturing_renderer(*args, **kwargs):
        rendered = original_renderer(*args, **kwargs)
        rendered_rules.append(rendered)
        return rendered

    monkeypatch.setattr(
        ground_named_shell_module,
        "render_named_ground_rules_pane",
        capturing_renderer,
    )
    rule = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="All six update areas must remain separate.",
        classification_reason="This constrains every generated fixture.",
        source_spans=("6개가 다 나눠져있어야함.",),
        proposal_rationale="Preserve the user's explicit fixture boundary.",
        rule_provenance="USER_STATED",
    )
    fact = GroundTurnDraft(
        kind="FACT",
        status="READY",
        content="The rear entrance is on level three.",
        classification_reason="This describes the campus world, not a Rule.",
        source_spans=("후문 3층에 있음",),
    )
    prepared_revisions = []
    applied = []

    def prepare(current, selected):
        prepared_revisions.append((current.revision, selected))
        return proposal(current, selected.content)

    def apply(current, frozen):
        applied.append(frozen)
        return replace(current, revision=current.revision + 1), "saved"

    with create_pipe_input() as pipe_input:
        # Submit → classify → R the selected READY Rule → approve → close.
        pipe_input.send_text("fixture requirements\rra\x1b")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: draft_batch(rule, fact),
            prepare_rule_draft=prepare,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared_revisions == [(0, rule)]
    assert len(applied) == 1
    assert result.session.revision == 1
    assert result.submitted_turns == ("fixture requirements",)
    assert any(
        "DRAFTS · NOT SAVED · 2" in rendered
        and "d1 [RULE · READY]" in rendered
        and "d2 [FACT · READY]" in rendered
        for rendered in rendered_rules
    )
    assert any(
        "DRAFTS · NOT SAVED · 1" in rendered
        and "RECLASSIFY REQUIRED" in rendered
        and "d1 [FACT · STALE]" in rendered
        for rendered in rendered_rules
    )


def test_named_draft_result_marks_rules_and_chat_until_explicit_visit(
    monkeypatch,
):
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    notifications = {}

    def capturing_pane(title, *args, **kwargs):
        notifications[title] = kwargs.get("notification")
        return original_pane_builder(title, *args, **kwargs)

    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    rule = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep share-class suffixes visible.",
        classification_reason="This is one independently reviewable Rule.",
        source_spans=("Keep share-class suffixes visible.",),
        proposal_rationale="The person stated this boundary.",
        rule_provenance="USER_STATED",
    )

    with create_pipe_input() as pipe_input:
        # The draft batch programmatically focuses Rules. Up is the person's
        # first explicit interaction with that pane, so only its dot clears.
        pipe_input.send_text(
            "Keep share-class suffixes visible.\r\x1b[A\x03"
        )
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: draft_batch(rule),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.applied_argvs == ()
    assert set(notifications) == {
        "GOAL",
        "CONTEXTS",
        "RULES",
        "MEMORIES",
        "CHAT",
    }
    assert not notifications["GOAL"]()
    assert not notifications["CONTEXTS"]()
    assert not notifications["RULES"]()
    assert not notifications["MEMORIES"]()
    assert notifications["CHAT"]()


def test_ready_rule_review_detaches_message_during_exact_approval(
    monkeypatch,
):
    original_frame = ground_named_shell_module.Frame
    original_pane_builder = (
        ground_named_shell_module.build_scrollable_text_pane
    )
    action_frames = []
    panes = {}
    observed = []
    feeder_errors: list[Exception] = []

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_named_shell_module,
        "Frame",
        capturing_frame,
    )
    monkeypatch.setattr(
        ground_named_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    rule = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep six areas separate.",
        classification_reason="This is one independently reviewable Rule.",
        source_spans=("six areas",),
        proposal_rationale="The user stated this boundary.",
        rule_provenance="USER_STATED",
    )

    with create_pipe_input() as pipe_input:

        def inspect_approval_layout() -> None:
            try:
                pipe_input.send_text("six areas\rr")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    action_rendered = bool(
                        action_frames
                        and action_frames[0].body.render_info is not None
                    )
                    chat = panes.get("CHAT")
                    if (
                        action_rendered
                        and chat is not None
                        and "DRAFT SELECTED" in chat.text_area.text
                    ):
                        observed.append(chat.frame.body is chat.text_area)
                        pipe_input.send_text("\x1b")
                        return
                    time.sleep(0.01)
                raise AssertionError("Rule approval was not rendered")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                pipe_input.send_text("\x03")

        feeder = threading.Thread(target=inspect_approval_layout)
        feeder.start()
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: draft_batch(
                rule,
                raw_source="six areas",
            ),
            prepare_rule_draft=lambda current, selected: proposal(
                current,
                selected.content,
            ),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=50),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert observed == [True]
    assert result.applied_argvs == ()


def test_remaining_rule_draft_is_prepared_against_updated_revision():
    first = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep six areas separate.",
        classification_reason="First structural boundary.",
        source_spans=("six areas",),
        proposal_rationale="User-stated first boundary.",
        rule_provenance="USER_STATED",
    )
    second = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="The wiki must cover every corresponding area.",
        classification_reason="Second coverage boundary.",
        source_spans=("wiki coverage",),
        proposal_rationale="User-stated second boundary.",
        rule_provenance="USER_STATED",
    )
    prepared_revisions = []
    interpretations = []
    first_after_save = replace(
        first,
        status="DUPLICATE",
        classification_reason="The first Rule is already proposed.",
    )

    def prepare(current, selected):
        prepared_revisions.append((current.revision, selected.content))
        return proposal(current, selected.content)

    def apply(current, _frozen):
        return replace(current, revision=current.revision + 1), "saved"

    def interpret(current, _dialogue, source_text):
        interpretations.append((current.revision, source_text))
        if len(interpretations) == 1:
            return draft_batch(first, second, raw_source=source_text)
        return draft_batch(
            first_after_save,
            second,
            raw_source=source_text,
        )

    with create_pipe_input() as pipe_input:
        # The first save makes all remaining semantic statuses stale. R runs
        # one fresh batch before the second exact-command review.
        pipe_input.send_text("two rules\rrarra\x1b")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=interpret,
            prepare_rule_draft=prepare,
            apply=apply,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared_revisions == [
        (0, first.content),
        (1, second.content),
    ]
    assert [revision for revision, _source in interpretations] == [0, 1]
    assert [source for _revision, source in interpretations] == [
        "two rules",
        "two rules",
    ]
    assert result.session.revision == 2
    assert len(result.applied_argvs) == 2


def test_non_rule_or_unclear_draft_never_builds_a_command():
    unclear = GroundTurnDraft(
        kind="FACT",
        status="NEEDS_CLARIFICATION",
        content="'That entrance' is closed.",
        classification_reason="The entrance referent is unresolved.",
        source_spans=("that entrance",),
    )
    prepared = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("ambiguous fact\rr\x1b")
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=lambda *_args: draft_batch(unclear),
            prepare_rule_draft=lambda *args: prepared.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared == []
    assert result.applied_argvs == ()


def test_saved_ground_change_discards_stale_unsaved_drafts_before_review():
    session = create_ground_session("fixture-ground", goal="Old Goal.")
    refreshed = replace(session, goal="Changed Goal.", revision=1)
    reloads = iter((session, refreshed))
    rule = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep six areas separate.",
        classification_reason="A structural Rule.",
        source_spans=("six areas",),
        proposal_rationale="The user stated this boundary.",
        rule_provenance="USER_STATED",
    )
    prepared = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("six areas\rr\x1b")
        result = run_named_ground_shell(
            session,
            interpret=lambda *_args: draft_batch(rule),
            prepare_rule_draft=lambda *args: prepared.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            reload_session=lambda _name: next(reloads),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert prepared == []
    assert result.session == refreshed
    assert result.applied_argvs == ()


def test_new_user_turn_stales_old_ready_draft_until_reclassified(
    monkeypatch,
):
    rule = GroundTurnDraft(
        kind="RULE",
        status="READY",
        content="Keep six areas separate.",
        classification_reason="A structural Rule.",
        source_spans=("six areas",),
        proposal_rationale="The user stated this boundary.",
        rule_provenance="USER_STATED",
    )
    calls = []
    prepared = []
    rendered_rules = []
    original_renderer = ground_named_shell_module.render_named_ground_rules_pane

    def interpret(_current, _dialogue, source_text):
        calls.append(source_text)
        if len(calls) == 1:
            return draft_batch(rule, raw_source=source_text)
        return Ask(
            kind="ASK",
            understanding="The earlier Rule may have been retracted.",
            question="What replacement, if any, should be retained?",
        )

    def capturing_renderer(*args, **kwargs):
        rendered = original_renderer(*args, **kwargs)
        rendered_rules.append(rendered)
        return rendered

    monkeypatch.setattr(
        ground_named_shell_module,
        "render_named_ground_rules_pane",
        capturing_renderer,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "six areas\r"
            "\t\t\t"
            "Actually retract that Rule.\r"
            "\x1b"
        )
        result = run_named_ground_shell(
            create_ground_session("fixture-ground"),
            interpret=interpret,
            prepare_rule_draft=lambda *args: prepared.append(args),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert calls == ["six areas", "Actually retract that Rule."]
    assert prepared == []
    assert result.applied_argvs == ()
    assert any(
        "RECLASSIFY REQUIRED" in rendered
        and "d1 [RULE · STALE]" in rendered
        for rendered in rendered_rules
    )


def test_named_escape_closes_with_unsent_text_in_the_message_box():
    session = create_ground_session("fixture-ground")
    interpreted = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("an unfinished Ground turn\x1b")
        result = run_named_ground_shell(
            session,
            interpret=lambda current, text, _source: interpreted.append(
                (current, text)
            ),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.session == session
    assert result.submitted_turns == ()
    assert result.applied_argvs == ()
    assert interpreted == []


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
            interpret=lambda current, text, _source: proposal(current, text),
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

    def interpret(current, text, _source_text):
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
            interpret=lambda current, text, _source: proposal(current, text),
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

    def interpret(current, text, _source_text):
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
