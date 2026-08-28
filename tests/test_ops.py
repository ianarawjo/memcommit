"""Unit tests for memcommit.application.capabilities.ops — pure in-memory operations, no disk I/O."""

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.core.context import Context, Memory, MemoryRef


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
# resolve
# ---------------------------------------------------------------------------


def test_resolve_memory_by_uid_prefix():
    ctx = make_ctx()
    memory = ops.add(ctx, "selected")

    assert ops.resolve(ctx, memory.uid[:8]) is memory


def test_resolve_embedded_context_by_exact_name():
    parent = make_ctx("parent")
    child = make_ctx("child")
    ops.embed(child, parent)

    assert ops.resolve(parent, "child") is child


def test_resolve_only_searches_direct_children():
    parent = make_ctx("parent")
    child = make_ctx("child")
    nested_memory = ops.add(child, "nested")
    ops.embed(child, parent)

    with pytest.raises(KeyError, match="No direct item matching"):
        ops.resolve(parent, nested_memory.uid[:8])


def test_resolve_not_found_raises_key_error():
    ctx = make_ctx()

    with pytest.raises(KeyError, match="No direct item matching"):
        ops.resolve(ctx, "missing")


def test_resolve_ambiguous_selector_raises_value_error():
    ctx = make_ctx()
    ctx.add(Memory(uid="aaaa1111-0000-0000-0000-000000000000", content="first"))
    ctx.add(Memory(uid="aaaa2222-0000-0000-0000-000000000000", content="second"))

    with pytest.raises(ValueError, match="Ambiguous selector"):
        ops.resolve(ctx, "aaaa")


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


def test_branch_creates_new_context_with_fresh_memory_occurrences():
    ctx = make_ctx("main")
    m1 = ops.add(ctx, "alpha")
    m2 = ops.add(ctx, "beta")

    branched = ops.branch(ctx, "feature")
    assert branched.name == "feature"
    assert branched.uid != ctx.uid
    branched_memories = tuple(
        item for item in branched.iter_items() if isinstance(item, Memory)
    )
    assert [item.content for item in branched_memories] == ["alpha", "beta"]
    assert {item.uid for item in branched_memories}.isdisjoint({m1.uid, m2.uid})


def test_branch_memories_are_independent_objects():
    ctx = make_ctx()
    mem = ops.add(ctx, "original")
    branched = ops.branch(ctx, "copy")

    # A branch owns a fresh occurrence rather than sharing a writable address.
    (branched_mem,) = tuple(
        item for item in branched.iter_items() if isinstance(item, Memory)
    )
    assert branched_mem is not mem
    assert branched_mem.uid != mem.uid
    assert branched_mem.content == mem.content


def test_branch_of_empty_context():
    ctx = make_ctx()
    branched = ops.branch(ctx, "empty-branch")
    assert branched.memories == {}


def test_branch_rejects_incomplete_reused_or_extra_memory_identity_maps():
    ctx = make_ctx()
    memory = ops.add(ctx, "original")

    with pytest.raises(ValueError, match="cover exactly"):
        ops.branch(ctx, "missing", memory_uid_map={})
    with pytest.raises(ValueError, match="cover exactly"):
        ops.branch(
            ctx,
            "extra",
            memory_uid_map={memory.uid: "fresh", "not-owned": "also-fresh"},
        )
    with pytest.raises(ValueError, match="invalid"):
        ops.branch(ctx, "reused", memory_uid_map={memory.uid: memory.uid})


def test_branch_subtree_regenerates_context_and_memory_occurrences():
    root = make_ctx("task")
    child = make_ctx("task/child")
    root_memory = ops.add(root, "root fact")
    child_memory = ops.add(child, "child fact")
    ops.embed(child, root)
    root.add(
        MemoryRef(
            uid="ref-to-child",
            target_context_uid=child.uid,
            target_context_name=child.name,
            target_memory_uid=child_memory.uid,
            target=child_memory,
        )
    )

    branch_root, branch_child = ops.branch_subtree(
        (root, child),
        "task",
        "experiment",
    )

    assert (branch_root.name, branch_child.name) == (
        "experiment",
        "experiment/child",
    )
    assert branch_root.uid != root.uid
    assert branch_child.uid != child.uid
    branch_root_memory = next(
        item for item in branch_root.iter_items() if isinstance(item, Memory)
    )
    branch_child_memory = next(
        item for item in branch_child.iter_items() if isinstance(item, Memory)
    )
    assert branch_root_memory.uid != root_memory.uid
    assert branch_child_memory.uid != child_memory.uid
    embedded = next(
        item for item in branch_root.iter_items() if isinstance(item, Context)
    )
    assert isinstance(embedded, Context)
    assert (embedded.uid, embedded.name) == (branch_child.uid, branch_child.name)
    reference = branch_root.memories["ref-to-child"]
    assert isinstance(reference, MemoryRef)
    assert (reference.target_context_uid, reference.target_context_name) == (
        branch_child.uid,
        branch_child.name,
    )
    assert reference.target_memory_uid == branch_child_memory.uid


def test_branch_subtree_retains_external_live_references():
    root = make_ctx("task")
    external = make_ctx("shared")
    external_memory = ops.add(external, "shared fact")
    ops.embed(external, root)
    root.add(
        MemoryRef(
            uid="external-ref",
            target_context_uid=external.uid,
            target_context_name=external.name,
            target_memory_uid=external_memory.uid,
            target=external_memory,
        )
    )

    (branched,) = ops.branch_subtree((root,), "task", "experiment")

    embedded = branched.memories[external.uid]
    assert isinstance(embedded, Context)
    assert embedded is not external
    assert (embedded.uid, embedded.name) == (external.uid, external.name)
    reference = branched.memories["external-ref"]
    assert isinstance(reference, MemoryRef)
    assert (reference.target_context_uid, reference.target_context_name) == (
        external.uid,
        external.name,
    )


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
