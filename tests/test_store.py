"""Tests for MemoryStore — disk persistence layer (uses isolated_store fixture)."""
import pytest

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.store import MemoryStore


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_store_init_creates_directories(isolated_store):
    MemoryStore()
    assert (isolated_store / "contexts").is_dir()
    assert (isolated_store / "state.json").exists()


def test_store_init_twice_is_idempotent(isolated_store):
    MemoryStore()
    MemoryStore()  # should not raise


# ---------------------------------------------------------------------------
# current context
# ---------------------------------------------------------------------------

def test_current_context_name_is_none_initially(isolated_store):
    store = MemoryStore()
    assert store.current_context_name() is None


def test_set_and_get_current(isolated_store):
    store = MemoryStore()
    ctx = ops.init("alpha")
    store.save(ctx)
    store.set_current("alpha")
    assert store.current_context_name() == "alpha"


def test_failed_state_replace_preserves_previous_current(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    store.save(first)
    store.save(second)
    store.set_current(first.name)
    state_before = store_module.STATE_FILE.read_bytes()
    original_write = store_module._write_json_atomic

    def fail_state_write(path, data):
        if path == store_module.STATE_FILE:
            raise OSError("injected state write failure")
        return original_write(path, data)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_state_write,
    )

    with pytest.raises(OSError, match="injected state write failure"):
        store.set_current(second.name)

    assert store_module.STATE_FILE.read_bytes() == state_before
    assert store.current_context_name() == first.name
    assert not list(isolated_store.glob(".state.json.write-*"))


# ---------------------------------------------------------------------------
# context_exists / save / load
# ---------------------------------------------------------------------------

def test_context_does_not_exist_before_save(isolated_store):
    store = MemoryStore()
    assert not store.context_exists("ghost")


def test_save_and_load_round_trip(isolated_store):
    store = MemoryStore()
    ctx = ops.init("myctx")
    ops.add(ctx, "hello")
    store.save(ctx)

    loaded = store.load("myctx")
    assert loaded.name == "myctx"
    assert len(loaded.memories) == 1
    mem = next(iter(loaded.memories.values()))
    assert mem.content == "hello"


def test_load_nonexistent_raises(isolated_store):
    store = MemoryStore()
    with pytest.raises(FileNotFoundError):
        store.load("ghost")


def test_load_current_with_no_context_raises(isolated_store):
    store = MemoryStore()
    with pytest.raises(RuntimeError, match="No current context"):
        store.load_current()


def test_load_current_returns_correct_context(isolated_store):
    store = MemoryStore()
    ctx = ops.init("active")
    store.save(ctx)
    store.set_current("active")

    loaded = store.load_current()
    assert loaded.name == "active"


# ---------------------------------------------------------------------------
# list_context_names
# ---------------------------------------------------------------------------

def test_list_context_names_empty(isolated_store):
    store = MemoryStore()
    assert store.list_context_names() == []


def test_list_context_names_returns_all(isolated_store):
    store = MemoryStore()
    for name in ("bravo", "alpha", "charlie"):
        store.save(ops.init(name))
    assert store.list_context_names() == ["alpha", "bravo", "charlie"]


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def test_delete_removes_context(isolated_store):
    store = MemoryStore()
    ctx = ops.init("to-delete")
    store.save(ctx)
    assert store.context_exists("to-delete")

    store.delete("to-delete")
    assert not store.context_exists("to-delete")


def test_delete_clears_current_if_active(isolated_store):
    store = MemoryStore()
    ctx = ops.init("current-one")
    store.save(ctx)
    store.set_current("current-one")

    store.delete("current-one")
    assert store.current_context_name() is None


def test_delete_nonexistent_raises(isolated_store):
    store = MemoryStore()
    with pytest.raises(FileNotFoundError):
        store.delete("ghost")


def test_delete_supports_legacy_non_uuid_context_identity(isolated_store):
    store = MemoryStore()
    ctx = ops.init("legacy")
    ctx.uid = "legacy-context-identity"
    store.save(ctx)

    store.delete(ctx.name)

    assert not store.context_exists(ctx.name)


def test_delete_removes_only_its_context_scoped_atomize_analysis(
    isolated_store,
):
    from memcommit.atomize import (
        AtomizeImpactReport,
        create_atomize_analysis,
    )

    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    store.save(first)
    store.save(second)
    for ctx in (first, second):
        store.save_atomize_analysis(
            create_atomize_analysis(
                ctx,
                AtomizeImpactReport(
                    context_uid=ctx.uid,
                    context_name=ctx.name,
                    memory_count=0,
                    projected_memory_count=0,
                    items=(),
                ),
            )
        )

    store.delete(first.name)

    assert store.load_atomize_analysis(first.uid) is None
    assert store.load_atomize_analysis(second.uid) is not None
    assert store.context_exists(second.name)


