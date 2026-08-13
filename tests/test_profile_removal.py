"""Soft-removal contracts for ordinary Profiles and complete Study groups."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory
from memcommit.profile_config import (
    PROFILE_REGISTRY_SCHEMA_VERSION,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
    virtual_authoring_registry,
)
from memcommit.profiles import (
    ProfileError,
    _write_registry,
    create_authority_grant,
    list_profiles,
    remove_profile,
    remove_study,
    study_run_profile_pairs,
    use_profile,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _create_store(root: Path, context_name: str, content: str) -> None:
    store = MemoryStore(root=root)
    context = ops.init(context_name)
    context.add(Memory(uid=str(uuid.uuid4()), content=content))
    store.save(context)
    store.set_current(context_name)


def _study_source(
    *,
    kind: str,
    study_uid: str,
    baseline_uid: str,
) -> dict[str, object]:
    return {
        "kind": kind,
        "study_uid": study_uid,
        "study_name": "removal-study",
        "created_at": "2026-08-13T12:00:00+00:00",
        "baseline_sha256": "a" * 64,
        "baseline_profile_uid": baseline_uid,
        "baseline_profile_name": "study-baseline",
    }


def _prepare_study_registry(
    isolated_store: Path,
    tmp_path: Path,
    monkeypatch,
) -> tuple[ProfileEntry, ProfileEntry]:
    monkeypatch.setenv("HOME", str(tmp_path))
    _create_store(isolated_store, "authoring", "Authoring memory")
    authoring = virtual_authoring_registry().active
    study_uid = str(uuid.uuid4())
    baseline_uid = str(uuid.uuid4())
    participant = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="removal-participant",
        kind="MANAGED",
        source=_study_source(
            kind="STUDY_RUN",
            study_uid=study_uid,
            baseline_uid=baseline_uid,
        ),
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="removal-authority",
        kind="MANAGED",
        source=_study_source(
            kind="STUDY_RUN_GRANTED_MEMORY",
            study_uid=study_uid,
            baseline_uid=baseline_uid,
        ),
    )
    _create_store(profile_store_dir(participant), "participant", "Participant memory")
    _create_store(profile_store_dir(authority), "source", "Granted memory")
    _write_registry(
        ProfileRegistry(
            generation=1,
            active_uid=authoring.uid,
            profiles=(authoring, participant, authority),
        )
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=participant.name,
        resource_name="source",
        attachment_name="participant",
        permissions=("READ",),
    )
    return participant, authority


def test_remove_one_study_child_hides_only_that_profile_and_keeps_pair(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    before = load_profile_registry()

    result = remove_profile(authority.name)
    current = load_profile_registry()

    assert result.profile == authority
    assert result.study_name == "removal-study"
    assert result.study_profile_count == 2
    assert result.study_removed_count == 1
    assert current.removed_profile_uids == (authority.uid,)
    assert current.profiles == before.profiles
    assert current.grants == before.grants
    assert profile_store_dir(authority).is_dir()
    assert study_run_profile_pairs(current.profiles)[0].authority == authority
    listed_registry, inspections = list_profiles()
    assert [profile.name for profile in listed_registry.visible_profiles] == [
        "authoring",
        participant.name,
    ]
    assert len(inspections) == 2
    assert inspections[1].granted_context_count == 1
    assert inspections[1].granted_memory_count == 1


def test_remove_study_hides_both_members_in_one_generation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    before = load_profile_registry()

    result = remove_study("removal-study")
    current = load_profile_registry()

    assert result.profiles == (participant, authority)
    assert result.newly_removed_count == 2
    assert current.generation == before.generation + 1
    assert current.removed_profile_uids == (participant.uid, authority.uid)
    assert current.profiles == before.profiles
    assert current.grants == before.grants
    assert [profile.name for profile in current.visible_profiles] == ["authoring"]
    assert profile_store_dir(participant).is_dir()
    assert profile_store_dir(authority).is_dir()


def test_remove_study_finishes_a_partially_removed_study(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    remove_profile(authority.name)

    result = remove_study("removal-study")

    assert result.newly_removed_count == 1
    assert load_profile_registry().removed_profile_uids == (
        participant.uid,
        authority.uid,
    )


def test_removed_profile_cannot_be_selected_directly(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    remove_profile(authority.name)

    with pytest.raises(ProfileError, match="removed from direct selection"):
        use_profile(authority.name)


def test_active_profile_and_active_study_removal_fail_without_registry_change(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, _authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    use_profile(participant.name)
    before = profile_registry_file().read_bytes()

    with pytest.raises(ProfileError, match="is active"):
        remove_profile(participant.name)
    with pytest.raises(ProfileError, match="contains the active Profile"):
        remove_study("removal-study")

    assert profile_registry_file().read_bytes() == before


def test_tui_review_identity_and_generation_are_revalidated(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    registry = load_profile_registry()

    with pytest.raises(ProfileError, match="changed after removal review"):
        remove_profile(
            authority.name,
            expected_uid=authority.uid,
            expected_generation=registry.generation - 1,
        )
    with pytest.raises(ProfileError, match="identity changed"):
        remove_profile(
            authority.name,
            expected_uid=str(uuid.uuid4()),
            expected_generation=registry.generation,
        )

    assert not load_profile_registry().removed_profile_uids


def test_cli_child_remove_keeps_study_header_and_marks_one_removed(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    removed = runner.invoke(
        app,
        ["profile", "remove", authority.name, "--force"],
    )
    listing = runner.invoke(app, ["profile", "list"])

    assert removed.exit_code == 0, removed.output
    assert f"Removed Profile '{authority.name}'" in removed.output
    assert "Profile UID, provenance, and Grants were retained." in removed.output
    assert "1 active · 1 removed" in removed.output
    assert listing.exit_code == 0, listing.output
    assert "removal-study  STUDY" in listing.output
    assert "1 removed" in listing.output
    assert f"profile={participant.name}" in listing.output
    assert authority.name not in listing.output
    assert "Removed Profiles hidden from this list: 1" in listing.output


def test_cli_study_remove_confirmation_can_cancel_without_changes(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _prepare_study_registry(isolated_store, tmp_path, monkeypatch)
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "remove-study", "removal-study"],
        input="n\n",
    )

    assert result.exit_code == 0, result.output
    assert "Study removal cancelled." in result.output
    assert profile_registry_file().read_bytes() == before


def test_registry_v3_rejects_removed_authoring_or_active_identity(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    record = json.loads(profile_registry_file().read_text(encoding="utf-8"))
    assert record["schema_version"] == PROFILE_REGISTRY_SCHEMA_VERSION
    authoring_uid = record["active_uid"]

    record["active_uid"] = authority.uid
    record["removed_profile_uids"] = [authority.uid]
    profile_registry_file().write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ProfileConfigError, match="active Profile cannot be removed"):
        load_profile_registry()

    record["removed_profile_uids"] = [authoring_uid]
    profile_registry_file().write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ProfileConfigError, match="authoring Profile cannot be removed"):
        load_profile_registry()


def test_registry_v2_loads_with_no_removed_profiles_and_migrates_on_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _prepare_study_registry(isolated_store, tmp_path, monkeypatch)
    record = json.loads(profile_registry_file().read_text(encoding="utf-8"))
    record["schema_version"] = 2
    record.pop("removed_profile_uids")
    profile_registry_file().write_text(json.dumps(record), encoding="utf-8")

    legacy = load_profile_registry()
    assert legacy.removed_profile_uids == ()

    _write_registry(legacy)
    migrated = json.loads(profile_registry_file().read_text(encoding="utf-8"))
    assert migrated["schema_version"] == PROFILE_REGISTRY_SCHEMA_VERSION
    assert migrated["removed_profile_uids"] == []
