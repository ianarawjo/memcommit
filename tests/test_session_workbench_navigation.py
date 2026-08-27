from __future__ import annotations

import pytest

from memcommit.application.reviewing.session_navigation import (
    SessionWorkbenchNavigation,
    WorkbenchSection,
)


def _sections(*uids: str) -> tuple[WorkbenchSection, ...]:
    return tuple(WorkbenchSection(uid, uid.split(":", 1)[0]) for uid in uids)


def test_focus_rows_and_semantic_sections_share_one_controller():
    navigation = SessionWorkbenchNavigation()
    sections = _sections("REPORT", "ITEM:a", "IMPACT", "APPLY")

    assert navigation.pane == "viewer"
    assert navigation.move_row(4, 2) == 2
    assert navigation.preview_selected_row() == 2
    assert navigation.pane == "viewer"
    navigation.open_selected(sections)
    assert navigation.pane == "viewer"
    assert navigation.viewer_row_index == 2
    assert navigation.move_section(sections, 2) == sections[2]
    assert navigation.toggle_frames() == "items"


def test_move_and_preview_keeps_items_focus_and_clears_stale_viewer_section():
    navigation = SessionWorkbenchNavigation(
        pane="items",
        section_uid="ITEM:stale",
    )

    assert navigation.move_and_preview_row(3, 2) == 2
    assert navigation.row_index == 2
    assert navigation.viewer_row_index == 2
    assert navigation.section_uid is None
    assert navigation.pane == "items"

    assert navigation.move_and_preview_row(3, 100) == 2
    assert navigation.pane == "items"


def test_three_frame_session_cycle_includes_todo_without_affecting_compare_toggle():
    navigation = SessionWorkbenchNavigation()
    panes = ("viewer", "items", "todo")

    assert navigation.cycle_panes(panes) == "items"
    assert navigation.cycle_panes(panes) == "todo"
    assert navigation.cycle_panes(panes, -1) == "items"
    assert navigation.toggle_frames() == "viewer"


def test_response_frame_joins_the_visible_session_order_when_an_item_is_open():
    navigation = SessionWorkbenchNavigation()
    panes = ("viewer", "responses", "items", "todo")

    assert navigation.cycle_panes(panes) == "responses"
    assert navigation.cycle_panes(panes) == "items"
    assert navigation.cycle_panes(panes) == "todo"
    assert navigation.cycle_panes(panes) == "viewer"


def test_save_location_can_join_the_visible_session_cycle():
    navigation = SessionWorkbenchNavigation()
    panes = ("viewer", "items", "save_location", "todo")

    assert navigation.cycle_panes(panes) == "items"
    assert navigation.cycle_panes(panes) == "save_location"
    assert navigation.cycle_panes(panes) == "todo"


def test_section_identity_survives_insertions_and_apply_is_not_an_offset():
    navigation = SessionWorkbenchNavigation(section_uid="APPLY")
    before = _sections("REPORT", "RESULTS", "APPLY")
    after = _sections("REPORT", "REVIEW_ITEMS", "RESULTS", "IMPACT", "APPLY")

    assert navigation.section_index(before) == 2
    assert navigation.section_index(after) == 4
    assert navigation.focus_section(after, kind="APPLY") == after[-1]


def test_duplicate_or_missing_sections_fail_closed():
    navigation = SessionWorkbenchNavigation()
    duplicate = _sections("REPORT", "REPORT")

    with pytest.raises(ValueError, match="unique"):
        navigation.bind_sections(duplicate)
    with pytest.raises(ValueError, match="unavailable"):
        navigation.focus_section(_sections("REPORT"), kind="APPLY")
