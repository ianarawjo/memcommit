from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.layout import to_container
from prompt_toolkit.output import DummyOutput
from memcommit.adapters.console.coordination.command_review.model import CommandReview

import memcommit.adapters.console.terminal.components.resolution.session_shell as resolution_shell_package
import memcommit.adapters.console.terminal.components.resolution.session_shell.presentation as resolution_presentation_module
import memcommit.adapters.console.terminal.components.resolution.session_shell.runtime as resolution_runtime_package
import memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.keymap.navigation_bindings as resolution_navigation_bindings_module
import memcommit.adapters.console.terminal.components.resolution.session_shell.runtime.runner as resolution_runtime_module
from memcommit.adapters.console.terminal.components.semantic_viewer.detail import (
    semantic_detail_block_fragments,
)
from memcommit.adapters.console.terminal.core.prompt_toolkit_theme import (
    MEMCOMMIT_TUI_STYLE,
)
from memcommit.adapters.console.terminal.components.resolution.session_shell import (
    RESOLUTION_WORKBENCH_STYLE,
    ResolutionDestination,
    ResolutionGlobalStrategy,
    SessionTodoView,
    _impact_arrow_expansion,
    _seeded_report_lines,
    _session_items_fragments,
    render_resolution_workbench_snapshot,
    resolution_report_fragments,
    resolution_review_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
    run_resolution_workbench_shell,
    session_review_action_view,
    session_todo_view,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionDetailBlock,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionOverviewSection,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
)
from memcommit.adapters.console.terminal.components.responses.model import ResponseDraft
from memcommit.application.capabilities.reviewing.result_workbench import ResultRef


def test_session_shell_package_preserves_public_owner_identity():
    assert (
        resolution_shell_package.render_resolution_workbench_snapshot
        is resolution_presentation_module.render_resolution_workbench_snapshot
    )
    assert (
        resolution_shell_package.run_resolution_workbench_shell
        is resolution_runtime_package.run_resolution_workbench_shell
        is resolution_runtime_module.run_resolution_workbench_shell
    )


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


def test_resolution_viewer_y_and_Y_share_focused_and_complete_copy_contract(
    monkeypatch,
):
    copied: list[tuple[str, str]] = []

    def fake_copy(text: str, *, success_message: str, writer=None):
        del writer
        copied.append((text, success_message))
        return type("Receipt", (), {"message": "COPIED"})()

    monkeypatch.setattr(
        resolution_navigation_bindings_module,
        "copy_plain_text",
        fake_copy,
    )

    action = _run(_view(_item("issue-1")), "yYq")

    assert action.kind == "CLOSE"
    assert copied[0][1] == "focused semantic unit"
    assert "Issue issue-1" in copied[0][0]
    assert copied[1][1] == "complete current document"
    assert "Resolve Meld" in copied[1][0]
    assert "Review the current resolution" in copied[1][0]


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


def test_save_location_frame_emits_an_exact_destination_change_before_apply():
    view = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )
    with create_pipe_input() as pipe_input:
        # SAVE LOCATION is the visible frame after Items. Enter opens its own
        # one-line editor without moving authoring into Viewer.
        pipe_input.send_text("\t\t\r\x15task-3/severed-final\r")
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


def test_save_location_editor_can_choose_parent_above_direct_input():
    view = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )
    with create_pipe_input() as pipe_input:
        # Direct input remains the initial editor focus. Up enters the shared
        # parent tree, Up moves from the nearest current parent to practice,
        # and Enter re-parents while preserving the exact leaf name.
        pipe_input.send_text("\t\t\r\x1b[A\x1b[A\r\r")
        action = run_resolution_workbench_shell(
            view,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(
                value="task-1/description/atomized",
                state="NOT CREATED",
                context_names=("practice", "task-1/description"),
                current_context="practice",
            ),
        )

    assert action.kind == "CHANGE_DESTINATION"
    assert action.destination == "practice/atomized"


@pytest.mark.parametrize("back_key", ("\x1b", "\x7f"))
def test_save_location_parent_tree_back_keys_restore_compact_frame(back_key):
    navigation = SessionWorkbenchNavigation()
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\r\x1b[A" + back_key + "q")
        action = run_resolution_workbench_shell(
            _view(),
            workbench_navigation=navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(
                value="task-1/description/atomized",
                context_names=("task-1/description",),
            ),
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == "save_location"


def test_report_places_context_locations_above_overview_and_apply_last():
    view = replace(
        _view(
            replace(_item("optional"), priority="OPTIONAL"),
            capabilities=frozenset({"ACCEPT"}),
            accept_enabled=True,
        ),
        context_locations=(
            ResolutionContextLocation("SOURCE", "practice/source"),
            ResolutionContextLocation(
                "OUTPUT",
                "practice/output",
                "NOT CREATED",
            ),
        ),
    )
    rendered = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            review_and_apply=True,
        )
    )

    assert "CONTEXT LOCATIONS" in rendered
    assert "SOURCE · practice/source" in rendered
    assert "OUTPUT · practice/output · NOT CREATED" in rendered
    assert "incoming -> baseline" not in rendered
    assert rendered.index("CONTEXT LOCATIONS") < rendered.index("OVERVIEW")
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "SAVE LOCATION" not in rendered
    assert "APPLY CONFIRMATION" in rendered


