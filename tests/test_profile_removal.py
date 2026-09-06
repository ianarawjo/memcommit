"""Permanent-deletion contracts for ordinary Profiles and Study groups."""

from __future__ import annotations

from tests.grant_placement_support import create_authority_grant_with_placement

import json
from pathlib import Path
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.profile.lifecycle as profile_lifecycle
import memcommit.adapters.console.commands.profile.study_profile as study_profile
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.profile.picker.model import (
    ProfilePickerAction,
    ProfilePickerRefresh,
)
from memcommit.core.context import Memory
from memcommit.application.operations.profile.config import (
    PROFILE_REGISTRY_SCHEMA_VERSION,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
    virtual_authoring_registry,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    _write_registry,
    list_profiles,
    remove_profile,
    remove_study,
    study_run_profile_pairs,
    use_profile,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _RecordingProgress:
    calls: list[tuple[str, str, int]] = []

    def __init__(self, operation: str, stage: str, *, total: int) -> None:
        self.calls.append((operation, stage, total))

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        return None


def _create_store(root: Path, context_name: str, content: str) -> None:
    store = MemoryStore(root=root)
    context = ops.init(context_name)
    context.add(Memory(uid=str(uuid.uuid4()), content=content))
    store.save(context)
    store.checkpoint(context, message="Profile deletion fixture")
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
    create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=participant.name,
        resource_name="source",
        permissions=("READ",),
    )
    return participant, authority


def test_remove_one_study_child_deletes_only_that_store_and_keeps_header(
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
    assert len(before.grants) == 1
    assert current.grants == ()
    assert not profile_store_dir(authority).exists()
    assert profile_store_dir(participant).is_dir()
    assert study_run_profile_pairs(current.profiles)[0].authority == authority
    listed_registry, inspections = list_profiles()
    assert [profile.name for profile in listed_registry.visible_profiles] == [
        "authoring",
        participant.name,
    ]
    assert len(inspections) == 2
    assert inspections[1].granted_context_count == 0
    assert inspections[1].granted_memory_count == 0
    assert result.removed_grant_count == 1
    assert result.deleted_store == profile_store_dir(authority)


def test_remove_study_deletes_both_stores_and_checkpoints_in_one_generation(
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
    assert len(before.grants) == 1
    assert current.grants == ()
    assert [profile.name for profile in current.visible_profiles] == ["authoring"]
    assert not profile_store_dir(participant).exists()
    assert not profile_store_dir(authority).exists()
    assert result.removed_grant_count == 1
    assert result.deleted_stores == (
        profile_store_dir(participant),
        profile_store_dir(authority),
    )


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
    assert not profile_store_dir(participant).exists()
    assert not profile_store_dir(authority).exists()


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


def test_cli_child_remove_keeps_study_header_and_reports_permanent_deletion(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    _RecordingProgress.calls = []
    monkeypatch.setattr(profile_lifecycle, "CommandProgress", _RecordingProgress)

    removed = runner.invoke(
        app,
        ["profile", "remove", authority.name, "--force"],
    )
    listing = runner.invoke(app, ["profile", "list"])

    assert removed.exit_code == 0, removed.output
    assert f"Permanently deleted Profile '{authority.name}'" in removed.output
    assert "Deleted store and all checkpoints:" in removed.output
    assert "Connected Grants removed: 1" in removed.output
    assert "content cannot be recovered" in removed.output
    assert "1 active · 1 removed" in removed.output
    assert listing.exit_code == 0, listing.output
    assert any(
        "removal-study" in line and "STUDY" in line
        for line in listing.output.splitlines()
    )
    assert "1 removed" in listing.output
    assert f"profile={participant.name}" in listing.output
    assert authority.name not in listing.output
    assert "Deleted Profile tombstones hidden from this list: 1" in listing.output
    assert not profile_store_dir(authority).exists()
    assert _RecordingProgress.calls == [
        ("profile remove", "deleting store and checkpoints", 1)
    ]


def test_interactive_removal_reloads_and_stays_in_profile_selector(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    calls: list[dict[str, object]] = []

    def select(
        entries,
        *,
        current,
        registry_generation,
        initial_status="",
        initial_row_index=None,
        apply_removal=None,
    ):
        assert callable(apply_removal)
        calls.append(
            {
                "names": tuple(entry.name for entry in entries),
                "current": current,
                "generation": registry_generation,
                "status": initial_status,
                "row_index": initial_row_index,
            }
        )
        if len(calls) == 1:
            action = ProfilePickerAction(
                kind="REMOVE_PROFILE",
                name=authority.name,
                uid=authority.uid,
                registry_generation=registry_generation,
            )
            status = apply_removal(action)
            return ProfilePickerRefresh(
                status=status,
                preferred_row_index=3,
            )
        return None

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.profile.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.profile.selector.choose_profile", select
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert [call["names"] for call in calls] == [
        ("authoring", participant.name, authority.name),
        ("authoring", participant.name),
    ]
    assert calls[1]["generation"] == calls[0]["generation"] + 1
    assert calls[0]["row_index"] is None
    assert calls[1]["row_index"] == 3
    assert "Deleted Profile 'removal-authority' permanently" in calls[1]["status"]
    assert "store/checkpoints deleted" in calls[1]["status"]
    assert "Profile selection cancelled." not in result.output
    assert not profile_store_dir(authority).exists()


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


def test_cli_study_remove_force_deletes_both_stores_and_prints_receipt(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    _RecordingProgress.calls = []
    monkeypatch.setattr(study_profile, "CommandProgress", _RecordingProgress)

    result = runner.invoke(
        app,
        ["profile", "remove-study", "removal-study", "--force"],
    )

    assert result.exit_code == 0, result.output
    assert "Permanently deleted Study 'removal-study' Profile stores." in result.output
    assert "Profile stores and checkpoint histories deleted: 2" in result.output
    assert "Connected Grants removed: 1" in result.output
    assert not profile_store_dir(participant).exists()
    assert not profile_store_dir(authority).exists()
    assert _RecordingProgress.calls == [
        ("profile remove-study", "deleting stores and checkpoints", 1)
    ]


def test_cli_confirmation_warns_that_profile_checkpoints_are_unrecoverable(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    result = runner.invoke(
        app,
        ["profile", "remove", authority.name],
        input="n\n",
    )

    assert result.exit_code == 0, result.output
    assert "every Memory, session, and checkpoint" in result.output
    assert "cannot be undone or recovered by mem" in result.output
    assert profile_store_dir(authority).is_dir()


def test_registry_write_failure_restores_prepared_store_and_checkpoint(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _participant, authority = _prepare_study_registry(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    before_registry = profile_registry_file().read_bytes()
    store = MemoryStore(root=profile_store_dir(authority))
    assert store.list_checkpoints("source")

    def fail_registry_write(_registry):
        raise OSError("simulated registry write failure")

    monkeypatch.setattr(
        "memcommit.application.operations.profile.model._storage._write_registry",
        fail_registry_write,
    )

    with pytest.raises(ProfileError, match="was not deleted"):
        remove_profile(authority.name)

    assert profile_registry_file().read_bytes() == before_registry
    assert profile_store_dir(authority).is_dir()
    assert store.list_checkpoints("source")


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


def test_registry_v2_with_attached_grants_requires_explicit_recreation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _prepare_study_registry(isolated_store, tmp_path, monkeypatch)
    record = json.loads(profile_registry_file().read_text(encoding="utf-8"))
    record["schema_version"] = 2
    record.pop("removed_profile_uids")
    profile_registry_file().write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(
        ProfileConfigError,
        match="Legacy attached Grants are unsupported",
    ):
        load_profile_registry()
