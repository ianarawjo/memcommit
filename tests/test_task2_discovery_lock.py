"""Frozen identity checks for the Task 2 discovery calibration corpus."""

from __future__ import annotations

import json

import pytest

from memcommit.eval.task2_discovery_lock import (
    DEFAULT_TASK2_DISCOVERY_LOCK,
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
    assert lock.corpus_digest == (
        "d98dd2bb55aa81efb692d9cd3e72aec4403d6ff5548437a17f81821c168f6ac9"
    )
    assert lock.sidecar_digest == (
        "0f6244e75fc739c752105ec02f9c5e9bee6eab8d883169644024f288676bff0c"
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
        "90ba30ad9f89dbe0c6c894913c7a786f4b9ccabf53194abb1532563870dcaa1a",
        "ae890afbba0a2aff1927bc9e0ed15a82dc34d61e9e988d151891346fee6ae46a",
        "ee384ab503ef6692ab0fc9a0fa5df7fb382dbef2523be31e0244bd1567eca8f5",
        "50ebd46986c267b1350021f38c9c28159c8cac3443109a3194f02c27ffbff08d",
    ]
    assert lock.independent_holdout is False
    assert lock.consumed_during_optimization is True


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
