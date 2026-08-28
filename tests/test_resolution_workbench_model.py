from __future__ import annotations

from dataclasses import replace

import pytest

from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionItem,
    ResolutionNavigation,
    ResolutionOption,
    ResolutionOverviewSection,
    ResolutionWorkbenchAction,
    ResolutionWorkbenchError,
    ResolutionWorkbenchView,
)


def _option(uid: str) -> ResolutionOption:
    return ResolutionOption(
        uid=uid,
        label=f"Option {uid}",
        text=f"Choose {uid}.",
    )


def _item(
    uid: str,
    *,
    options: tuple[ResolutionOption, ...] = (),
    selected_option_uid: str | None = None,
) -> ResolutionItem:
    return ResolutionItem(
        uid=uid,
        kind="ISSUE",
        status="OPEN",
        priority="REQUIRED",
        title=f"Issue {uid}",
        summary=f"Summary for {uid}.",
        question="What should happen?" if options else "",
        options=options,
        selected_option_uid=selected_option_uid,
    )


def _view(
    *uids: str,
    revision: str = "revision-1",
    items: tuple[ResolutionItem, ...] | None = None,
    capabilities: frozenset[str] = frozenset(),
    accept_enabled: bool = False,
) -> ResolutionWorkbenchView:
    projected_items = tuple(_item(uid) for uid in uids) if items is None else items
    return ResolutionWorkbenchView(
        operation="MELD",
        artifact_uid="meld-1",
        revision=revision,
        title="Resolve Meld",
        route="source -> target",
        status="OPEN",
        metrics=(),
        overview="Review the current resolution.",
        list_label="ISSUES",
        items=projected_items,
        empty_message="No issues.",
        results_label="CHANGES",
        results=(),
        capabilities=capabilities,  # type: ignore[arg-type]
        accept_enabled=accept_enabled,
    )


def test_projection_rejects_duplicate_item_and_option_uids() -> None:
    with pytest.raises(
        ResolutionWorkbenchError,
        match="Duplicate resolution option uid",
    ):
        _item("issue-1", options=(_option("same"), _option("same")))

    duplicate = _item("issue-1")
    with pytest.raises(
        ResolutionWorkbenchError,
        match="Duplicate resolution item uid",
    ):
        _view(items=(duplicate, duplicate))

    with pytest.raises(
        ResolutionWorkbenchError,
        match="Duplicate resolution Context-location role",
    ):
        replace(
            _view(),
            context_locations=(
                ResolutionContextLocation("SOURCE", "one"),
                ResolutionContextLocation("SOURCE", "two"),
            ),
        )

    with pytest.raises(
        ResolutionWorkbenchError,
        match="Duplicate resolution overview-section uid",
    ):
        replace(
            _view(),
            overview_sections=(
                ResolutionOverviewSection("same", "ONE", "First."),
                ResolutionOverviewSection("same", "TWO", "Second."),
            ),
        )

    with pytest.raises(
        ResolutionWorkbenchError,
        match="overview-section focus scope",
    ):
        ResolutionOverviewSection(
            "bad-focus",
            "UNDERSTOOD",
            "Text.",
            focus_body="yes",  # type: ignore[arg-type]
        )


def test_compact_rule_row_retains_a_complete_title_beyond_label_length() -> None:
    full_rule = "Complete Rule content " * 40

    item = ResolutionItem(
        uid="long-rule",
        kind="RULE",
        status="PROPOSED",
        priority="CHANGE",
        title=full_rule,
        summary="The detailed rationale remains available.",
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
        compact_row_suffix="SUPPORT 2 · BOUNDARY 1",
    )

    assert item.title == full_rule
    assert len(item.title) > 500


def test_projection_rejects_non_boolean_results_visibility() -> None:
    with pytest.raises(
        ResolutionWorkbenchError,
        match="Invalid resolution results visibility",
    ):
        replace(_view(), show_results=1)  # type: ignore[arg-type]


def test_item_response_semantics_distinguish_changes_from_open_decisions() -> None:
    change = ResolutionItem(
        uid="change-1",
        kind="EDIT",
        status="PLANNED",
        priority="CHANGE",
        title="Target Memory",
        summary="Apply the exact edit.",
        role="CHANGE",
        obligation="NONE",
        response_state="NOT_APPLICABLE",
    )

    assert change.effective_obligation == "NONE"

    with pytest.raises(
        ResolutionWorkbenchError,
        match="non-applicable response requires no review obligation",
    ):
        ResolutionItem(
            uid="invalid-1",
            kind="ISSUE",
            status="OPEN",
            priority="REQUIRED",
            title="Invalid issue",
            summary="This state is contradictory.",
            obligation="REQUIRED",
            response_state="NOT_APPLICABLE",
        )