def test_delete_preflights_invalid_exact_atomize_artifact(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("protected")
    store.save(ctx)
    analysis_path = store._atomize_analysis_path(ctx.uid)
    analysis_path.parent.mkdir(parents=True)
    analysis_path.mkdir()

    with pytest.raises(ValueError, match="Atomize analysis storage is invalid"):
        store.delete(ctx.name)

    assert store.context_exists(ctx.name)
    assert analysis_path.is_dir()


# ---------------------------------------------------------------------------
# checkpoints
# ---------------------------------------------------------------------------

def test_checkpoint_is_created_on_auto_save(isolated_store):
    from memcommit.context import AutoCheckpoint
    store = MemoryStore()
    ctx = ops.init("ckpt-ctx")
    store.save(ctx, AutoCheckpoint(command="init", args={}, description="setup"))

    cps = store.list_checkpoints("ckpt-ctx")
    assert len(cps) == 1
    assert cps[0]["command"] == "init"


def test_auto_checkpoint_is_rolled_back_when_context_write_fails(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    ctx = ops.init("failed-new-context")
    original_write = store_module._write_json_atomic

    def fail_context_write(path, data):
        if path.name == "context.json":
            raise OSError("injected context write failure")
        return original_write(path, data)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_context_write,
    )

    with pytest.raises(OSError, match="injected context write failure"):
        store.save(
            ctx,
            AutoCheckpoint(
                command="init",
                args={},
                description="must roll back",
            ),
        )

    assert not store.context_exists(ctx.name)
    assert not (isolated_store / "contexts" / ctx.name).exists()


def test_failed_existing_context_write_does_not_leave_false_checkpoint(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    ctx = ops.init("existing")
    store.save(ctx)
    original_bytes = store._context_file(ctx.name).read_bytes()
    ops.add(ctx, "unpersisted")
    original_write = store_module._write_json_atomic

    def fail_context_write(path, data):
        if path.name == "context.json":
            raise OSError("injected context write failure")
        return original_write(path, data)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_context_write,
    )

    with pytest.raises(OSError, match="injected context write failure"):
        store.save(
            ctx,
            AutoCheckpoint(
                command="atomize",
                args={"trace": {"operation_id": "not-retained"}},
                description="must roll back",
            ),
        )

    assert store._context_file(ctx.name).read_bytes() == original_bytes
    assert store.list_checkpoints(ctx.name) == []


def test_list_checkpoints_sorted_newest_first(isolated_store):
    from memcommit.context import AutoCheckpoint
    import time
    store = MemoryStore()
    ctx = ops.init("timeline")
    store.save(ctx, AutoCheckpoint(command="first", args={}, description="first"))
    time.sleep(0.01)
    ops.add(ctx, "a memory")
    store.save(ctx, AutoCheckpoint(command="second", args={}, description="second"))

    cps = store.list_checkpoints("timeline")
    assert len(cps) == 2
    assert cps[0]["command"] == "second"  # newest first


def test_rapid_checkpoints_with_same_description_use_unique_files(isolated_store):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    ctx = ops.init("rapid-history")
    for index in range(6):
        ops.add(ctx, f"memory {index}")
        store.save(
            ctx,
            AutoCheckpoint(
                command="embed",
                args={"index": index},
                description="Repeated operation description",
            ),
        )

    checkpoints = store.list_checkpoints("rapid-history")
    checkpoint_files = list(
        (
            isolated_store
            / "contexts"
            / "rapid-history"
            / "checkpoints"
        ).glob("*.json")
    )
    assert len(checkpoints) == 6
    assert len(checkpoint_files) == 6
    assert len({checkpoint["uid"] for checkpoint in checkpoints}) == 6


def test_revert_restores_earlier_state(isolated_store):
    from memcommit.context import AutoCheckpoint
    store = MemoryStore()

    ctx = ops.init("rev-ctx")
    store.save(ctx, AutoCheckpoint(command="init", args={}, description="init"))

    cps_after_init = store.list_checkpoints("rev-ctx")
    init_uid = cps_after_init[0]["uid"]

    ops.add(ctx, "memory added after init")
    store.save(ctx, AutoCheckpoint(command="add", args={}, description="add"))

    # Revert to the init checkpoint (empty context).
    store.revert("rev-ctx", uid_prefix=init_uid[:8])

    restored = store.load("rev-ctx")
    assert restored.memories == {}
