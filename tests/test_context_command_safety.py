"""Cross-command regression tests for shared ordinary-Context boundaries."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.commands.branch_dialog import BranchCreationReceipt
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _save(store: MemoryStore, context: Context) -> Context:
    store.create_context(context)
    return context


def _rename(store: MemoryStore, old: str, new: str) -> None:
    store.rename_contexts(store.plan_context_rename(old, new))


def test_delete_approval_does_not_delete_recreated_name(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    victim = _save(store, ops.init("victim"))
    store.set_current(victim.name)
    replacement: Context | None = None

    def replace_during_approval(*args, **kwargs):
        nonlocal replacement
        store.delete(victim.name)
        replacement = ops.init(victim.name)
        ops.add(replacement, "new owner")
        store.create_context(replacement)
        return True

    monkeypatch.setattr(
        "memcommit.commands.delete.typer.confirm",
        replace_during_approval,
    )

    result = runner.invoke(app, ["delete", victim.name])

    assert result.exit_code == 1
    assert "changed after deletion was reviewed" in result.stderr
    assert replacement is not None
    loaded = store.load_direct(victim.name)
    assert loaded.uid == replacement.uid
    assert [item.content for item in loaded.iter_items()] == ["new owner"]


def test_embed_rejects_source_renamed_after_load(isolated_store, monkeypatch):
    store = MemoryStore()
    _save(store, ops.init("old"))
    owner = _save(store, ops.init("owner"))
    store.set_current(owner.name)
    original_embed = ops.embed

    def rename_then_embed(child, parent, **kwargs):
        _rename(store, "old", "new")
        original_embed(child, parent, **kwargs)

    monkeypatch.setattr("memcommit.embed_runtime.ops.embed", rename_then_embed)

    result = runner.invoke(app, ["embed", "old", "--into", owner.name])

    assert result.exit_code == 1
    assert "source Context no longer exists" in result.stderr
    assert store.context_exists("new")
    assert not any(
        isinstance(item, Context)
        for item in store.load_direct(owner.name).iter_items()
    )


def test_merge_rejects_source_renamed_after_load(isolated_store, monkeypatch):
    store = MemoryStore()
    source = ops.init("old")
    ops.add(source, "source fact")
    _save(store, source)
    owner = _save(store, ops.init("owner"))
    store.set_current(owner.name)
    from memcommit.merge_runtime import plan_context_merge

    def rename_then_plan(candidate, target, **kwargs):
        _rename(store, "old", "new")
        return plan_context_merge(candidate, target, **kwargs)

    # The runtime no longer delegates classification to the legacy mutable
    # ops.merge helper. Interpose at the new pure planning boundary and retain
    # the same rename-between-load-and-apply safety assertion.
    monkeypatch.setattr(
        "memcommit.merge_runtime.plan_context_merge",
        rename_then_plan,
    )

    result = runner.invoke(app, ["merge", "old"])

    assert result.exit_code == 1
    assert "source Context no longer exists" in result.stderr
    assert tuple(store.load_direct(owner.name).iter_items()) == ()


def test_reference_rejects_source_renamed_after_load(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("old")
    memory = ops.add(source, "source fact")
    _save(store, source)
    owner = _save(store, ops.init("owner"))
    store.set_current(owner.name)
    original_reference = ops.reference_memory

    def rename_then_reference(item, candidate, target):
        _rename(store, "old", "new")
        return original_reference(item, candidate, target)

    monkeypatch.setattr(
        "memcommit.operations.reference.runtime.ops.reference_memory",
        rename_then_reference,
    )

    result = runner.invoke(
        app,
        ["reference", memory.uid[:8], "--from", "old", "--into", owner.name],
    )

    assert result.exit_code == 1
    assert "source Context no longer exists" in result.stderr
    assert tuple(store.load_direct(owner.name).iter_items()) == ()


def test_branch_does_not_overwrite_concurrent_destination(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save(store, ops.init("source"))
    store.set_current(source.name)
    original_branch = ops.branch
    competitor: Context | None = None

    def create_competitor(candidate, name):
        nonlocal competitor
        result = original_branch(candidate, name)
        competitor = ops.init(name)
        ops.add(competitor, "concurrent owner")
        store.create_context(competitor)
        return result

    monkeypatch.setattr(
        "memcommit.operations.branch.runtime.ops.branch",
        create_competitor,
    )

    result = runner.invoke(app, ["branch", "feature"])

    assert result.exit_code == 1
    assert "already exists" in result.stderr
    assert competitor is not None
    loaded = store.load_direct("feature")
    assert loaded.uid == competitor.uid
    assert [item.content for item in loaded.iter_items()] == [
        "concurrent owner"
    ]
    assert store.current_context_name() == source.name


def test_branch_preserves_concurrent_current_selection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save(store, ops.init("source"))
    _save(store, ops.init("other"))
    store.set_current(source.name)
    original_branch = ops.branch

    def switch_then_branch(candidate, name):
        result = original_branch(candidate, name)
        store.set_current("other")
        return result

    monkeypatch.setattr(
        "memcommit.operations.branch.runtime.ops.branch",
        switch_then_branch,
    )

    result = runner.invoke(app, ["branch", "feature"])

    assert result.exit_code == 1
    assert "current Context changed" in result.stderr
    assert store.current_context_name() == "other"
    assert not store.context_exists("feature")


def test_bare_branch_preserves_a_switch_made_while_the_picker_is_open(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save(store, ops.init("source"))
    _save(store, ops.init("other"))
    store.set_current(source.name)

    def switch_then_choose(*args, **kwargs):
        store.set_current("other")
        return BranchCreationReceipt("source", "feature")

    monkeypatch.setattr(
        "memcommit.commands.branch.choose_branch_creation",
        switch_then_choose,
    )

    result = runner.invoke(app, ["branch"])

    assert result.exit_code == 1
    assert "current Context changed" in result.stderr
    assert store.current_context_name() == "other"
    assert not store.context_exists("feature")


def test_bare_init_preserves_a_switch_made_while_the_editor_is_open(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save(store, ops.init("source"))
    _save(store, ops.init("other"))
    store.set_current(source.name)

    def switch_then_choose(view):
        store.set_current("other")
        return "new-context"

    monkeypatch.setattr(
        "memcommit.commands.init.choose_context_name",
        switch_then_choose,
    )

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "current Context changed" in result.stderr
    assert store.current_context_name() == "other"
    assert not store.context_exists("new-context")


def test_bare_branch_does_not_overwrite_a_target_created_during_setup(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "source fact")
    _save(store, source)
    store.set_current(source.name)

    def create_target_then_choose(*args, **kwargs):
        target = ops.init("feature")
        ops.add(target, "concurrent fact")
        _save(store, target)
        return BranchCreationReceipt("source", "feature")

    monkeypatch.setattr(
        "memcommit.commands.branch.choose_branch_creation",
        create_target_then_choose,
    )

    result = runner.invoke(app, ["branch"])

    assert result.exit_code == 1
    assert "already exists" in result.stderr
    preserved = store.load_direct("feature")
    assert [item.content for item in preserved.memories.values()] == [
        "concurrent fact"
    ]
    assert store.current_context_name() == "source"


def test_branch_rejects_history_changed_after_snapshot(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    store.create_context(
        source,
        AutoCheckpoint(command="init", args={}, description="initial"),
    )
    store.set_current(source.name)
    original_branch = ops.branch

    def checkpoint_then_branch(candidate, name):
        result = original_branch(candidate, name)
        store.checkpoint(
            candidate,
            message="concurrent checkpoint",
            command="checkpoint",
        )
        return result

    monkeypatch.setattr(
        "memcommit.operations.branch.runtime.ops.branch",
        checkpoint_then_branch,
    )

    result = runner.invoke(app, ["branch", "feature"])

    assert result.exit_code == 1
    assert "Checkpoint history" in result.stderr
    assert not store.context_exists("feature")
    assert store.current_context_name() == source.name


def test_revert_preserves_unavailable_embedded_context_pointer(isolated_store):
    store = MemoryStore()
    child = _save(store, ops.init("child"))
    parent = ops.init("parent")
    ops.embed(child, parent)
    old_memory = ops.add(parent, "old state")
    store.create_context(
        parent,
        AutoCheckpoint(command="init", args={}, description="initial"),
    )
    target = store.list_checkpoints(parent.name)[0]
    current = store.load_direct(parent.name)
    ops.add(current, "new state")
    store.save(
        current,
        AutoCheckpoint(command="add", args={}, description="newer"),
    )
    store.delete(child.name)

    store.revert(parent.name, target["uid"][:8])

    restored = store.load_direct(parent.name)
    assert [
        (item.uid, item.name)
        for item in restored.iter_items()
        if isinstance(item, Context)
    ] == [(child.uid, child.name)]
    assert [
        item.uid for item in restored.iter_items() if isinstance(item, Memory)
    ] == [old_memory.uid]


def test_revert_exception_restores_exact_context_and_history(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("history")
    ops.add(context, "old state")
    store.create_context(
        context,
        AutoCheckpoint(command="init", args={}, description="initial"),
    )
    target = store.list_checkpoints(context.name)[0]
    current = store.load_direct(context.name)
    ops.add(current, "new state")
    store.save(
        current,
        AutoCheckpoint(command="add", args={}, description="newer"),
    )
    context_path = store._context_file(context.name)
    checkpoint_dir = store._checkpoints_dir(context.name)
    before_context = context_path.read_bytes()
    before_history = {
        path.name: path.read_bytes()
        for path in sorted(checkpoint_dir.glob("*.json"))
    }
    original_write = store_module._write_json_atomic

    def fail_context_replace(path, data):
        if path == context_path:
            raise OSError("injected Context replace failure")
        return original_write(path, data)

    monkeypatch.setattr(store_module, "_write_json_atomic", fail_context_replace)

    with pytest.raises(OSError, match="injected Context replace failure"):
        store.revert(context.name, target["uid"][:8])

    assert context_path.read_bytes() == before_context
    assert {
        path.name: path.read_bytes()
        for path in sorted(checkpoint_dir.glob("*.json"))
    } == before_history