def test_report_action_focus_includes_its_explanatory_paragraph():
    view = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )

    fragments = resolution_report_fragments(
        view,
        focused_section=2,
        review_and_apply=True,
    )

    assert any(
        style == "class:viewer-section" and "APPLY CONFIRMATION" in text
        for style, text in fragments
    )
    assert any(
        style == "class:viewer-body.focused" and "Enter to confirm" in text
        for style, text in fragments
    )


def test_report_focuses_operation_declared_overview_units_not_the_group():
    view = replace(
        _view(),
        overview_sections=(
            ResolutionOverviewSection("understood", "UNDERSTOOD", "Source meaning."),
            ResolutionOverviewSection("changed", "CHANGED", "One split."),
            ResolutionOverviewSection("unresolved", "UNRESOLVED", "One referent."),
        ),
    )

    for index, heading in enumerate(("UNDERSTOOD", "CHANGED", "UNRESOLVED")):
        fragments = resolution_report_fragments(view, focused_section=index)
        assert "WHAT MEM UNDERSTOOD" not in "".join(text for _style, text in fragments)
        assert any(
            style == "class:viewer-section" and heading in text
            for style, text in fragments
        )
        assert not any(
            style == "class:viewer-section" and "WHAT MEM UNDERSTOOD" in text
            for style, text in fragments
        )
        body_style = next(
            style
            for style, text in fragments
            if {
                "UNDERSTOOD": "Source meaning.",
                "CHANGED": "One split.",
                "UNRESOLVED": "One referent.",
            }[heading]
            in text
        )
        assert body_style == "class:viewer-body.focused"
        assert (
            RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(body_style).bold is False
        )


def test_operation_can_keep_overview_body_neutral_within_the_same_stop():
    view = replace(
        _view(),
        overview_sections=(
            ResolutionOverviewSection(
                "heading-only",
                "ASSESSMENT",
                "Keep this explanatory prose neutral.",
                focus_body=False,
            ),
        ),
    )

    fragments = resolution_report_fragments(view, focused_section=0)

    assert any(
        style == "class:viewer-section" and "ASSESSMENT" in text
        for style, text in fragments
    )
    assert any(
        style == "class:viewer-body" and "Keep this explanatory prose" in text
        for style, text in fragments
    )


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
        focused_section=1,
    )
    rendered = "".join(text for _style, text in fragments)

    assert "ISSUES · 2" in rendered
    assert "ISSUE 1 · Issue a" in rendered
    assert "── ISSUE 1 · Issue a ──" not in rendered
    assert any(
        style == "class:report-label.focused" and "ISSUE 1 · Issue a" in text
        for style, text in fragments
    )
    assert (
        RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str("class:report-label").bold
        is True
    )
    assert (
        RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
            "class:report-label.focused"
        ).bold
        is True
    )
    assert not any(
        style == "class:viewer-section" and "ISSUES · 2" in text
        for style, text in fragments
    )
    assert any(
        style == "class:report-label" and "ISSUES · 2" in text
        for style, text in fragments
    )
    assert any(
        style == "class:report-label" and "ISSUE 2 · Issue b" in text
        for style, text in fragments
    )
    assert "ISSUE 2 · Issue b" in rendered
    assert "RESOLVE ALL · WHOLE-SET STRATEGY" in rendered
    assert "Choose broadest" in rendered


def test_report_focuses_a_finding_title_summary_and_question_as_one_block():
    item = _item(
        "a",
        options=(ResolutionOption("reading", "Reading", "Use this reading."),),
    )
    view = _view(item)

    fragments = resolution_report_fragments(view, focused_section=1)

    assert any(
        style == "class:report-label.focused" and "ISSUE 1 · Issue a" in text
        for style, text in fragments
    )
    assert any(
        style == "class:viewer-body.focused" and "Summary for a." in text
        for style, text in fragments
    )
    assert any(
        style == "class:viewer-body.focused" and "QUESTION · Which answer" in text
        for style, text in fragments
    )
    assert (
        RESOLUTION_WORKBENCH_STYLE.get_attrs_for_style_str(
            "class:viewer-body.focused"
        ).bold
        is False
    )


