from __future__ import annotations

import json

import pytest

from memcommit.store import MemoryStore
from memcommit.study_prewarm.installations import (
    declared_installation_matches,
    declared_installation_path,
    record_declared_installation,
)
from memcommit.study_prewarm.registry import (
    StudyPrewarmEntry,
    StudyPrewarmRegistryError,
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
