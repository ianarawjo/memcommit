"""Snapshot Reference application, runtime, and CLI contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory, MemoryRef
from memcommit.reference_application import (
    FrozenReferencePlan,
    ReferenceError,
    ReferenceRequest,
    ReferenceResult,
    run_reference,
)
from memcommit.reference_runtime import MemoryStoreReferencePort
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
    assert runner.invoke(
        app,
        ["reference", memory.uid[:8], "--from", "source"],
    ).exit_code == 0
    reference = next(iter(store.load("target").iter_items()))
    assert isinstance(reference, MemoryRef)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    shown = runner.invoke(app, ["show", reference.uid[:8]])

    assert shown.exit_code == 0
    assert "version one" in shown.output
    assert "version two" not in shown.output