def test_report_navigation_moves_once_per_complete_finding():
    first = _item(
        "a",
        options=(ResolutionOption("reading", "Reading", "Use this reading."),),
    )
    second = _item(
        "b",
        options=(ResolutionOption("reading", "Reading", "Use this reading."),),
    )
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Overview → complete finding A → complete finding B. A long finding's
        # title, explanation, and question never become separate arrow stops.
        pipe_input.send_text("\x1b[B" * 2 + "q")
        action = run_resolution_workbench_shell(
            _view(first, second),
            split_viewer_items=True,
            workbench_navigation=navigation,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert navigation.section_uid == "ITEM:b"
    assert navigation.row_index == 2


def test_operation_can_hide_an_inapplicable_generic_results_section():
    view = replace(_view(_item("a")), show_results=False)

    fragments = resolution_report_fragments(view, read_only=True)
    seeded = _seeded_report_lines(
        view,
        "MEM COMPARE · SAVED",
        (),
        False,
        True,
    )

    assert "CHANGES" not in "".join(text for _style, text in fragments)
    assert not any(line.startswith("CHANGES") for line in seeded)


def test_exact_results_heading_stays_bold_at_rest_and_in_focus():
    view = replace(_view(_item("a")), results_label="EXACT RESULTS")

    resting = resolution_report_fragments(view, focused_section=1, read_only=True)
    focused = resolution_report_fragments(view, focused_section=2, read_only=True)

    assert any(
        style == "class:report-label" and "EXACT RESULTS · 0" in text
        for style, text in resting
    )
    assert any(
        style == "class:report-label.focused" and "EXACT RESULTS · 0" in text
        for style, text in focused
    )


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
    assert " OPTIONS\n" in rendered
    assert "┌" in rendered
    assert "2. Other direction" in rendered
    assert "EVIDENCE\n" in rendered
    assert "advisor1 · #1" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "Review the current resolution." not in rendered


def test_options_use_common_meld_boxes_with_blue_focus_and_checkmark():
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
    assert not any(
        marker in text for _style, text in waiting for marker in ("○", "●", "◇")
    )

    navigation.selected_option_uid = "one"
    active = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=2,
        option_navigation_active=True,
    )
    assert any(
        style == "class:memcommit.choice.border.focused" and "┏" in text
        for style, text in active
    )
    assert (
        "class:memcommit.choice.active.focused",
        "✓ 1. First",
    ) in active
    active_text = "".join(text for _style, text in active)
    assert not any(marker in active_text for marker in ("○", "●", "◇"))
    focused_style = MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
        "class:memcommit.choice.active.focused"
    )
    assert focused_style.bold is True
    selected_style = MEMCOMMIT_TUI_STYLE.get_attrs_for_style_str(
        "class:memcommit.choice.active"
    )
    assert selected_style.bgcolor == "8bd5ff"
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
        # Open conflict 1, Tab into RESPONSES, select the already-focused first
        # choice, then move through choice 2 to the separate Response box.
        pipe_input.send_text("\t\x1b[B\r\t\r\x1b[B\x1b[B\r\r")
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


