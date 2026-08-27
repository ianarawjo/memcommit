from __future__ import annotations

import json
import uuid

import pytest

import memcommit.study_scenarios.legacy.prewarm.installations as installations_module
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
)
from memcommit.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.installations import (
    declared_artifact_available,
    declared_installation_matches,
    declared_installation_path,
    record_declared_installation,
)
from memcommit.study_scenarios.legacy.prewarm.registry import (
    StudyPrewarmEntry,
    StudyPrewarmRegistryError,
    attach_shared_bundle,
    bundle_reference_path,
    load_artifact,
    load_registry,
    publish_artifact,
    registry_root,
    shared_bundle_root,
)


def _entry() -> StudyPrewarmEntry:
    return StudyPrewarmEntry(
        key="a" * 64,
        operation="ATOMIZE",
        task="tutorial",
        policy="EXACT_PREWARM",
        artifact="artifacts/atomize.json",
        artifact_sha256="b" * 64,
        enabled=True,
    )


def test_hidden_receipt_round_trips_exact_entry_and_evidence(isolated_store):
    store = MemoryStore()
    entry = _entry()
    evidence = {"analysis_digest": "c" * 64, "source_uid": "source-1"}

    record_declared_installation(store, entry=entry, evidence=evidence)

    assert declared_installation_matches(
        store,
        entry=entry,
        evidence=evidence,
    )
    value = json.loads(
        declared_installation_path(store, entry).read_text(encoding="utf-8")
    )
    assert value["entry_key"] == entry.key
    assert value["artifact_sha256"] == entry.artifact_sha256
    assert value["evidence"] == dict(sorted(evidence.items()))
    assert "analysis_uid" not in value
    assert "session_uid" not in value


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("entry_key", "d" * 64),
        ("artifact_sha256", "e" * 64),
        ("operation", "COMPARE"),
        ("task", "task-1"),
        ("evidence", {"analysis_digest": "f" * 64}),
    ),
)
def test_hidden_receipt_tampering_is_an_exact_miss(
    isolated_store,
    field,
    replacement,
):
    store = MemoryStore()
    entry = _entry()
    evidence = {"analysis_digest": "c" * 64, "source_uid": "source-1"}
    record_declared_installation(store, entry=entry, evidence=evidence)
    path = declared_installation_path(store, entry)
    value = json.loads(path.read_text(encoding="utf-8"))
    value[field] = replacement
    path.write_text(json.dumps(value), encoding="utf-8")

    assert not declared_installation_matches(
        store,
        entry=entry,
        evidence=evidence,
    )


def test_hidden_receipt_rejects_unexpected_fields_and_invalid_json(isolated_store):
    store = MemoryStore()
    entry = _entry()
    evidence = {"analysis_digest": "c" * 64}
    record_declared_installation(store, entry=entry, evidence=evidence)
    path = declared_installation_path(store, entry)
    value = json.loads(path.read_text(encoding="utf-8"))
    value["session_uid"] = "must-not-be-visible"
    path.write_text(json.dumps(value), encoding="utf-8")

    assert not declared_installation_matches(
        store,
        entry=entry,
        evidence=evidence,
    )

    path.write_text("{", encoding="utf-8")
    with pytest.raises(StudyPrewarmRegistryError, match="receipt is invalid"):
        declared_installation_matches(
            store,
            entry=entry,
            evidence=evidence,
        )


def test_hidden_receipt_rejects_unsafe_file_and_directory(
    isolated_store,
    tmp_path,
):
    store = MemoryStore()
    entry = _entry()
    evidence = {"analysis_digest": "c" * 64}
    path = declared_installation_path(store, entry)
    path.parent.mkdir(parents=True)
    target = tmp_path / "receipt.json"
    target.write_text("{}", encoding="utf-8")
    path.symlink_to(target)

    with pytest.raises(StudyPrewarmRegistryError, match="receipt is unsafe"):
        declared_installation_matches(
            store,
            entry=entry,
            evidence=evidence,
        )

    path.unlink()
    path.parent.rmdir()
    path.parent.write_text("occupied", encoding="utf-8")
    with pytest.raises(
        StudyPrewarmRegistryError,
        match="receipt directory is unsafe",
    ):
        record_declared_installation(store, entry=entry, evidence=evidence)


@pytest.mark.parametrize(
    "evidence",
    ({}, {"": "value"}, {"digest": ""}),
)
def test_hidden_receipt_rejects_empty_evidence(isolated_store, evidence):
    store = MemoryStore()

    with pytest.raises(
        StudyPrewarmRegistryError,
        match="installation evidence is invalid",
    ):
        record_declared_installation(store, entry=_entry(), evidence=evidence)


