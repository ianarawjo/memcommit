from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.commands.resolution_workbench_shell as resolution_shell_module
from memcommit.commands.semantic_detail_renderer import (
    semantic_detail_block_fragments,
)
from memcommit.commands.resolution_workbench_shell import (
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _session_items_fragments,
    render_resolution_workbench_snapshot,
    resolution_report_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
    run_resolution_workbench_shell,
    session_todo_view,
)
from memcommit.impact_controller import ImpactController
from memcommit.memory_diff import MemoryChange
from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation
from memcommit.result_workbench import ResultRef


def _item(
    uid: str,
    *,
    options: tuple[ResolutionOption, ...] = (),
) -> ResolutionItem:
    return ResolutionItem(
        uid=uid,
        kind="ISSUE",
        status="OPEN",
        priority="REQUIRED",
        title=f"Issue {uid}",
        summary=f"Summary for {uid}.",
        question="Which answer should be used?" if options else "",
        options=options,
    )


def _view(
    *items: ResolutionItem,
    revision: str = "revision-1",
    capabilities: frozenset[str] = frozenset({"SUBMIT_ITEM"}),
    accept_enabled: bool = False,
) -> ResolutionWorkbenchView:
    return ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="meld-1",
        revision=revision,
        title="Resolve Meld",
        route="incoming -> baseline",
        status="OPEN",
        metrics=(),
        overview="Review the current resolution.",
        list_label="ISSUES",
        items=items,
        empty_message="No issues.",
        results_label="CHANGES",
        results=(),
        capabilities=capabilities,  # type: ignore[arg-type]
        accept_enabled=accept_enabled,
    )


def _run(
    view: ResolutionWorkbenchView,
    keys: str,
    *,
    navigation: ResolutionNavigation | None = None,
):
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        return run_resolution_workbench_shell(
            view,
            navigation=navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )


def test_nested_arrow_and_enter_option_selection_returns_uid_bound_comment():
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the baseline."),
            ResolutionOption("replace", "Replace", "Use the incoming text."),
        ),
    )

    # Enter expands the issue, Down moves within its nested option list, and
    # Enter chooses that option. Tab then opens the issue-scoped composer.
    action = _run(
        _view(item),
        "\r\x1b[B\r\tUse the incoming wording.\r",
    )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "issue-1"
    assert action.option_uid == "replace"
    assert action.comment == "Use the incoming wording."


def test_save_location_card_emits_an_exact_destination_change_before_apply():
    view = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )
    with create_pipe_input() as pipe_input:
        # Open the Report, move from its title through understanding, review
        # set, and results to SAVE LOCATION, then edit the exact Context name.
        pipe_input.send_text("\r\x1b[B\x1b[B\x1b[B\x1b[B\r\x15task-3/severed-final\r")
        action = run_resolution_workbench_shell(
            view,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(value="task-3/severed"),
        )

    assert action.kind == "CHANGE_DESTINATION"
    assert action.destination == "task-3/severed-final"


@pytest.mark.parametrize("numeric_key", ["1", "2", "3", "4", "5"])
def test_numeric_shortcuts_are_inert(numeric_key: str):
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the baseline."),
            ResolutionOption("replace", "Replace", "Use the incoming text."),
        ),
    )

    # A number typed while browsing neither opens an issue nor chooses an
    # option. The following Enter only expands the issue, so no option is
    # attached to the later comment action.
    action = _run(
        _view(item),
        f"{numeric_key}\r\tExplain without choosing.\r",
    )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "issue-1"
    assert action.option_uid is None
    assert action.comment == "Explain without choosing."


@pytest.mark.parametrize("back_key", ["\x1b", "\x7f"])
def test_back_key_collapses_detail_before_close(back_key: str):
    navigation = ResolutionNavigation()
    view = _view(_item("issue-1"))

    # Escape and Backspace both unwind detail. Q then closes the workbench.
    action = _run(view, f"\r{back_key}q", navigation=navigation)

    assert action.kind == "CLOSE"
    assert navigation.selected_item_uid == "issue-1"
    assert navigation.expanded_item_uid is None


def test_escape_from_composer_discards_unsent_comment_and_closes():
    action = _run(
        _view(_item("issue-1")),
        "\tan unfinished issue comment\x1b",
    )

    assert action.kind == "CLOSE"
    assert action.item_uid is None
    assert action.option_uid is None
    assert action.comment == ""


