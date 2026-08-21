"""MemoryRef and explicit Context ordering contracts."""

import json

import click
import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.semantic.changes import parse_proposals
from memcommit.store import MemoryStore


runner = CliRunner()


def test_snapshot_reference_round_trip_retains_exact_content(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    parent = ops.init("parent")
    reference = ops.reference_memory(memory, source, parent)
    store.save(parent)

    record = json.loads(
        (isolated_store / "contexts" / "parent" / "context.json").read_text()
    )["memories"][reference.uid]
    assert record == {
        "type": "memory_snapshot_ref",
        "uid": reference.uid,
        "target_context": {"uid": source.uid, "name": source.name},
        "target_memory_uid": memory.uid,
        "content": "version one",
        "content_sha256": reference.snapshot_content_sha256,
    }

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    loaded = store.load("parent").memories[reference.uid]
    assert isinstance(loaded, MemoryRef)
    assert loaded.is_snapshot
    assert loaded.target is not None
    assert loaded.target.content == "version one"


def test_snapshot_reference_survives_source_deletion(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "retained evidence")
    store.save(source)
    parent = ops.init("parent")
    reference = ops.reference_memory(memory, source, parent)
    store.save(parent)

    store.delete("source")

    loaded = store.load("parent").memories[reference.uid]
    assert isinstance(loaded, MemoryRef)
    assert loaded.is_snapshot
    assert loaded.is_resolved
    assert loaded.target is not None
    assert loaded.target.content == "retained evidence"


def test_snapshot_reference_rejects_in_memory_content_tampering(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "reviewed evidence")
    store.save(source)
    parent = ops.init("parent")
    reference = ops.reference_memory(memory, source, parent)
    store.save(parent)

    loaded = store.load("parent")
    loaded_reference = loaded.memories[reference.uid]
    assert isinstance(loaded_reference, MemoryRef)
    assert loaded_reference.target is not None
    loaded_reference.target.content = "unreviewed replacement"

    with pytest.raises(ValueError, match="snapshot content digest"):
        store.save(loaded)

    reloaded = store.load("parent").memories[reference.uid]
    assert isinstance(reloaded, MemoryRef)
    assert reloaded.target is not None
    assert reloaded.target.content == "reviewed evidence"


def test_memory_ref_round_trip_stores_pointer_only(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "source text must not be copied")
    store.save(source)

    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)

    context_file = isolated_store / "contexts" / "parent" / "context.json"
    data = json.loads(context_file.read_text())
    record = data["memories"][ref.uid]

    assert record == {
        "type": "memory_ref",
        "uid": ref.uid,
        "target_context": {"uid": source.uid, "name": source.name},
        "target_memory_uid": memory.uid,
    }
    assert "content" not in record
    assert data["order"] == [ref.uid]

    loaded_ref = next(iter(store.load("parent").iter_items()))
    assert isinstance(loaded_ref, MemoryRef)
    assert loaded_ref.target is not None
    assert loaded_ref.target.content == "source text must not be copied"


def test_memory_ref_reads_latest_target_after_parent_reload(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)

    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)

    loaded_ref = store.load("parent").memories[ref.uid]
    assert isinstance(loaded_ref, MemoryRef)
    assert loaded_ref.target is not None
    assert loaded_ref.target.content == "version two"


def test_deleted_target_leaves_dangling_ref_that_can_be_resaved(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "temporary")
    store.save(source)

    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)

    source.remove(memory.uid)
    store.save(source)

    dangling = store.load("parent").memories[ref.uid]
    assert isinstance(dangling, MemoryRef)
    assert dangling.target is None

    store.save(store.load("parent"))
    reloaded = store.load("parent").memories[ref.uid]
    assert isinstance(reloaded, MemoryRef)
    assert reloaded.target is None


def test_recreated_context_with_same_name_does_not_retarget_ref(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "original")
    store.save(source)

    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)

    store.delete("source")
    replacement = ops.init("source")
    replacement.add(Memory(uid=memory.uid, content="unrelated replacement"))
    store.save(replacement)

    loaded_ref = store.load("parent").memories[ref.uid]
    assert isinstance(loaded_ref, MemoryRef)
    assert loaded_ref.target is None