def test_participant_stores_pin_one_shared_immutable_bundle(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    baseline = tmp_path / "baseline"
    first = tmp_path / "first"
    second = tmp_path / "second"
    baseline.mkdir()
    first.mkdir()
    second.mkdir()
    baseline_uid = "11111111-1111-4111-8111-111111111111"
    artifact = {"kind": "TEST_STUDY_PREWARM", "value": "shared once"}
    entry = publish_artifact(
        baseline,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-1",
        key="a" * 64,
        artifact=artifact,
    )

    first_digest = attach_shared_bundle(
        baseline_store_root=baseline,
        participant_store_root=first,
    )
    second_digest = attach_shared_bundle(
        baseline_store_root=baseline,
        participant_store_root=second,
    )

    assert first_digest == second_digest
    assert first_digest is not None
    assert not registry_root(first).exists()
    assert not registry_root(second).exists()
    assert bundle_reference_path(first).stat().st_size < 512
    assert bundle_reference_path(second).stat().st_size < 512
    assert shared_bundle_root(first_digest).is_dir()
    assert load_registry(first) == load_registry(second) == load_registry(baseline)
    assert load_artifact(first, entry) == artifact
    assert load_artifact(second, entry) == artifact

    publish_artifact(
        baseline,
        baseline_profile_uid=baseline_uid,
        operation="COMPARE",
        task="task-1",
        key="b" * 64,
        artifact={"kind": "TEST_STUDY_PREWARM", "value": "new revision"},
    )
    third = tmp_path / "third"
    third.mkdir()
    third_digest = attach_shared_bundle(
        baseline_store_root=baseline,
        participant_store_root=third,
    )

    assert third_digest != first_digest
    assert len(load_registry(first).entries) == 1
    assert len(load_registry(third).entries) == 2


def test_shared_bundle_reference_fails_closed_when_artifact_changes(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    baseline = tmp_path / "baseline"
    participant = tmp_path / "participant"
    baseline.mkdir()
    participant.mkdir()
    entry = publish_artifact(
        baseline,
        baseline_profile_uid="22222222-2222-4222-8222-222222222222",
        operation="COMPARE",
        task="task-2",
        key="c" * 64,
        artifact={"kind": "TEST_STUDY_PREWARM", "value": "frozen"},
    )
    digest = attach_shared_bundle(
        baseline_store_root=baseline,
        participant_store_root=participant,
    )
    assert digest is not None
    path = shared_bundle_root(digest) / entry.artifact
    path.write_text("{}", encoding="utf-8")

    # An unrelated registry listing stays lazy; the exact artifact read is the
    # integrity boundary for the participant's first matching operation.
    assert load_registry(participant) is not None
    with pytest.raises(StudyPrewarmRegistryError, match="changed after lookup"):
        load_artifact(participant, entry)


@pytest.mark.parametrize(
    "operation",
    (
        "COMPARE",
        "UPDATE",
        "MELD_DIRECTIONAL",
        "MELD_RESOLUTION",
        "SEVER",
        "ATOMIZE",
        "SUMMARIZE",
    ),
)
def test_every_study_cache_family_uses_the_same_first_use_bundle_gate(
    isolated_store,
    tmp_path,
    monkeypatch,
    operation,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    baseline = tmp_path / "baseline"
    participant = tmp_path / "participant"
    baseline.mkdir()
    participant.mkdir()
    baseline_uid = str(uuid.uuid4())
    participant_profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="participant",
        kind="MANAGED",
        source={
            "kind": STUDY_RUN_PARTICIPANT_SOURCE_KIND,
            "study_uid": str(uuid.uuid4()),
            "study_name": "shared-cache-test",
            "created_at": "2026-08-13T00:00:00+00:00",
            "baseline_sha256": "a" * 64,
            "baseline_profile_uid": baseline_uid,
            "baseline_profile_name": "baseline",
        },
    )
    profiles = ProfileRegistry(
        generation=1,
        active_uid=participant_profile.uid,
        profiles=(participant_profile,),
    )
    monkeypatch.setattr(
        installations_module,
        "load_profile_registry",
        lambda: profiles,
    )
    monkeypatch.setattr(
        installations_module,
        "profile_store_dir",
        lambda _profile: participant,
    )
    entry = publish_artifact(
        baseline,
        baseline_profile_uid=baseline_uid,
        operation=operation,
        task="tutorial" if operation == "ATOMIZE" else "task-1",
        key="d" * 64,
        artifact={"kind": "TEST_STUDY_PREWARM", "operation": operation},
    )
    attach_shared_bundle(
        baseline_store_root=baseline,
        participant_store_root=participant,
    )
    store = MemoryStore(root=participant)

    assert declared_artifact_available(
        store,
        entry=entry,
        evidence={"request_digest": "e" * 64},
    )
    assert not (participant / "study-prewarm-installations").exists()