def test_render_syncs_selection_when_supplier_replaces_the_complete_list():
    navigation = ResolutionNavigation()
    initial = _view(_item("a"), _item("b"), _item("c"))
    resolution_workbench_fragments(initial, navigation)
    navigation.move_item(initial, 1)

    replacement = _view(
        _item("new"),
        _item("c"),
        _item("b"),
        _item("a"),
        revision="revision-2",
    )
    rendered = "".join(
        text
        for _style, text in resolution_workbench_fragments(
            replacement,
            navigation,
        )
    )

    assert navigation.selected_item_uid == "b"
    assert "›  3. [REQUIRED] Issue b" in rendered


@pytest.mark.parametrize(
    ("capabilities", "accept_enabled"),
    [
        (frozenset(), False),
        (frozenset({"ACCEPT"}), False),
    ],
)
def test_accept_key_cannot_cross_capability_or_readiness_gate(
    capabilities: frozenset[str],
    accept_enabled: bool,
):
    action = _run(
        _view(
            capabilities=capabilities,
            accept_enabled=accept_enabled,
        ),
        "aq",
    )

    assert action.kind == "CLOSE"


def test_accept_key_returns_action_only_when_adapter_enables_it():
    action = _run(
        _view(
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=True,
        ),
        "a",
    )

    assert action.kind == "ACCEPT"


def test_snapshot_neutralizes_terminal_controls_across_adapter_text():
    view = ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="meld-1",
        revision="revision-1",
        title="Resolve\x1b[31m",
        route="incoming \u202e-> baseline",
        status="OPEN\u2066",
        metrics=(),
        overview="Line one\nLine two\x1b[32m\u202ereversed",
        list_label="ISSUES",
        items=(
            ResolutionItem(
                uid="issue-1",
                kind="ISSUE",
                status="OPEN",
                priority="REQUIRED",
                title="Unsafe\x1b[33m title",
                summary="Summary\u202ethat cannot spoof layout.",
            ),
        ),
        empty_message="No issues.",
        results_label="CHANGES",
        results=(
            ResolutionResult(
                uid="result-1",
                marker="+",
                label="ADD",
                text="Result\x1b[2J text",
            ),
        ),
    )

    snapshot = render_resolution_workbench_snapshot(view)

    assert "Line one\nLine two�[32m�reversed" in snapshot
    assert "Resolve�[31m" in snapshot
    assert "Result�[2J text" in snapshot
    assert "\x1b" not in snapshot
    assert "\u202e" not in snapshot
    assert "\u2066" not in snapshot


def test_split_report_contains_conflicts_and_whole_set_strategies():
    view = _view(_item("a"), _item("b"))
    strategies = (
        ResolutionGlobalStrategy("Preserve all", "PRESERVE_ALL"),
        ResolutionGlobalStrategy("Choose broadest", "SUBMIT_ALL", "Broad."),
    )

    fragments = resolution_report_fragments(
        view,
        strategies=strategies,
        focused_section=3,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "ISSUES · 2" in rendered
    assert "── ISSUE 1 · Issue a ──" in rendered
    assert "ISSUE 2 · Issue b" in rendered
    assert "RESOLVE ALL · WHOLE-SET STRATEGY" in rendered
    assert "Choose broadest" in rendered


def test_items_hanging_wrap_tracks_the_supplied_frame_width():
    item = replace(
        _item("a"),
        title=(
            "A long review target whose visible title must wrap inside the "
            "Items frame instead of being clipped at a fixed character limit"
        ),
    )
    view = _view(item)

    rendered = "".join(
        text
        for _style, text in _session_items_fragments(
            view,
            selected_index=1,
            focused=True,
            content_width=48,
            report_label="Complete Meld report",
        )
    )
    lines = rendered.splitlines()
    item_lines = lines[1:]

    assert "…" not in rendered
    assert len(item_lines) > 1
    assert all(len(line) <= 48 for line in item_lines)
    assert item_lines[0].index("A long") == item_lines[1].index("visible")


def test_issue_detail_is_compact_and_section_navigable():
    item = ResolutionItem(
        uid="a",
        kind="CONFLICT",
        status="OPEN",
        priority="REQUIRED",
        title="Question paradigm",
        summary="The choice changes the proposal.",
        question="Which form should be used?",
        options=(ResolutionOption("one", "First", "Use the first form."),),
        blocks=(
            ResolutionDetailBlock(
                "EVIDENCE",
                "advisor1 · #1\nA supporting Memory.",
            ),
        ),
    )
    view = _view(item)
    navigation = ResolutionNavigation(selected_item_uid="a")

    rendered = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            view,
            navigation,
            focused_section=1,
        )
    )

    assert "REVIEW DETAIL · 1/1 · REQUIRED · CONFLICT · OPEN" in rendered
    assert "REVIEW SET · REQUIRED 1 · OPTIONAL 0" in rendered
    assert "WHY THIS NEEDS REVIEW" in rendered
    assert "OPERATION DETAIL" in rendered
    assert "QUESTION\n" in rendered
    assert "╭─ OPTIONS " in rendered
    assert "2. Other direction" in rendered
    assert "EVIDENCE\n" in rendered
    assert "advisor1 · #1" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "Review the current resolution." not in rendered


