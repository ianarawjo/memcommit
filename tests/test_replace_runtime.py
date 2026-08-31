"""Store atomicity and recovery tests for deterministic Replace."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Context, MemoryRef
from memcommit.application.operations.direct_changes.replace.application import ReplaceRequest, ReplaceStalePlanError
from memcommit.application.operations.direct_changes.replace.runtime import execute_replace_plan, plan_replace_with_store
from memcommit.persistence.store import MemoryStore


runner = CliRunner()


def _save(store: MemoryStore, name: str, *contents: str) -> Context:
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.save(context)
    return context


def test_replace_applies_multiple_contexts_as_one_undo_redo_unit(
    isolated_store,
) -> None:
    store = MemoryStore()
    _save(store, "replace/a", "old value")
    _save(store, "replace/b", "old value twice: old value")
    store.set_current("replace/a")
    plan, port = plan_replace_with_store(
        ReplaceRequest("old value", "new value", ("replace/a", "replace/b")),
        store=store,
    )

    result = execute_replace_plan(plan, port=port)

    assert result.applied is True
    assert result.changed_memory_count == 2
    assert result.occurrence_count == 3
    assert len(result.checkpoints) == 2
    assert [
        memory.content for memory in store.load_direct("replace/a").memories.values()
    ] == ["new value"]
    assert [
        memory.content for memory in store.load_direct("replace/b").memories.values()
    ] == ["new value twice: new value"]

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert "Undid command: mem replace" in undone.output
    assert [
        memory.content for memory in store.load_direct("replace/a").memories.values()
    ] == ["old value"]
    assert [
        memory.content for memory in store.load_direct("replace/b").memories.values()
    ] == ["old value twice: old value"]

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    assert "Redid command: mem replace" in redone.output
    assert [
        memory.content for memory in store.load_direct("replace/a").memories.values()
    ] == ["new value"]


def test_replace_revalidates_unmatched_scanned_contexts(isolated_store) -> None:
    store = MemoryStore()
    _save(store, "replace/root", "needle here")
    child = _save(store, "replace/root/child", "unrelated")
    plan, port = plan_replace_with_store(
        ReplaceRequest(
            "needle",
            "thread",
            ("replace/root",),
            include_descendants=True,
        ),
        store=store,
    )
    child.add("a new needle")
    store.save(child)

    with pytest.raises(ReplaceStalePlanError, match="changed"):
        execute_replace_plan(plan, port=port)
    assert [
        memory.content
        for memory in store.load_direct("replace/root").memories.values()
    ] == ["needle here"]
    assert store.list_checkpoints("replace/root") == []


def test_replace_rejects_namespace_membership_change_after_review(
    isolated_store,
) -> None:
    store = MemoryStore()
    _save(store, "replace/root", "needle here")
    plan, port = plan_replace_with_store(
        ReplaceRequest(
            "needle",
            "thread",
            ("replace/root",),
            include_descendants=True,
        ),
        store=store,
    )
    _save(store, "replace/root/new-child", "needle added later")

    with pytest.raises(ReplaceStalePlanError, match="namespace changed"):
        execute_replace_plan(plan, port=port)
    assert [
        memory.content
        for memory in store.load_direct("replace/root").memories.values()
    ] == ["needle here"]


def test_replace_follows_local_embeds_without_editing_reference_records(
    isolated_store,
) -> None:
    store = MemoryStore()
    child = _save(store, "replace/child", "needle child")
    source = _save(store, "replace/reference-source", "needle referenced")
    root = _save(store, "replace/root", "needle root")
    root.add(child)
    referenced = next(iter(source.memories.values()))
    root.add(
        MemoryRef(
            uid="reference-1",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    store.save(root)
    plan, port = plan_replace_with_store(
        ReplaceRequest(
            "needle",
            "thread",
            ("replace/root",),
            follow_embeds=True,
        ),
        store=store,
    )

    assert [context.context_name for context in plan.contexts] == [
        "replace/root",
        "replace/child",
    ]
    assert plan.changed_memory_count == 2
    execute_replace_plan(plan, port=port)
    assert [
        memory.content for memory in store.load_direct("replace/root").memories.values()
        if hasattr(memory, "content") and not isinstance(memory, MemoryRef)
    ] == ["thread root"]
    assert [
        memory.content for memory in store.load_direct("replace/child").memories.values()
    ] == ["thread child"]
    assert [
        memory.content
        for memory in store.load_direct("replace/reference-source").memories.values()
    ] == ["needle referenced"]


def test_replace_batch_rolls_back_contexts_and_checkpoints_on_write_failure(
    isolated_store,
    monkeypatch,
) -> None:
    store = MemoryStore()
    _save(store, "replace/a", "needle a")
    _save(store, "replace/b", "needle b")
    plan, port = plan_replace_with_store(
        ReplaceRequest("needle", "thread", ("replace/a", "replace/b")),
        store=store,
    )
    original = MemoryStore._save_locked
    replace_writes = 0

    def fail_second(self, context, checkpoint=None, **kwargs):
        nonlocal replace_writes
        if checkpoint is not None and checkpoint.command == "replace":
            replace_writes += 1
            if replace_writes == 2:
                raise OSError("injected second Replace write failure")
        return original(self, context, checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second)

    with pytest.raises(OSError, match="injected"):
        execute_replace_plan(plan, port=port)
    for name, expected in (("replace/a", "needle a"), ("replace/b", "needle b")):
        assert [
            memory.content for memory in store.load_direct(name).memories.values()
        ] == [expected]
        assert store.list_checkpoints(name) == []


def test_replace_no_match_revalidates_but_creates_no_checkpoint(
    isolated_store,
) -> None:
    store = MemoryStore()
    _save(store, "replace/source", "nothing here")
    plan, port = plan_replace_with_store(
        ReplaceRequest("needle", "thread", ("replace/source",)),
        store=store,
    )

    result = execute_replace_plan(plan, port=port)

    assert result.applied is False
    assert result.checkpoints == ()
    assert store.list_checkpoints("replace/source") == []


def test_replace_rejects_foreign_runtime_plan(isolated_store) -> None:
    store = MemoryStore()
    _save(store, "replace/source", "needle")
    plan, _port = plan_replace_with_store(
        ReplaceRequest("needle", "thread", ("replace/source",)),
        store=store,
    )
    _other_plan, other_port = plan_replace_with_store(
        ReplaceRequest("needle", "thread", ("replace/source",)),
        store=store,
    )

    with pytest.raises(Exception, match="different runtime"):
        execute_replace_plan(plan, port=other_port)
