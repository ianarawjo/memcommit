"""Profile review and navigation contracts without running a terminal app."""

from __future__ import annotations

from dataclasses import replace

import pytest

from memcommit.adapters.console.commands.profile.picker.model import ProfilePickerEntry
from memcommit.adapters.console.commands.profile.picker.rows import build_picker_rows
from memcommit.adapters.console.commands.profile.picker.state import ProfilePickerState
from memcommit.application.operations.profile.config import ProfileConfigError

ENTRIES = (
    ProfilePickerEntry("authoring", 1, "notes", uid="authoring-uid"),
    ProfilePickerEntry(
        "pilot-participant",
        2,
        "practice",
        uid="participant-uid",
        study_uid="study-uid",
        study_name="pilot",
        study_created_at="2026-09-06",
        study_role="PARTICIPANT",
        study_profile_count=2,
    ),
    ProfilePickerEntry(
        "pilot-authority",
        3,
        "sources",
        uid="authority-uid",
        study_uid="study-uid",
        study_name="pilot",
        study_created_at="2026-09-06",
        study_role="GRANTED_MEMORY",
        study_profile_count=2,
    ),
)


def make_state(*, current="authoring", initial_row_index=None):
    return ProfilePickerState.create(
        build_picker_rows(ENTRIES, current=current),
        current=current,
        registry_generation=17,
        initial_row_index=initial_row_index,
    )


@pytest.mark.parametrize(
    "row_index, kind, uid",
    [
        (0, "RENAME_PROFILE", "authoring-uid"),
        (1, "RENAME_STUDY", "study-uid"),
        (2, "RENAME_PROFILE", "participant-uid"),
    ],
)
def test_rename_back_restores_reviewed_draft_and_keeps_frozen_identity(
    row_index, kind, uid
):
    state = make_state(initial_row_index=row_index)
    state.begin_rename()
    assert state.edit is not None
    old_name = state.edit.value

    state.review_name("first-name")
    action = state.action
    assert action is not None
    assert (action.kind, action.name, action.uid, action.registry_generation) == (
        kind,
        old_name,
        uid,
        17,
    )
    state.move(1)
    assert state.index == row_index
    assert state.back()
    assert state.action is None
    assert state.edit.value == "first-name"
    assert state.status == "Rename review cancelled"

    state.review_name("corrected-name")
    assert state.action == replace(action, new_name="corrected-name")
    assert state.back()
    assert state.back()
    assert state.stage is None
    assert state.index == row_index
    assert not state.back()


def test_create_back_preserves_draft_and_append_position_without_changing_current():
    state = make_state(initial_row_index=2)
    state.begin_create()
    assert state.action is None
    assert state.edit.value == ""
    state.review_name("new-profile")
    action = state.action
    assert action.kind == "CREATE_PROFILE"
    assert action.row_index == len(state.rows)
    assert action.registry_generation == 17
    assert action.uid is None
    assert state.back()
    assert state.edit.value == "new-profile"
    assert state.status == "Create review cancelled"
    state.review_name("corrected-profile")
    assert state.action == replace(action, name="corrected-profile")
    assert state.back()
    assert state.back()
    assert state.status == "Profile creation cancelled"
    assert state.current == "authoring"
    assert state.index == 2


@pytest.mark.parametrize("name", ["", " padded", "padded ", "two/parts", "two\nlines"])
def test_invalid_name_never_enters_review_or_replaces_the_edit_target(name):
    state = make_state(initial_row_index=2)
    state.begin_rename()
    edit = state.edit
    with pytest.raises((ProfileConfigError, ValueError)):
        state.review_name(name)
    assert state.edit is edit
    assert state.action is None


@pytest.mark.parametrize(
    "current, row_index",
    [
        ("authoring", 0),
        ("pilot-participant", 1),
        ("pilot-participant", 2),
    ],
)
def test_current_profile_or_its_study_cannot_enter_removal_review(current, row_index):
    state = make_state(current=current, initial_row_index=row_index)
    state.review_removal()
    assert state.action is None
    assert state.stage is None
    assert state.status_is_error
    assert "CURRENT" in state.status


def test_removal_back_returns_to_same_row_and_never_turns_into_use():
    state = make_state(initial_row_index=1)
    state.review_removal()
    assert state.action.kind == "REMOVE_STUDY"
    assert state.action.uid == "study-uid"
    assert state.action.registry_generation == 17
    assert state.use_profile() is None
    assert state.back()
    assert state.stage is None
    assert state.index == 1
    assert state.status == "Removal review cancelled"
    assert state.use_profile() is None
    state.move(1)
    assert state.use_profile().name == "pilot-participant"


def test_blocked_profile_never_opens_name_or_removal_review():
    entries = (
        ENTRIES[0],
        ProfilePickerEntry(
            "fixed",
            1,
            "notes",
            uid="fixed-uid",
            rename_block="Rename blocked",
            removal_block="Removal blocked",
        ),
    )
    state = ProfilePickerState.create(
        build_picker_rows(entries, current="authoring"),
        current="authoring",
        initial_row_index=1,
    )
    state.begin_rename()
    assert state.stage is None
    assert state.status == "Rename blocked"
    assert state.status_is_error
    state.review_removal()
    assert state.stage is None
    assert state.status == "Removal blocked"
    assert state.status_is_error


def test_reloaded_catalog_clamps_visual_position_and_keeps_current_distinct():
    state = make_state(initial_row_index=99)
    assert state.index == len(state.rows) - 1
    assert state.current == "authoring"
    state.move(1)
    assert state.index == len(state.rows) - 1
    state.move(-99)
    assert state.index == 0
