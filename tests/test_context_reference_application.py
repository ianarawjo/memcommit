"""Immutable direct and recursive Context Reference contracts."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory, MemoryRef
from memcommit.context_snapshot import ContextSnapshotRef
from memcommit.reference_application import (
    ContextReferenceRequest,
    ReferenceError,
)
from memcommit.reference_runtime import (
    MemoryStoreReferencePort,
    execute_context_reference,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _fixture() -> tuple[MemoryStore, Context, Context, Context, Context]:
    store = MemoryStore()
    root = ops.init("source")
    ops.add(root, "root fact")
    descendant = ops.init("source/child")
    ops.add(descendant, "descendant fact")
    embedded = ops.init("library")
    ops.add(embedded, "embedded fact")
    ops.embed(embedded, root)
    target = ops.init("target")
    for context in (root, descendant, embedded, target):
        store.save(context)
    store.set_current(target.name)
    return store, root, descendant, embedded, target


def _contents(context: Context) -> set[str]:
    found: set[str] = set()
    seen: set[str] = set()

    def visit(current: Context) -> None:
        if current.uid in seen:
            return
        seen.add(current.uid)
        for item in current.iter_items():
            if isinstance(item, Memory):
                found.add(item.content)
            elif isinstance(item, Context):
                visit(item)

    visit(context)
    return found


def test_direct_context_reference_freezes_only_the_selected_frame(isolated_store):
    store, _root, _descendant, _embedded, _target = _fixture()

    result = execute_context_reference(
        ContextReferenceRequest("source", "target"),
        store=store,
    )

    item = store.load("target").memories[result.reference_uid]
    assert isinstance(item, ContextSnapshotRef)
    assert item.include_descendants is False
    assert _contents(item) == {"root fact"}
    embedded = next(value for value in item.iter_items() if isinstance(value, Context))
    assert embedded.name == "library"
    assert list(embedded.iter_items()) == []


def test_recursive_context_reference_freezes_descendants_and_embeds(
    isolated_store,
):
    store, root, descendant, embedded, _target = _fixture()

    result = execute_context_reference(
        ContextReferenceRequest(
            "source",
            "target",
            include_descendants=True,
            follow_embeds=True,
        ),
        store=store,
    )

    for source in (root, descendant, embedded):
        store.delete(source.name)
    item = store.load("target").memories[result.reference_uid]
    assert isinstance(item, ContextSnapshotRef)
    assert item.include_descendants is True
    assert result.context_count == 3
    assert _contents(item) == {
        "root fact",
        "descendant fact",
        "embedded fact",
    }

    listed = runner.invoke(app, ["ls", "target", "--recursive"])
    shown = runner.invoke(
        app,
        ["show", result.reference_uid[:8], "--context", "target"],
    )
    shown_recursive = runner.invoke(
        app,
        ["show", "--recursive", "--context", "target"],
    )
    assert listed.exit_code == 0, listed.output
    assert "context reference" in listed.output
    assert "descendant fact" in listed.output
    assert "embedded fact" in listed.output
    assert shown.exit_code == 0, shown.output
    assert "root fact" in shown.output
    assert shown_recursive.exit_code == 0, shown_recursive.output
    assert "root fact" in shown_recursive.output
    assert "descendant fact" in shown_recursive.output
    assert "embedded fact" in shown_recursive.output


def test_context_reference_freezes_live_memory_embed_content(isolated_store):
    store = MemoryStore()
    owner = ops.init("owner")
    memory = ops.add(owner, "live embedded fact")
    source = ops.init("source")
    live = ops.embed_memory(memory, owner, source)
    target = ops.init("target")
    for context in (owner, source, target):
        store.save(context)
    store.set_current(target.name)

    result = execute_context_reference(
        ContextReferenceRequest("source", "target"),
        store=store,
    )
    store.delete("owner")
    store.delete("source")

    snapshot = store.load("target").memories[result.reference_uid]
    assert isinstance(snapshot, ContextSnapshotRef)
    retained = snapshot.memories[live.uid]
    assert isinstance(retained, MemoryRef)
    assert retained.is_snapshot is True
    assert retained.target is not None
    assert retained.target.content == "live embedded fact"
    record = snapshot.snapshot_package["contexts"][0]
    assert record["memories"][live.uid]["snapshot_origin"] == "embed"


def test_context_reference_rejects_target_inside_recursive_scope(isolated_store):
    store, _root, _descendant, _embedded, _target = _fixture()

    with pytest.raises(ReferenceError, match="inside its frozen Source scope"):
        execute_context_reference(
            ContextReferenceRequest(
                "source",
                "source/child",
                include_descendants=True,
                follow_embeds=True,
            ),
            store=store,
        )


def test_cli_supports_context_reference_and_compatible_memory_from_form(
    isolated_store,
):
    store, root, _descendant, _embedded, _target = _fixture()
    memory = next(item for item in root.iter_items() if isinstance(item, Memory))

    context_result = runner.invoke(
        app,
        ["reference", "--from", "source", "--to", "target", "--recursive"],
    )
    memory_result = runner.invoke(
        app,
        [
            "reference",
            memory.uid[:8],
            "--from",
            "source",
            "--into",
            "target",
        ],
    )

    assert context_result.exit_code == 0, context_result.output
    assert "recursive Context snapshot" in context_result.output
    assert memory_result.exit_code == 0, memory_result.output
    assert "Referenced snapshot" in memory_result.output
    loaded = store.load("target")
    assert any(isinstance(item, ContextSnapshotRef) for item in loaded.iter_items())


def test_reference_rejects_duplicate_target_aliases_without_mutation(
    isolated_store,
):
    store, _root, _descendant, _embedded, target = _fixture()
    before = target.to_dict()

    result = runner.invoke(
        app,
        [
            "reference",
            "--from",
            "source",
            "--into",
            "target",
            "--to",
            "other",
        ],
    )

    assert result.exit_code == 2
    assert "--into and --to" in result.stderr
    assert store.load_direct("target").to_dict() == before
    assert store.list_checkpoints("target") == []


def test_memory_reference_rejects_context_scope_flags(isolated_store):
    result = runner.invoke(
        app,
        ["reference", "abcd1234", "--from", "source", "--recursive"],
    )

    assert result.exit_code == 2
    assert "apply only to a Context Reference" in result.stderr


def test_context_reference_apply_rejects_source_drift(isolated_store):
    store, root, _descendant, _embedded, _target = _fixture()
    port = MemoryStoreReferencePort.capture(store)
    request = ContextReferenceRequest("source", "target")
    plan = port.freeze_context(request)
    ops.add(root, "changed after review")
    store.save(root)

    with pytest.raises(RuntimeError, match="source Context changed"):
        port.apply_context(plan)
    assert list(store.load("target").iter_items()) == []


def test_context_reference_undo_redo_restores_self_contained_package(
    isolated_store,
):
    store, root, descendant, embedded, _target = _fixture()
    created = runner.invoke(
        app,
        ["reference", "source", "--into", "target", "--recursive"],
    )
    assert created.exit_code == 0, created.output
    snapshot_uid = store.load("target").ordered_uids()[0]

    assert runner.invoke(app, ["undo"]).exit_code == 0
    assert store.load("target").ordered_uids() == []
    for source in (root, descendant, embedded):
        store.delete(source.name)
    assert runner.invoke(app, ["redo"]).exit_code == 0

    restored = store.load("target").memories[snapshot_uid]
    assert isinstance(restored, ContextSnapshotRef)
    assert _contents(restored) == {
        "root fact",
        "descendant fact",
        "embedded fact",
    }