def test_revert_restores_pointer_and_order_but_reads_latest_target(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)

    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(
        parent,
        AutoCheckpoint(
            command="reference",
            args={},
            description="reference",
        ),
    )
    reference_checkpoint = store.list_checkpoints("parent")[0]["uid"]

    extra = ops.add(parent, "later parent item")
    store.save(
        parent,
        AutoCheckpoint(command="add", args={}, description="later add"),
    )
    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)

    store.revert("parent", reference_checkpoint)
    restored = store.load("parent")
    restored_ref = restored.memories[ref.uid]

    assert extra.uid not in restored.memories
    assert restored.ordered_uids() == [ref.uid]
    assert isinstance(restored_ref, MemoryRef)
    assert restored_ref.target is not None
    assert restored_ref.target.content == "version two"


def test_reverting_an_inherited_checkpoint_keeps_branch_identity(isolated_store):
    assert runner.invoke(app, ["init", "main"]).exit_code == 0
    assert runner.invoke(app, ["add", "shared baseline"]).exit_code == 0
    store = MemoryStore()
    inherited_checkpoint = store.list_checkpoints("main")[0]["uid"]

    assert runner.invoke(app, ["branch", "feature"]).exit_code == 0
    assert runner.invoke(app, ["switch", "main"]).exit_code == 0
    assert runner.invoke(app, ["add", "main must survive"]).exit_code == 0
    assert runner.invoke(app, ["switch", "feature"]).exit_code == 0

    result = runner.invoke(app, ["revert", inherited_checkpoint[:8]])

    assert result.exit_code == 0
    main_contents = [item.content for item in store.load("main").iter_items()]
    feature = store.load("feature")
    feature_contents = [item.content for item in feature.iter_items()]
    assert main_contents == ["shared baseline", "main must survive"]
    assert feature.name == "feature"
    assert feature_contents == ["shared baseline"]


def test_reference_has_independent_uid_and_is_selected_by_that_uid():
    source = ops.init("source")
    memory = ops.add(source, "target")
    parent = ops.init("parent")

    ref = ops.embed_memory(memory, source, parent)

    assert ref.uid != memory.uid
    assert ops.resolve(parent, ref.uid[:8]) is ref
    with pytest.raises(KeyError):
        ops.resolve(parent, memory.uid)


def test_remove_reference_detaches_only_the_parent():
    source = ops.init("source")
    memory = ops.add(source, "keep me")
    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)

    removed = ops.remove(parent, ref.uid)

    assert removed is ref
    assert ref.uid not in parent.memories
    assert source.memories[memory.uid] is memory


def test_reference_target_view_cannot_mutate_source_memory():
    source = ops.init("source")
    memory = ops.add(source, "original")
    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)

    assert ref.target is not None
    ref.target.content = "attempted write-through"

    assert source.memories[memory.uid].content == "original"
    assert "content" not in parent.to_dict()["memories"][ref.uid]


def test_merge_deduplicates_references_to_the_same_target():
    origin = ops.init("origin")
    memory = ops.add(origin, "shared target")
    source = ops.init("source")
    target = ops.init("target")
    source_ref = ops.embed_memory(memory, origin, source)
    target_ref = ops.embed_memory(memory, origin, target)

    added = ops.merge(source, target)

    assert source_ref.uid != target_ref.uid
    assert added == []
    assert list(target.iter_items()) == [target_ref]


def test_semantic_proposals_cannot_edit_or_remove_reference():
    source = ops.init("source")
    memory = ops.add(source, "protected")
    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)

    changes = parse_proposals(
        {
            "proposed_changes": [
                {"operation": "remove", "uid": ref.uid, "reason": "no"},
                {
                    "operation": "edit",
                    "uid": ref.uid,
                    "new_content": "mutated",
                    "reason": "no",
                },
            ]
        },
        parent,
    )

    assert changes == []


def test_legacy_context_without_order_uses_memories_key_order(isolated_store):
    MemoryStore()
    context_dir = isolated_store / "contexts" / "legacy"
    context_dir.mkdir()
    data = {
        "uid": "legacy-context",
        "name": "legacy",
        "memories": {
            "second": {"type": "memory", "uid": "second", "content": "two"},
            "first": {"type": "memory", "uid": "first", "content": "one"},
        },
    }
    (context_dir / "context.json").write_text(json.dumps(data))

    loaded = MemoryStore().load("legacy")

    assert loaded.order == ["second", "first"]
    assert [item.content for item in loaded.iter_items()] == ["two", "one"]


def test_explicit_order_is_canonical_and_repairs_invalid_entries():
    data = {
        "uid": "ordered-context",
        "name": "ordered",
        "memories": {
            "a": {"type": "memory", "uid": "a", "content": "A"},
            "b": {"type": "memory", "uid": "b", "content": "B"},
            "c": {"type": "memory", "uid": "c", "content": "C"},
        },
        "order": ["c", "missing", "a", "c"],
    }

    loaded = Context.from_dict(data)

    assert loaded.order == ["c", "a", "b"]
    assert loaded.to_dict()["order"] == ["c", "a", "b"]
    assert [item.content for item in loaded.iter_items()] == ["C", "A", "B"]


