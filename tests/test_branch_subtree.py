"""Atomic lexical-subtree Branch behavior."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.persistence.store as store_module
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.console.commands.branch.receipt import BranchCreationReceipt
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    reconstruct_memory_history,
)
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _checkpoint(label: str) -> AutoCheckpoint:
    return AutoCheckpoint(
        command="fixture",
        args={"label": label},
        description=f"Created {label}.",
    )


def _source_hierarchy(store: MemoryStore) -> tuple[Context, Context, Memory]:
    child = ops.init("source/child")
    child_memory = ops.add(child, "child fact")
    store.create_context(child, _checkpoint("child"))

    root = ops.init("source")
    ops.add(root, "root fact")
    ops.embed(child, root)
    root.add(
        MemoryRef(
            uid="child-memory-ref",
            target_context_uid=child.uid,
            target_context_name=child.name,
            target_memory_uid=child_memory.uid,
            target=child_memory,
        )
    )
    store.create_context(root, _checkpoint("root"))
    store.set_current(root.name)
    return root, child, child_memory


def test_explicit_subtree_branch_clones_hierarchy_and_internal_pointers(
    isolated_store,
):
    store = MemoryStore()
    source_root, source_child, child_memory = _source_hierarchy(store)
    root_history = store.list_checkpoints(source_root.name)
    child_history = store.list_checkpoints(source_child.name)

    result = runner.invoke(
        app,
        ["branch", "experiment", "-r"],
    )

    assert result.exit_code == 0
    assert "Branched subtree 'source' → 'experiment'" in result.output
    assert "2 Context(s), 1 descendant(s)" in result.output
    assert store.current_context_name() == "experiment"
    branch_root = store.load_direct("experiment")
    branch_child = store.load_direct("experiment/child")
    assert branch_root.uid != source_root.uid
    assert branch_child.uid != source_child.uid
    branch_child_memory = next(
        item for item in branch_child.iter_items() if isinstance(item, Memory)
    )
    branch_root_memory = next(
        item for item in branch_root.iter_items() if isinstance(item, Memory)
    )
    assert branch_child_memory.uid != child_memory.uid
    assert branch_child_memory.content == child_memory.content
    embedded = next(
        item for item in branch_root.iter_items() if isinstance(item, Context)
    )
    assert (embedded.uid, embedded.name) == (
        branch_child.uid,
        branch_child.name,
    )
    reference = branch_root.memories["child-memory-ref"]
    assert isinstance(reference, MemoryRef)
    assert (reference.target_context_uid, reference.target_context_name) == (
        branch_child.uid,
        branch_child.name,
    )
    assert reference.target_memory_uid == branch_child_memory.uid
    branch_root_history = store.list_checkpoints("experiment")
    assert branch_root_history[0]["command"] == "branch"
    assert [entry["uid"] for entry in branch_root_history[1:]] == [
        entry["uid"] for entry in root_history
    ]
    history_embedded = next(
        value
        for value in branch_root_history[1]["snapshot"]["memories"].values()
        if value["type"] == "context_ref"
    )
    assert (history_embedded["uid"], history_embedded["name"]) == (
        branch_child.uid,
        branch_child.name,
    )
    branch_child_history = store.list_checkpoints("experiment/child")
    assert branch_child_history[0]["command"] == "branch"
    assert branch_child_history[1:] == child_history
    child_trace = reconstruct_memory_history(store, branch_child, branch_child_memory.uid)
    assert child_trace.warnings == ()
    branch_event = next(
        event for event in child_trace.events if event.kind == "BRANCHED"
    )
    assert branch_event.context_transition is not None
    assert branch_event.context_transition.source.name == "source/child"
    assert branch_event.context_transition.target.name == "experiment/child"
    assert branch_event.command_operation is not None
    assert {context.name for context in branch_event.command_operation.contexts} == {
        "experiment",
        "experiment/child",
    }

    changed = store.load_for_update("experiment/child")
    ops.add(changed, "branch-only fact")
    store.save(changed, _checkpoint("branch edit"))
    assert [
        item.content
        for item in store.load_direct("source/child").iter_items()
        if isinstance(item, Memory)
    ] == ["child fact"]

    # Reverting the root through inherited history must not reconnect its
    # embedded child to the original Source hierarchy.
    store.revert(
        "experiment",
        branch_root_history[1]["uid"],
        keep_history=True,
    )
    restored_root = store.load_direct("experiment")
    restored_root_memory = next(
        item for item in restored_root.iter_items() if isinstance(item, Memory)
    )
    assert restored_root_memory.uid == branch_root_memory.uid
    assert restored_root_memory.uid not in source_root.memories
    restored_embed = next(
        item for item in restored_root.iter_items() if isinstance(item, Context)
    )
    assert (restored_embed.uid, restored_embed.name) == (
        branch_child.uid,
        branch_child.name,
    )
    restored_reference = restored_root.memories["child-memory-ref"]
    assert isinstance(restored_reference, MemoryRef)
    assert restored_reference.target_memory_uid == branch_child_memory.uid


def test_recursive_branch_undo_cancels_the_complete_created_tree_and_redo_restores_it(
    isolated_store,
):
    store = MemoryStore()
    source_root, source_child, _memory = _source_hierarchy(store)
    source_records = {
        source_root.name: store.load_direct(source_root.name).to_dict(),
        source_child.name: store.load_direct(source_child.name).to_dict(),
    }

    branched = runner.invoke(app, ["branch", "experiment", "-r"])

    assert branched.exit_code == 0, branched.output
    branch_records = {
        name: store.load_direct(name).to_dict()
        for name in ("experiment", "experiment/child")
    }
    branch_history_uids = {
        name: [entry["uid"] for entry in store.list_checkpoints(name)]
        for name in branch_records
    }

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    undo_command = (
        "Undid command: mem branch experiment --from source --source-descendants"
    )
    assert undo_command in undone.output
    assert "Affected Contexts: 2" in undone.output
    assert not store.context_exists("experiment")
    assert not store.context_exists("experiment/child")
    assert store.current_context_name() == "source"
    assert {
        name: store.load_direct(name).to_dict() for name in source_records
    } == source_records

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output
    redo_command = (
        "Redid command: mem branch experiment --from source --source-descendants"
    )
    assert redo_command in redone.output
    assert store.current_context_name() == "experiment"
    assert {
        name: store.load_direct(name).to_dict() for name in branch_records
    } == branch_records
    for name, original_uids in branch_history_uids.items():
        restored_uids = [entry["uid"] for entry in store.list_checkpoints(name)]
        assert restored_uids[-len(original_uids) :] == original_uids


def test_recursive_branch_undo_failure_restores_every_created_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _source_hierarchy(store)
    assert runner.invoke(app, ["branch", "experiment", "-r"]).exit_code == 0
    records = {
        name: store.load_direct(name).to_dict()
        for name in ("experiment", "experiment/child")
    }
    histories = {name: store.list_checkpoints(name) for name in records}
    original_save = MemoryStore._save_locked
    undo_saves = 0

    def fail_second_undo(self, context, auto_checkpoint, **kwargs):
        nonlocal undo_saves
        if auto_checkpoint is not None and auto_checkpoint.command == "undo":
            undo_saves += 1
            if undo_saves == 2:
                raise OSError("injected Branch Undo failure")
        return original_save(self, context, auto_checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_undo)

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 1
    assert "injected Branch Undo failure" in undone.stderr
    assert store.current_context_name() == "experiment"
    assert {name: store.load_direct(name).to_dict() for name in records} == records
    assert {name: store.list_checkpoints(name) for name in histories} == histories
    assert store.list_command_context_archives() == ()


def test_exact_branch_keeps_legacy_shallow_live_reference(isolated_store):
    store = MemoryStore()
    _source_root, source_child, _ = _source_hierarchy(store)

    result = runner.invoke(app, ["branch", "experiment"])

    assert result.exit_code == 0
    assert not store.context_exists("experiment/child")
    branch_root = store.load_direct("experiment")
    embedded = next(
        item for item in branch_root.iter_items() if isinstance(item, Context)
    )
    assert (embedded.uid, embedded.name) == (
        source_child.uid,
        source_child.name,
    )


def test_interactive_receipt_can_request_the_subtree(isolated_store, monkeypatch):
    store = MemoryStore()
    _source_hierarchy(store)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.branch.command.choose_branch_creation",
        lambda *args, **kwargs: BranchCreationReceipt(
            source_name="source",
            target_name="experiment",
            include_descendants=True,
        ),
    )

    result = runner.invoke(app, ["branch"])

    assert result.exit_code == 0
    assert store.context_exists("experiment")
    assert store.context_exists("experiment/child")


def test_subtree_destination_conflict_preflights_the_whole_batch(isolated_store):
    store = MemoryStore()
    _source_hierarchy(store)
    occupied = ops.init("experiment/child")
    ops.add(occupied, "existing owner")
    store.create_context(occupied)

    result = runner.invoke(
        app,
        ["branch", "experiment", "--source-descendants"],
    )

    assert result.exit_code == 1
    assert "experiment/child" in result.stderr
    assert "already exists" in result.stderr
    assert not store.context_exists("experiment")
    assert [
        item.content for item in store.load_direct("experiment/child").iter_items()
    ] == ["existing owner"]
    assert store.current_context_name() == "source"


def test_subtree_branch_rejects_new_descendant_after_snapshot(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _source_hierarchy(store)
    original = ops.branch_subtree

    def add_descendant_then_branch(contexts, source_root, target_root):
        result = original(contexts, source_root, target_root)
        store.create_context(ops.init("source/new-child"))
        return result

    monkeypatch.setattr(
        "memcommit.application.operations.branch.runtime.ops.branch_subtree",
        add_descendant_then_branch,
    )

    result = runner.invoke(
        app,
        ["branch", "experiment", "--source-descendants"],
    )

    assert result.exit_code == 1
    assert "Source Context subtree changed" in result.stderr
    assert not store.context_exists("experiment")
    assert not store.context_exists("experiment/child")
    assert store.context_exists("source/new-child")


def test_subtree_branch_rejects_changed_descendant_history(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _source_hierarchy(store)
    original = ops.branch_subtree

    def checkpoint_child_then_branch(contexts, source_root, target_root):
        result = original(contexts, source_root, target_root)
        child = store.load_direct("source/child")
        store.checkpoint(
            child,
            message="concurrent child checkpoint",
            command="checkpoint",
        )
        return result

    monkeypatch.setattr(
        "memcommit.application.operations.branch.runtime.ops.branch_subtree",
        checkpoint_child_then_branch,
    )

    result = runner.invoke(
        app,
        ["branch", "experiment", "--source-descendants"],
    )

    assert result.exit_code == 1
    assert "Checkpoint history for 'source/child' changed" in result.stderr
    assert not store.context_exists("experiment")
    assert not store.context_exists("experiment/child")


def test_subtree_branch_rolls_back_every_target_after_copy_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _source_hierarchy(store)
    original_write = store_module._write_json_atomic

    def fail_child_history(path, data):
        if "experiment/child/checkpoints" in path.as_posix():
            raise OSError("forced subtree checkpoint failure")
        return original_write(path, data)

    monkeypatch.setattr(store_module, "_write_json_atomic", fail_child_history)

    result = runner.invoke(
        app,
        ["branch", "experiment", "--source-descendants"],
    )

    assert result.exit_code == 1
    assert "forced subtree checkpoint failure" in result.stderr
    assert not store.context_exists("experiment")
    assert not store.context_exists("experiment/child")
    assert store.current_context_name() == "source"
