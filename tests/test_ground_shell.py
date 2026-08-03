from __future__ import annotations

import shlex
import threading
import time
from dataclasses import dataclass

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth

import memcommit.commands.ground_shell as ground_shell_module
from memcommit.commands.ground_shell import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    GroundShellContextSuggestion,
    GroundShellMemoryDraft,
    GroundShellNewContextSuggestion,
    GroundShellProposal,
    GroundShellRuleDraft,
    _anchored_conversation_fragments,
    format_proposal_command,
    render_ground_cases_pane,
    render_ground_contexts_pane,
    render_ground_goal_pane,
    render_ground_rules_pane,
    render_ground_top_panel,
    render_proposal_review,
    run_ground_shell as _run_ground_shell,
)


def run_ground_shell(**kwargs):
    """Keep legacy interaction tests deterministic; async has focused tests."""
    kwargs.setdefault("background_interpretation", False)
    return _run_ground_shell(**kwargs)


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
    context_suggestions: tuple[GroundShellContextSuggestion, ...] = ()
    new_context_suggestions: tuple[
        GroundShellNewContextSuggestion, ...
    ] = ()
    rule_drafts: tuple[GroundShellRuleDraft, ...] = ()
    memory_drafts: tuple[GroundShellMemoryDraft, ...] = ()


@dataclass(frozen=True)
class Propose:
    kind: str
    understanding: str
    question: str
    ground_name: str
    goal: str
    command: str = "rm -rf ignored-raw-command"
    context_suggestions: tuple[GroundShellContextSuggestion, ...] = ()
    new_context_suggestions: tuple[
        GroundShellNewContextSuggestion, ...
    ] = ()
    rule_drafts: tuple[GroundShellRuleDraft, ...] = ()
    memory_drafts: tuple[GroundShellMemoryDraft, ...] = ()


def proposal(text: str = "Compare report coverage.") -> Propose:
    return Propose(
        kind="PROPOSE",
        understanding=f"Understood: {text}",
        question="Approve this initial Ground?",
        ground_name="task-1-report-coverage",
        goal="Find what was reported and what remains unclear.",
    )


def proposal_with_contexts(
    text: str = "Compare report coverage.",
) -> Propose:
    base = proposal(text)
    return Propose(
        kind=base.kind,
        understanding=base.understanding,
        question=base.question,
        ground_name=base.ground_name,
        goal=base.goal,
        context_suggestions=(
            GroundShellContextSuggestion(
                context_name="temp/task-1",
                role="MAIN",
                reason="Strongest Task 1 name match.",
            ),
            GroundShellContextSuggestion(
                context_name="temp/task-1-atomized",
                role="ALTERNATIVE",
                reason="Processed Task 1 variant.",
            ),
        ),
    )


def proposal_with_new_context(
    text: str = "Find a reusable ticker rule.",
) -> Propose:
    base = proposal(text)
    return Propose(
        kind=base.kind,
        understanding=base.understanding,
        question=base.question,
        ground_name="ticker-rules",
        goal="Find reusable company-name to ticker Rules.",
        new_context_suggestions=(
            GroundShellNewContextSuggestion(
                context_name="ticker-rule-examples",
                reason="A dedicated example Context may help.",
            ),
        ),
    )


def test_blank_goal_inline_direct_edit_is_preserved_in_creation_proposal():
    seen = []
    applied = []
    exact_goal = "Build a separated Task 1 campus wiki."

    def interpret(text):
        seen.append(text)
        return Propose(
            kind="PROPOSE",
            understanding="The directly edited Goal is exact.",
            question="Approve creating this Ground?",
            ground_name="task-1-campus-wiki",
            goal=exact_goal,
        )

    with create_pipe_input() as pipe_input:
        # MESSAGE -> GOAL -> expanded EDIT. The creation command still waits
        # for A after the provider supplies only a portable Ground name.
        pipe_input.send_text(f"\te{exact_goal}\ra")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda value: applied.append(value) or "created",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert result.proposal is not None
    assert result.proposal.goal == exact_goal
    assert len(applied) == 1
    assert "EDIT (DIRECTLY) · PRESERVE EXACTLY" in seen[0]
    assert exact_goal in seen[0]


