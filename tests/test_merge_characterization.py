"""Frozen compatibility contract for the historical direct Merge operation."""

from __future__ import annotations

from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Context, Memory
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _create(store: MemoryStore, context: Context) -> Context:
    store.create_context(context)
    return context


def test_direct_merge_keeps_target_revision_for_an_existing_uid(isolated_store):
    store = MemoryStore()
    shared_uid = "00000000-0000-0000-0000-000000000001"
    source = ops.init("source")
    source.add(Memory(uid=shared_uid, content="source revision"))
    novel = ops.add(source, "source-only addition")
    _create(store, source)
    target = ops.init("target")
    target.add(Memory(uid=shared_uid, content="target revision"))
    _create(store, target)
    store.set_current(target.name)

    unresolved = runner.invoke(app, ["merge", source.name])
    result = runner.invoke(app, ["merge", source.name, "--keep-target-all"])

    assert unresolved.exit_code == 1
    assert "CONTENT_DIVERGENCE" in unresolved.output
    assert result.exit_code == 0, result.output + result.stderr
    assert "NEW 1 (1 memory)" in result.output
    assert "KEPT TARGET 1" in result.output
    merged = store.load_direct(target.name)
    assert merged.memories[shared_uid].content == "target revision"
    assert novel.uid not in merged.memories
    assert any(
        isinstance(item, Memory) and item.content == "source-only addition"
        for item in merged.iter_items()
    )


def test_direct_merge_does_not_propagate_source_absence(isolated_store):
    store = MemoryStore()
    source = _create(store, ops.init("source"))
    target = ops.init("target")
    retained = ops.add(target, "target-only item")
    _create(store, target)
    store.set_current(target.name)

    result = runner.invoke(app, ["merge", source.name])

    assert result.exit_code == 0, result.output + result.stderr
    assert "NEW 0" in result.output
    assert "TARGET CHANGED NO" in result.output
    assert retained.uid in store.load_direct(target.name).memories


def test_direct_merge_does_not_open_lexical_descendants(isolated_store):
    store = MemoryStore()
    source = _create(store, ops.init("source"))
    source_child = ops.init("source/child")
    ops.add(source_child, "descendant-only fact")
    _create(store, source_child)
    target = _create(store, ops.init("target"))
    target_child = _create(store, ops.init("target/child"))
    store.set_current(target.name)

    result = runner.invoke(app, ["merge", source.name])

    assert result.exit_code == 0, result.output + result.stderr
    assert "NEW 0" in result.output
    assert "TARGET CHANGED NO" in result.output
    assert tuple(store.load_direct(target.name).iter_items()) == ()
    assert tuple(store.load_direct(target_child.name).iter_items()) == ()


def test_direct_merge_copies_one_embedded_context_pointer(isolated_store):
    store = MemoryStore()
    child = _create(store, ops.init("source/embedded"))
    source = ops.init("source")
    source.add(Context(uid=child.uid, name=child.name))
    _create(store, source)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)

    result = runner.invoke(app, ["merge", source.name])

    assert result.exit_code == 0, result.output + result.stderr
    assert "NEW 1 (1 embedded context)" in result.output
    (embedded,) = tuple(store.load_direct(target.name).iter_items())
    assert isinstance(embedded, Context)
    assert (embedded.uid, embedded.name) == (child.uid, child.name)


def test_direct_merge_records_one_checkpoint_and_a_noop_receipt(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "one addition")
    _create(store, source)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)

    first = runner.invoke(app, ["merge", source.name])
    second = runner.invoke(app, ["merge", source.name])

    assert first.exit_code == second.exit_code == 0
    assert "NEW 1 (1 memory)" in first.output
    assert "NEW 0" in second.output
    assert "ALREADY PRESENT 1" in second.output
    checkpoints = store.list_checkpoints(target.name)
    assert len(checkpoints) == 2
    assert all(entry["command"] == "merge" for entry in checkpoints)
