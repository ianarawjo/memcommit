"""Exact legacy Save As recovery and failure boundaries across real Store files."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.atomize_restoration_support import create_save_as, snapshot_records
from memcommit.application.capabilities.command_recovery import build_command_stacks
from memcommit.persistence import store as store_module
from memcommit.persistence.store.command_restoration.handlers.atomize import restoration


@pytest.mark.parametrize("with_workbench", [True, False])
def test_save_as_undo_redo_preserves_identity_analysis_and_checkpoint_lineage(
    isolated_store, with_workbench
):
    case = create_save_as(with_workbench=with_workbench)
    store = case.store
    source_before = store.load_direct(case.source.name).to_dict()
    for _ in range(2):
        undone = store.restore_recent_context_command("undo")
        assert undone.unit.uid == case.unit.uid
        assert not store.context_exists(case.output.name)
        assert store.load_atomize_analysis(case.output.uid) is None
        assert store.current_context_name() == case.source.name
        reviewing = store.load_atomize_workbench(case.analysis)
        assert (None if reviewing is None else reviewing.to_dict()) == (
            None if case.reviewing is None else case.reviewing.to_dict()
        )
        assert build_command_stacks(store).redo[-1].uid == case.unit.uid
        redone = store.restore_recent_context_command("redo")
        assert redone.unit.uid == case.unit.uid
        assert store.load_direct(case.output.name).to_dict() == case.output.to_dict()
        assert store.load_atomize_analysis(case.output.uid).uid == case.analysis.uid
        assert store.current_context_name() == case.output.name
        terminal = store.load_atomize_workbench(case.analysis)
        assert (None if terminal is None else terminal.to_dict()) == (
            None if case.terminal is None else case.terminal.to_dict()
        )
        checkpoint_uids = {
            item["uid"] for item in store.list_checkpoints(case.output.name)
        }
        assert {
            case.checkpoint.uid,
            undone.checkpoints[0].uid,
            redone.checkpoints[0].uid,
        } <= checkpoint_uids
        assert not case.archive.exists()
        assert store.load_direct(case.source.name).to_dict() == source_before


@pytest.mark.parametrize("direction", ["undo", "redo"])
@pytest.mark.parametrize("move_number", [1, 2, 3])
def test_each_partial_file_move_failure_restores_all_records(
    isolated_store, monkeypatch, direction, move_number
):
    case = create_save_as()
    if direction == "redo":
        case.store.restore_recent_context_command("undo")
    before = snapshot_records(case.store)
    original = Path.rename
    calls = 0

    def fail_move(path, target):
        nonlocal calls
        calls += 1
        if calls == move_number:
            raise OSError("injected file move failure")
        return original(path, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_move)
        with pytest.raises(OSError, match="injected file move"):
            case.store.restore_recent_context_command(direction)
    assert snapshot_records(case.store) == before
    case.store.restore_recent_context_command(direction)


@pytest.mark.parametrize("direction", ["undo", "redo"])
@pytest.mark.parametrize(
    "step,after_write",
    [
        ("checkpoint", False),
        ("context", False),
        ("workbench", False),
        ("workbench", True),
        ("state", False),
        ("state", True),
    ],
)
def test_failed_record_writes_restore_the_whole_attempt(
    isolated_store, monkeypatch, direction, step, after_write
):
    case = create_save_as()
    store = case.store
    if direction == "redo":
        store.restore_recent_context_command("undo")
    before = snapshot_records(store)
    attribute = {
        "checkpoint": "_checkpoint_locked",
        "context": "_write_json_atomic",
        "workbench": "_save_atomize_workbench_locked",
        "state": "_write_state",
    }[step]
    owner = store_module if step == "context" else store
    original = getattr(owner, attribute)
    failed = False

    def fail_once(*args, **kwargs):
        nonlocal failed
        if failed or (
            step == "context" and args[0] != store._context_file(case.output.name)
        ):
            return original(*args, **kwargs)
        failed = True
        if after_write:
            original(*args, **kwargs)
        raise OSError("injected record write failure")

    with monkeypatch.context() as patch:
        patch.setattr(owner, attribute, fail_once)
        with pytest.raises(OSError, match="injected record write"):
            store.restore_recent_context_command(direction)
    assert snapshot_records(store) == before
    store.restore_recent_context_command(direction)


def test_undo_archive_preparation_failure_does_not_publish_checkpoint(
    isolated_store, monkeypatch
):
    case = create_save_as()
    before = snapshot_records(case.store)
    original = Path.mkdir

    def fail_archive(path, *args, **kwargs):
        if path == case.archive:
            raise OSError("injected archive creation failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_archive)
    with pytest.raises(OSError, match="injected archive creation"):
        case.store.restore_recent_context_command("undo")
    assert snapshot_records(case.store) == before


def test_undo_manifest_failure_restores_files_checkpoint_and_workbench(
    isolated_store, monkeypatch
):
    case = create_save_as()
    before = snapshot_records(case.store)

    def fail_manifest(*args):
        raise OSError("injected manifest failure")

    monkeypatch.setattr(restoration, "_write_json_atomic", fail_manifest)
    with pytest.raises(OSError, match="injected manifest failure"):
        case.store.restore_recent_context_command("undo")
    assert snapshot_records(case.store) == before


@pytest.mark.parametrize("step", ["unlink", "rmdir"])
def test_redo_archive_cleanup_failure_restores_navigation_and_retryable_archive(
    isolated_store, monkeypatch, step
):
    case = create_save_as()
    case.store.restore_recent_context_command("undo")
    before = snapshot_records(case.store)
    original = getattr(Path, step)
    target = case.archive / "manifest.json" if step == "unlink" else case.archive

    def fail_cleanup(path, *args, **kwargs):
        if path == target:
            raise OSError("injected archive cleanup failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, step, fail_cleanup)
        with pytest.raises(OSError, match="injected archive cleanup"):
            case.store.restore_recent_context_command("redo")
    assert snapshot_records(case.store) == before
    case.store.restore_recent_context_command("redo")


def test_redo_rejects_manifest_that_disagrees_with_creation_receipt(isolated_store):
    case = create_save_as()
    case.store.restore_recent_context_command("undo")
    path = case.archive / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["current_before"] = "unrelated/context"
    path.write_text(json.dumps(manifest))
    before = snapshot_records(case.store)
    with pytest.raises(RuntimeError, match="archived Atomize result changed"):
        case.store.restore_recent_context_command("redo")
    assert snapshot_records(case.store) == before


def test_state_lock_remains_held_during_cleanup_failure_compensation(
    isolated_store, monkeypatch
):
    case = create_save_as()
    store = case.store
    store.restore_recent_context_command("undo")
    before = snapshot_records(store)
    lock = store._state_write_lock
    write = store._write_state
    rmdir = Path.rmdir
    locked = False
    observed_currents = []

    @contextmanager
    def track_state_lock():
        nonlocal locked
        with lock():
            locked = True
            try:
                yield
            finally:
                locked = False

    def write_under_lock(state):
        assert locked
        observed_currents.append(state["current"])
        write(state)

    def fail_archive_removal(path):
        if path == case.archive:
            raise OSError("injected cleanup failure after navigation")
        rmdir(path)

    monkeypatch.setattr(store, "_state_write_lock", track_state_lock)
    monkeypatch.setattr(store, "_write_state", write_under_lock)
    monkeypatch.setattr(Path, "rmdir", fail_archive_removal)
    with pytest.raises(OSError, match="injected cleanup"):
        store.restore_recent_context_command("redo")
    assert observed_currents == [case.output.name, case.source.name]
    assert not locked
    assert snapshot_records(store) == before