def test_split_detail_submits_response_without_a_fabricated_option():
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the first direction."),
            ResolutionOption("replace", "Replace", "Use the second direction."),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Open conflict 1, enter RESPONSES on choice 1, move through choice 2
        # into the separate Response box, and submit a free-form resolution.
        pipe_input.send_text(
            "\t\x1b[B\r\t\x1b[B\x1b[B\rUse a staged combination instead.\r"
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
                    group_heading="MEMORIES IN CONFLICT",
                    sources_heading="SOURCE MEMORIES",
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
    assert not any(
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
                    group_heading="MEMORIES IN CONFLICT",
                    sources_heading="SOURCE MEMORIES",
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
        # Open the item, Tab into RESPONSES, move through its supplied choice
        # to the separate Response box, then save and close from the frame.
        pipe_input.send_text("\t\x1b[B\r\t\x1b[B\rA separate response.\rq")
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


def test_split_responses_composes_the_shared_input_as_a_separate_inner_box(
    monkeypatch,
):
    built_inputs = []
    frames = []
    original_builder = resolution_runtime_module.build_framed_multiline_input
    original_frame = resolution_runtime_module.Frame

    def recording_builder(*args, **kwargs):
        component = original_builder(*args, **kwargs)
        built_inputs.append(component)
        return component

    def recording_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        frames.append(frame)
        return frame

    monkeypatch.setattr(
        resolution_runtime_module,
        "build_framed_multiline_input",
        recording_builder,
    )
    monkeypatch.setattr(resolution_runtime_module, "Frame", recording_frame)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        run_resolution_workbench_shell(
            _view(_item("issue-1")),
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    response_input = built_inputs[0]
    responses_frame = next(frame for frame in frames if frame.title == "RESPONSES")
    assert response_input.frame.title == "RESPONSE"
    assert to_container(response_input.frame) in responses_frame.body.children


def test_split_viewer_section_navigation_selects_matching_item_row():
    navigation = ResolutionNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        # Viewer starts focused. Four Down presses move title -> understanding
        # -> item-list heading -> issue a -> issue b, synchronizing the row.
        pipe_input.send_text("\x1b[B\x1b[B\x1b[B\x1b[Bq")
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


def test_atomize_detail_down_uses_semantic_memory_stops_with_acceleration(
    monkeypatch,
):
    class TwoSectionAccelerator:
        def move(self, direction, *, app, move_one):
            for _ in range(2):
                move_one(direction)
                app.invalidate()

        def reset(self):
            pass

    monkeypatch.setattr(
        resolution_runtime_module,
        "NavigationAccelerator",
        TwoSectionAccelerator,
    )
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                group_heading="",
                sources_heading="SOURCE MEMORY",
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

    focused_memory = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=1,
        content_width=40,
    )
    focused_reason = resolution_viewer_fragments(
        view,
        ResolutionNavigation(selected_item_uid=item.uid),
        focused_section=2,
        content_width=40,
    )
    memory_text = "".join(
        text for style, text in focused_memory if style == "class:memory-object.focused"
    )
    assert memory_text.count("source Memory") == 20
    assert ("class:block-heading", "\n SOURCE MEMORY\n") in focused_memory
    assert any(
        style == "class:viewer-section" and "SOURCE 1 · FROM" in text
        for style, text in focused_memory
    )
    assert not any(
        style == "class:viewer-section" and text == "\n SOURCE MEMORY\n"
        for style, text in focused_memory
    )
    assert any(
        style == "class:viewer-section" and "WHY THIS SPLIT" in text
        for style, text in focused_reason
    )

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
    assert any(
        style == "class:viewer-body.focused" and "COMPOSITE · 5 CHILDREN" in text
        for style, text in opened
    )
    assert not any(
        style in {"class:viewer-section", "class:detail-card.focused"}
        and "ATOMIZE SPLIT" in text
        for style, text in opened
    )

    with create_pipe_input() as pipe_input:
        # Move from REPORT to the split, open it, then one held-arrow pulse
        # starts on Classification, visits the whole Source Memory once, and
        # then reaches Why. Terminal wrapping must not add focus stops.
        pipe_input.send_text("\t\x1b[B\r\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.section_uid == ("ITEM:atomize-split:EVIDENCE:0:REASON")


def test_proposed_memories_are_individual_stops_with_expandable_evidence():
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                group_heading="",
                sources_heading="SOURCE MEMORY",
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
        style == "class:memory-object.focused"
        and "MEMORY 1 · First proposed Memory." in text
        for style, text in collapsed
    )

    second = resolution_viewer_fragments(
        view,
        navigation,
        focused_section=4,
    )
    assert any(
        style == "class:memory-object.focused"
        and "MEMORY 2 · Second proposed Memory." in text
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
        pipe_input.send_text("\t\x1b[B\r\x1b[B\x1b[B\x1b[B\r\x1b\x1b[Bq")
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


def test_split_workbench_starts_with_report_focused_in_viewer():
    navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        # Identity and collection chrome are skipped: one Down press moves
        # directly from the overview to issue a without entering from Items.
        pipe_input.send_text("\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            navigation=navigation,
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            global_strategies=(
                ResolutionGlobalStrategy("Preserve all", "PRESERVE_ALL"),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "viewer"
    assert navigation.selected_item_uid == "a"


def test_item_arrow_selection_immediately_previews_the_matching_viewer():
    item_navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\x1b[B\r\t\x1b[Bq")
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
        # Open item a, return focus to Items, then Up selects REPORT and aligns
        # Viewer immediately. Another Up now belongs to shared frame-boundary
        # traversal and would intentionally return focus to Viewer.
        pipe_input.send_text("\t\x1b[B\r\t\x1b[Aq")
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
        pipe_input.send_text("\t\x1b[B\r\tq")
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
        pipe_input.send_text("\t\x1b[B\r\t\tq")
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


def test_save_location_frame_joins_visible_tab_order_before_todo():
    workbench_navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\tq")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            workbench_navigation=workbench_navigation,
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(
                value="task-3/severed",
                state="NOT CREATED",
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert workbench_navigation.pane == "save_location"


def test_save_location_editor_keeps_text_keys_local_and_retries_validation():
    validated: list[str] = []

    def validate(value: str) -> None:
        validated.append(value)
        if value != "approved/location":
            raise ValueError("Choose the approved location.")

    with create_pipe_input() as pipe_input:
        # The q in the invalid candidate is ordinary editor text, not Close.
        # Failed validation retains the editor for an exact corrected retry.
        pipe_input.send_text("\t\t\r\x15draftq/location\r\x15approved/location\r")
        action = run_resolution_workbench_shell(
            _view(_item("a")),
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(
                value="draft/location",
                state="NOT CREATED",
                validate=validate,
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CHANGE_DESTINATION"
    assert action.destination == "approved/location"
    assert validated == ["draftq/location", "approved/location"]


def test_save_location_frame_remains_between_items_and_todo_in_final_review():
    navigation = SessionWorkbenchNavigation()
    view = _view(
        _item("a"),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )

    with create_pipe_input() as pipe_input:
        # A opens final review in Viewer; two Tabs follow the still-visible
        # layout through Items to Save Location, before To Do.
        pipe_input.send_text("a\t\tq")
        action = run_resolution_workbench_shell(
            view,
            workbench_navigation=navigation,
            split_viewer_items=True,
            review_and_apply=True,
            destination=ResolutionDestination(
                value="result/final",
                state="NOT CREATED",
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == "save_location"


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
        # End resolves the last semantic stop by stable identity regardless of
        # how many review, result, or impact sections precede APPLY. Repeated
        # Down now has a separate meaning at the boundary: enter Items.
        pipe_input.send_text("\x1b[Fq")
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
        # Viewer starts at the first declared overview, then moves through
        # items and impact to the focused Memory.
        pipe_input.send_text("\x1b[B" * 2 + "\rq")
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

    collapsed_fragments = resolution_report_fragments(
        view,
        impact_controller=controller,
    )
    collapsed_rendered = "".join(text for _style, text in collapsed_fragments)
    assert "▸ ~ [EDIT]" in collapsed_rendered

    fragments = resolution_report_fragments(
        view,
        impact_controller=controller,
        expanded_impact_section_uid=f"REPORT:IMPACT:{memory_uid}",
    )

    rule_style = next(style for style, text in fragments if "RULE ·" in text)
    reason_style = next(style for style, text in fragments if "WHY ·" in text)
    rendered = "".join(text for _style, text in fragments)
    assert "▾ ~ [EDIT]" in rendered
    assert "Prefer the current evidence." in rendered
    assert "The source evidence changed." in rendered
    assert rule_style == ""
    assert reason_style == ""

    workbench_navigation = SessionWorkbenchNavigation()
    with create_pipe_input() as pipe_input:
        # Viewer moves from the overview through items and impact to the
        # located Update Memory. Right opens, Left closes, and Enter retains
        # its existing toggle behavior.
        pipe_input.send_text("\x1b[B" * 2 + "\x1b[C\x1b[D\rq")
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


def test_expanded_update_impact_comment_revises_the_same_change_draft():
    memory_uid = "12345678-1111-1111-1111-111111111111"
    change = ResolutionItem(
        uid=f"edit:target-context:{memory_uid}",
        kind="EDIT",
        status="PLANNED",
        priority="CHANGE",
        title=f"target/context Memory [{memory_uid}]",
        summary="The source evidence changed.",
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        blocks=(
            ResolutionDetailBlock("OWNER", "Context target/context [target-context]"),
            ResolutionDetailBlock("MEMORY UID", memory_uid),
        ),
        commentable=True,
    )
    view = replace(
        _view(
            change,
            capabilities=frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"}),
            accept_enabled=True,
        ),
        operation="UPDATE",
        artifact_uid="update-1",
        title="Review staged Update",
    )
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
            ),
        ),
    )
    expanded = "".join(
        text
        for _style, text in resolution_report_fragments(
            view,
            impact_controller=controller,
            expanded_impact_section_uid=f"REPORT:IMPACT:{memory_uid}",
        )
    )
    assert "RESPONSE · Press C to comment on this proposed change." in expanded

    saved: list[tuple[str, str | None, str]] = []
    with create_pipe_input() as pipe_input:
        # Move through Viewer to the Impact change, expand it, and comment
        # without detouring through the separate Items detail.
        pipe_input.send_text("\x1b[B" * 3 + "\x1b[CcKeep the date less specific.\rq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            global_strategies=(
                ResolutionGlobalStrategy("Revise from comments", "CUSTOM"),
            ),
            impact_controller=controller,
            draft_saver=lambda uid, option_uid, comment: saved.append(
                (uid, option_uid, comment)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"
    assert saved == [(change.uid, None, "Keep the date less specific.")]


def test_commentable_change_draft_requires_incorporation_before_apply():
    item = replace(
        _item("change"),
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        commentable=True,
    )
    view = _view(
        item,
        capabilities=frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"}),
        accept_enabled=True,
    )

    action = session_review_action_view(
        view,
        {item.uid: ResponseDraft(None, "Remove this proposed change.")},
        whole_set_available=True,
    )

    assert action.kind == "INCORPORATE RESPONSES"
    assert "1 saved change comment" in action.detail


def test_commentable_change_response_is_included_in_revision_turn():
    item = replace(
        _item("change"),
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        commentable=True,
    )
    view = _view(
        item,
        capabilities=frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"}),
        accept_enabled=True,
    )

    with create_pipe_input() as pipe_input:
        # Open the change, Tab to RESPONSES, save one comment, then traverse
        # Responses → Items → To Do. Final review opens at its summary, so
        # End reaches the incorporation action before Enter confirms it.
        pipe_input.send_text(
            "\t\x1b[B\r\t\rRemove this proposed change.\r\t\t\r\x1b[F\r"
        )
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            global_strategies=(
                ResolutionGlobalStrategy("Revise from comments", "CUSTOM"),
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert "Issue change: Response: Remove this proposed change." in (action.comment)


def test_semantic_turn_command_is_built_for_review_and_rebuilt_at_approval():
    item = replace(
        _item("change"),
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        commentable=True,
    )
    view = _view(
        item,
        capabilities=frozenset({"SUBMIT_ITEM", "SUBMIT_ALL", "ACCEPT"}),
        accept_enabled=True,
    )
    reviewed = []

    def command(action):
        reviewed.append(action)
        return CommandReview(
            ("mem", "update", "--comment", action.comment, "--expect-session", "rev-1"),
            ("Replace the staged proposal only.",),
        )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text(
            "\t\x1b[B\r\t\rRemove this proposed change.\r\t\t\r\x1b[F\r"
        )
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            global_strategies=(
                ResolutionGlobalStrategy("Revise from comments", "SUBMIT_ALL"),
            ),
            turn_command_review=command,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert reviewed == [action, action]


def test_final_apply_remains_commandless_when_operation_callback_excludes_it():
    view = replace(
        _view(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    reviewed_kinds: list[str] = []

    def command(action):
        reviewed_kinds.append(action.kind)
        return None

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior="FINAL_REVIEW",
            turn_command_review=command,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "ACCEPT"
    assert reviewed_kinds == ["ACCEPT", "ACCEPT"]


def test_impact_arrows_open_only_the_focused_row_and_close_it_idempotently():
    first = "REPORT:IMPACT:first"
    second = "REPORT:IMPACT:second"

    assert _impact_arrow_expansion(None, first, expand=True) == first
    assert _impact_arrow_expansion(first, second, expand=True) == second
    assert _impact_arrow_expansion(second, second, expand=False) is None
    assert _impact_arrow_expansion(first, second, expand=False) == first
    assert _impact_arrow_expansion(first, None, expand=True) == first


@pytest.mark.parametrize(
    ("kind", "expected"),
    (
        ("RESPONSES", "Responses are stacked · use Up/Down"),
        ("ITEM", "This detail is vertical · use Up/Down"),
        ("REPORT", "This report is vertical · use Up/Down"),
        ("TODO", "This frame has no Left/Right action"),
    ),
)
def test_split_horizontal_noop_explains_the_real_stacked_path(
    kind: str,
    expected: str,
) -> None:
    message = resolution_presentation_module._stacked_horizontal_key_message(kind)

    assert message.startswith(expected)


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
        pipe_input.send_text("\t\x1b[B\r\t\r\t\x1b[B\r\t\r\t\t\r\x1b[F\r")
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


def test_review_and_apply_requires_final_confirmation_and_can_go_back():
    view = replace(
        _view(_item("optional")),
        items=(replace(_item("optional"), obligation="OPTIONAL"),),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )

    with create_pipe_input() as pipe_input:
        # The first Enter only opens Review and Apply. Escape returns to the
        # report without applying, and Q then closes the workbench.
        pipe_input.send_text("\x1b[Z\r\x1bq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"

    final = session_review_action_view(view, {}, whole_set_available=False)
    fragments = resolution_review_fragments(
        view,
        {},
        (),
        0,
        final,
        focused_section=1,
    )
    rendered = "".join(text for _style, text in fragments)
    assert "APPLY CONFIRMATION" in rendered
    assert "APPLY AS IS" in rendered
    assert "Esc/Backspace returns without applying." in rendered
    assert any(
        style == "class:detail-card.focused" and "APPLY AS IS" in text
        for style, text in fragments
    )
    assert any(
        style == "class:detail-card.focused"
        and "Enter to apply the exact current proposal as is" in text
        for style, text in fragments
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Z\r\x1b[F\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "ACCEPT"


def test_no_required_decision_can_start_at_final_approval_and_back_to_report():
    optional = replace(
        _item("optional"),
        obligation="OPTIONAL",
    )
    view = replace(
        _view(optional),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )

    with create_pipe_input() as pipe_input:
        # Direct entry begins at the final-review summary. Down reaches the
        # exact action card and Enter approves it without a preliminary A or
        # To Do traversal.
        pipe_input.send_text("\x1b[B\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior="FINAL_REVIEW",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "ACCEPT"

    with create_pipe_input() as pipe_input:
        # The shortcut changes only the entry surface. Escape still unwinds
        # to the complete report, where Q closes without applying.
        pipe_input.send_text("\x1bq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior="FINAL_REVIEW",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"


def test_legacy_final_review_flag_remains_compatible_during_operation_rollout():
    optional = replace(_item("optional"), obligation="OPTIONAL")
    view = replace(
        _view(optional),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            start_final_review_when_no_required=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "ACCEPT"


def test_required_decision_prevents_direct_final_approval_entry():
    required = _item("required")
    view = replace(
        _view(required),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )

    with create_pipe_input() as pipe_input:
        # An unanswered REQUIRED item must suppress the local auto-accept path;
        # Q proves the ordinary decision workbench remained active.
        pipe_input.send_text("q")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior="AUTO_ACCEPT",
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"


def test_reversible_local_decision_free_proposal_auto_accepts_without_rendering():
    optional = replace(
        _item("optional"),
        obligation="OPTIONAL",
    )
    view = replace(
        _view(optional),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )

    action = run_resolution_workbench_shell(
        view,
        split_viewer_items=True,
        review_and_apply=True,
        decision_free_behavior="AUTO_ACCEPT",
        app_output=DummyOutput(),
        require_tty=False,
    )

    assert action.kind == "ACCEPT"


def test_pending_response_blocks_local_auto_accept_and_requires_incorporation():
    change = replace(
        _item("change"),
        obligation="NONE",
        commentable=True,
    )
    view = replace(
        _view(change),
        capabilities=frozenset({"SUBMIT_ALL", "ACCEPT"}),
        accept_enabled=True,
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            decision_free_behavior="AUTO_ACCEPT",
            global_strategies=(
                ResolutionGlobalStrategy("Revise", "CUSTOM", "Revise proposal."),
            ),
            draft_loader=lambda _uid: (None, "Use narrower wording."),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "CLOSE"


def test_review_after_closing_detail_preserves_its_staged_choice():
    option = ResolutionOption(
        "recommended",
        "Use recommendation",
        "Keep the staged semantic recommendation.",
    )
    answered = replace(
        _item("required", options=(option,)),
        response_state="ANSWERED",
        selected_option_uid=option.uid,
    )
    view = replace(
        _view(answered),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )

    with create_pipe_input() as pipe_input:
        # Inspect the staged answer, return to the report, then cross both
        # explicit review stops. Closing detail must not clear the answer.
        pipe_input.send_text("\t\x1b[B\r\x1ba\x1b[B\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "ACCEPT"


def test_final_review_cards_focus_their_complete_semantic_content():
    view = replace(
        _view(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    action = SessionTodoView(
        "INCORPORATE RESPONSES",
        "Incorporate saved responses",
        "Request one revised complete proposal.",
    )
    strategy = ResolutionGlobalStrategy("Preserve unresolved", "SUBMIT_ALL")

    summary = resolution_review_fragments(view, {}, (strategy,), 0, action, 0)
    policy = resolution_review_fragments(view, {}, (strategy,), 0, action, 1)
    final_action = resolution_review_fragments(view, {}, (strategy,), 0, action, 2)

    assert any(
        style == "class:detail-card.focused"
        and "No staged issue responses yet." in text
        for style, text in summary
    )
    assert any(
        style == "class:detail-card.focused" and "Preserve unresolved" in text
        for style, text in policy
    )
    assert any(
        style == "class:detail-card.focused"
        and "Request one revised complete proposal." in text
        for style, text in final_action
    )


def test_ready_final_review_omits_a_meaningless_zero_response_count():
    view = replace(
        _view(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="CHANGES",
    )

    fragments = resolution_review_fragments(
        view,
        {},
        (),
        0,
        SessionTodoView("APPLY", "Apply proposal", "Apply the reviewed result."),
    )
    rendered = "".join(text for _style, text in fragments)

    assert "No open issue responses remain in the current proposal." in rendered
    assert "RESPONSES · 0/0 ANSWERED" not in rendered
    assert "OPEN REVIEWS · NONE" in rendered


@pytest.mark.parametrize(
    ("entry_keys", "expected_pane", "expected_section"),
    [
        ("\x1b[Z", "todo", None),
        ("\x1b[F", "viewer", "REPORT:ACTION"),
    ],
)
def test_final_review_summary_enter_restores_the_exact_entry_surface(
    entry_keys,
    expected_pane,
    expected_section,
):
    view = replace(
        _view(),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Enter opens final review from the chosen surface; the summary's own
        # Enter returns without applying, and Q then closes the restored view.
        pipe_input.send_text(entry_keys + "\r\rq")
        result = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert result.kind == "CLOSE"
    assert navigation.pane == expected_pane
    if expected_section is not None:
        assert navigation.section_uid == expected_section


@pytest.mark.parametrize("entry_keys", ("\x1b[Z", "\x1b[F"))
def test_todo_and_report_resolve_all_open_the_shared_final_review(entry_keys):
    strategy = ResolutionGlobalStrategy(
        "Preserve every unresolved distinction",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Shift-Tab enters To Do; End targets Report's RESOLVE ALL. Either Enter
        # must open the same non-mutating review instead of merely refocusing
        # Report or redrawing the current surface.
        pipe_input.send_text(entry_keys + "\rq")
        action = run_resolution_workbench_shell(
            _view(capabilities=frozenset({"SUBMIT_ALL"})),
            split_viewer_items=True,
            global_strategies=(strategy,),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == "viewer"
    assert navigation.section_uid == "REVIEW:SUMMARY"


def test_resolve_all_review_uses_its_own_shared_surface_title():
    strategy = ResolutionGlobalStrategy(
        "Preserve every unresolved distinction",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )
    fragments = resolution_review_fragments(
        _view(),
        {},
        (strategy,),
        0,
        SessionTodoView("RESOLVE ALL", strategy.label, strategy.comment),
        review_title="RESOLVE ALL",
    )

    rendered = "".join(text for _style, text in fragments)
    assert "╭─ RESOLVE ALL" in rendered
    assert "Esc/Backspace returns without resolving." in rendered


def test_resolve_all_final_review_runs_only_its_confirmed_strategy():
    strategy = ResolutionGlobalStrategy(
        "Preserve every unresolved distinction",
        "SUBMIT_ALL",
        "Preserve every unresolved distinction.",
    )

    with create_pipe_input() as pipe_input:
        # To Do Enter opens review, End reaches its final action, and only the
        # second Enter returns the operation-authored whole-set action.
        pipe_input.send_text("\x1b[Z\r\x1b[F\r")
        action = run_resolution_workbench_shell(
            _view(capabilities=frozenset({"SUBMIT_ALL"})),
            split_viewer_items=True,
            global_strategies=(strategy,),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "SUBMIT_ALL"
    assert action.comment == "Preserve every unresolved distinction."


def test_final_review_hides_viewer_title_and_focuses_top_summary(monkeypatch):
    view = replace(
        _view(_item("optional")),
        items=(replace(_item("optional"), obligation="OPTIONAL"),),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    frames = []
    original_frame = resolution_runtime_module.Frame

    def recording_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        frames.append(frame)
        return frame

    monkeypatch.setattr(resolution_runtime_module, "Frame", recording_frame)
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # Shift-Tab reaches To Do. Enter opens final review at the top summary
        # instead of leaving keyboard focus on the To Do handoff below it.
        pipe_input.send_text("\x1b[Z\rq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == "viewer"
    assert navigation.section_uid == "REVIEW:SUMMARY"
    assert any(frame.title == "" for frame in frames)


@pytest.mark.parametrize(
    ("navigation_keys", "expected_pane"),
    [
        ("\t", "items"),
        ("\t\t", "todo"),
        ("\t\t\t", "viewer"),
        ("\x1b[Z", "todo"),
        ("\x1b[Z\x1b[Z", "items"),
        ("\x1b[Z\x1b[Z\x1b[Z", "viewer"),
    ],
)
def test_final_review_tab_order_visits_viewer_items_todo_without_closing_review(
    monkeypatch,
    navigation_keys,
    expected_pane,
):
    view = replace(
        _view(_item("optional")),
        items=(replace(_item("optional"), obligation="OPTIONAL"),),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    frames = []
    original_frame = resolution_runtime_module.Frame

    def recording_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        frames.append(frame)
        return frame

    monkeypatch.setattr(resolution_runtime_module, "Frame", recording_frame)
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # A opens final review at Viewer. Forward traversal is 1→2→3→1;
        # reverse traversal is 1→3→2→1, matching visible cyclic order.
        pipe_input.send_text("a" + navigation_keys + "q")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == expected_pane
    if expected_pane == "items":
        assert navigation.row_index == 0
    assert any(frame.title == "" for frame in frames)


def test_final_review_down_crosses_from_action_to_items_without_closing_review(
    monkeypatch,
):
    view = replace(
        _view(_item("optional")),
        items=(replace(_item("optional"), obligation="OPTIONAL"),),
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
        accept_mode="AS_IS",
    )
    frames = []
    original_frame = resolution_runtime_module.Frame

    def recording_frame(*args, **kwargs):
        frame = original_frame(*args, **kwargs)
        frames.append(frame)
        return frame

    monkeypatch.setattr(resolution_runtime_module, "Frame", recording_frame)
    navigation = SessionWorkbenchNavigation()

    with create_pipe_input() as pipe_input:
        # A opens final review at its summary. End reaches APPLY AS IS, and the
        # next Down crosses the Viewer boundary into Items without activating
        # or discarding the reviewed confirmation surface.
        pipe_input.send_text("a\x1b[F\x1b[Bq")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
            workbench_navigation=navigation,
        )

    assert action.kind == "CLOSE"
    assert navigation.pane == "items"
    assert navigation.row_index == 0
    assert navigation.section_uid == "REVIEW:ACTION"
    assert any(frame.title == "" for frame in frames)


def test_review_and_apply_can_authorize_one_compound_atomize_action():
    item = replace(
        _item("answered"),
        obligation="OPTIONAL",
        response_state="ANSWERED",
        response_text="Keep the reviewed causal scope.",
    )
    view = replace(
        _view(item),
        operation="ATOMIZE",
        capabilities=frozenset({"SUBMIT_ALL", "INCORPORATE_AND_APPLY"}),
    )
    policy = ResolutionGlobalStrategy(
        "Keep unanswered optional findings as analyzed",
        "SUBMIT_ALL",
        "Keep unanswered optional findings as analyzed.",
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Z\r\x1b[F\r")
        action = run_resolution_workbench_shell(
            view,
            split_viewer_items=True,
            global_strategies=(policy,),
            review_and_apply=True,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert action.kind == "INCORPORATE_AND_APPLY"
    assert "Keep the reviewed causal scope." in action.comment


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
        # Open the conflict, Tab into Responses, then Enter twice on its first
        # choice so the second activation clears it. Traversing through Items
        # to To Do must reopen that required conflict rather than apply a
        # whole-set fallback over it.
        pipe_input.send_text("\t\x1b[B\r\t\r\r\t\t\rq")
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
        {"a": ResponseDraft(None, "Use the local wording.")},
        review_and_apply=True,
        read_only=False,
    )
    assert incorporate.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(
            open_view,
            {"a": ResponseDraft(None, "Use the local wording.")},
            whole_set_available=True,
        ).kind
        == "INCORPORATE RESPONSES"
    )
    assert incorporate.unresolved_item_uids == ()
    assert incorporate.detail == (
        "INCORPORATE RESPONSES is available. Enter to confirm the decided state."
    )
    incorporate_report = "".join(
        text
        for _style, text in resolution_report_fragments(
            open_view,
            strategies=(policy,),
            drafts={"a": ResponseDraft(None, "Use the local wording.")},
            review_and_apply=True,
        )
    )
    assert "APPLY CONFIRMATION" in incorporate_report

    apply_view = replace(
        open_view,
        accept_enabled=True,
        capabilities=frozenset({"ACCEPT"}),
    )
    apply = session_todo_view(
        apply_view,
        {"a": ResponseDraft(None, "Use the local wording.")},
        review_and_apply=True,
        read_only=False,
    )
    assert apply.kind == "REVIEW AND APPLY"
    assert (
        session_review_action_view(
            apply_view,
            {"a": ResponseDraft(None, "Use the local wording.")},
            whole_set_available=True,
        ).kind
        == "APPLY"
    )

    complete = session_todo_view(
        open_view,
        {"a": ResponseDraft(None, "Use the local wording.")},
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

    assert todo.kind == "REVIEW AND APPLY"
    final_action = session_review_action_view(view, {}, whole_set_available=True)
    assert final_action.kind == "APPLY AS IS"
    assert final_action.label == "Apply Meld as is"
    assert final_action.detail == (
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
    assert "APPLY CONFIRMATION" in report


def test_saved_response_uses_response_frame_and_todo_incorporation():
    presentation = ResolutionIssuePresentation(
        evidence=(
            ResolutionIssueEvidence(
                group_heading="",
                sources_heading="SOURCE MEMORY",
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
    rendered = "".join(
        text
        for _style, text in resolution_viewer_fragments(
            _view(item, capabilities=frozenset({"SUBMIT_ALL"})),
            ResolutionNavigation(selected_item_uid=item.uid),
            include_response_sections=False,
        )
    )
    assert "RESPONSE" not in rendered
    assert "INCORPORATE RESPONSES" not in rendered

    with create_pipe_input() as pipe_input:
        # Open the item, traverse Viewer → Responses → Items → To Do, then
        # confirm the saved-response incorporation from final review.
        pipe_input.send_text("\t\x1b[B\r\t\t\t\r\x1b[F\r")
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
        {"a": ResponseDraft(None, "")},
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
        # Viewer is initially focused; Shift-Tab follows screen order to To Do.
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
