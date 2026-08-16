"""Live Memory Embed application, runtime, and CLI contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory, MemoryRef
from memcommit.embed_application import (
    EmbedError,
    EmbedPlacement,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    MemoryEmbedResult,
    run_memory_embed,
)
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.tui.operations.embed import choose_embed_setup
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


class _Port:
    def __init__(self) -> None:
        self.plan = FrozenMemoryEmbedPlan(
            request=MemoryEmbedRequest("memory", "source", "target"),
            source_name="source",
            source_uid="source-uid",
            source_digest="source-digest",
            memory_uid="memory-uid",
            memory_content="content",
            memory_content_sha256="content-digest",
            into_name="target",
            into_uid="target-uid",
            into_digest="target-digest",
            placement=EmbedPlacement(0, None, None),
            item_count=0,
            token=object(),
        )

    def freeze_memory(self, request: MemoryEmbedRequest) -> FrozenMemoryEmbedPlan:
        return replace(self.plan, request=request)

    def apply_memory(self, plan: FrozenMemoryEmbedPlan) -> MemoryEmbedResult:
        return MemoryEmbedResult(
            embed_uid="embed-uid",
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            memory_uid=plan.memory_uid,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            placement=plan.placement,
            checkpoint_uid="checkpoint-uid",
        )


def test_application_rejects_a_memory_plan_for_another_request():
    port = _Port()
    request = MemoryEmbedRequest("memory", "source", "target")

    with pytest.raises(EmbedError, match="no longer matches"):
        run_memory_embed(
            request,
            port=port,
            frozen_plan=replace(
                port.plan,
                request=MemoryEmbedRequest("other", "source", "target"),
            ),
        )


def test_runtime_rejects_source_drift_without_partial_memory_embed(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    target = ops.init("target")
    store.save(target)
    port = MemoryStoreEmbedPort.capture(store)
    request = MemoryEmbedRequest(memory.uid[:8], "source", "target")
    plan = port.freeze_memory(request)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)

    with pytest.raises(RuntimeError, match="Source Context changed"):
        port.apply_memory(plan)
    assert list(store.load("target").iter_items()) == []


def test_cli_memory_embed_uses_from_and_preserves_reviewed_gap(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0
    assert runner.invoke(app, ["add", "before"]).exit_code == 0
    assert runner.invoke(app, ["add", "after"]).exit_code == 0
    target = store.load("target")
    before, after = tuple(target.iter_items())

    result = runner.invoke(
        app,
        [
            "embed",
            memory.uid[:8],
            "--from",
            "source",
            "--into",
            "target",
            "--before",
            after.uid[:8],
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Embedded Memory" in result.output
    target = store.load("target")
    assert target.ordered_uids()[0] == before.uid
    link = target.memories[target.ordered_uids()[1]]
    assert isinstance(link, MemoryRef)
    assert link.is_live
    assert target.ordered_uids()[2] == after.uid


def test_cli_memory_embed_reads_latest_source_after_target_reload(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    source = store.load("source")
    memory = next(iter(source.iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0
    assert runner.invoke(
        app,
        ["embed", memory.uid[:8], "--from", "source", "--into", "target"],
    ).exit_code == 0
    target = store.load("target")
    link = next(iter(target.iter_items()))
    assert isinstance(link, MemoryRef)

    source.replace(Memory(uid=memory.uid, content="version two"))
    store.save(source)
    reloaded = store.load("target").memories[link.uid]

    assert isinstance(reloaded, MemoryRef)
    assert reloaded.is_live
    assert reloaded.target is not None
    assert reloaded.target.content == "version two"


def test_memory_embed_rejects_a_self_link_before_publication(isolated_store):
    store = MemoryStore()
    context = ops.init("one")
    memory = ops.add(context, "owned here")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        [
            "embed",
            memory.uid[:8],
            "--from",
            context.name,
            "--into",
            context.name,
        ],
    )

    assert result.exit_code == 1
    assert "must be distinct" in result.stderr
    assert store.load_direct(context.name).ordered_uids() == [memory.uid]


def test_interactive_embed_returns_exact_frozen_memory_plan(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "live source")
    target = ops.init("target")
    marker = ops.add(target, "target marker")
    store.save(source)
    store.save(target)
    store.set_current(target.name)
    port = MemoryStoreEmbedPort.capture(store)

    with create_pipe_input() as pipe_input:
        # Memory mode → Source row → direct Memory → Target → position → review.
        pipe_input.send_text("\x1b[C\t\x1b[B\r\t\t\t\r")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert isinstance(plan, FrozenMemoryEmbedPlan)
    assert plan.source_name == source.name
    assert plan.memory_uid == memory.uid
    assert plan.into_name == target.name
    assert plan.placement.previous_uid == marker.uid
    before = store.load_direct(target.name).to_dict()

    result = run_memory_embed(plan.request, port=port, frozen_plan=plan)

    assert result.embed_uid in store.load_direct(target.name).memories
    assert before != store.load_direct(target.name).to_dict()
