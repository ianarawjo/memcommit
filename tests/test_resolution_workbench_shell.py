from __future__ import annotations

from dataclasses import replace

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.resolution_workbench_shell import (
    ResolutionGlobalStrategy,
    render_resolution_workbench_snapshot,
    resolution_report_fragments,
    resolution_viewer_fragments,
    resolution_workbench_fragments,
    run_resolution_workbench_shell,
)
from memcommit.impact_controller import ImpactController
from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.session_workbench_navigation import SessionWorkbenchNavigation


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


def test_escape_collapses_detail_before_close():
    navigation = ResolutionNavigation()
    view = _view(_item("issue-1"))

    # First Escape unwinds the expanded detail. Q then closes the workbench.
    action = _run(view, "\r\x1bq", navigation=navigation)

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

    assert "CONFLICT 1/1 · Question paradigm" in rendered
    assert "╭─ QUESTION " in rendered
    assert "╭─ OPTIONS " in rendered
    assert "2. Other direction" in rendered
    assert "╭─ EVIDENCE " in rendered
    assert "│   advisor1 · #1" in rendered
    assert "╯\n\n ╭─ QUESTION" in rendered
    assert "WHAT MEM UNDERSTOOD" not in rendered
    assert "Review the current resolution." not in rendered


def test_split_detail_submits_a_supplied_option_with_an_optional_comment():
    item = _item(
        "issue-1",
        options=(
            ResolutionOption("keep", "Keep", "Keep the first direction."),
            ResolutionOption("replace", "Replace", "Use the second direction."),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Open conflict 1, choose its first supplied option, then use C to
        # send that choice with the optional comment field empty.
        pipe_input.send_text("\x1b[B\r\rc\r")
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
        # Open conflict 1, move beyond both supplied options to Other
        # direction, and submit a free-form resolution.
        pipe_input.send_text(
            "\x1b[B\r\x1b[C\x1b[C\rUse a staged combination instead.\r"
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


def test_item_selection_does_not_replace_open_viewer_until_enter():
    item_navigation = ResolutionNavigation()
    workbench_navigation = SessionWorkbenchNavigation()
    view = _view(_item("a"), _item("b"))

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r\t\x1b[Bq")
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
    assert workbench_navigation.viewer_row_index == 1
    assert item_navigation.selected_item_uid == "a"


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
        # impact, apply. The controller must retain APPLY by identity rather
        # than by the pre-review-items numeric offset.
        pipe_input.send_text("\t" + "\x1b[B" * 6 + "q")
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
    assert workbench_navigation.row_index == 2


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
        pipe_input.send_text(
            "\x1b[B\r\r\t\x1b[B\r\r\t\x1b[B\r"
        )
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


def test_review_and_apply_treats_enter_again_as_selection_cancellation():
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
        # The second Enter on the same option clears it. Final review therefore
        # routes the conflict through the explicit unresolved policy.
        pipe_input.send_text("\x1b[B\r\r\r\t\x1b[B\r")
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
    assert "Choose this reading" not in action.comment
    assert "Issue a" in action.comment
    assert "Preserve every unresolved distinction." in action.comment
