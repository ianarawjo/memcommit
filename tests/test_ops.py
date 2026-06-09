"""Unit tests for memcommit.ops — pure in-memory operations, no disk I/O."""
import pytest

import memcommit.ops as ops
from memcommit.context import Context, Memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx(name: str = "test") -> Context:
    return ops.init(name)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_returns_context_with_correct_name():
    ctx = ops.init("myctx")
    assert isinstance(ctx, Context)
    assert ctx.name == "myctx"


def test_init_starts_empty():
    ctx = ops.init("empty")
    assert ctx.memories == {}


def test_init_assigns_uid():
    ctx = ops.init("x")
    assert ctx.uid and len(ctx.uid) == 36  # uuid4 string


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_returns_memory():
    ctx = make_ctx()
    mem = ops.add(ctx, "hello world")
    assert isinstance(mem, Memory)
    assert mem.content == "hello world"


def test_add_stores_memory_in_context():
    ctx = make_ctx()
    mem = ops.add(ctx, "some info")
    assert mem.uid in ctx.memories
    assert ctx.memories[mem.uid] is mem


def test_add_multiple_memories():
    ctx = make_ctx()
    m1 = ops.add(ctx, "first")
    m2 = ops.add(ctx, "second")
    assert len(ctx.memories) == 2
    assert m1.uid != m2.uid


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def test_remove_by_full_uid():
    ctx = make_ctx()
    mem = ops.add(ctx, "to remove")
    removed = ops.remove(ctx, mem.uid)
    assert isinstance(removed, Memory)
    assert removed.uid == mem.uid
    assert mem.uid not in ctx.memories


def test_remove_by_prefix():
    ctx = make_ctx()
    mem = ops.add(ctx, "prefixed removal")
    prefix = mem.uid[:8]
    removed = ops.remove(ctx, prefix)
    assert removed.uid == mem.uid
    assert mem.uid not in ctx.memories


def test_remove_not_found_raises_key_error():
    ctx = make_ctx()
    with pytest.raises(KeyError, match="No item with uid"):
        ops.remove(ctx, "nonexistent")


def test_remove_ambiguous_prefix_raises_value_error():
    ctx = make_ctx()
    # Force two memories whose uids share the same first character by adding them
    # and faking a shared prefix scenario by directly inserting.
    m1 = Memory(uid="aaaa1111-0000-0000-0000-000000000000", content="first")
    m2 = Memory(uid="aaaa2222-0000-0000-0000-000000000000", content="second")
    ctx.add(m1)
    ctx.add(m2)
    with pytest.raises(ValueError, match="Ambiguous prefix"):
        ops.remove(ctx, "aaaa")


# ---------------------------------------------------------------------------
# branch
# ---------------------------------------------------------------------------

def test_branch_creates_new_context_with_same_memories():
    ctx = make_ctx("main")
    m1 = ops.add(ctx, "alpha")
    m2 = ops.add(ctx, "beta")

    branched = ops.branch(ctx, "feature")
    assert branched.name == "feature"
    assert branched.uid != ctx.uid
    assert set(branched.memories.keys()) == {m1.uid, m2.uid}


def test_branch_memories_are_independent_objects():
    ctx = make_ctx()
    mem = ops.add(ctx, "original")
    branched = ops.branch(ctx, "copy")

    # Same uid but different Memory instance — mutating one should not affect the other.
    branched_mem = branched.memories[mem.uid]
    assert branched_mem is not mem
    assert branched_mem.content == mem.content


def test_branch_of_empty_context():
    ctx = make_ctx()
    branched = ops.branch(ctx, "empty-branch")
    assert branched.memories == {}


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def test_merge_adds_items_from_source():
    src = make_ctx("src")
    tgt = make_ctx("tgt")
    m = ops.add(src, "new fact")

    added = ops.merge(src, tgt)
    assert len(added) == 1
    assert added[0].uid == m.uid
    assert m.uid in tgt.memories


def test_merge_skips_duplicates():
    src = make_ctx("src")
    tgt = make_ctx("tgt")
    m = Memory(uid="shared-uid-0000-0000-0000-000000000000", content="shared")
    src.add(m)
    tgt.add(m)

    added = ops.merge(src, tgt)
    assert added == []
    assert len(tgt.memories) == 1


def test_merge_is_idempotent():
    src = make_ctx("src")
    tgt = make_ctx("tgt")
    ops.add(src, "fact")

    ops.merge(src, tgt)
    ops.merge(src, tgt)  # second merge should add nothing
    assert len(tgt.memories) == 1


def test_merge_returns_only_newly_added():
    src = make_ctx("src")
    tgt = make_ctx("tgt")
    shared = Memory(uid="shared-uid-1111-0000-0000-000000000000", content="old")
    novel = ops.add(src, "new")
    src.add(shared)
    tgt.add(shared)

    added = ops.merge(src, tgt)
    assert len(added) == 1
    assert added[0].uid == novel.uid


# ---------------------------------------------------------------------------
# embed
# ---------------------------------------------------------------------------

def test_embed_adds_child_context_to_parent():
    parent = make_ctx("parent")
    child = make_ctx("child")
    ops.embed(child, parent)
    assert child.uid in parent.memories


def test_embed_self_raises():
    ctx = make_ctx()
    with pytest.raises(ValueError, match="Cannot embed a context into itself"):
        ops.embed(ctx, ctx)


def test_embed_already_embedded_raises():
    parent = make_ctx("p")
    child = make_ctx("c")
    ops.embed(child, parent)
    with pytest.raises(ValueError, match="already embedded"):
        ops.embed(child, parent)


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------

def test_chunk_splits_paragraphs():
    ctx = make_ctx()
    mem = ops.add(ctx, "First paragraph.\n\nSecond paragraph.")
    original, chunks = ops.chunk(ctx, mem.uid[:8], "paragraphs")
    assert original.uid == mem.uid
    assert len(chunks) == 2
    assert chunks[0].content == "First paragraph."
    assert chunks[1].content == "Second paragraph."


def test_chunk_unknown_method_raises():
    ctx = make_ctx()
    mem = ops.add(ctx, "some content")
    with pytest.raises(ValueError, match="Unknown chunking method"):
        ops.chunk(ctx, mem.uid[:8], "bogus_method")


def test_chunk_not_found_raises():
    ctx = make_ctx()
    with pytest.raises(KeyError):
        ops.chunk(ctx, "nonexistent", "paragraphs")


def test_chunk_on_embedded_context_raises():
    parent = make_ctx("p")
    child = make_ctx("c")
    ops.embed(child, parent)
    with pytest.raises(TypeError, match="not a Memory"):
        ops.chunk(parent, child.uid[:8], "paragraphs")


def test_chunk_new_memories_have_fresh_uids():
    ctx = make_ctx()
    mem = ops.add(ctx, "Para one.\n\nPara two.")
    original, chunks = ops.chunk(ctx, mem.uid, "paragraphs")
    uids = [c.uid for c in chunks]
    assert original.uid not in uids
    assert len(set(uids)) == len(uids)  # all unique
