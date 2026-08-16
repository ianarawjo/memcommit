"""Frozen identity checks for the Task 2 discovery calibration corpus."""

from __future__ import annotations

import json

import pytest

from memcommit.eval.task2_discovery_lock import (
    DEFAULT_TASK2_DISCOVERY_LOCK,
    LEGACY_TASK2_DISCOVERY_LOCK,
    TASK2_DISCOVERY_LOCK_REVISION,
    TASK2_DISCOVERY_LOCK_SLICES,
    Task2DiscoveryLockError,
    load_and_validate_task2_discovery_lock,
    load_task2_discovery_lock,
    validate_task2_discovery_lock,
)


def _lock_value() -> dict[str, object]:
    return json.loads(DEFAULT_TASK2_DISCOVERY_LOCK.read_text(encoding="utf-8"))


def test_task2_discovery_lock_replays_all_progressive_slices() -> None:
    lock, corpus = load_and_validate_task2_discovery_lock()

    assert lock.language == "en"
    assert lock.schema_version == 2
    assert lock.revision == TASK2_DISCOVERY_LOCK_REVISION
    assert lock.corpus_digest == (
        "2e42279f3f78e4e033d0ba951b2d90ba0859e7564dea3ea8302a422f68beef8d"
    )
    assert lock.sidecar_digest == (
        "fb0f6652f665fd65fe3b3df2468d9e04a5115efe10e578c60a588825389b9642"
    )
    assert (len(corpus.left), len(corpus.right), len(corpus.relations)) == (
        150,
        150,
        138,
    )
    assert tuple(item.group_count for item in lock.slices) == (
        TASK2_DISCOVERY_LOCK_SLICES
    )
    assert [
        (item.selected_left_count, item.selected_right_count)
        for item in lock.slices
    ] == [(29, 27), (58, 56), (112, 111), (150, 150)]
    assert [item.input_digest for item in lock.slices] == [
        "1a4771f87747ec2a64a3fb204366931f6bd3ec0e880531795034fe55bc12f44a",
        "7fcfac5377dea5a0a753ccea566be75029f176d757876ad0ced8b541acb4f4fe",
        "7e4b7fab7b6ab70dfe5d14544064aed168a3a231adb84cd4abe5557ac70ec82f",
        "8b32452536f1344582432dbc04e88a1e0772523c45ad515ecd2606c34cfd545c",
    ]
    assert lock.independent_holdout is False
    assert lock.consumed_during_optimization is True


def test_task2_discovery_v1_identity_is_archived_without_false_replay() -> None:
    lock = load_task2_discovery_lock(LEGACY_TASK2_DISCOVERY_LOCK)

    assert lock.schema_version == 1
    assert lock.revision == "task2-relation-discovery-calibration-v1"
    assert lock.corpus_digest == (
        "d98dd2bb55aa81efb692d9cd3e72aec4403d6ff5548437a17f81821c168f6ac9"
    )
    assert lock.sidecar_digest == (
        "0f6244e75fc739c752105ec02f9c5e9bee6eab8d883169644024f288676bff0c"
    )
    with pytest.raises(Task2DiscoveryLockError, match="no longer matches"):
        validate_task2_discovery_lock(lock)


def test_task2_discovery_lock_rejects_duplicate_json_keys(tmp_path) -> None:
    raw = DEFAULT_TASK2_DISCOVERY_LOCK.read_text(encoding="utf-8")
    raw = raw.replace(
        '  "language": "en",',
        '  "language": "en",\n  "language": "en",',
        1,
    )
    path = tmp_path / "duplicate.lock.json"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(Task2DiscoveryLockError, match="strict UTF-8 JSON"):
        load_task2_discovery_lock(path)


def test_task2_discovery_lock_rejects_holdout_misrepresentation(tmp_path) -> None:
    value = _lock_value()
    value["independent_holdout"] = True
    path = tmp_path / "false-holdout.lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(Task2DiscoveryLockError, match="calibration boundary"):
        load_task2_discovery_lock(path)


def test_task2_discovery_lock_detects_slice_input_drift(tmp_path) -> None:
    value = _lock_value()
    slices = value["slices"]
    assert isinstance(slices, list)
    assert isinstance(slices[0], dict)
    slices[0]["input_digest"] = "0" * 64
    path = tmp_path / "drift.lock.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    lock = load_task2_discovery_lock(path)

    with pytest.raises(Task2DiscoveryLockError, match="slice 26"):
        validate_task2_discovery_lock(lock)