def test_action_validation_binds_item_and_option_uids_and_capabilities() -> None:
    item = _item(
        "issue-1",
        options=(_option("keep"), _option("replace")),
    )
    view = _view(
        items=(item,),
        capabilities=frozenset({"SUBMIT_ITEM", "SUBMIT_ALL"}),
    )
    valid = ResolutionWorkbenchAction(
        kind="SUBMIT_ITEM",
        item_uid="issue-1",
        option_uid="replace",
    )
    assert view.validate_action(valid) is valid

    with pytest.raises(ResolutionWorkbenchError, match="No resolution item"):
        view.validate_action(
            ResolutionWorkbenchAction(
                kind="SUBMIT_ITEM",
                item_uid="stale-issue",
                comment="Use this answer.",
            )
        )

    with pytest.raises(ResolutionWorkbenchError, match="No resolution option"):
        view.validate_action(
            ResolutionWorkbenchAction(
                kind="SUBMIT_ITEM",
                item_uid="issue-1",
                option_uid="stale-option",
            )
        )

    with pytest.raises(ResolutionWorkbenchError, match="DEFER.*unavailable"):
        view.validate_action(ResolutionWorkbenchAction(kind="DEFER"))


def test_empty_view_readiness_is_owned_by_the_adapter() -> None:
    not_ready = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=False,
    )
    ready = _view(
        capabilities=frozenset({"ACCEPT"}),
        accept_enabled=True,
    )

    accept = ResolutionWorkbenchAction(kind="ACCEPT")
    with pytest.raises(ResolutionWorkbenchError, match="not ready"):
        not_ready.validate_action(accept)
    assert ready.validate_action(accept) is accept
    assert not_ready.items == ready.items == ()


def test_compound_incorporate_and_apply_requires_explicit_capability_and_guidance():
    action = ResolutionWorkbenchAction(
        kind="INCORPORATE_AND_APPLY",
        comment="Use the saved responses, then apply the resulting proposal.",
    )
    enabled = _view(capabilities=frozenset({"INCORPORATE_AND_APPLY"}))

    assert enabled.validate_action(action) is action

    with pytest.raises(ResolutionWorkbenchError, match="unavailable"):
        _view().validate_action(action)
    with pytest.raises(ResolutionWorkbenchError, match="requires a comment"):
        enabled.validate_action(ResolutionWorkbenchAction(kind="INCORPORATE_AND_APPLY"))


def test_navigation_preserves_uid_across_add_and_reorder_then_clamps_ordinal() -> None:
    navigation = ResolutionNavigation()
    navigation.sync(_view("a", "b", "c"))
    navigation.move_item(_view("a", "b", "c"), 1)
    assert navigation.selected_item_uid == "b"

    added_and_reordered = _view("new", "c", "b", "a")
    navigation.sync(added_and_reordered)
    assert navigation.selected_item_uid == "b"

    selected_removed = _view("new", "c", "a")
    navigation.sync(selected_removed)
    assert navigation.selected_item_uid == "a"

    navigation.sync(_view("only"))
    assert navigation.selected_item_uid == "only"


def test_navigation_can_resume_when_an_empty_list_becomes_nonempty() -> None:
    navigation = ResolutionNavigation()
    empty = _view()
    navigation.sync(empty)

    assert navigation.selected_item_uid is None
    assert navigation.current_item(empty) is None

    populated = _view("first", "second")
    navigation.sync(populated)
    assert navigation.selected_item_uid == "first"
    assert navigation.current_item(populated) == populated.items[0]


def test_revision_change_clears_expansion_and_ephemeral_option_selection() -> None:
    item = _item(
        "issue-1",
        options=(_option("one"), _option("two")),
    )
    initial = _view(items=(item,), revision="revision-1")
    navigation = ResolutionNavigation()
    navigation.sync(initial)
    navigation.toggle_detail(initial)
    navigation.move_option(initial, 1)
    navigation.toggle_option(initial)

    assert navigation.expanded_item_uid == "issue-1"
    assert navigation.option_cursor_uid == "two"
    assert navigation.selected_option_uid == "two"

    reassessed = _view(items=(item,), revision="revision-2")
    navigation.sync(reassessed)

    assert navigation.selected_item_uid == "issue-1"
    assert navigation.expanded_item_uid is None
    assert navigation.option_cursor_uid is None
    assert navigation.selected_option_uid is None