def test_options_card_explains_entry_and_uses_blue_focus_with_checkmark():
    item = _item(
        "option-guidance",
        options=(
            ResolutionOption("one", "First", "Use the first form."),
            ResolutionOption("two", "Second", "Use the second form."),
        ),
    )
    view = _view(item)
    navigation = ResolutionNavigation(selected_item_uid=item.uid)
    navigation.toggle_detail(view)

    waiting = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=4,
    )
    assert "Enter to choose an option" in "".join(text for _style, text in waiting)
    assert not any("› ○" in text for _style, text in waiting)

    navigation.selected_option_uid = "one"
    active = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=2,
        option_navigation_active=True,
    )
    assert any(
        style == "class:option-card.focused" and "› ✓ 1. First" in text
        for style, text in active
    )
    active_text = "".join(text for _style, text in active)
    assert "╭─ ✓ 1. First" not in active_text
    focused_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:option-card.focused"
    )
    assert focused_style.underline is True
    neutral_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:option-card"
    )
    assert neutral_style.underline is False
    selected_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:option-card.selected"
    )
    assert selected_style.color == "8bd5ff"
    assert selected_style.underline is False
    reference_style = RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
        "class:reference"
    )
    assert reference_style.color == "c6a0f6"
    reference_fragments = semantic_detail_block_fragments(
        heading="RESULT",
        text="Proposed result.",
        refs=(ResultRef("memory", "result-1"),),
    )
    assert any(style == "class:reference" for style, _text in reference_fragments)


def test_focused_bottom_detail_card_anchors_after_its_closing_border():
    item = ResolutionItem(
        uid="bottom-card",
        kind="CONFLICT",
        status="OPEN",
        priority="REQUIRED",
        title="Opening-length rule",
        summary="Choose one rule.",
        blocks=(
            ResolutionDetailBlock("EVIDENCE", "A long evidence explanation."),
            ResolutionDetailBlock("RELATIONS", "R1 · CONFLICT"),
            ResolutionDetailBlock("PROPOSED RESULT", "Use the reviewed rule."),
        ),
    )
    fragments = resolution_viewer_fragments(
        _view(item),
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=3,
    )
    proposed_start = next(
        index
        for index, (_style, text) in enumerate(fragments)
        if "PROPOSED RESULT" in text
    )
    proposed_content = next(
        index
        for index, (_style, text) in enumerate(
            fragments[proposed_start:],
            proposed_start,
        )
        if "Use the reviewed rule." in text
    )
    anchor = max(
        index
        for index, (style, _text) in enumerate(fragments)
        if style == "[SetCursorPosition]"
    )

    assert anchor > proposed_content


