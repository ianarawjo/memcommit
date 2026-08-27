"""Live Memory Embed application, runtime, and CLI contracts."""

from __future__ import annotations

from dataclasses import replace

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory, MemoryRef
from memcommit.application.operations.embed.application import (
    EmbedError,
    EmbedPlacement,
    FrozenMemoryEmbedPlan,
    MemoryEmbedRequest,
    MemoryEmbedResult,
    run_memory_embed,
)
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.interfaces.tui.operations.embed import choose_embed_setup
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from memcommit.persistence.store import MemoryStore


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


def test_runtime_rejects_target_drift_without_partial_memory_embed(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "version one")
    store.save(source)
    target = ops.init("target")
    store.save(target)
    port = MemoryStoreEmbedPort.capture(store)
    plan = port.freeze_memory(MemoryEmbedRequest(memory.uid[:8], "source", "target"))

    marker = ops.add(target, "concurrent target value")
    store.save(target)

    with pytest.raises(RuntimeError, match="Into Context changed"):
        port.apply_memory(plan)
    reloaded = store.load("target")
    assert reloaded.ordered_uids() == [marker.uid]


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


def test_cli_memory_embed_defaults_to_current_target(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "source-owned value")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    result = runner.invoke(
        app,
        ["embed", memory.uid[:8], "--from", source.name],
    )

    assert result.exit_code == 0, result.output
    link = next(iter(store.load_direct(target.name).iter_items()))
    assert isinstance(link, MemoryRef)
    assert link.is_live
    assert link.target_context_name == source.name
    assert link.target_memory_uid == memory.uid


def test_cli_bare_memory_uid_finds_unique_local_owner_without_from(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("practice/1")
    memory = ops.add(source, "a is apple")
    target = ops.init("practice/4")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    result = runner.invoke(
        app,
        ["embed", memory.uid[:7], "--into", target.name],
    )

    assert result.exit_code == 0, result.output + result.stderr
    link = next(iter(store.load_direct(target.name).iter_items()))
    assert isinstance(link, MemoryRef)
    assert link.target_context_name == source.name
    assert link.target_memory_uid == memory.uid


def test_cli_memory_embed_accepts_canonical_and_relative_qualified_locators(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("practice/3")
    first = ops.add(source, "first")
    second = ops.add(source, "second")
    target = ops.init("practice/4")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    canonical = runner.invoke(app, ["embed", f"practice/3:{first.uid[:8]}"])
    relative = runner.invoke(app, ["embed", f"../3:{second.uid[:8]}"])

    assert canonical.exit_code == 0, canonical.output + canonical.stderr
    assert relative.exit_code == 0, relative.output + relative.stderr
    links = tuple(store.load_direct(target.name).iter_items())
    assert [item.target_memory_uid for item in links] == [first.uid, second.uid]


def test_cli_memory_embed_blocks_duplicate_bare_uid_and_lists_every_owner(
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

    result = runner.invoke(app, ["embed", shared_uid[:8]])

    assert result.exit_code == 1
    assert f'  branch/source:{shared_uid} "source copy"' in result.stderr
    assert f'  branch/target:{shared_uid} "target copy"' in result.stderr
    assert (
        "To select one, rerun with its CONTEXT:UID value shown above."
        in result.stderr
    )
    assert store.load_direct(target.name).to_dict() == before


def test_cli_memory_embed_rejects_two_source_owner_spellings(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    memory = ops.add(source, "source value")
    target = ops.init("target")
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    result = runner.invoke(
        app,
        ["embed", f"source:{memory.uid[:8]}", "--from", "source"],
    )

    assert result.exit_code == 1
    assert "either CONTEXT:UID or an explicit Context option" in result.stderr
    assert store.load_direct(target.name).ordered_uids() == []


def test_cli_missing_memory_with_from_uses_memory_specific_error(isolated_store):
    store = MemoryStore()
    source = ops.init("practice/1")
    target = ops.init("practice/4")
    store.save(source)
    store.save(target)
    store.set_current(source.name)

    result = runner.invoke(
        app,
        [
            "embed",
            "ca562047",
            "--from",
            source.name,
            "--into",
            target.name,
        ],
    )

    assert result.exit_code == 1
    assert "No directly owned Memory" in result.stderr
    assert "practice/1" in result.stderr
    assert "Granted view" not in result.stderr
    assert store.load_direct(target.name).ordered_uids() == []


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


def test_cli_memory_embed_undo_and_redo_restore_the_live_link(isolated_store):
    assert runner.invoke(app, ["init", "source"]).exit_code == 0
    assert runner.invoke(app, ["add", "version one"]).exit_code == 0
    store = MemoryStore()
    memory = next(iter(store.load("source").iter_items()))
    assert isinstance(memory, Memory)
    assert runner.invoke(app, ["init", "target"]).exit_code == 0
    assert runner.invoke(
        app,
        ["embed", memory.uid[:8], "--from", "source", "--into", "target"],
    ).exit_code == 0
    embed_uid = store.load("target").ordered_uids()[0]

    assert runner.invoke(app, ["undo"]).exit_code == 0
    assert store.load("target").ordered_uids() == []
    assert runner.invoke(app, ["redo"]).exit_code == 0

    restored = store.load("target").memories[embed_uid]
    assert isinstance(restored, MemoryRef)
    assert restored.is_live
    assert restored.target is not None
    assert restored.target.content == "version one"


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


def test_interactive_embed_selects_current_context_memory_before_action_rejects_it(
    isolated_store,
):
    store = MemoryStore()
    peer = ops.init("peer")
    target = ops.init("target")
    memory = ops.add(target, "owned by the current Target")
    store.save(peer)
    store.save(target)
    store.set_current(target.name)
    port = MemoryStoreEmbedPort.capture(store)
    attempts: list[tuple[str, str, str]] = []
    freeze_memory_exact_gap = port.freeze_memory_exact_gap

    def record_attempt(source_name, memory_selector, into_name, placement):
        attempts.append((source_name, memory_selector, into_name))
        return freeze_memory_exact_gap(
            source_name,
            memory_selector,
            into_name,
            placement,
        )

    port.freeze_memory_exact_gap = record_attempt  # type: ignore[method-assign]

    with create_pipe_input() as pipe_input:
        # Memory mode opens the current Target's direct Memories. Selection and
        # command synchronization retain that same Source/Target pair; only the
        # exact action rejects it, after which Escape closes without publication.
        pipe_input.send_text("\x1b[C\t\x1b[B\r\t\t\t\r\x1b")
        plan = choose_embed_setup(
            port,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert plan is None
    assert attempts == [(target.name, memory.uid, target.name)]
    assert store.load_direct(target.name).ordered_uids() == [memory.uid]
    assert store.list_checkpoints(target.name) == []


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
        # Memory mode starts at current Target. Move to the peer Source, open
        # its direct items, choose the Memory, then review the Target position.
        pipe_input.send_text("\x1b[C\t\x1b[A\r\x1b[B\r\t\t\t\r")
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
