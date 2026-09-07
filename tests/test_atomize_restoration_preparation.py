"""Restoration plans reject stale state without publishing any partial result."""

import copy
from dataclasses import replace
import uuid

import pytest

from tests.atomize_restoration_support import create_save_as, snapshot_records
from memcommit.application.capabilities import ops
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.command_restoration.handlers.atomize.preparation import (
    load_undo_context,
    prepare_redo,
    prepare_undo,
)
from memcommit.persistence.store.command_restoration.handlers.atomize.records import (
    AtomizeArchiveManifest,
    load_creation_receipt,
)
from memcommit.persistence.store.command_restoration.handlers.atomize.restoration import (
    _session_locks,
)


def test_preparation_only_reads_and_changes_detached_workbench_copies(isolated_store):
    case = create_save_as()
    store = case.store
    change = case.unit.changes[0]
    before = snapshot_records(store)
    with store._command_write_lock(), store._context_graph_lock(exclusive=False):
        with store._context_write_lock(change.context_name):
            current = load_undo_context(store, change)
            receipt = load_creation_receipt(
                store.list_checkpoints(change.context_name), change
            )
            with _session_locks(store, case.source.uid, case.output.uid):
                prepared = prepare_undo(store, case.unit, current, receipt)
                assert prepared.workbench_before.application is not None
                assert prepared.workbench_after.application is None
    assert snapshot_records(store) == before
    store.restore_recent_context_command("undo")
    before = snapshot_records(store)
    with store._command_write_lock(), store._context_graph_lock(exclusive=False):
        with store._context_write_lock(change.context_name):
            archive, raw, context, entries = store._load_command_context_archive(
                change.checkpoint_uid
            )
            with _session_locks(store, case.source.uid, case.output.uid):
                prepared = prepare_redo(
                    store,
                    case.unit,
                    archive,
                    context,
                    AtomizeArchiveManifest.from_dict(raw),
                    load_creation_receipt(entries, change),
                )
                assert prepared.workbench_before.application is None
                assert prepared.workbench_after.application is not None
    assert snapshot_records(store) == before


@pytest.mark.parametrize("direction", ["undo", "redo"])
@pytest.mark.parametrize("changed", ["source_analysis", "workbench", "output"])
def test_changed_records_reject_restoration_before_any_writes(
    isolated_store, direction, changed
):
    case = create_save_as()
    store = case.store
    if direction == "redo":
        store.restore_recent_context_command("undo")
    if changed == "source_analysis":
        store.save_atomize_analysis(replace(case.analysis, uid=str(uuid.uuid4())))
    elif changed == "workbench":
        workbench = copy.deepcopy(
            case.terminal if direction == "undo" else case.reviewing
        )
        workbench.toggle_sort()
        store.save_atomize_workbench(workbench)
    elif direction == "undo":
        output = store.load_direct(case.output.name)
        ops.add(output, "An independent edit.")
        store.save(output)
    else:
        store.save_atomize_analysis(
            replace(
                case.analysis,
                context_uid=case.output.uid,
                context_name=case.output.name,
            )
        )
    before = snapshot_records(store)
    with pytest.raises((ValueError, ConcurrentContextUpdateError)):
        store.restore_recent_context_command(direction)
    assert snapshot_records(store) == before


def test_unrelated_current_context_is_preserved_across_undo_redo(isolated_store):
    case = create_save_as()
    other = ops.init("unrelated")
    case.store.save(other)
    case.store.set_current(other.name)
    navigation = copy.deepcopy(case.store._read_state())
    case.store.restore_recent_context_command("undo")
    assert case.store._read_state() == navigation
    case.store.restore_recent_context_command("redo")
    assert case.store._read_state() == navigation