def test_blank_goal_direct_edit_fails_closed_if_provider_rewrites_it():
    exact_goal = "Keep this Goal exactly."
    applied = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(f"\te{exact_goal}\r\x1b")
        result = run_ground_shell(
            interpret=lambda _text: Propose(
                kind="PROPOSE",
                understanding="I rewrote the Goal.",
                question="Approve?",
                ground_name="rewritten-goal",
                goal="A different Goal.",
            ),
            apply=lambda value: applied.append(value),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.proposal is None
    assert applied == []


def test_blank_goal_refine_reopens_exact_edit_and_agent_comment_fields():
    seen = []
    exact_goal = "Build a separated Task 1 campus wiki."
    revised_goal = f"{exact_goal} Revised."
    comment = "Keep this wording exact."

    def interpret(text):
        seen.append(text)
        proposed_goal = exact_goal if len(seen) == 1 else revised_goal
        return Propose(
            kind="PROPOSE",
            understanding="The directly edited Goal is exact.",
            question="Approve creating this Ground?",
            ground_name="task-1-campus-wiki",
            goal=proposed_goal,
        )

    with create_pipe_input() as pipe_input:
        # MESSAGE -> GOAL -> EDIT -> COMMENT -> review -> refine.  Pressing
        # Typing immediately after E must change the reopened direct field,
        # not append prose to a host-framed payload in ordinary Message.
        pipe_input.send_text(
            f"\te{exact_goal}\t{comment}\re Revised.\r\x1b"
        )
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert len(seen) == 2
    assert result.proposal is not None
    assert result.proposal.goal == revised_goal
    assert "EDIT (DIRECTLY) · PRESERVE EXACTLY" in seen[1]
    assert "COMMENT (FOR THE AGENT)" in seen[1]
    assert revised_goal in seen[1]
    assert comment in seen[1]


def test_blank_goal_escape_collapses_editor_before_cancelling_shell():
    interpreted = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\teunsubmitted edit\x1b\x1b")
        result = run_ground_shell(
            interpret=lambda text: interpreted.append(text),
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert interpreted == []
    assert result.submitted_turns == ()


def test_blank_goal_inline_tab_submits_comment_only_to_agent():
    seen = []

    def interpret(text):
        seen.append(text)
        return Ask(
            kind="ASK",
            understanding="The comment concerns the Goal.",
            question="What exact outcome should the Goal name?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\te\tExplain the intended audience.\r\x1b"
        )
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert len(seen) == 1
    assert "FOCUS · GOAL" in seen[0]
    assert "COMMENT (FOR THE AGENT)" in seen[0]
    assert "Explain the intended audience." in seen[0]
    assert result.submitted_turns == (seen[0],)


@pytest.mark.parametrize(
    ("tabs", "focus"),
    [
        (3, "RULES"),
        (4, "MEMORIES"),
    ],
)
def test_blank_rule_and_memory_focused_comments_exclude_agent_previews(
    tabs,
    focus,
):
    seen: list[str] = []
    comment = "Reconsider this pane using only my new explanation."
    agent_rule = "AGENT-ONLY RULE PREVIEW"
    agent_memory = "AGENT-ONLY MEMORY PREVIEW"
    first = Ask(
        kind="ASK",
        understanding="The first turn supports tentative previews.",
        question="What should be corrected?",
        rule_drafts=(
            GroundShellRuleDraft(
                content=agent_rule,
                rationale="Synthetic Rule for correction.",
                origin="AGENT_SUGGESTED",
                source_spans=(),
            ),
        ),
        memory_drafts=(
            GroundShellMemoryDraft(
                content=agent_memory,
                expected="AGENT-ONLY EXPECTED PREVIEW",
                rationale="Synthetic Memory for correction.",
                case_role="FIT",
                disposition="UNRESOLVED",
                rule_draft_index=1,
                origin="AGENT_SUGGESTED",
                source_spans=(),
            ),
        ),
    )

    def interpret(text: str):
        seen.append(text)
        if len(seen) == 1:
            return first
        return Ask(
            kind="ASK",
            understanding="The focused correction was received.",
            question="What should happen next?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(("\t" * tabs) + f"c{comment}\r\x1b")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Find a reusable naming convention.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert len(seen) == 2
    follow_up = seen[1]
    assert f"FOCUS · {focus}" in follow_up
    assert "COMMENT (FOR THE AGENT)" in follow_up
    assert comment in follow_up
    assert agent_rule not in follow_up
    assert agent_memory not in follow_up
    assert "AGENT-ONLY EXPECTED PREVIEW" not in follow_up


@pytest.mark.parametrize(
    ("tabs", "focus"),
    [
        (1, "GOAL"),
        (2, "CONTEXTS"),
        (3, "RULES"),
        (4, "MEMORIES"),
    ],
)
def test_blank_enter_opens_conversation_inside_each_semantic_pane(
    tabs,
    focus,
):
    seen: list[str] = []
    comment = f"Discuss {focus.lower()} here."

    def interpret(text: str):
        seen.append(text)
        return Ask(
            kind="ASK",
            understanding="The focused pane comment was received.",
            question="What should happen next?",
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(("\t" * tabs) + f"\r{comment}\r\x1b")
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Start one Ground.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert len(seen) == 2
    assert f"FOCUS · {focus}" in seen[1]
    assert comment in seen[1]


def test_blank_inline_goal_keeps_five_panes_and_both_fields_at_24_rows(
    monkeypatch,
):
    original_pane = ground_shell_module.build_scrollable_text_pane
    original_message = ground_shell_module.build_framed_multiline_input
    original_edit = ground_shell_module.build_inline_direct_edit_input
    panes = {}
    messages = []
    editors = []
    observed = []
    errors = []

    def capture_pane(title, *args, **kwargs):
        value = original_pane(title, *args, **kwargs)
        panes[title] = value
        return value

    def capture_message(title, *args, **kwargs):
        value = original_message(title, *args, **kwargs)
        messages.append(value)
        return value

    def capture_edit(*args, **kwargs):
        value = original_edit(*args, **kwargs)
        editors.append(value)
        return value

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capture_pane,
    )
    monkeypatch.setattr(
        ground_shell_module,
        "build_framed_multiline_input",
        capture_message,
    )
    monkeypatch.setattr(
        ground_shell_module,
        "build_inline_direct_edit_input",
        capture_edit,
    )

    with create_pipe_input() as pipe_input:
        def inspect() -> None:
            try:
                pipe_input.send_text("\te")
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    if panes and messages and editors:
                        infos = [
                            pane.text_area.window.render_info
                            for pane in panes.values()
                        ]
                        edit_info = editors[0].text_area.window.render_info
                        comment_info = messages[0].text_area.window.render_info
                        if (
                            all(info is not None for info in infos)
                            and edit_info is not None
                            and comment_info is not None
                            and messages[0].frame.title
                            == "COMMENT (FOR THE AGENT)"
                        ):
                            observed.append(
                                (
                                    [info.window_height for info in infos],
                                    edit_info.window_height,
                                    comment_info.window_height,
                                )
                            )
                            pipe_input.send_text("\x1b\x1b")
                            return
                    time.sleep(0.01)
                raise AssertionError("blank Goal editor was not rendered")
            except Exception as error:  # pragma: no cover - assertion relay
                errors.append(error)
                pipe_input.send_text("\x03")

        feeder = threading.Thread(target=inspect)
        feeder.start()
        result = run_ground_shell(
            interpret=lambda _text: pytest.fail("must not interpret"),
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert errors == []
    assert not feeder.is_alive()
    assert result.status == "CANCELLED"
    assert len(observed) == 1
    pane_heights, edit_height, comment_height = observed[0]
    assert all(height >= 1 for height in pane_heights)
    assert edit_height >= 1
    assert comment_height >= 1


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
    assert "CONTEXTS\n  NAME-ONLY CHECK · NOT BOUND" in blank
    assert "CURRENT · (none)" in blank
    assert "RULES\n  (none yet)" in blank
    assert "MEMORIES\n  (none yet)" in blank
    assert "Find what was reported." in proposed
    assert "COMPLETION" not in proposed
    assert "PROPOSED COMMAND · NOT RUN" in review
    assert "Ground: CREATE task-1-report-coverage" in review
    assert "Goal: SET" in review
    assert "Rules: unchanged (none)" in review
    assert "Ground Memories: unchanged (none)" in review
    assert "Context selections: local only (not saved or bound)" in review
    assert "Contexts: unchanged" in review
    assert "Context Memories: unchanged" in review
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
    assert (
        "Rule drafts may appear as the Ground takes shape."
        in render_ground_rules_pane()
    )
    assert (
        "Memory drafts may appear as the Ground takes shape."
        in render_ground_cases_pane()
    )
    contexts = render_ground_contexts_pane()
    assert "CURRENT · (none)" in contexts
    assert "no ordinary Context locator names found" in contexts
    suggested = render_ground_contexts_pane(
        (
            GroundShellContextSuggestion(
                context_name="temp/task-1",
                role="MAIN",
                reason="The name matches Task 1.",
            ),
            GroundShellContextSuggestion(
                context_name="temp/task-1-atomized",
                role="ALTERNATIVE",
                reason="A processed Task 1 variant.",
            ),
        ),
        current_context_name="test/update/from",
        catalog_count=4,
        discovery_complete=True,
    )
    assert "NAME-ONLY CHECK · NOT BOUND" in suggested
    assert (
        "CURRENT · test/update/from · NO DISPLAYED MATCH · NOT BOUND"
        in suggested
    )
    assert (
        "MAIN? · temp/task-1 · NOT BOUND — The name matches Task 1."
        in suggested
    )
    assert (
        "ALTERNATIVE · temp/task-1-atomized · NOT BOUND — "
        "A processed Task 1 variant."
        in suggested
    )
    assert "no Context Memory content read" in suggested
    assert "SOURCE?" not in suggested
    assert "DERIVED?" not in suggested
    assert "TARGET?" not in suggested
    assert all(
        not line.startswith("  ")
        for line in suggested.splitlines()
    )
    assert GROUND_GOAL_FRAME_HEIGHT.preferred == 5
    assert GROUND_GOAL_FRAME_HEIGHT.max == 5


def test_first_turn_renders_new_context_and_immediate_rule_memory_drafts():
    new_context = GroundShellNewContextSuggestion(
        context_name="ticker-rule-examples",
        reason="No dedicated example Context exists yet.",
    )
    rule = GroundShellRuleDraft(
        content=(
            "Use a short uppercase base code and preserve share-class suffixes."
        ),
        rationale="Test this hypothesis against both ordinary and boundary cases.",
        origin="AGENT_SUGGESTED",
        source_spans=(),
    )
    apple = GroundShellMemoryDraft(
        content="Apple Inc.",
        expected="AAPL",
        rationale="The mapping was supplied by the user.",
        case_role="FIT",
        disposition="INCLUDE",
        rule_draft_index=1,
        origin="USER_EXACT",
        source_spans=("Apple Inc. -> AAPL",),
    )
    berkshire = GroundShellMemoryDraft(
        content="Berkshire Hathaway\nClass B",
        expected="BRK.B",
        rationale="Synthetic boundary example; verify before use.",
        case_role="BOUNDARY",
        disposition="UNRESOLVED",
        rule_draft_index=1,
        origin="AGENT_SUGGESTED",
        source_spans=(),
    )
    frozen = GroundShellProposal(
        ground_name="ticker-rules",
        goal="Find reusable Rules relating company names and generated tickers.",
        understanding="Build and test a reusable ticker generator.",
        question="Create this Ground?",
        new_context_suggestions=(new_context,),
        rule_drafts=(rule,),
        memory_drafts=(apple, berkshire),
    )

    contexts = render_ground_contexts_pane(
        (
            GroundShellContextSuggestion(
                context_name="existing-examples",
                role="MAIN",
                reason="The closest existing locator name.",
            ),
            GroundShellContextSuggestion(
                context_name="naming-notes",
                role="ALTERNATIVE",
                reason="A broader existing alternative.",
            ),
        ),
        new_context_suggestions=(new_context,),
        discovery_complete=True,
        candidate_cursor_name="existing-examples",
    )
    rules = render_ground_rules_pane((rule,))
    memories = render_ground_cases_pane((apple, berkshire))
    top = render_ground_top_panel(frozen)
    review = render_proposal_review(frozen)

    assert contexts.index("ALTERNATIVE · naming-notes") < contexts.index(
        "NEW? · ticker-rule-examples · NOT CREATED"
    )
    assert "[ ] NEW?" not in contexts
    assert "› NEW?" not in contexts
    assert "ADD NEW CONTEXT · N to enter an exact Context name" in contexts
    assert (
        "r1 [Suggested] [Unverified] Use a short uppercase base code"
        in rules
    )
    assert (
        "c1 [Provided] [Source-matched] Apple Inc. | AAPL "
        "· FIT / INCLUDE · r1"
        in memories
    )
    assert (
        "c2 [Suggested] [Unverified] Berkshire Hathaway ↵ Class B | "
        "BRK.B · BOUNDARY / UNRESOLVED · r1"
    ) in memories
    assert "NOTES ·" not in rules
    assert "NOTES ·" not in memories
    assert "NEW? · ticker-rule-examples" in top
    assert "DRAFTS · NOT SAVED" not in top
    assert "Rules: unchanged (none)" in review
    assert "Ground Memories: unchanged (none)" in review
    assert (
        "Provider new-Context suggestion: unaccepted (not created)"
        in review
    )
    accepted_local_effects = ground_shell_module._render_proposal_effects_block(
        frozen,
        has_local_new_context=True,
    )
    assert "New Context plan: local only (not created)" in accepted_local_effects
    assert "unaccepted" not in accepted_local_effects
    command = format_proposal_command(frozen)
    assert command.startswith("mem ground ticker-rules --goal")
    assert "ticker-rule-examples" not in command
    assert "Apple" not in command


def test_shell_freeze_rejects_mismatched_source_matched_preview_fields():
    mismatched_rule = GroundShellRuleDraft(
        content="Microsoft maps to MSFT.",
        rationale="Not covered by the claimed span.",
        origin="USER_EXACT",
        source_spans=("Apple Inc. -> AAPL",),
    )
    mismatched_memory = GroundShellMemoryDraft(
        content="Apple Inc.",
        expected="MSFT",
        rationale="Expected output is not covered by the claimed span.",
        case_role="FIT",
        disposition="INCLUDE",
        rule_draft_index=0,
        origin="USER_EXACT",
        source_spans=("Apple Inc. -> AAPL",),
    )

    with pytest.raises(ValueError, match="invalid Rule drafts"):
        ground_shell_module._freeze_rule_drafts(
            Propose(
                kind="PROPOSE",
                understanding="Preview a Rule.",
                question="Review it?",
                ground_name="ticker-rules",
                goal="Find a reusable ticker Rule.",
                rule_drafts=(mismatched_rule,),
            )
        )
    with pytest.raises(ValueError, match="invalid Memory drafts"):
        ground_shell_module._freeze_memory_drafts(
            Propose(
                kind="PROPOSE",
                understanding="Preview a Memory.",
                question="Review it?",
                ground_name="ticker-rules",
                goal="Find a reusable ticker Rule.",
                memory_drafts=(mismatched_memory,),
            ),
            rule_draft_count=0,
        )


def test_contexts_prefers_five_body_rows_without_breaking_compact_minimum():
    assert GROUND_CONTEXTS_FRAME_HEIGHT.min == 3
    assert GROUND_CONTEXTS_FRAME_HEIGHT.preferred == 7
    assert GROUND_CONTEXTS_FRAME_HEIGHT.max == 10


def test_initial_agent_turn_populates_rule_and_memory_panes_before_creation(
    monkeypatch,
):
    original_pane_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    rule = GroundShellRuleDraft(
        content="Preserve a dot-prefixed share-class suffix.",
        rationale="Initial hypothesis.",
        origin="AGENT_SUGGESTED",
        source_spans=(),
    )
    memory = GroundShellMemoryDraft(
        content="North Star Energy Inc.\nClass B",
        expected="NSE.B",
        rationale="Synthetic boundary example.",
        case_role="BOUNDARY",
        disposition="UNRESOLVED",
        rule_draft_index=1,
        origin="AGENT_SUGGESTED",
        source_spans=(),
    )

    def interpreted(text):
        return Propose(
            kind="PROPOSE",
            understanding=f"Understood: {text}",
            question="Create this Ground?",
            ground_name="ticker-rules",
            goal="Find reusable company-name to ticker Rules.",
            new_context_suggestions=(
                GroundShellNewContextSuggestion(
                    context_name="ticker-rule-examples",
                    reason="A dedicated example Context may help.",
                ),
            ),
            rule_drafts=(rule,),
            memory_drafts=(memory,),
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        result = run_ground_shell(
            interpret=interpreted,
            apply=lambda *_args: pytest.fail("must not apply"),
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert "r1 [Suggested] [Unverified]" in panes["RULES"].text_area.text
    assert "Preserve a dot-prefixed share-class suffix." in (
        panes["RULES"].text_area.text
    )
    assert "c1 [Suggested] [Unverified]" in (
        panes["MEMORIES"].text_area.text
    )
    assert "North Star Energy Inc. ↵ Class B | NSE.B" in (
        panes["MEMORIES"].text_area.text
    )
    assert "NEW? · ticker-rule-examples · NOT CREATED" in (
        panes["CONTEXTS"].text_area.text
    )


def test_blank_ground_keeps_every_pane_and_message_body_visible_at_24_rows(
    monkeypatch,
):
    original_pane_builder = ground_shell_module.build_scrollable_text_pane
    original_input_builder = ground_shell_module.build_framed_multiline_input
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
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    monkeypatch.setattr(
        ground_shell_module,
        "build_framed_multiline_input",
        capturing_input,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_ground_shell(
            interpret=lambda *_args: pytest.fail("must not interpret"),
            apply=lambda *_args: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=100),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
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


def test_blank_ground_prefers_five_context_body_rows_at_30_rows(monkeypatch):
    original_pane_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_ground_shell(
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


def test_blank_ground_flexible_panes_fill_a_tall_terminal(monkeypatch):
    original_pane_builder = ground_shell_module.build_scrollable_text_pane
    original_frame = ground_shell_module.Frame
    panes = {}
    action_frames = []

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )
    monkeypatch.setattr(
        ground_shell_module,
        "Frame",
        capturing_frame,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_ground_shell(
            interpret=proposal,
            apply=lambda *_args: pytest.fail("must not apply"),
            initial_request="Review the Ground layout.",
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
    action_height = action_frames[0].body.render_info.window_height
    assert heights["GOAL"] <= 3
    assert heights["CONTEXTS"] <= 8
    assert min(flexible) > 4
    assert max(flexible) - min(flexible) <= 1
    # Five read frames plus ACTION contribute twelve border rows; the
    # header/footer contribute two. No unallocated band remains below ACTION.
    assert sum(heights.values()) + action_height + 14 == 60


def test_blank_action_panels_are_content_sized_and_fit_narrow_terminals(
    monkeypatch,
):
    original_frame = ground_shell_module.Frame
    action_frames = []

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    monkeypatch.setattr(ground_shell_module, "Frame", capturing_frame)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        run_ground_shell(
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


def test_blank_approval_action_renders_two_body_rows_at_24_by_30(
    monkeypatch,
):
    original_frame = ground_shell_module.Frame
    original_pane_builder = ground_shell_module.build_scrollable_text_pane
    action_frames = []
    panes = {}
    feeder_errors: list[Exception] = []
    rendered_height: list[int] = []
    dialogue_height: list[int] = []
    dialogue_text: list[str] = []

    def capturing_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        if kwargs.get("title") == "ACTION":
            action_frames.append(frame)
        return frame

    def capturing_pane(title, *args, **kwargs):
        pane = original_pane_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(ground_shell_module, "Frame", capturing_frame)
    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_pane,
    )

    with create_pipe_input() as pipe_input:
        def approve_after_render() -> None:
            try:
                pipe_input.send_text("Review Task 1.\r")
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
                            return
                    time.sleep(0.01)
                raise AssertionError("approval Action was not rendered")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                pipe_input.send_text("\x1b")

        feeder = threading.Thread(target=approve_after_render)
        feeder.start()
        result = run_ground_shell(
            interpret=proposal,
            apply=lambda _value: "created",
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=24, columns=30),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert result.status == "APPLIED"
    assert rendered_height == [2]
    assert dialogue_height and dialogue_height[0] >= 1
    assert (
        "mem ground task-1-report-coverage --goal"
        in dialogue_text[0]
    )


def test_current_main_is_rendered_once_and_candidate_reasons_stay_one_line():
    rendered = render_ground_contexts_pane(
        (
            GroundShellContextSuggestion(
                context_name="temp/task-1",
                role="ALTERNATIVE",
                reason="Current candidate\nwith a compact reason.",
            ),
            GroundShellContextSuggestion(
                context_name="temp/task-1-atomized",
                role="MAIN",
                reason="Best processed candidate.",
            ),
        ),
        current_context_name="temp/task-1-atomized",
        catalog_count=16,
        discovery_complete=True,
    )

    assert rendered.count("MAIN?") == 1
    assert (
        "[ ] CURRENT · MAIN? · temp/task-1-atomized · NOT BOUND — "
        "Best processed candidate."
    ) in rendered
    assert rendered.count("temp/task-1-atomized") == 1
    assert (
        "[ ] ALTERNATIVE · temp/task-1 · NOT BOUND — "
        "Current candidate with a compact reason."
    ) in rendered


@pytest.mark.parametrize("suffix", [".", "..", "…"])
def test_context_discovery_thinking_suffix_is_rendered(suffix):
    rendered = render_ground_contexts_pane(
        current_context_name="test/update/from",
        catalog_count=16,
        discovery_in_progress=True,
        thinking_suffix=suffix,
    )

    assert (
        f"THINKING{suffix} · ranking 16 Context locator names; "
        "CURRENT stays local"
    ) in rendered


def test_context_candidate_cursor_and_multiple_selections_are_distinct():
    candidates = proposal_with_contexts().context_suggestions

    recommended = render_ground_contexts_pane(
        candidates,
        current_context_name="elsewhere",
        catalog_count=2,
        discovery_complete=True,
        candidate_cursor_name="temp/task-1",
    )
    selected_multiple = render_ground_contexts_pane(
        candidates,
        current_context_name="elsewhere",
        catalog_count=2,
        discovery_complete=True,
        candidate_cursor_name="temp/task-1-atomized",
        selected_context_names=(
            "temp/task-1-atomized",
            "temp/task-1",
        ),
    )
    selected_current = render_ground_contexts_pane(
        candidates,
        current_context_name="temp/task-1",
        catalog_count=2,
        discovery_complete=True,
        candidate_cursor_name="temp/task-1",
        selected_context_names=("temp/task-1",),
    )

    assert "› [ ] MAIN? · temp/task-1 · NOT BOUND" in recommended
    assert (
        "  [ ] ALTERNATIVE · temp/task-1-atomized · NOT BOUND"
        in recommended
    )
    assert "  [x] ADDITIONAL · temp/task-1 · SELECTED" in selected_multiple
    assert (
        "› [x] MAIN · temp/task-1-atomized · SELECTED · NOT BOUND"
        in selected_multiple
    )
    assert selected_current.count("CURRENT · MAIN · temp/task-1 ·") == 1
    assert (
        "› [x] CURRENT · MAIN · temp/task-1 · SELECTED · NOT BOUND"
        in selected_current
    )
    assert "[ ] MAIN? · temp/task-1 · NOT BOUND" not in selected_current

    finished = render_ground_contexts_pane(
        candidates,
        current_context_name="elsewhere",
        selected_context_names=(
            "temp/task-1-atomized",
            "temp/task-1",
        ),
        selection_finished=True,
    )
    assert "SELECTED CONTEXTS · 2 · NOT BOUND" in finished
    assert (
        "MAIN · temp/task-1-atomized · SELECTED · NOT BOUND"
        in finished
    )
    assert "ADDITIONAL · temp/task-1 · SELECTED · NOT BOUND" in finished
    assert "ALTERNATIVE" not in finished
    assert "[ ]" not in finished


def test_new_and_add_context_rows_are_cursorable_but_not_checkable():
    suggested = GroundShellNewContextSuggestion(
        context_name="test/ground/ticker-rule-examples",
        reason="A dedicated example Context may help.",
    )
    existing = proposal_with_contexts().context_suggestions

    new_focused = render_ground_contexts_pane(
        existing,
        new_context_suggestions=(suggested,),
        discovery_complete=True,
        candidate_cursor_kind="NEW_SUGGESTION",
        candidate_cursor_name=suggested.context_name,
    )
    add_focused = render_ground_contexts_pane(
        existing,
        new_context_suggestions=(suggested,),
        discovery_complete=True,
        candidate_cursor_kind="ADD_NEW",
    )

    assert (
        "› NEW? · test/ground/ticker-rule-examples · NOT CREATED"
        in new_focused
    )
    assert "[ ] NEW?" not in new_focused
    assert (
        "› ADD NEW CONTEXT · N to enter an exact Context name"
        in add_focused
    )
    assert "[ ] ADD NEW CONTEXT" not in add_focused


def test_add_new_context_remains_available_without_catalog_or_suggestion():
    rendered = render_ground_contexts_pane(discovery_complete=True)
    finished_empty = render_ground_contexts_pane(
        discovery_complete=True,
        selection_finished=True,
    )

    assert "MAIN? · (none found from locator names)" in rendered
    assert "ADD NEW CONTEXT · N to enter an exact Context name" in rendered
    assert "CONTINUE WITHOUT CONTEXT PLAN · Review Ground only" in rendered
    assert "CONTEXT PLAN · NONE · NOT BOUND" in finished_empty
    assert "NEW ONLY" not in finished_empty


def test_approval_can_suspend_into_empty_store_add_context_editor():
    validated: list[str] = []
    applied: list[GroundShellProposal] = []
    exact_name = "test/ground/ticker-rule-examples"

    with create_pipe_input() as pipe_input:
        # APPROVAL starts on Chat. Tab reaches Goal then Contexts; N
        # suspends the receipt, opens blank ADD, and restores it after review.
        pipe_input.send_text(f"\t\tn{exact_name}\ra")
        result = run_ground_shell(
            interpret=proposal,
            apply=lambda value: applied.append(value) or "created",
            validate_new_context=lambda name: validated.append(name) or name,
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]
    assert validated == [exact_name]
    assert result.new_context_name_hint == exact_name
    assert exact_name not in format_proposal_command(result.proposal)


def test_approval_viewport_anchor_tracks_end_of_exact_proposed_command():
    command_block = (
        "PROPOSED COMMAND · NOT RUN\n  mem ground report-review"
    )
    fragments = _anchored_conversation_fragments(
        [
            "OLDER CHAT\n  enough text to require scrolling",
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


def test_approval_down_arrow_stays_in_focused_memories(monkeypatch):
    original_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    memory_drafts = tuple(
        GroundShellMemoryDraft(
            content=f"Example {index}",
            expected=f"E{index}",
            rationale="Synthetic navigation fixture.",
            case_role="FIT",
            disposition="UNRESOLVED",
            rule_draft_index=0,
            origin="AGENT_SUGGESTED",
            source_spans=(),
        )
        for index in range(1, 4)
    )
    frozen = Propose(
        kind="PROPOSE",
        understanding="Three draft Memories are available.",
        question="Approve this initial Ground?",
        ground_name="memory-navigation",
        goal="Review draft Memory navigation.",
        memory_drafts=memory_drafts,
    )
    applied = []

    with create_pipe_input() as pipe_input:
        # APPROVAL starts on CHAT. Four Tabs reach MEMORIES. V opens the
        # grid; Down/Right move cells without replacing the frozen command.
        pipe_input.send_text(
            "\t\t\t\tv\x1b[B" + ("\x1b[C" * 7) + "a"
        )
        result = run_ground_shell(
            interpret=lambda _text: frozen,
            apply=lambda value: applied.append(value) or "created",
            initial_request="Review draft Memory navigation.",
            app_input=pipe_input,
            app_output=SizedDummyOutput(rows=40, columns=50),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]
    assert result.proposal is not None
    assert result.proposal.ground_name == frozen.ground_name
    assert result.proposal.goal == frozen.goal
    memories = panes["MEMORIES"].text_area.text
    assert "TABLE · 3 MEMORIES · ROW 2/3 · COLUMN RULE" in memories
    assert "CELL · c2 · RULE" in memories
    assert not panes["MEMORIES"].text_area.window.wrap_lines()
    assert (
        panes["MEMORIES"].text_area.buffer.document.cursor_position_col > 50
    )
    dialogue = panes["CHAT"].text_area.text
    assert "PROPOSED COMMAND · NOT RUN" in dialogue
    assert "EFFECTS · ONE COMMAND" not in dialogue


def test_blank_memory_table_toggles_back_to_the_same_list_row(monkeypatch):
    original_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )
    drafts = tuple(
        GroundShellMemoryDraft(
            content=f"Input {index}",
            expected=f"Output {index}",
            rationale="Synthetic preview.",
            case_role="FIT",
            disposition="UNRESOLVED",
            rule_draft_index=0,
            origin="AGENT_SUGGESTED",
            source_spans=(),
        )
        for index in range(1, 4)
    )
    response = Ask(
        kind="ASK",
        understanding="The draft examples need one clarification.",
        question="Which naming convention should apply?",
        memory_drafts=drafts,
    )

    with create_pipe_input() as pipe_input:
        # ASK returns to MESSAGE. Four Tabs reach MEMORIES; the selected row
        # survives TABLE -> LIST while the remembered table column stays local.
        pipe_input.send_text("\t\t\t\tv\x1b[B\x1b[Cv\x1b")
        result = run_ground_shell(
            interpret=lambda _text: response,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Find a reusable example convention.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    memories = panes["MEMORIES"].text_area
    assert "TABLE ·" not in memories.text
    assert "c2 [Suggested] [Unverified] Input 2 | Output 2" in memories.text
    assert memories.buffer.document.cursor_position_row == 1
    assert memories.window.wrap_lines()


def test_memory_view_key_remains_literal_text_in_message():
    seen = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("v\r\x1b")
        result = run_ground_shell(
            interpret=lambda text: seen.append(text)
            or Ask(
                kind="ASK",
                understanding="The literal message was received.",
                question="What should happen next?",
            ),
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert seen == ["v"]


def test_focused_comment_key_remains_literal_text_in_message():
    seen = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("c\r\x1b")
        result = run_ground_shell(
            interpret=lambda text: seen.append(text)
            or Ask(
                kind="ASK",
                understanding="The literal message was received.",
                question="What should happen next?",
            ),
            apply=lambda _value: pytest.fail("must not apply"),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert seen == ["c"]


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
        # MESSAGE → GOAL → CONTEXTS → RULES → MEMORIES → CHAT.
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


def test_context_selection_supports_multiple_names_before_separate_approval(
    monkeypatch,
):
    original_renderer = ground_shell_module.render_ground_contexts_pane
    rendered: list[str] = []
    applied: list[GroundShellProposal] = []

    def capturing_renderer(*args, **kwargs):
        value = original_renderer(*args, **kwargs)
        rendered.append(value)
        return value

    monkeypatch.setattr(
        ground_shell_module,
        "render_ground_contexts_pane",
        capturing_renderer,
    )

    with create_pipe_input() as pipe_input:
        # Provider MAIN? is auto-focused. Visit RULES and return, then choose
        # the alternative first (local Main) and the recommendation second.
        # F finishes the set; A separately approves the unchanged command.
        pipe_input.send_text(
            "Review Task 1.\r"
            "\t"
            "\x1b[Z"
            "\x1b[B"
            " "
            "\x1b[A"
            " "
            "f"
            "a"
        )
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda value: applied.append(value) or "created",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]
    assert result.proposal is not None
    assert format_proposal_command(result.proposal) == (
        "mem ground task-1-report-coverage --goal "
        "'Find what was reported and what remains unclear.'"
    )
    assert result.selected_context_names == (
        "temp/task-1-atomized",
        "temp/task-1",
    )
    assert any(
        "SELECTED CONTEXTS · 2 · NOT BOUND" in value
        and "MAIN · temp/task-1-atomized · SELECTED · NOT BOUND" in value
        and "ADDITIONAL · temp/task-1 · SELECTED · NOT BOUND" in value
        and "ALTERNATIVE" not in value
        for value in rendered
    )
    assert result.proposal.context_suggestions[0].role == "MAIN"
    assert result.proposal.context_suggestions[1].role == "ALTERNATIVE"


def test_context_selection_requires_one_checked_name_before_finishing():
    applied = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("fa\x1b")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda value: applied.append(value),
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.selected_context_names == ()
    assert applied == []


def test_suggested_new_context_can_be_edited_without_entering_creation_argv(
    monkeypatch,
):
    original_renderer = ground_shell_module.render_ground_contexts_pane
    rendered: list[str] = []
    validated: list[str] = []
    applied: list[GroundShellProposal] = []

    def capturing_renderer(*args, **kwargs):
        value = original_renderer(*args, **kwargs)
        rendered.append(value)
        return value

    def validate_name(name: str) -> str:
        validated.append(name)
        return name

    monkeypatch.setattr(
        ground_shell_module,
        "render_ground_contexts_pane",
        capturing_renderer,
    )
    exact_name = "test/ground/ticker-rule-examples"
    with create_pipe_input() as pipe_input:
        # NEW? is focused. N opens its prefilled exact editor; Ctrl-A and
        # Ctrl-K replace the suggestion. A still approves only Ground create.
        pipe_input.send_text(f"n\x01\x0b{exact_name}\ra")
        result = run_ground_shell(
            interpret=proposal_with_new_context,
            apply=lambda value: applied.append(value) or "created",
            validate_new_context=validate_name,
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]
    assert validated == [exact_name]
    assert result.selected_context_names == ()
    assert result.new_context_name_hint == exact_name
    assert exact_name not in format_proposal_command(result.proposal)
    assert any(
        "CONTEXT PLAN · NEW ONLY · NOT BOUND" in value
        and f"NEW CONTEXT · {exact_name} · LOCAL ONLY · NOT CREATED"
        in value
        for value in rendered
    )


def test_suggested_new_context_can_be_accepted_without_retyping():
    validated: list[str] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("n\ra")
        result = run_ground_shell(
            interpret=proposal_with_new_context,
            apply=lambda _value: "created",
            validate_new_context=lambda name: validated.append(name) or name,
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert validated == ["ticker-rule-examples"]
    assert result.new_context_name_hint == "ticker-rule-examples"


def test_context_name_editor_rejects_newline_before_exact_acceptance():
    validated: list[str] = []

    with create_pipe_input() as pipe_input:
        # Ctrl-J is consumed in the exact-name field; the unchanged suggestion
        # remains valid and can then be accepted with Enter.
        pipe_input.send_text("n\n\ra")
        result = run_ground_shell(
            interpret=proposal_with_new_context,
            apply=lambda _value: "created",
            validate_new_context=lambda name: validated.append(name) or name,
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert validated == ["ticker-rule-examples"]
    assert result.new_context_name_hint == "ticker-rule-examples"


def test_suggested_new_context_can_be_ignored_before_ground_approval():
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        # NEW?, ADD, then the explicit no-Context path. A remains separate.
        pipe_input.send_text("\x1b[B\x1b[Bfa")
        result = run_ground_shell(
            interpret=proposal_with_new_context,
            apply=lambda value: applied.append(value) or "created",
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert applied == [result.proposal]
    assert result.selected_context_names == ()
    assert result.new_context_name_hint is None


def test_add_new_context_row_opens_a_blank_exact_name_editor():
    validated: list[str] = []
    exact_name = "test/ground/ticker-rule-examples"

    with create_pipe_input() as pipe_input:
        # MAIN, ALTERNATIVE, then the direct ADD row.
        pipe_input.send_text(f"\x1b[B\x1b[Bn{exact_name}\ra")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda _value: "created",
            validate_new_context=lambda name: validated.append(name) or name,
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert validated == [exact_name]
    assert result.selected_context_names == ()
    assert result.new_context_name_hint == exact_name


def test_escape_collapses_new_context_editor_before_cancelling():
    validated: list[str] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("n\x1bq")
        result = run_ground_shell(
            interpret=proposal_with_new_context,
            apply=lambda _value: pytest.fail("must not apply"),
            validate_new_context=lambda name: validated.append(name) or name,
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert validated == []
    assert result.new_context_name_hint is None


def test_new_context_agent_comment_does_not_transmit_local_names():
    seen: list[str] = []

    def interpret(text: str):
        seen.append(text)
        return proposal_with_new_context(text)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "n\tUse the repository test namespace.\rq"
        )
        result = run_ground_shell(
            interpret=interpret,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Find a reusable ticker Rule.",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert len(seen) == 2
    assert "COMMENT (FOR THE AGENT)" in seen[1]
    assert "Use the repository test namespace." in seen[1]
    assert "ticker-rule-examples" not in seen[1]
    assert result.new_context_name_hint is None


def test_invalid_direct_new_context_name_stays_uncreated():
    applied: list[GroundShellProposal] = []

    def reject_name(name: str) -> str:
        raise ValueError(f"Invalid Context name: {name}")

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\x1b[Bn../escape\r\x1bq")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda value: applied.append(value),
            validate_new_context=reject_name,
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.new_context_name_hint is None
    assert applied == []


def test_finished_context_selection_can_be_reopened_before_approval():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            " f"
            "\x1b[Z\x1b[Z\x1b[Z"
            "f"
            "\x1b[B"
            " "
            "f"
            "a"
        )
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda _value: "created",
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "APPLIED"
    assert result.selected_context_names == (
        "temp/task-1",
        "temp/task-1-atomized",
    )


def test_ask_context_selection_can_be_reopened_from_input_mode():
    suggestions = proposal_with_contexts().context_suggestions

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            " f"
            "\t\t"
            "f"
            "\x1b[B"
            " "
            "f"
            "\x1b"
        )
        result = run_ground_shell(
            interpret=lambda _text: Ask(
                kind="ASK",
                understanding="Two local Context names may be relevant.",
                question="What roles should they eventually have?",
                context_suggestions=suggestions,
            ),
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.selected_context_names == (
        "temp/task-1",
        "temp/task-1-atomized",
    )


def test_context_candidates_auto_focus_with_a_visible_frame_title(monkeypatch):
    original_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert panes["CONTEXTS"].frame.title == "CONTEXTS"
    assert callable(panes["CONTEXTS"].frame.container.style)
    assert (
        "class:memcommit.focused"
        in panes["CONTEXTS"].frame.container.style()
    )
    assert panes["GOAL"].frame.title == "GOAL"
    assert panes["CHAT"].frame.title == "CHAT"


def test_page_scroll_does_not_toggle_or_apply_a_different_context(monkeypatch):
    original_renderer = ground_shell_module.render_ground_contexts_pane
    rendered: list[str] = []
    applied: list[GroundShellProposal] = []

    def capturing_renderer(*args, **kwargs):
        value = original_renderer(*args, **kwargs)
        rendered.append(value)
        return value

    monkeypatch.setattr(
        ground_shell_module,
        "render_ground_contexts_pane",
        capturing_renderer,
    )

    with create_pipe_input() as pipe_input:
        # PageDown scrolls without moving the semantic cursor. Space checks
        # provider MAIN?, F finishes locally, then Escape discards it.
        pipe_input.send_text("\x1b[6~ f\x1b")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda value: applied.append(value),
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert applied == []
    assert result.selected_context_names == ("temp/task-1",)
    assert any(
        "SELECTED CONTEXTS · 1 · NOT BOUND" in value
        and "MAIN · temp/task-1 · SELECTED · NOT BOUND" in value
        for value in rendered
    )
    assert not any(
        "MAIN · temp/task-1-atomized · SELECTED" in value
        for value in rendered
    )


def test_context_page_down_moves_the_focused_viewport(monkeypatch):
    original_builder = ground_shell_module.build_scrollable_text_pane
    panes = {}

    def capturing_builder(title, *args, **kwargs):
        pane = original_builder(title, *args, **kwargs)
        panes[title] = pane
        return pane

    monkeypatch.setattr(
        ground_shell_module,
        "build_scrollable_text_pane",
        capturing_builder,
    )

    with create_pipe_input() as pipe_input:
        # Context suggestions auto-focus CONTEXTS. PageDown must browse that
        # viewport without moving the semantic candidate cursor.
        pipe_input.send_text("\x1b[6~\x1b")
        result = run_ground_shell(
            interpret=proposal_with_contexts,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Review Task 1.",
            context_catalog_count=2,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    contexts = panes["CONTEXTS"].text_area
    marker_row = contexts.text[: contexts.text.index("› ")].count("\n")
    assert result.status == "CANCELLED"
    assert contexts.buffer.document.cursor_position_row > marker_row


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


def test_initial_name_check_renders_thinking_and_escape_discards_late_result(
    monkeypatch,
):
    original_renderer = ground_shell_module.render_ground_contexts_pane
    thinking_cycle_rendered = threading.Event()
    interpreter_started = threading.Event()
    release_interpreter = threading.Event()
    feeder_errors: list[Exception] = []
    applied: list[GroundShellProposal] = []
    rendered: list[str] = []
    thinking_labels: list[str] = []
    expected_cycle = ["THINKING.", "THINKING..", "THINKING…"]

    monkeypatch.setattr(
        ground_shell_module,
        "_THINKING_INTERVAL_SECONDS",
        0.01,
    )

    def capturing_renderer(*args, **kwargs):
        value = original_renderer(*args, **kwargs)
        rendered.append(value)
        if kwargs.get("discovery_in_progress"):
            label = next(
                line.split(" ·", 1)[0]
                for line in value.splitlines()
                if line.startswith("THINKING")
            )
            if not thinking_labels or thinking_labels[-1] != label:
                thinking_labels.append(label)
            if thinking_labels[-3:] == expected_cycle:
                thinking_cycle_rendered.set()
        return value

    monkeypatch.setattr(
        ground_shell_module,
        "render_ground_contexts_pane",
        capturing_renderer,
    )

    def blocked_interpreter(text: str):
        interpreter_started.set()
        if not release_interpreter.wait(2):
            raise RuntimeError("test did not release interpreter")
        return proposal(text)

    with create_pipe_input() as pipe_input:
        def close_while_thinking() -> None:
            try:
                if not interpreter_started.wait(2):
                    raise AssertionError("interpreter did not start")
                if not thinking_cycle_rendered.wait(2):
                    raise AssertionError("thinking cycle was not rendered")
                pipe_input.send_text("\x1b")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)
                release_interpreter.set()

        feeder = threading.Thread(target=close_while_thinking)
        feeder.start()
        started_at = time.monotonic()
        result = _run_ground_shell(
            interpret=blocked_interpreter,
            apply=lambda value: applied.append(value),
            initial_request="Separate Task 1 into usable Contexts.",
            current_context_name="test/update/from",
            context_catalog_count=16,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        elapsed = time.monotonic() - started_at
        renders_after_exit = len(rendered)
        release_interpreter.set()
        time.sleep(0.05)
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert result.status == "CANCELLED"
    assert elapsed < 0.5
    assert applied == []
    assert thinking_labels[:3] == expected_cycle
    assert len(rendered) == renders_after_exit
    assert any(
        "CURRENT · test/update/from · STATE POINTER ONLY · NOT BOUND" in value
        and (
            "THINKING. · ranking 16 Context locator names; "
            "CURRENT stays local"
        )
        in value
        for value in rendered
    )


def test_completed_name_check_replaces_thinking_with_one_main_and_alternatives(
    monkeypatch,
):
    original_renderer = ground_shell_module.render_ground_contexts_pane
    ready_rendered = threading.Event()
    feeder_errors: list[Exception] = []
    rendered: list[str] = []
    candidates = (
        GroundShellContextSuggestion(
            context_name="temp/task-1",
            role="MAIN",
            reason="Strongest Task 1 name match.",
        ),
        GroundShellContextSuggestion(
            context_name="temp/task-1-atomized",
            role="ALTERNATIVE",
            reason="Processed Task 1 variant.",
        ),
    )

    def capturing_renderer(*args, **kwargs):
        value = original_renderer(*args, **kwargs)
        rendered.append(value)
        if kwargs.get("discovery_complete") and "MAIN?" in value:
            ready_rendered.set()
        return value

    monkeypatch.setattr(
        ground_shell_module,
        "render_ground_contexts_pane",
        capturing_renderer,
    )

    def interpreted(text: str):
        base = proposal(text)
        return Propose(
            kind=base.kind,
            understanding=base.understanding,
            question=base.question,
            ground_name=base.ground_name,
            goal=base.goal,
            context_suggestions=candidates,
        )

    with create_pipe_input() as pipe_input:
        def close_after_result() -> None:
            try:
                if not ready_rendered.wait(2):
                    raise AssertionError("completed Context check was not rendered")
                pipe_input.send_text("\x1b")
            except Exception as error:  # pragma: no cover - assertion relay
                feeder_errors.append(error)

        feeder = threading.Thread(target=close_after_result)
        feeder.start()
        result = _run_ground_shell(
            interpret=interpreted,
            apply=lambda _value: pytest.fail("must not apply"),
            initial_request="Separate Task 1 into usable Contexts.",
            current_context_name="test/update/from",
            context_catalog_count=16,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
        feeder.join(timeout=2)

    assert feeder_errors == []
    assert not feeder.is_alive()
    assert result.status == "CANCELLED"
    final = next(value for value in rendered if "MAIN?" in value)
    assert "THINKING" not in final
    assert final.count("MAIN?") == 1
    assert "MAIN? · temp/task-1 · NOT BOUND" in final
    assert "ALTERNATIVE · temp/task-1-atomized · NOT BOUND" in final


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


def test_failed_direct_goal_apply_discards_inline_draft_before_refine():
    exact_goal = "Build a separated Task 1 campus wiki."
    interpret_calls = []
    apply_calls = []

    def interpret(text: str):
        interpret_calls.append(text)
        return Propose(
            kind="PROPOSE",
            understanding="The directly edited Goal is exact.",
            question="Approve creating this Ground?",
            ground_name="task-1-campus-wiki",
            goal=exact_goal,
        )

    def fail(value: GroundShellProposal):
        apply_calls.append(value)
        raise RuntimeError("CLI result is unknown")

    with create_pipe_input() as pipe_input:
        # After A reaches the apply boundary, E must not reconstruct the same
        # direct proposal. Escape closes from ordinary input without another
        # provider or apply call.
        pipe_input.send_text(f"\te{exact_goal}\rae\x1b")
        result = run_ground_shell(
            interpret=interpret,
            apply=fail,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result.status == "CANCELLED"
    assert result.proposal is None
    assert len(interpret_calls) == 1
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


def test_nonempty_catalog_requires_one_main_at_shell_boundary():
    applied: list[GroundShellProposal] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("Choose a Context.\rq")
        result = run_ground_shell(
            interpret=proposal,
            apply=lambda value: applied.append(value),
            context_catalog_count=1,
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
