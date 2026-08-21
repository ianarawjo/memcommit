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
    assert "No directly owned Memory with uid starting" in missing.output
    reloaded = store.load("notes")
    assert reloaded.memories[first.uid].content == "first"
    assert reloaded.memories[second.uid].content == "second"
    assert store.list_checkpoints("notes") == []


def test_bare_selector_searches_local_contexts_when_absent_from_current(
    isolated_store,
):
    store = MemoryStore()
    owner = Context(uid="owner-context", name="practice/3")
    memory = Memory(uid="ca562047-owner-memory", content="before")
    owner.add(memory)
    current = Context(uid="current-context", name="practice/4")
    store.save(owner)
    store.save(current)
    store.set_current(current.name)

    result = invoke("edit", memory.uid[:8], "after")

    assert result.exit_code == 0
    assert f"Edited [{memory.uid[:8]}] in 'practice/3'" in result.output
    assert store.current_context_name() == "practice/4"
    assert store.load("practice/3").memories[memory.uid].content == "after"


@pytest.mark.parametrize(
    "locator",
    ("practice/3#ca562047", "../3#ca562047"),
)
def test_qualified_selector_accepts_canonical_or_relative_context_locator(
    isolated_store,
    locator,
):
    store = MemoryStore()
    owner = Context(uid="owner-context", name="practice/3")
    memory = Memory(uid="ca562047-owner-memory", content="before")
    owner.add(memory)
    store.save(owner)
    store.save(Context(uid="current-context", name="practice/4"))
    store.set_current("practice/4")

    result = invoke("edit", locator, "after")

    assert result.exit_code == 0
    assert store.load("practice/3").memories[memory.uid].content == "after"
    assert store.current_context_name() == "practice/4"


def test_cross_context_search_requires_qualifier_when_uid_is_ambiguous(
    isolated_store,
):
    store = MemoryStore()
    duplicate_uid = "ca562047-duplicate-memory"
    for name in ("branch/a", "branch/b"):
        context = Context(uid=f"context-{name}", name=name)
        context.add(Memory(uid=duplicate_uid, content=name))
        store.save(context)
    store.save(Context(uid="current-context", name="branch/current"))
    store.set_current("branch/current")

    result = invoke("edit", "ca562047", "after")

    assert result.exit_code == 1
    assert "Ambiguous Memory selector" in result.output
    assert "branch/a#ca562047" in result.output
    assert "branch/b#ca562047" in result.output
    assert store.load("branch/a").memories[duplicate_uid].content == "branch/a"
    assert store.load("branch/b").memories[duplicate_uid].content == "branch/b"


def test_qualified_selector_cannot_be_combined_with_context_option(isolated_store):
    result = invoke(
        "edit",
        "practice/3#ca562047",
        "replacement",
        "--context",
        "practice/3",
    )

    assert result.exit_code == 1
    assert "cannot be combined with --context" in result.output


def test_edit_can_search_local_owner_without_current_context(isolated_store):
    store = MemoryStore()
    owner = Context(uid="owner-context", name="notes")
    memory = Memory(uid="abcd1234-owner-memory", content="before")
    owner.add(memory)
    store.save(owner)

    result = invoke("edit", memory.uid[:8], "replacement")

    assert result.exit_code == 0
    assert store.load("notes").memories[memory.uid].content == "replacement"


def test_edit_reports_missing_local_owner_without_current_context(isolated_store):
    result = invoke("edit", "abcd1234", "replacement")

    assert result.exit_code == 1
    assert "No directly owned Memory" in result.output