def test_split_detail_submits_a_supplied_option_with_an_optional_comment():
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the first direction."),
            ResolutionOption("replace", "Replace", "Use the second direction."),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Open conflict 1, move to OPTIONS, Enter its nested navigation,
        # select the first option, then submit an empty optional comment.
        pipe_input.send_text("\x1b[B\r\x1b[B\x1b[B\r\rc\r")
        action = run_resolution_workbench_shell(
            _view(item),
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "issue-1"
    assert action.option_uid == "keep"
    assert action.comment == ""


def test_split_detail_submits_other_direction_without_a_fabricated_option():
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the first direction."),
            ResolutionOption("replace", "Replace", "Use the second direction."),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Open conflict 1, enter OPTIONS, move beyond both supplied options to
        # Other direction, and submit a free-form resolution.
        pipe_input.send_text(
            "\x1b[B\r\x1b[B\x1b[B\r\x1b[B\x1b[B\rUse a staged combination instead.\r"
        )
        action = run_resolution_workbench_shell(
            _view(item),
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ITEM"
    assert action.item_uid == "issue-1"
    assert action.option_uid is None
    assert action.comment == "Use a staged combination instead."


def test_inline_other_direction_keeps_current_detail_visible():
    item = replace(
        _item(
            "issue-1",
            options=(ResolutionOption("keep", "Keep", "Keep this direction."),),
        ),
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    heading="MEMORIES IN CONFLICT",
                    classification="CONFLICT",
                    reason_heading="WHY THESE MEMORIES CONFLICT",
                    reason="They prescribe incompatible actions.",
                    sources=(
                        ResolutionIssueSource(
                            label="SOURCE 1",
                            context_name="advisor/a",
                            memory_uid="memory-1",
                            content="Use the first direction.",
                        ),
                    ),
                ),
            ),
            prompt_heading="RESOLUTION QUESTION",
            options_heading="PROPOSED RESOLUTIONS",
            other_option_label="Different resolution",
            response_heading="ENTER A RESPONSE",
        ),
    )
    optional_item = replace(
        _item("optional"),
        priority="HELPFUL",
    )
    view = _view(item, optional_item)
    navigation = ResolutionNavigation(selected_item_uid=item.uid)
    navigation.toggle_detail(view)

    fragments = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=3,
        option_navigation_active=True,
        other_direction_focused=True,
        other_direction_editing=True,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "Issue issue-1" in rendered
    assert "PROPOSED RESOLUTIONS" in rendered
    assert "REVIEW SET · REQUIRED 1 · OPTIONAL 1" in rendered
    assert any(
        style == "class:viewer-section" and "RESOLUTION QUESTION" in text
        for style, text in fragments
    )
    assert any(
        style == "class:detail-card.focused" and "PROPOSED RESOLUTIONS" in text
        for style, text in fragments
    )
    assert "Editing below · Enter save · Ctrl-J newline" in rendered
    assert "◇ OTHER DIRECTION" not in rendered


def test_inline_response_enter_saves_and_returns_without_closing_workbench():
    item = _item(
        "issue-1",
        options=(ResolutionOption("keep", "Keep", "Keep this direction."),),
    )
    saved: list[tuple[str, str | None, str]] = []

    with create_pipe_input() as pipe_input:
        # Open the item, enter its response editor with Tab, save with Enter,
        # then close from the restored Viewer focus.
        pipe_input.send_text("\r\tAdditional guidance.\rq")
        action = run_resolution_workbench_shell(
            _view(item),
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert saved == [("issue-1", None, "Additional guidance.")]


def test_actionable_response_is_focusable_and_opens_inline_with_enter():
    item = replace(
        _item(
            "issue-1",
            options=(ResolutionOption("keep", "Keep", "Keep this direction."),),
        ),
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    heading="MEMORIES IN CONFLICT",
                    classification="CONFLICT",
                    reason_heading="WHY THESE MEMORIES CONFLICT",
                    reason="They prescribe incompatible actions.",
                    sources=(
                        ResolutionIssueSource(
                            label="SOURCE 1",
                            context_name="advisor/a",
                            memory_uid="memory-1",
                            content="Use the first direction.",
                        ),
                    ),
                ),
            ),
            prompt_heading="RESOLUTION QUESTION",
            options_heading="PROPOSED RESOLUTIONS",
            other_option_label="Different resolution",
            response_heading="LEGACY RESPONSE INSTRUCTION",
        ),
    )
    saved: list[tuple[str, str | None, str]] = []

    with create_pipe_input() as pipe_input:
        # Open the item, move through Classification, Source, Why, Decision,
        # and Response, then save the inline field.
        pipe_input.send_text(
            "\x1b[B\r\x1b[B\x1b[B\x1b[B\x1b[B\x1b[B\rA separate response.\rq"
        )
        action = run_resolution_workbench_shell(
            _view(item),
            split_viewer_items=True,
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert saved == [("issue-1", None, "A separate response.")]


def test_split_viewer_section_navigation_selects_matching_item_row():
    navigation = ResolutionNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        # Tab focuses Viewer. Four Down presses move title -> understanding ->
        # item-list heading -> issue a -> issue b, which must synchronize the
        # lower row.
        pipe_input.send_text("\t\x1b[B\x1b[B\x1b[B\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            split_viewer_items=True,
            global_strategies=(
                ResolutionGlobalStrategy("Preserve all", "PRESERVE_ALL"),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert navigation.selected_item_uid == "b"


def test_atomize_detail_down_uses_shared_viewer_arrow_acceleration(monkeypatch):
    class TwoSectionAccelerator:
        def move(self, direction, *, app, move_one):
            for _ in range(2):
                move_one(direction)
                app.invalidate()

        def reset(self):
            pass

    monkeypatch.setattr(
        resolution_shell_module,
        "NavigationAccelerator",
        TwoSectionAccelerator,
    )
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                heading="SOURCE MEMORY",
                sources=(
                    ResolutionIssueSource(
                        label="SOURCE 1",
                        context_name="practice/description",
                        memory_uid="12345678-1111-1111-1111-111111111111",
                        content="A long source Memory " * 20,
                        ordinal=1,
                    ),
                ),
                classification="COMPOSITE · 5 CHILDREN",
                reason_heading="WHY THIS SPLIT",
                reason="The claims are independently revisable.",
            ),
        ),
        prompt_heading="REVIEW QUESTION",
        options_heading="PROPOSED RESPONSES",
        other_option_label="Different direction",
        response_heading="COMMENT OR ENTER A DIFFERENT DIRECTION",
    )
    item = ResolutionItem(
        uid="atomize-split",
        kind="ATOMIZE_SPLIT",
        status="OPEN",
        priority="REVIEW",
        title="ATOMIZE SPLIT",
        summary="The source contains several claims.",
        blocks=(
            ResolutionDetailBlock(
                heading="PROPOSED CHILDREN",
                text="",
                memory_rows=tuple(
                    ResolutionMemoryRow(
                        ordinal=index,
                        content=f"Proposed child {index}.",
                        evidence=(f"Source span {index}.",),
                    )
                    for index in range(1, 6)
                ),
            ),
        ),
        issue_presentation=presentation,
    )
    view = replace(
        _view(item),
        operation="ATOMIZE",
        title="MEM ATOMIZE",
    )
    workbench_navigation = SessionWorkbenchNavigation()

    first_line = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=1,
        content_width=40,
    )
    second_line = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=2,
        content_width=40,
    )
    first_focused = "".join(
        text for style, text in first_line if style == "class:memory-object.focused"
    )
    second_focused = "".join(
        text for style, text in second_line if style == "class:memory-object.focused"
    )
    assert first_focused
    assert second_focused
    assert first_focused != second_focused

    opened = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=0,
        content_width=40,
    )
    assert any(
        style == "class:viewer-section" and "CLASSIFICATION" in text
        for style, text in opened
    )
    assert not any(
        style in {"class:viewer-section", "class:detail-card.focused"}
        and "ATOMIZE SPLIT" in text
        for style, text in opened
    )

    with create_pipe_input() as pipe_input:
        # Move from REPORT to the split, open it, then one held-arrow pulse
        # starts on Classification and then reaches the second wrapped Source
        # Memory line.
        pipe_input.send_text("\x1b[B\r\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == (
        "ITEM:atomize-split:EVIDENCE:0:SOURCE:0:"
        "12345678-1111-1111-1111-111111111111:LINE:1"
    )


