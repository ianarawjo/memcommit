"""Canonical checkpoint-window and revision History contracts."""

from __future__ import annotations

from memcommit.application.capabilities import ops
from memcommit.application.capabilities.history.query.checkpoint_history_slicing import (
    build_checkpoint_history_slice,
)
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.persistence.store import MemoryStore


def _save(store: MemoryStore, context, command: str) -> str:
    store.save(
        context,
        AutoCheckpoint(command=command, args={}, description=f"Ran {command}"),
    )
    return store.list_checkpoints(context.name)[0]["uid"]


def test_checkpoint_history_slice_owns_reference_embed_and_revision_queries(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("history-slice")
    store.save(context)
    initial_uid = _save(store, context, "init")
    memory = ops.add(context, "Before")
    add_uid = _save(store, context, "add")
    context.replace(Memory(memory.uid, "After"))
    edit_uid = _save(store, context, "edit")

    history = build_checkpoint_history_slice(store, context.name)

    assert history.context_uid == context.uid
    assert [item.uid for item in history.reference((initial_uid, edit_uid))] == [
        initial_uid,
        edit_uid,
    ]
    assert [item.uid for item in history.after(add_uid)] == [add_uid, edit_uid]
    revision = history.revision(edit_uid)
    assert revision.before_snapshot["memories"][memory.uid]["content"] == "Before"
    assert revision.after_snapshot["memories"][memory.uid]["content"] == "After"
    assert [transition.kind for transition in history.transitions(edit_uid)] == [
        "EDITED"
    ]


def test_checkpoint_history_slice_freezes_store_evidence_once(isolated_store):
    store = MemoryStore()
    context = ops.init("one-read")
    store.save(context)
    _save(store, context, "init")

    class CountingSource:
        def __init__(self):
            self.checkpoint_reads = 0

        def load_direct(self, name):
            return store.load_direct(name)

        def list_checkpoints(self, name):
            self.checkpoint_reads += 1
            return store.list_checkpoints(name)

        def list_context_names(self):
            return store.list_context_names()

        def load_atomize_analysis(self, context_uid):
            return None

    source = CountingSource()

    history = build_checkpoint_history_slice(source, context.name)

    assert source.checkpoint_reads == 1
    assert len(history.timeline.checkpoints) == 1
    assert len(history.physical_entries) == 1
