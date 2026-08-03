from __future__ import annotations

import os

import pytest

import memcommit.commands.ground_session_picker as ground_picker_module
import memcommit.ops as ops
from memcommit.commands.ground_session_picker import (
    ground_session_picker_location,
    list_ground_session_catalog,
    list_ground_session_entries,
    reload_selected_ground_session,
)
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
)
from memcommit.store import MemoryStore


def test_ground_session_entries_are_read_only_and_carry_exact_reopen_argv(
    isolated_store,
):
    store = MemoryStore(create=False)
    older = create_ground_session("older-ground", goal="Older Goal.")
    newer = create_ground_session("newer-ground", goal="Newer Goal.")
    store.save_ground_session(older)
    store.save_ground_session(newer)
    older_path = isolated_store / "ground-sessions" / "older-ground.json"
    newer_path = isolated_store / "ground-sessions" / "newer-ground.json"
    os.utime(older_path, (10, 10))
    os.utime(newer_path, (20, 20))
    before = {
        path.name: path.read_bytes()
        for path in (older_path, newer_path)
    }

    entries = list_ground_session_entries(store)

    assert {entry.key for entry in entries} == {
        "older-ground",
        "newer-ground",
    }
    by_key = {entry.key: entry for entry in entries}
    assert by_key["newer-ground"].sort_timestamp == 20
    assert by_key["newer-ground"].group == "Unbound"
    assert by_key["newer-ground"].reopen_argv == (
        "mem",
        "ground",
        "newer-ground",
    )
    assert {
        path.name: path.read_bytes()
        for path in (older_path, newer_path)
    } == before


def test_bound_ground_groups_by_raw_context_and_retains_all_contexts_in_detail(
    isolated_store,
):
    store = MemoryStore()
    raw = ops.init("temp/task-1")
    derived = ops.init("temp/task-1-atomized")
    target = ops.init("campus-wiki")
    session = bind_ground_workbench(
        create_ground_session(
            "task-1-fixture",
            goal="Build a traceable Task 1 fixture.",
        ),
        description="Use Task 1 source material to build the campus wiki.",
        raw_context=raw,
        derived_context=derived,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Cover the campus wiki target.",
            ),
        ),
    )
    store.save_ground_session(session)

    picker_entry = list_ground_session_entries(store)[0]

    assert picker_entry.group == "temp/task-1"
    assert (
        "Contexts: temp/task-1, temp/task-1-atomized, campus-wiki"
        in picker_entry.detail
    )


def test_ground_session_entries_do_not_create_missing_storage(isolated_store):
    store = MemoryStore(create=False)

    assert list_ground_session_entries(store) == ()
    assert not isolated_store.exists()


def test_ground_picker_location_matches_frozen_store_not_live_active_profile(
    tmp_path,
    monkeypatch,
):
    authoring_root = tmp_path / "authoring"
    task_root = tmp_path / "task-1"
    task_uid = "11111111-1111-1111-1111-111111111111"
    registry = ProfileRegistry(
        generation=2,
        active_uid=task_uid,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name="authoring",
                kind="AUTHORING",
            ),
            ProfileEntry(
                uid=task_uid,
                name="task-1",
                kind="MANAGED",
            ),
        ),
    )
    monkeypatch.setattr(ground_picker_module.store_module, "STORE_DIR", authoring_root)
    monkeypatch.setattr(ground_picker_module, "load_profile_registry", lambda: registry)
    monkeypatch.setattr(
        ground_picker_module,
        "profile_store_dir",
        lambda profile: authoring_root if profile.name == "authoring" else task_root,
    )

    location = ground_session_picker_location()

    assert location.profile_name == "authoring"
    assert location.store_path == str(authoring_root)


def test_ground_picker_location_marks_an_isolated_store_unregistered(
    isolated_store,
    monkeypatch,
):
    registry = ProfileRegistry(
        generation=1,
        active_uid=AUTHORING_PROFILE_UID,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name="authoring",
                kind="AUTHORING",
            ),
        ),
    )
    monkeypatch.setattr(ground_picker_module, "load_profile_registry", lambda: registry)
    monkeypatch.setattr(
        ground_picker_module,
        "profile_store_dir",
        lambda _profile: isolated_store.parent / "other",
    )

    location = ground_session_picker_location()

    assert location.profile_name == "(unregistered)"
    assert location.store_path == str(isolated_store)


def test_ground_session_entries_reject_untrusted_storage_entry(
    isolated_store,
):
    root = isolated_store / "ground-sessions"
    root.mkdir(parents=True)
    (root / "unexpected.txt").write_text("not a Ground", encoding="utf-8")

    with pytest.raises(ValueError, match="storage is invalid"):
        list_ground_session_entries(MemoryStore(create=False))


def test_ground_catalog_ignores_atomic_writer_scratch_file(isolated_store):
    store = MemoryStore(create=False)
    session = create_ground_session("stable-ground")
    store.save_ground_session(session)
    scratch = (
        isolated_store
        / "ground-sessions"
        / ".stable-ground.json.write-0123456789abcdef0123456789abcdef"
    )
    scratch.write_text("unfinished", encoding="utf-8")

    catalog = list_ground_session_catalog(store)

    assert [entry.picker_entry.key for entry in catalog] == ["stable-ground"]


def test_ground_catalog_rejects_replacement_under_selected_name(isolated_store):
    store = MemoryStore(create=False)
    original = create_ground_session("stable-ground", goal="Original Goal.")
    store.save_ground_session(original)
    selected = list_ground_session_catalog(store)[0]
    replacement = create_ground_session(
        "stable-ground",
        goal="Replacement Goal.",
    )
    store.save_ground_session(replacement, replace=True)

    with pytest.raises(ValueError, match="changed while the list was open"):
        reload_selected_ground_session(store, selected)