def test_proposed_memories_are_individual_stops_with_expandable_evidence():
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                heading="SOURCE MEMORY",
                sources=(
                    ResolutionIssueSource(
                        label="SOURCE 1",
                        context_name="notes",
                        memory_uid="source-1",
                        content="A composite source.",
                    ),
                ),
                classification="COMPOSITE · 2 CHILDREN",
                reason_heading="WHY THIS SPLIT",
                reason="The claims can change independently.",
            ),
        ),
        prompt_heading="REVIEW QUESTION",
        options_heading="PROPOSED RESPONSES",
        other_option_label="Different direction",
        response_heading="RESPONSE",
    )
    rows = (
        ResolutionMemoryRow(1, "First proposed Memory.", ("first evidence",)),
        ResolutionMemoryRow(2, "Second proposed Memory.", ("second evidence",)),
    )
    item = replace(
        _item("split"),
        kind="ATOMIZE_SPLIT",
        blocks=(ResolutionDetailBlock("PROPOSED CHILDREN", "", memory_rows=rows),),
        issue_presentation=presentation,
    )
    view = _view(item)
    navigation = ResolutionNavigation(selected_item_uid=item.uid)

    collapsed = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=3,
    )
    collapsed_text = "".join(text for _style, text in collapsed)
    assert "first evidence" not in collapsed_text
    assert "second evidence" not in collapsed_text
    assert any(
        style == "class:memory-object.focused" and "[1] First proposed Memory." in text
        for style, text in collapsed
    )

    second = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=4,
    )
    assert any(
        style == "class:memory-object.focused" and "[2] Second proposed Memory." in text
        for style, text in second
    )

    expanded = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=3,
        expanded_memory_section_uid="ITEM:split:BLOCK:0:MEMORY:1",
    )
    expanded_text = "".join(text for _style, text in expanded)
    assert "first evidence" in expanded_text
    assert "second evidence" not in expanded_text

    workbench_navigation = SessionWorkbenchNavigation()
    with create_pipe_input() as pipe_input:
        # Open the item, reach child 1, expand and collapse its evidence, then
        # Down must move to child 2 rather than skipping the Memory list.
        pipe_input.send_text("\x1b[B\r\x1b[B\x1b[B\x1b[B\r\x1b\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == "ITEM:split:BLOCK:0:MEMORY:2"


def test_enter_on_report_moves_focus_from_items_into_viewer():
    navigation = ResolutionNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        # Enter opens the selected REPORT row in Viewer. Three Down presses
        # move through title, understanding, and the list heading to issue a.
        # If focus had remained in ITEMS, the same keys would select issue b.
        pipe_input.send_text("\r\x1b[B\x1b[B\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            split_viewer_items=True,
            global_strategies=(
                ResolutionGlobalStrategy("Preserve all", "PRESERVE_ALL"),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert navigation.selected_item_uid == "a"


def test_item_arrow_selection_immediately_previews_the_matching_viewer():
    item_navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\x1b[Z\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            navigation=item_navigation,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.row_index == 2
    assert workbench_navigation.viewer_row_index == 2
    assert item_navigation.selected_item_uid == "b"


def test_up_on_the_report_row_replaces_a_stale_item_viewer():
    item_navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Open item a, return focus to Items, then Up selects REPORT. A second
        # Up at the boundary must still align Viewer with REPORT.
        pipe_input.send_text("\x1b[B\r\t\x1b[A\x1b[Aq")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            navigation=item_navigation,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "items"
    assert workbench_navigation.row_index == 0
    assert workbench_navigation.viewer_row_index == 0
    assert item_navigation.expanded_item_uid is None


def test_tab_from_open_viewer_visits_items_before_todo():
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Open the first item in Viewer, then one Tab must focus the visually
        # adjacent Items frame rather than skipping directly to To Do.
        pipe_input.send_text("\x1b[B\r\tq")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "items"


def test_second_tab_from_open_viewer_reaches_todo_after_items():
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\t\tq")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "todo"


def test_apply_section_uses_stable_identity_after_review_items_and_impact():
    view = replace(
        _view(
            _item("a"),
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=True,
        ),
        operation="UPDATE",
        title="Review staged Update",
    )
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Viewer order is title, understanding, review-items, item, results,
        # impact, one impact Memory, then apply. The controller must retain
        # APPLY by identity rather than by the numeric offset.
        pipe_input.send_text("\t" + "\x1b[B" * 7 + "q")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            impact_controller=ImpactController.from_resolution(
                view,
                title="IMPACT · UPDATE",
                summary="Exact staged effects.",
            ),
            workbench_navigation=workbench_navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == "REPORT:ACTION"
    # The report may describe the action, but the actionable control now lives
    # in the separate To Do frame and therefore has no synthetic Items row.
    assert workbench_navigation.row_index == 0


def test_enter_on_impact_memory_opens_rationale_without_leaving_report():
    view = replace(
        _view(
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=True,
        ),
        results=(
            ResolutionResult(
                uid="result-1",
                marker="+",
                label="KEEP",
                text="Retained Memory.",
                reason="The rule requires retention.",
                rules=("Retain required information.",),
            ),
        ),
    )
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Items → Viewer, then title → understanding → items → impact → Memory.
        pipe_input.send_text("\t" + "\x1b[B" * 4 + "\rq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            impact_controller=ImpactController.from_resolution(
                view,
                title="IMPACT · UPDATE",
                summary="Exact staged effects.",
            ),
            workbench_navigation=workbench_navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "viewer"
    assert workbench_navigation.section_uid == "REPORT:IMPACT:result-1"


def test_expanded_located_update_impact_renders_rule_and_reason_neutrally():
    view = replace(
        _view(
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=True,
        ),
        operation="UPDATE",
        artifact_uid="update-1",
        title="Review staged Update",
    )
    memory_uid = "12345678-1111-1111-1111-111111111111"
    controller = ImpactController.from_memory_changes(
        operation="UPDATE",
        artifact_uid=view.artifact_uid,
        revision=view.revision,
        title="IMPACT · UPDATE",
        summary="Exact staged effects.",
        changes=(
            MemoryChange(
                marker="~",
                treatment="EDIT",
                location="target/context",
                memory_uid=memory_uid,
                before="Earlier content.",
                after="Updated content.",
                reason="The source evidence changed.",
                rules=("Prefer the current evidence.",),
            ),
        ),
    )

    fragments = resolution_report_fragments(
        view,
        impact_controller=controller,
        expanded_impact_section_uid=f"REPORT:IMPACT:{memory_uid}",
    )

    rule_style = next(style for style, text in fragments if "RULE ·" in text)
    reason_style = next(style for style, text in fragments if "WHY ·" in text)
    rendered = "".join(text for _style, text in fragments)
    assert "Prefer the current evidence." in rendered
    assert "The source evidence changed." in rendered
    assert rule_style == ""
    assert reason_style == ""

    workbench_navigation = SessionWorkbenchNavigation()
    with create_pipe_input() as pipe_input:
        # Items → Viewer, then title → understanding → items → impact → the
        # located Update Memory. Enter must expand its rationale in place.
        pipe_input.send_text("\t" + "\x1b[B" * 4 + "\rq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            impact_controller=controller,
            workbench_navigation=workbench_navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == f"REPORT:IMPACT:{memory_uid}"


def test_review_and_apply_stages_each_choice_before_one_whole_set_turn():
    first = _item(
        "a",
        options=(ResolutionOption("a-1", "First A", "Use answer A."),),
    )
    second = _item(
        "b",
        options=(ResolutionOption("b-1", "First B", "Use answer B."),),
    )
    policy = ResolutionGlobalStrategy(
        "Preserve unresolved",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )

    with create_pipe_input() as pipe_input:
        # Select the first option in each conflict, then open the final review
        # row and submit the combined resolution turn.
        pipe_input.send_text("\x1b[B\r\x1b[B\x1b[B\r\r\t\x1b[B\r\x1b[B\x1b[B\r\r\t\t\r")
        action = run_resolution_workbench_shell(
            _view(first, second, capabilities=frozenset({"SUBMIT_ALL"})),
            split_viewer_items=True,
            global_strategies=(policy,),
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert "Issue a: Choose this reading: Use answer A." in action.comment
    assert "Issue b: Choose this reading: Use answer B." in action.comment


def test_todo_reopens_a_required_conflict_after_selection_cancellation():
    item = _item(
        "a",
        options=(ResolutionOption("a-1", "First A", "Use answer A."),),
    )
    policy = ResolutionGlobalStrategy(
        "Preserve unresolved",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )

    with create_pipe_input() as pipe_input:
        # The second Enter on the same option clears it. To Do must reopen that
        # required conflict instead of applying a whole-set fallback over it.
        pipe_input.send_text("\x1b[B\r\x1b[B\x1b[B\r\r\r\t\rq")
        action = run_resolution_workbench_shell(
            _view(item, capabilities=frozenset({"SUBMIT_ALL"})),
            split_viewer_items=True,
            global_strategies=(policy,),
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"


def test_todo_derives_conflict_then_incorporate_then_apply_states():
    conflict = replace(_item("a"), kind="CONTENT_CONFLICT")
    optional = replace(
        _item("b"),
        kind="CONTENT_CONFLICT",
        priority="HELPFUL",
    )
    open_view = _view(conflict, optional)
    policy = ResolutionGlobalStrategy(
        "Preserve unresolved distinctions",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )

    pending = session_todo_view(
        open_view,
        {},
        review_and_apply=True,
        read_only=False,
    )
    assert pending.kind == "RESOLVE"
    assert pending.label == "Resolve 1 required conflict"
    assert pending.detail.startswith("1 optional review may be skipped.")
    assert pending.unresolved_item_uids == ("a",)
    pending_report = "".join(
        text
        for _style, text in resolution_report_fragments(
            open_view,
            strategies=(policy,),
            review_and_apply=True,
        )
    )
    assert "RESOLVE\n" in pending_report
    assert "INCORPORATE RESPONSES" not in pending_report

    incorporate = session_todo_view(
        open_view,
        {"a": (None, "Use the local wording.")},
        review_and_apply=True,
        read_only=False,
    )
    assert incorporate.kind == "INCORPORATE RESPONSES"
    assert incorporate.unresolved_item_uids == ()
    assert incorporate.detail.startswith("1 optional review may be skipped.")
    assert "No Context or Memory changes" in incorporate.detail
    incorporate_report = "".join(
        text
        for _style, text in resolution_report_fragments(
            open_view,
            strategies=(policy,),
            drafts={"a": (None, "Use the local wording.")},
            review_and_apply=True,
        )
    )
    assert "INCORPORATE RESPONSES" in incorporate_report

    apply_view = replace(
        open_view,
        accept_enabled=True,
        capabilities=frozenset({"ACCEPT"}),
    )
    apply = session_todo_view(
        apply_view,
        {"a": (None, "Use the local wording.")},
        review_and_apply=True,
        read_only=False,
    )
    assert apply.kind == "APPLY CHANGES"
    assert apply.detail.startswith(
        "1 optional review remains open and will be skipped."
    )

    complete = session_todo_view(
        open_view,
        {"a": (None, "Use the local wording.")},
        review_and_apply=False,
        read_only=False,
        whole_set_available=False,
    )
    assert complete.kind == "COMPLETE"
    assert complete.label == "Required review is complete"
    assert complete.detail.startswith("1 optional review remains open.")


def test_todo_exposes_adapter_declared_apply_as_is_without_required_gate():
    unresolved = replace(
        _item("a"),
        priority="HIGH",
        obligation="OPTIONAL",
    )
    review = replace(
        _item("b"),
        priority="REVIEW",
        role="OPTIONAL_REVIEW",
        obligation="OPTIONAL",
    )
    view = replace(
        _view(unresolved, review),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
        unresolved_at_apply_count=1,
    )

    todo = session_todo_view(
        view,
        {},
        review_and_apply=True,
        read_only=False,
    )

    assert todo.kind == "APPLY AS IS"
    assert todo.label == "Apply Meld as is"
    assert todo.detail == (
        "1 unresolved finding will be recorded at apply. "
        "1 optional review remains open. "
        "Enter to apply the exact current proposal as is. Recovery: mem undo."
    )
    report = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
        )
    )
    assert "APPLY AS IS · MELD" in report


def test_saved_response_exposes_inline_incorporation_below_response():
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                heading="SOURCE MEMORY",
                classification="COMPOSITE",
                reason_heading="WHY THIS SPLIT",
                reason="The claims can change independently.",
                sources=(
                    ResolutionIssueSource(
                        label="SOURCE 1",
                        context_name="notes",
                        memory_uid="memory-a",
                        content="A composite source Memory.",
                    ),
                ),
            ),
        ),
        prompt_heading="REVIEW QUESTION",
        options_heading="PROPOSED RESPONSES",
        other_option_label="Different direction",
        response_heading="RESPONSE",
    )
    item = replace(
        _item("a"),
        issue_presentation=presentation,
        response_state="ANSWERED",
        response_text="Keep the causal scope with the final child.",
    )
    policy = ResolutionGlobalStrategy(
        "Keep unanswered optional findings as analyzed",
        "SUBMIT_ALL",
        "Keep unanswered optional findings as analyzed.",
    )
    inline = SessionTodoView(
        "INCORPORATE RESPONSES",
        "Incorporate saved responses",
        "Enter to create a revised complete proposal. No Context or Memory changes will be applied yet.",
    )
    rendered = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            _view(item, capabilities=frozenset({"SUBMIT_ALL"})),
            ResolutionNavigation(selected_item_uid=item.uid),
            inline_action=inline,
        )
    )
    assert rendered.index("RESPONSE") < rendered.index("INCORPORATE RESPONSES")

    with create_pipe_input() as pipe_input:
        # Open the item, jump to its final inline incorporation section, and
        # run the same whole-set action as To Do.
        pipe_input.send_text("\x1b[B\r\x1b[F\r")
        action = run_resolution_workbench_shell(
            _view(item, capabilities=frozenset({"SUBMIT_ALL"})),
            split_viewer_items=True,
            global_strategies=(policy,),
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert "Keep the causal scope with the final child." in action.comment


def test_todo_treats_an_explicitly_cleared_durable_answer_as_open():
    option = ResolutionOption("option-a", "Answer A", "Use answer A.")
    answered = replace(
        _item("a", options=(option,)),
        response_state="ANSWERED",
        selected_option_uid="option-a",
    )

    todo = session_todo_view(
        _view(answered),
        {"a": (None, "")},
        review_and_apply=True,
        read_only=False,
    )

    assert todo.kind == "RESOLVE"
    assert todo.unresolved_item_uids == ("a",)


def test_read_only_todo_can_return_an_explicit_apply_handoff():
    handoff = SessionTodoView(
        "APPLY?",
        "Continue to Meld Apply",
        "Open the owning workflow; no change yet.",
    )

    with create_pipe_input() as pipe_input:
        # Items is the initial hub; Shift-Tab reaches To Do directly.
        pipe_input.send_text("\x1b[Z\r")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            split_viewer_items=True,
            read_only=True,
            read_only_handoff=handoff,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "HANDOFF"
