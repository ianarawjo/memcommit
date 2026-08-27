"""Snapshot Reference application, runtime, and CLI contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory, MemoryRef
from memcommit.application.operations.reference.application import (
    FrozenReferencePlan,
    ReferenceError,
    ReferenceRequest,
    ReferenceResult,
    run_reference,
)
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _Port:
    def __init__(self) -> None:
        self.plan = FrozenReferencePlan(
            request=ReferenceRequest("memory", "source", "target"),
            source_name="source",
            source_uid="source-uid",
            source_digest="source-digest",
            memory_uid="memory-uid",
            memory_content="content",
            memory_content_sha256="content-digest",
            into_name="target",
            into_uid="target-uid",
            into_digest="target-digest",
            token=object(),
        )

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        return replace(self.plan, request=request)

    def apply(self, plan: FrozenReferencePlan) -> ReferenceResult:
        return ReferenceResult(
            reference_uid="reference-uid",
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            memory_uid=plan.memory_uid,
            memory_content_sha256=plan.memory_content_sha256,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            checkpoint_uid="checkpoint-uid",
        )


def test_application_rejects_a_plan_for_another_request():
    port = _Port()
    request = ReferenceRequest("memory", "source", "target")

    with pytest.raises(ReferenceError, match="no longer matches"):
        run_reference(
            request,
            port=port,
            frozen_plan=replace(
                port.plan,
                request=ReferenceRequest("other", "source", "target"),
            ),
        )


def test_runtime_freezes_source_and_target_before_snapshot_apply(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    target = ops.init("target")
    store.save(target)
    store.set_current(target.name)
    port = MemoryStoreReferencePort.capture(store)
    request = ReferenceRequest(memory.uid[:8], source.name)
    plan = port.freeze(request)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)

    with pytest.raises(RuntimeError, match="Source Context changed"):
        port.apply(plan)
    assert list(store.load("target").iter_items()) == []


def test_runtime_rejects_target_drift_without_overwriting_it(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    target = ops.init("target")
    store.save(target)
    port = MemoryStoreReferencePort.capture(store)
    plan = port.freeze(ReferenceRequest(memory.uid[:8], "source", "target"))

    marker = ops.add(target, "concurrent target value")
    store.save(target)

    with pytest.raises(RuntimeError, match="Target Context changed"):
        port.apply(plan)
    reloaded = store.load("target")
    assert reloaded.ordered_uids() == [marker.uid]


def test_cli_reference_operand_roles_are_actionable_outside_a_tty(isolated_store):
    context_route = runner.invoke(app, ["reference", "abcd1234"])
    explicit_context = runner.invoke(
        app,
        ["reference", "--from", "abcd1234"],
    )
    bare = runner.invoke(app, ["reference"])

    assert context_route.exit_code == 1
    assert "No directly owned Memory" in context_route.stderr
    assert explicit_context.exit_code == 1
    assert "No current Context" in explicit_context.stderr
    assert bare.exit_code == 1
    assert "outside a terminal" in bare.stderr


def test_cli_reference_finds_unique_bare_uid_and_qualified_relative_owner(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("practice/3")
    first = ops.add(source, "first snapshot")
    second = ops.add(source, "second snapshot")
    target = ops.init("practice/4")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    bare = runner.invoke(app, ["reference", first.uid[:7]])
    qualified = runner.invoke(app, ["reference", f"../3:{second.uid[:8]}"])

    assert bare.exit_code == 0, bare.output + bare.stderr
    assert qualified.exit_code == 0, qualified.output + qualified.stderr
    snapshots = tuple(store.load_direct(target.name).iter_items())
    assert [item.target_memory_uid for item in snapshots] == [
        first.uid,
        second.uid,
    ]
    assert all(isinstance(item, MemoryRef) and item.is_snapshot for item in snapshots)


def test_cli_reference_blocks_duplicate_bare_uid_and_lists_every_owner(
    isolated_store,
):
    store = MemoryStore()
    shared_uid = "aaaaaaaa-0000-0000-0000-000000000000"
    source = ops.init("branch/source")
    source.add(Memory(uid=shared_uid, content="source copy"))
    target = ops.init("branch/target")
    target.add(Memory(uid=shared_uid, content="target copy"))
    store.save(source)
    store.save(target)
    store.set_current(target.name)
    before = store.load_direct(target.name).to_dict()

    result = runner.invoke(app, ["reference", shared_uid[:8]])

    assert result.exit_code == 1
    assert f'  branch/source:{shared_uid} "source copy"' in result.stderr
    assert f'  branch/target:{shared_uid} "target copy"' in result.stderr
    assert (
        "To select one, rerun with its CONTEXT:UID value shown above."
        in result.stderr
    )
    assert store.load_direct(target.name).to_dict() == before


def test_cli_reference_rejects_two_source_owner_spellings(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "source value")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    result = runner.invoke(
        app,
        ["reference", f"source:{memory.uid[:8]}", "--from", "source"],
    )

    assert result.exit_code == 1
    assert "either CONTEXT:UID or an explicit Context option" in result.stderr
    assert store.load_direct(target.name).ordered_uids() == []


def test_bare_cli_reference_enters_and_can_cancel_interactive_setup(
    isolated_store,
    monkeypatch,
):
    import memcommit.adapters.interfaces.cli.reference as reference_cli

    monkeypatch.setattr(reference_cli, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(reference_cli, "choose_reference_setup", lambda _port: None)

    result = runner.invoke(app, ["reference"])

    assert result.exit_code == 0
    assert "Reference cancelled" in result.output


def test_cli_reference_persists_snapshot_and_one_checkpoint(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0

    result = runner.invoke(
        app,
        ["reference", memory.uid[:8], "--from", "source"],
    )

    assert result.exit_code == 0, result.output
    assert "Referenced snapshot" in result.output
    reference = next(iter(store.load("target").iter_items()))
    assert isinstance(reference, MemoryRef)
    assert reference.is_snapshot
    assert reference.target is not None
    assert reference.target.content == "version one"
    reference_checkpoints = [
        checkpoint
        for checkpoint in store.list_checkpoints("target")
        if checkpoint["command"] == "reference"
    ]
    assert len(reference_checkpoints) == 1
    checkpoint = reference_checkpoints[0]
    assert checkpoint["command"] == "reference"
    assert checkpoint["args"]["snapshot"] is True


def test_cli_reference_stays_fixed_after_source_change(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["reference", memory.uid[:8], "--from", "source"],
        ).exit_code
        == 0
    )
    reference = next(iter(store.load("target").iter_items()))
    assert isinstance(reference, MemoryRef)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    shown = runner.invoke(app, ["show", reference.uid[:8]])

    assert shown.exit_code == 0
    assert "version one" in shown.output
    assert "version two" not in shown.output


def test_cli_reference_undo_and_redo_restore_the_snapshot(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    memory = next(iter(store.load("source").iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["reference", memory.uid[:8], "--from", "source"],
        ).exit_code
        == 0
    )
    snapshot_uid = store.load("target").ordered_uids()[0]

    assert runner.invoke(app, ["undo"]).exit_code == 0
    assert store.load("target").ordered_uids() == []
    assert runner.invoke(app, ["redo"]).exit_code == 0

    restored = store.load("target").memories[snapshot_uid]
    assert isinstance(restored, MemoryRef)
    assert restored.is_snapshot
    assert restored.target is not None
    assert restored.target.content == "version one"
