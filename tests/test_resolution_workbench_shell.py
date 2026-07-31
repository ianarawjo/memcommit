from __future__ import annotations

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.resolution_workbench_shell import (
    render_resolution_workbench_snapshot,
    resolution_workbench_fragments,
    run_resolution_workbench_shell,
)
from memcommit.resolution_workbench import (
    ResolutionItem,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionResult,
    ResolutionWorkbenchView,
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
