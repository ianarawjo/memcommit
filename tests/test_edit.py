"""Deterministic direct-Memory editing contracts."""

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.store import MemoryStore


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def current_memory() -> Memory:
    item = next(iter(MemoryStore().load_current().iter_items()))
    assert isinstance(item, Memory)
    return item


def test_ops_edit_preserves_uid_and_explicit_order():
    ctx = ops.init("ordered")
    first = ops.add(ctx, "first")
    target = ops.add(ctx, "before")
    last = ops.add(ctx, "last")
    order_before = ctx.ordered_uids()

    original = ops.edit(ctx, target.uid[:8], "after")

    assert original.uid == target.uid
    assert original.content == "before"
    assert ctx.ordered_uids() == order_before == [first.uid, target.uid, last.uid]
    edited = ctx.memories[target.uid]
    assert isinstance(edited, Memory)
    assert edited.uid == target.uid
    assert edited.content == "after"


def test_ops_edit_rejects_non_memory_direct_item():
    parent = ops.init("parent")
    child = ops.init("child")
    ops.embed(child, parent)

    with pytest.raises(TypeError, match="not a Memory directly owned"):
        ops.edit(parent, child.uid[:8], "replacement")


def test_ops_edit_uid_prefix_ignores_colliding_context_name():
    parent = ops.init("parent")
    memory = Memory(
        uid="aaaa1111-0000-0000-0000-000000000000",
        content="before",
    )
    child = ops.init("aaaa")
    parent.add(memory)
    ops.embed(child, parent)

    ops.edit(parent, "aaaa", "after")

    assert parent.memories[memory.uid].content == "after"
    assert parent.memories[child.uid] is child


def test_cli_edit_replaces_content_and_renders_before_after(isolated_store):
    assert invoke("init", "notes").exit_code == 0
    assert invoke("add", "old content").exit_code == 0
    memory = current_memory()

    result = invoke("edit", memory.uid[:8], "new content")

    assert result.exit_code == 0
    assert f"Edited [{memory.uid[:8]}]" in result.output
    assert "- old content" in result.output
    assert "+ new content" in result.output
    stored = MemoryStore().load_current().memories[memory.uid]
    assert isinstance(stored, Memory)
    assert stored.content == "new content"


def test_cli_edit_creates_one_post_edit_checkpoint(isolated_store):
    invoke("init", "notes")
    invoke("add", "old content")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid, "new content")

    assert result.exit_code == 0
    checkpoints = store.list_checkpoints("notes")
    assert len(checkpoints) == checkpoint_count + 1
    checkpoint = checkpoints[0]
    assert checkpoint["command"] == "edit"
    assert checkpoint["args"] == {
        "uid": memory.uid,
        "content": "new content",
    }
    assert (
        checkpoint["snapshot"]["memories"][memory.uid]["content"]
        == "new content"
    )


def test_revert_to_add_checkpoint_restores_pre_edit_content(isolated_store):
    invoke("init", "notes")
    invoke("add", "old content")
    store = MemoryStore()
    memory = current_memory()
    add_checkpoint = next(
        checkpoint
        for checkpoint in store.list_checkpoints("notes")
        if checkpoint["command"] == "add"
    )
    invoke("edit", memory.uid[:8], "new content")

    result = invoke("revert", add_checkpoint["uid"][:8])

    assert result.exit_code == 0
    restored = store.load("notes").memories[memory.uid]
    assert isinstance(restored, Memory)
    assert restored.content == "old content"


def test_same_content_is_noop_without_checkpoint(isolated_store):
    invoke("init", "notes")
    invoke("add", "unchanged content")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid[:8], "unchanged content")

    assert result.exit_code == 0
    assert "unchanged" in result.output
    assert len(store.list_checkpoints("notes")) == checkpoint_count


def test_whitespace_replacement_is_preserved_and_checkpointed(isolated_store):
    invoke("init", "notes")
    invoke("add", "keep this")
    store = MemoryStore()
    memory = current_memory()
    checkpoint_count = len(store.list_checkpoints("notes"))

    result = invoke("edit", memory.uid[:8], "   ")

    assert result.exit_code == 0
    assert len(store.list_checkpoints("notes")) == checkpoint_count + 1
    stored = store.load("notes").memories[memory.uid]
    assert isinstance(stored, Memory)
    assert stored.content == "   "


def test_memory_reference_cannot_be_edited(isolated_store):
    invoke("init", "source")
    invoke("add", "source content")
    store = MemoryStore()
    source_memory = current_memory()

    invoke("init", "parent")
    invoke("reference", source_memory.uid[:8], "--from", "source")
    parent = store.load("parent")
    reference = next(iter(parent.iter_items()))
    checkpoint_count = len(store.list_checkpoints("parent"))

    result = invoke("edit", reference.uid[:8], "mutated through reference")

    assert result.exit_code == 1
    assert "not a Memory directly owned" in result.output
    assert len(store.list_checkpoints("parent")) == checkpoint_count
    source = store.load("source").memories[source_memory.uid]
    assert isinstance(source, Memory)
    assert source.content == "source content"


def test_ambiguous_prefix_and_missing_memory_do_not_mutate(isolated_store):
    store = MemoryStore()
    ctx = Context(uid="context-uid", name="notes")
    first = Memory(
        uid="aaaa1111-0000-0000-0000-000000000000",
        content="first",
    )
    second = Memory(
        uid="aaaa2222-0000-0000-0000-000000000000",
        content="second",
    )
    ctx.add(first)
    ctx.add(second)
    store.save(ctx)
    store.set_current("notes")

    ambiguous = invoke("edit", "aaaa", "replacement")
    missing = invoke("edit", "bbbb", "replacement")

    assert ambiguous.exit_code == 1
    assert "Ambiguous prefix" in ambiguous.output
    assert missing.exit_code == 1
    assert "No item with uid starting" in missing.output
    reloaded = store.load("notes")
    assert reloaded.memories[first.uid].content == "first"
    assert reloaded.memories[second.uid].content == "second"
    assert store.list_checkpoints("notes") == []


def test_edit_fails_without_current_context(isolated_store):
    result = invoke("edit", "abcd1234", "replacement")

    assert result.exit_code == 1
    assert "No current context" in result.output
