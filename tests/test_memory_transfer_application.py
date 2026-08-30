"""Direct-Memory Copy and Move application, Store, CLI, and history contracts."""

from __future__ import annotations

from dataclasses import replace
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef
from memcommit.application.operations.copy_and_move.application import (
    CopyMemoriesRequest,
    MemoryTransferError,
    MemoryTransferStalePlanError,
    MoveMemoriesRequest,
)
from memcommit.application.operations.copy.application import run_copy
from memcommit.application.operations.copy_and_move.runtime import MemoryStoreCopyAndMovePort
from memcommit.application.operations.move.application import run_move
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    memories = tuple(ops.add(context, content) for content in contents)
    store.save(context)
    return context, memories


def test_cli_copy_batch_uses_fresh_uids_preserves_order_and_source(isolated_store):
    store = MemoryStore()
    source, memories = _context(store, "source", "alpha", "beta")
    target, (marker,) = _context(store, "target", "marker")
    store.set_current(target.name)

    result = runner.invoke(
        app,
        [
            "copy",
            memories[1].uid[:8],
            memories[0].uid[:8],
            "--from",
            source.name,
            "--before",
            marker.uid[:8],
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "COPIED" in result.output
    reloaded_source = store.load_direct(source.name)
    assert [item.content for item in reloaded_source.iter_items()] == [
        "alpha",
        "beta",
    ]
    reloaded_target = store.load_direct(target.name)
    copied = tuple(reloaded_target.iter_items())
    assert [item.content for item in copied] == ["beta", "alpha", "marker"]
    assert [item.uid for item in copied[:2]] != [memories[1].uid, memories[0].uid]
    copied_uids = [item.uid for item in copied[:2]]
    assert len(store.list_checkpoints(target.name)) == 1
    assert store.list_checkpoints(source.name) == []

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output + undone.stderr
    assert "Undid command: mem copy" in undone.output
    assert [
        item.uid for item in store.load_direct(target.name).iter_items()
    ] == [marker.uid]
    assert [
        item.uid for item in store.load_direct(source.name).iter_items()
    ] == [memories[0].uid, memories[1].uid]

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert "Redid command: mem copy" in redone.output
    assert [
        item.uid for item in store.load_direct(target.name).iter_items()
    ] == [*copied_uids, marker.uid]


def test_cli_copy_rejects_removed_preserve_uids_flag_without_mutation(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "value")
    target, _ = _context(store, "target")
    result = runner.invoke(
        app,
        [
            "copy",
            f"source:{memory.uid[:8]}",
            "--into",
            target.name,
            "--preserve-uids",
        ],
    )

    assert result.exit_code == 2
    assert "No such option: --preserve-uids" in result.stderr
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}
    with pytest.raises(TypeError, match="uid_policy"):
        CopyMemoriesRequest(
            (f"source:{memory.uid[:8]}",),
            into_locator=target.name,
            uid_policy="PRESERVE",
        )


def test_fresh_copy_uid_is_new_across_the_complete_local_store(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "value")
    target, _ = _context(store, "target")
    fresh_uid = "bbbbbbbb-0000-4000-8000-000000000000"
    generated = iter(
        (
            uuid.UUID(memory.uid),
            uuid.UUID(fresh_uid),
            uuid.UUID("cccccccc-0000-4000-8000-000000000000"),
        )
    )
    original_uuid4 = uuid.uuid4

    def controlled_uuid4():
        try:
            return next(generated)
        except StopIteration:
            return original_uuid4()

    monkeypatch.setattr(
        "memcommit.application.operations.copy_and_move.runtime.uuid.uuid4",
        controlled_uuid4,
    )

    copied = run_copy(
        CopyMemoriesRequest(
            (f"source:{memory.uid}",),
            into_locator=target.name,
        ),
        port=MemoryStoreCopyAndMovePort.capture(store),
    )

    assert copied.items[0].into_memory_uid == fresh_uid
    assert list(store.load_direct(target.name).memories) == [fresh_uid]


def test_cli_copy_and_move_share_one_current_relative_locator_snapshot(
    isolated_store,
):
    store = MemoryStore()
    source, (alpha, beta) = _context(
        store,
        "tree/source",
        "alpha",
        "beta",
    )
    target, _ = _context(store, "tree/target")
    store.set_current(target.name)

    copied = runner.invoke(
        app,
        ["copy", f"../source:{alpha.uid[:8]}", "--into", "."],
    )
    moved = runner.invoke(
        app,
        ["move", beta.uid[:8], "--from", "../source", "--into", "."],
    )

    assert copied.exit_code == 0, copied.output + copied.stderr
    assert moved.exit_code == 0, moved.output + moved.stderr
    assert [
        item.content for item in store.load_direct(target.name).iter_items()
    ] == ["alpha", "beta"]
    assert list(store.load_direct(source.name).memories) == [alpha.uid]


def test_cli_repeatable_memory_options_and_to_alias_execute_ordered_batches(
    isolated_store,
):
    store = MemoryStore()
    source, (alpha, beta, gamma) = _context(
        store,
        "source",
        "alpha",
        "beta",
        "gamma",
    )
    target, _ = _context(store, "target")

    copied = runner.invoke(
        app,
        [
            "copy",
            "--memory",
            f"source:{alpha.uid[:8]}",
            "-m",
            f"source:{beta.uid[:8]}",
            "--to",
            target.name,
        ],
    )
    moved = runner.invoke(
        app,
        [
            "move",
            "-m",
            f"source:{gamma.uid[:8]}",
            "--to",
            target.name,
        ],
    )

    assert copied.exit_code == 0, copied.output + copied.stderr
    assert moved.exit_code == 0, moved.output + moved.stderr
    assert [
        item.content for item in store.load_direct(target.name).iter_items()
    ] == ["alpha", "beta", "gamma"]
    assert list(store.load_direct(source.name).memories) == [alpha.uid, beta.uid]


def test_fresh_copy_can_duplicate_inside_its_source_context(isolated_store):
    store = MemoryStore()
    context, (memory,) = _context(store, "same", "repeat me")
    store.set_current(context.name)

    result = runner.invoke(
        app,
        ["copy", memory.uid[:8], "--from", "."],
    )

    assert result.exit_code == 0, result.output + result.stderr
    copies = tuple(store.load_direct(context.name).iter_items())
    assert [item.content for item in copies] == ["repeat me", "repeat me"]
    assert copies[0].uid == memory.uid
    assert copies[1].uid != memory.uid


def test_transfer_respects_target_and_source_memory_write_protection(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "protected source")
    target, _ = _context(store, "target")

    assert runner.invoke(app, ["lock", "context", target.name]).exit_code == 0
    blocked_copy = runner.invoke(
        app,
        ["copy", f"source:{memory.uid[:8]}", "--into", target.name],
    )
    assert blocked_copy.exit_code == 1
    assert "Context 'target' is locked" in blocked_copy.stderr
    assert store.load_direct(target.name).memories == {}
    assert runner.invoke(app, ["unlock", "context", target.name]).exit_code == 0

    assert (
        runner.invoke(
            app,
            ["lock", "memory", memory.uid, "--context", source.name],
        ).exit_code
        == 0
    )
    allowed_copy = runner.invoke(
        app,
        ["copy", f"source:{memory.uid[:8]}", "--into", target.name],
    )
    assert allowed_copy.exit_code == 0, allowed_copy.output + allowed_copy.stderr

    blocked_move = runner.invoke(
        app,
        ["move", f"source:{memory.uid[:8]}", "--into", target.name],
    )
    assert blocked_move.exit_code == 1
    assert f"Memory [{memory.uid[:8]}]" in blocked_move.stderr
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert len(store.load_direct(target.name).memories) == 1


def test_move_batch_across_sources_is_one_undo_and_redo_unit(isolated_store):
    store = MemoryStore()
    first, (alpha,) = _context(store, "first", "alpha")
    second, (beta,) = _context(store, "second", "beta")
    target, (marker,) = _context(store, "target", "marker")
    store.set_current(target.name)

    moved = runner.invoke(
        app,
        [
            "move",
            f"first:{alpha.uid[:8]}",
            f"second:{beta.uid[:8]}",
            "--after",
            marker.uid[:8],
        ],
    )

    assert moved.exit_code == 0, moved.output + moved.stderr
    assert store.load_direct(first.name).memories == {}
    assert store.load_direct(second.name).memories == {}
    assert [item.uid for item in store.load_direct(target.name).iter_items()] == [
        marker.uid,
        alpha.uid,
        beta.uid,
    ]

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output + undone.stderr
    assert "Undid command: mem move" in undone.output
    assert list(store.load_direct(first.name).memories) == [alpha.uid]
    assert list(store.load_direct(second.name).memories) == [beta.uid]
    assert list(store.load_direct(target.name).memories) == [marker.uid]

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output + redone.stderr
    assert "Redid command: mem move" in redone.output
    assert store.load_direct(first.name).memories == {}
    assert store.load_direct(second.name).memories == {}
    assert [item.uid for item in store.load_direct(target.name).iter_items()] == [
        marker.uid,
        alpha.uid,
        beta.uid,
    ]


def test_move_retargets_inbound_live_embed_by_default(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    ref = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    result = runner.invoke(
        app,
        ["move", f"source:{memory.uid[:8]}", "--into", "target"],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "RETARGET LINKS" in result.output
    assert "Retargeted 1 live Memory Embed" in result.output
    moved_ref = store.load_direct(watcher.name).memories[ref.uid]
    assert isinstance(moved_ref, MemoryRef)
    assert moved_ref.target_context_uid == target.uid
    assert moved_ref.target_context_name == target.name
    assert moved_ref.target_memory_uid == memory.uid
    assert store.load_direct(source.name).memories == {}
    assert list(store.load_direct(target.name).memories) == [memory.uid]


def test_move_retains_explicit_internal_block_policy_without_partial_change(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    ref = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    before = {
        name: store.load_direct(name).to_dict()
        for name in (source.name, target.name, watcher.name)
    }

    with pytest.raises(MemoryTransferError, match="blocked by 1 inbound"):
        run_move(
            MoveMemoriesRequest(
                (f"source:{memory.uid[:8]}",),
                into_locator=target.name,
                link_policy="BLOCK",
            ),
            port=MemoryStoreCopyAndMovePort.capture(store),
        )

    assert ref.uid in store.load_direct(watcher.name).memories
    assert {
        name: store.load_direct(name).to_dict()
        for name in (source.name, target.name, watcher.name)
    } == before


def test_move_retargets_local_live_embeds_and_history_atomically(isolated_store):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    ref = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    store.set_current(target.name)

    result = runner.invoke(
        app,
        [
            "move",
            f"source:{memory.uid[:8]}",
            "--retarget-links",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "Retargeted 1 live Memory Embed" in result.output
    moved_ref = store.load_direct(watcher.name).memories[ref.uid]
    assert isinstance(moved_ref, MemoryRef)
    assert moved_ref.target_context_uid == target.uid
    assert moved_ref.target_context_name == target.name
    assert moved_ref.target_memory_uid == memory.uid
    assert list(store.load_direct(target.name).memories) == [memory.uid]
    assert store.load_direct(source.name).memories == {}

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output + undone.stderr
    restored_ref = store.load_direct(watcher.name).memories[ref.uid]
    assert isinstance(restored_ref, MemoryRef)
    assert restored_ref.target_context_uid == source.uid
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}


def test_move_retarget_rejects_a_locked_link_owner_without_partial_change(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    ref = ops.embed_memory(memory, source, watcher)
    store.save(watcher)
    assert runner.invoke(app, ["lock", "context", watcher.name]).exit_code == 0

    result = runner.invoke(
        app,
        [
            "move",
            f"source:{memory.uid[:8]}",
            "--into",
            target.name,
            "--retarget-links",
        ],
    )

    assert result.exit_code == 1
    assert "Context 'watcher' is locked" in result.stderr
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}
    unchanged = store.load_direct(watcher.name).memories[ref.uid]
    assert isinstance(unchanged, MemoryRef)
    assert unchanged.target_context_uid == source.uid


def test_move_break_links_leaves_an_explicit_dangling_embed(isolated_store):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    ref = ops.embed_memory(memory, source, watcher)
    store.save(watcher)

    result = runner.invoke(
        app,
        [
            "move",
            f"source:{memory.uid[:8]}",
            "--into",
            target.name,
            "--break-links",
        ],
    )

    assert result.exit_code == 0, result.output + result.stderr
    assert "Left 1 live Memory Embed" in result.output
    dangling = store.load(watcher.name).memories[ref.uid]
    assert isinstance(dangling, MemoryRef)
    assert dangling.target_context_uid == source.uid
    assert dangling.target is None
    assert list(store.load_direct(target.name).memories) == [memory.uid]


def test_move_rejects_same_uid_branch_copies_before_target_mutation(isolated_store):
    store = MemoryStore()
    shared_uid = "aaaaaaaa-0000-0000-0000-000000000000"
    first, _ = _context(store, "first")
    second, _ = _context(store, "second")
    first.add(Memory(uid=shared_uid, content="first branch value"))
    second.add(Memory(uid=shared_uid, content="second branch value"))
    store.save(first)
    store.save(second)
    target, _ = _context(store, "target")

    result = runner.invoke(
        app,
        [
            "move",
            f"first:{shared_uid}",
            f"second:{shared_uid}",
            "--into",
            target.name,
        ],
    )

    assert result.exit_code == 1
    assert "same-UID branch copies" in result.stderr
    assert list(store.load_direct(first.name).memories) == [shared_uid]
    assert list(store.load_direct(second.name).memories) == [shared_uid]
    assert store.load_direct(target.name).memories == {}


def test_move_rejects_a_target_uid_collision_before_source_mutation(
    isolated_store,
):
    store = MemoryStore()
    shared_uid = "dddddddd-0000-4000-8000-000000000000"
    source, _ = _context(store, "source")
    target, _ = _context(store, "target")
    source.add(Memory(uid=shared_uid, content="source value"))
    target.add(Memory(uid=shared_uid, content="target branch value"))
    store.save(source)
    store.save(target)

    result = runner.invoke(
        app,
        ["move", f"source:{shared_uid}", "--into", target.name],
    )

    assert result.exit_code == 1
    assert "collide" in result.stderr
    assert store.load_direct(source.name).memories[shared_uid].content == "source value"
    assert (
        store.load_direct(target.name).memories[shared_uid].content
        == "target branch value"
    )


def test_move_default_retarget_refuses_a_target_owned_self_link(isolated_store):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "linked")
    target, _ = _context(store, "target")
    ref = ops.embed_memory(memory, source, target)
    store.save(target)
    before_source = store.load_direct(source.name).to_dict()
    before_target = store.load_direct(target.name).to_dict()

    result = runner.invoke(
        app,
        [
            "move",
            f"source:{memory.uid[:8]}",
            "--into",
            target.name,
        ],
    )

    assert result.exit_code == 1
    assert "self-link" in result.stderr
    assert ref.uid[:8] not in result.output
    assert store.load_direct(source.name).to_dict() == before_source
    assert store.load_direct(target.name).to_dict() == before_target


def test_copy_rejects_source_drift_without_target_publication(isolated_store):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "version one")
    target, _ = _context(store, "target")
    port = MemoryStoreCopyAndMovePort.capture(store)
    request = CopyMemoriesRequest(
        (f"source:{memory.uid[:8]}",),
        into_locator="target",
    )
    plan = port.freeze_copy(request)
    changed = store.load_direct(source.name)
    changed.replace(Memory(uid=memory.uid, content="version two"))
    store.save(changed)

    with pytest.raises(MemoryTransferStalePlanError, match="nothing was copied"):
        port.apply_copy(plan)
    assert store.load_direct(target.name).memories == {}


def test_copy_rejects_a_modified_frozen_plan_without_target_publication(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "exact value")
    target, _ = _context(store, "target")
    port = MemoryStoreCopyAndMovePort.capture(store)
    request = CopyMemoriesRequest(
        (f"source:{memory.uid[:8]}",),
        into_locator="target",
    )
    plan = port.freeze_copy(request)
    changed_item = replace(plan.memories[0], content="unreviewed value")

    with pytest.raises(MemoryTransferError, match="plan was modified"):
        run_copy(
            request,
            port=port,
            frozen_plan=replace(plan, memories=(changed_item,)),
        )

    assert store.load_direct(target.name).memories == {}


def test_move_rejects_graph_drift_without_partial_publication(isolated_store):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "value")
    target, _ = _context(store, "target")
    watcher, _ = _context(store, "watcher")
    port = MemoryStoreCopyAndMovePort.capture(store)
    request = MoveMemoriesRequest(
        (f"source:{memory.uid[:8]}",),
        into_locator="target",
    )
    plan = port.freeze_move(request)
    changed = store.load_for_update(watcher.name)
    ops.add(changed, "concurrent graph change")
    store.save(changed)

    with pytest.raises(MemoryTransferStalePlanError, match="nothing was moved"):
        port.apply_move(plan)
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}


def test_move_rolls_back_an_intermediate_store_failure_and_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "value")
    target, _ = _context(store, "target")
    original_save_locked = store._save_locked
    calls = 0

    def fail_second_save(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second Context failure")
        return original_save_locked(*args, **kwargs)

    monkeypatch.setattr(store, "_save_locked", fail_second_save)

    with pytest.raises(OSError, match="injected second Context failure"):
        run_move(
            MoveMemoriesRequest(
                (f"source:{memory.uid}",),
                into_locator=target.name,
            ),
            port=MemoryStoreCopyAndMovePort.capture(store),
        )

    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}
    assert store.list_checkpoints(source.name) == []
    assert store.list_checkpoints(target.name) == []


def test_cli_transfer_rejects_conflicting_options_before_store_change(
    isolated_store,
):
    store = MemoryStore()
    source, (memory,) = _context(store, "source", "value")
    target, _ = _context(store, "target")
    store.set_current(target.name)

    mixed_selection = runner.invoke(
        app,
        ["copy", memory.uid[:8], "--memory", memory.uid[:8], "--from", "source"],
    )
    two_targets = runner.invoke(
        app,
        [
            "copy",
            memory.uid[:8],
            "--from",
            "source",
            "--into",
            "target",
            "--to",
            "target",
        ],
    )
    two_link_policies = runner.invoke(
        app,
        [
            "move",
            memory.uid[:8],
            "--from",
            "source",
            "--retarget-links",
            "--break-links",
        ],
    )

    assert mixed_selection.exit_code == 1
    assert "not both" in mixed_selection.stderr
    assert two_targets.exit_code == 1
    assert "Target was supplied with more than one option" in two_targets.stderr
    assert two_link_policies.exit_code == 1
    assert "Pass only one" in two_link_policies.stderr
    assert list(store.load_direct(source.name).memories) == [memory.uid]
    assert store.load_direct(target.name).memories == {}