def test_add_remove_replace_and_clear_keep_order_in_sync():
    ctx = Context(uid="ctx", name="ordered")
    first = Memory(uid="first", content="one")
    second = Memory(uid="second", content="two")
    inserted = Memory(uid="inserted", content="middle")

    ctx.add(first)
    ctx.add(second)
    ctx.add(inserted, position=1)
    ctx.replace(Memory(uid="first", content="ONE"))

    assert ctx.ordered_uids() == ["first", "inserted", "second"]

    ctx.remove("inserted")
    assert ctx.ordered_uids() == ["first", "second"]

    ctx.add(Memory(uid="first", content="ONE AGAIN"))
    assert ctx.ordered_uids() == ["first", "second"]

    ctx.clear()
    assert ctx.memories == {}
    assert ctx.order == []


def test_branch_and_merge_preserve_explicit_order():
    source = ops.init("source")
    first = ops.add(source, "first")
    second = ops.add(source, "second")
    source.order = [second.uid, first.uid]

    branched = ops.branch(source, "branch")
    assert branched.ordered_uids() == [second.uid, first.uid]

    target = ops.init("target")
    existing = ops.add(target, "existing")
    ops.merge(source, target)
    assert target.ordered_uids() == [existing.uid, second.uid, first.uid]


def test_reference_cli_lists_shows_snapshot_and_detaches(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.iter_items()))
    assert isinstance(memory, Memory)

    assert runner.invoke(app, ["init", "parent"]).exit_code == 0
    result = runner.invoke(
        app,
        ["reference", memory.uid[:8], "--from", "source"],
    )
    assert result.exit_code == 0

    parent = store.load("parent")
    ref = next(iter(parent.iter_items()))
    assert isinstance(ref, MemoryRef)

    listing = runner.invoke(app, ["list"])
    assert listing.exit_code == 0
    assert ref.uid[:8] in listing.output
    assert f"[source][memory {memory.uid[:8]}]" in listing.output

    shown = runner.invoke(app, ["show", ref.uid[:8]], color=True)
    assert shown.exit_code == 0
    shown_plain = click.unstyle(shown.output)
    assert "Reference:" in shown_plain
    assert "State: READ ONLY" in shown_plain
    assert "version one" in shown_plain
    assert "\x1b[38;2;198;160;246mReference\x1b[0m" in shown.output

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    shown_again = runner.invoke(app, ["show", ref.uid[:8]])
    assert shown_again.exit_code == 0
    assert "version one" in shown_again.output
    assert "version two" not in shown_again.output

    removed = runner.invoke(app, ["remove", ref.uid[:8]])
    assert removed.exit_code == 0
    assert memory.uid in store.load("source").memories
    assert ref.uid not in store.load("parent").memories


def test_show_handles_a_dangling_reference(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "will disappear")
    store.save(source)
    parent = ops.init("parent")
    ref = ops.embed_memory(memory, source, parent)
    store.save(parent)
    store.set_current("parent")

    source.remove(memory.uid)
    store.save(source)

    result = runner.invoke(app, ["show", ref.uid[:8]], color=True)

    assert result.exit_code == 0
    plain = click.unstyle(result.output)
    assert "Embedded Memory:" in plain
    assert "State: DANGLING" in plain
    assert "embedded Memory Source is unavailable" in plain
    assert "\x1b[38;2;238;212;159mEmbedded Memory\x1b[0m" in result.output


def test_chunk_replaces_a_memory_at_its_original_order_position(isolated_store):
    assert runner.invoke(app, ["init", "ordered"]).exit_code == 0
    assert runner.invoke(app, ["add", "before"]).exit_code == 0
    assert runner.invoke(app, ["add", "part one\n\npart two"]).exit_code == 0
    assert runner.invoke(app, ["add", "after"]).exit_code == 0

    store = MemoryStore()
    before, original, after = list(store.load("ordered").iter_items())
    result = runner.invoke(
        app,
        ["chunk", original.uid[:8], "--method", "paragraphs"],
    )

    assert result.exit_code == 0
    contents = [item.content for item in store.load("ordered").iter_items()]
    assert contents == ["before", "part one", "part two", "after"]
    assert before.uid == store.load("ordered").ordered_uids()[0]
    assert after.uid == store.load("ordered").ordered_uids()[-1]
