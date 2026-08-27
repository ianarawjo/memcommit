"""Recoverable checkpoint timeline and direct-Memory privacy contracts."""

from memcommit.context import (
    AutoCheckpoint,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.history import build_history
from memcommit.application import ops
from memcommit.store import MemoryStore


def _save_step(store, ctx, command, description):
    store.save(
        ctx,
        AutoCheckpoint(
            command=command,
            args={},
            description=description,
        ),
    )
    return store.list_checkpoints(ctx.name)[0]["uid"]


def test_build_history_reconstructs_direct_memory_versions_and_transitions(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("campus")
    store.save(ctx)
    _save_step(store, ctx, "init", "Initialized campus")

    shuttle = ops.add(ctx, "The shuttle detour is active.")
    _save_step(store, ctx, "add", "Added shuttle notice")
    ctx.replace(Memory(uid=shuttle.uid, content="The shuttle route is normal."))
    _save_step(store, ctx, "edit", "Updated shuttle notice")
    ctx.remove(shuttle.uid)
    _save_step(store, ctx, "remove", "Removed shuttle notice")

    timeline = build_history(store, "campus")

    assert [transition.kind for transition in timeline.transitions] == [
        "CREATED",
        "EDITED",
        "REMOVED",
    ]
    assert [version.content for version in timeline.versions] == [
        "The shuttle detour is active.",
        "The shuttle route is normal.",
    ]
    assert timeline.states[-1].current is True
    assert all(checkpoint.selectable for checkpoint in timeline.checkpoints)


def test_build_history_flattens_revert_log_snapshot_and_marks_archived_entries(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("journal")
    store.save(ctx)
    initial_uid = _save_step(store, ctx, "init", "Initialized journal")
    ops.add(ctx, "Day one")
    day_one_uid = _save_step(store, ctx, "add", "Added day one")
    ops.add(ctx, "Day two")
    day_two_uid = _save_step(store, ctx, "add", "Added day two")

    pre_revert, _ = store.revert(
        "journal",
        initial_uid,
        keep_history=False,
    )
    timeline = build_history(store, "journal")
    by_uid = {checkpoint.uid: checkpoint for checkpoint in timeline.checkpoints}

    assert by_uid[initial_uid].selectable is True
    assert by_uid[pre_revert.uid].selectable is True
    assert by_uid[day_one_uid].selectable is False
    assert by_uid[day_two_uid].selectable is False
    assert any(transition.kind == "RESTORED" for transition in timeline.transitions)
    assert timeline.states[-1].current is True
    assert timeline.states[-1].restored is True


def test_build_history_never_resolves_refs_or_query_only_content(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("privacy")
    ctx.add(Memory(uid="ordinary", content="Visible ordinary Memory"))
    ctx.add(
        MemoryRef(
            uid="ref",
            target_context_uid="secret-context",
            target_context_name="secret",
            target_memory_uid="secret-memory",
            target=Memory(uid="secret-memory", content="SECRET REF CONTENT"),
        )
    )
    ctx.add(
        QueryContextRef(
            uid="query",
            name="restricted-contracts",
            target_source_uid="secret-source",
            provider="codex_chatgpt",
        )
    )
    store.save(ctx)
    _save_step(store, ctx, "init", "Initialized privacy fixture")

    def forbidden(*args, **kwargs):
        raise AssertionError("history opened concealed or referenced content")

    monkeypatch.setattr(MemoryStore, "_load_direct_memory", forbidden)
    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden)

    timeline = build_history(store, "privacy")

    assert [version.content for version in timeline.versions] == [
        "Visible ordinary Memory"
    ]
    serialized = repr(timeline)
    assert "SECRET REF CONTENT" not in serialized
    assert "secret-source" not in serialized
