"""Tests for MemoryStore — disk persistence layer (uses isolated_store fixture)."""
import json
from pathlib import Path
import uuid

import pytest

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.store import (
    ConcurrentContextUpdateError,
    ContextDeletionCommittedError,
    MemoryStore,
    checkpoint_history_digest,
    context_record_digest,
    validate_context_name,
)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def test_validate_context_name_accepts_namespace_without_creating_store_state(
    isolated_store,
):
    name = "test/ground/ticker-rule-examples"

    assert validate_context_name(name) == name
    assert not isolated_store.exists()


@pytest.mark.parametrize(
    "name",
    (
        "../escape",
        "/absolute",
        "repeated//separator",
        r"windows\separator",
        "parent/context.json",
    ),
)
def test_validate_context_name_rejects_invalid_names_without_creating_store_state(
    isolated_store,
    name,
):
    with pytest.raises(ValueError, match="Context name|Invalid context name"):
        validate_context_name(name)

    assert not isolated_store.exists()


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


def test_set_current_context_if_rejects_deleted_and_recreated_target(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    target = ops.init("target")
    ops.add(target, "translated")
    store.save(source)
    store.save(target)
    store.set_current(source.name)
    target_digest = store_module.context_record_digest(target)

    store.delete(target.name)
    replacement = ops.init("target")
    ops.add(replacement, "different owner")
    store.create_context(replacement)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed before it could be selected",
    ):
        store.set_current_context_if(
            source.name,
            target.name,
            expected_context_uid=target.uid,
            expected_context_digest=target_digest,
        )

    assert store.current_context_name() == source.name


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


def test_context_storage_root_symlink_fails_closed_for_all_record_paths(
    isolated_store,
):
    store = MemoryStore()
    contexts_root = isolated_store / "contexts"
    contexts_root.rmdir()
    outside_root = isolated_store.parent / "outside-contexts"
    outside_context = outside_root / "external"
    outside_context.mkdir(parents=True)
    outside_file = outside_context / "context.json"
    outside_file.write_text(
        json.dumps(ops.init("external").to_dict()),
        encoding="utf-8",
    )
    contexts_root.symlink_to(outside_root, target_is_directory=True)

    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.context_exists("external")
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.list_context_names()
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.load("external")
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.save(ops.init("new"))
    with pytest.raises(ValueError, match="storage root.*symbolic link"):
        store.delete("external")

    assert outside_file.is_file()


def test_tolerant_context_catalog_preserves_typed_omission_diagnostics(
    isolated_store,
):
    store = MemoryStore()
    store.save(ops.init("valid"))
    malformed = isolated_store / "contexts" / "malformed" / "context.json"
    malformed.parent.mkdir()
    malformed.write_text("{not-json", encoding="utf-8")
    outside = isolated_store.parent / "linked-contexts"
    outside.mkdir()
    (isolated_store / "contexts" / "linked").symlink_to(
        outside,
        target_is_directory=True,
    )

    catalog = store.scan_context_catalog()

    assert catalog.names == ("valid",)
    assert not catalog.complete
    assert {
        (diagnostic.code, diagnostic.relative_path)
        for diagnostic in catalog.diagnostics
    } == {
        ("INVALID_JSON", "malformed/context.json"),
        ("UNSAFE_ENTRY", "linked"),
    }
    # Human navigation retains its tolerant header-valid projection.
    assert store.list_context_names() == ["valid"]


def test_strict_direct_context_graph_rejects_any_catalog_omission(
    isolated_store,
):
    store = MemoryStore()
    store.save(ops.init("valid"))
    malformed = isolated_store / "contexts" / "malformed" / "context.json"
    malformed.parent.mkdir()
    malformed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed.*invalid JSON"):
        store.load_direct_context_graph_strict()


def test_create_context_never_overwrites_an_existing_context(isolated_store):
    store = MemoryStore()
    existing = ops.init("owned")
    ops.add(existing, "keep")
    store.save(existing)
    candidate = ops.init("owned")
    ops.add(candidate, "overwrite")

    with pytest.raises(FileExistsError, match="already exists"):
        store.create_context(candidate)

    loaded = store.load_direct("owned")
    assert loaded.uid == existing.uid
    assert [item.content for item in loaded.iter_items()] == ["keep"]


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
    memory = ops.add(ctx, "private body must not enter the lifecycle ledger")
    from memcommit.context import AutoCheckpoint

    store.save(
        ctx,
        AutoCheckpoint(
            command="add",
            args={"memory_uids": [memory.uid]},
            description="Added private test body",
        ),
    )
    assert store.context_exists("to-delete")
    previous_checkpoint = store.list_checkpoints(ctx.name)[0]

    event = store.delete("to-delete")

    assert not store.context_exists("to-delete")
    assert event.kind == "CONTEXT_DELETED"
    assert event.context_uid == ctx.uid
    assert event.last_context_name == ctx.name
    assert event.last_context_digest == context_record_digest(ctx)
    assert event.previous_checkpoint_uid == previous_checkpoint["uid"]
    assert event.previous_checkpoint_status == "RECORDED"
    assert event.previous_checkpoint_digest == store_module._canonical_json_digest(
        previous_checkpoint
    )
    assert event.descendants_preserved is True
    assert store.list_context_lifecycle_events() == [event]

    event_path = isolated_store / "ledger" / "context-events" / (
        event.event_uid + ".json"
    )
    serialized = json.loads(event_path.read_text(encoding="utf-8"))
    assert serialized == event.to_dict()
    assert "private body" not in json.dumps(serialized)
    assert "snapshot" not in serialized
    assert "memories" not in serialized


def test_delete_without_checkpoint_records_absent_checkpoint_metadata(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("no-history")
    store.save(context)

    event = store.delete(context.name)

    assert event.previous_checkpoint_status == "NONE"
    assert event.previous_checkpoint_uid is None
    assert event.previous_checkpoint_digest is None


def test_delete_with_unreadable_checkpoint_records_unknown_history(
    isolated_store,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("unreadable-history")
    store.save(
        context,
        AutoCheckpoint(command="init", args={}, description="setup"),
    )
    checkpoint_dir = isolated_store / "contexts" / context.name / "checkpoints"
    (checkpoint_dir / "corrupt.json").write_text("{not-json", encoding="utf-8")

    event = store.delete(context.name)

    assert not store.context_exists(context.name)
    assert event.previous_checkpoint_status == "UNREADABLE"
    assert event.previous_checkpoint_uid is None
    assert event.previous_checkpoint_digest is None


def test_delete_recreate_same_name_retains_distinct_context_lifetimes(
    isolated_store,
):
    store = MemoryStore()
    first = ops.init("reused")
    store.save(first)
    first_event = store.delete(first.name)

    second = ops.init("reused")
    store.save(second)
    second_event = store.delete(second.name)

    assert first.uid != second.uid
    assert first_event.context_uid == first.uid
    assert second_event.context_uid == second.uid
    assert first_event.event_uid != second_event.event_uid
    assert first_event.operation_id != second_event.operation_id
    assert {
        event.context_uid
        for event in store.list_context_lifecycle_events(context_name="reused")
    } == {first.uid, second.uid}


def test_context_lifecycle_events_support_recursive_namespace_filter(
    isolated_store,
):
    store = MemoryStore()
    parent = ops.init("tree")
    child = ops.init("tree/child")
    store.save(parent)
    store.save(child)

    parent_event = store.delete(parent.name)
    assert store.context_exists(child.name)
    child_event = store.delete(child.name)

    assert store.list_context_lifecycle_events(context_name="tree") == [
        parent_event
    ]
    assert set(
        store.list_context_lifecycle_events(
            context_name="tree",
            recursive=True,
        )
    ) == {parent_event, child_event}


def test_delete_ledger_write_failure_restores_context_and_history(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("ledger-write-failure")
    ops.add(context, "must survive")
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="setup"),
    )
    store.set_current(context.name)
    history_before = store.list_checkpoints(context.name)

    def fail_ledger_write(event):
        raise OSError("injected lifecycle ledger failure")

    monkeypatch.setattr(store, "_write_context_lifecycle_event", fail_ledger_write)

    with pytest.raises(OSError, match="injected lifecycle ledger failure"):
        store.delete(context.name)

    assert store.load_direct(context.name).to_dict() == context.to_dict()
    assert store.list_checkpoints(context.name) == history_before
    assert store.current_context_name() == context.name
    assert store.list_context_lifecycle_events() == []


@pytest.mark.parametrize("symlink_target", ["ledger", "context-events"])
def test_delete_refuses_symlinked_lifecycle_storage_and_restores_context(
    isolated_store,
    monkeypatch,
    symlink_target,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("unsafe-ledger")
    ops.add(context, "must remain inside the Context")
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="setup"),
    )
    store.set_current(context.name)
    history_before = store.list_checkpoints(context.name)
    outside = isolated_store.parent / f"outside-{symlink_target}"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    ledger_dir = isolated_store / "ledger"
    if symlink_target == "ledger":
        ledger_dir.symlink_to(outside, target_is_directory=True)
    else:
        ledger_dir.mkdir()
        (ledger_dir / "context-events").symlink_to(
            outside,
            target_is_directory=True,
        )

    with pytest.raises(ValueError, match="symbolic link"):
        store.delete(context.name)

    assert store.load_direct(context.name).to_dict() == context.to_dict()
    assert store.list_checkpoints(context.name) == history_before
    assert store.current_context_name() == context.name
    assert sentinel.read_text(encoding="utf-8") == "untouched"
    assert list(outside.iterdir()) == [sentinel]


def test_event_directory_fsync_failure_removes_event_and_restores_context(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("ledger-fsync-failure")
    store.save(
        context,
        AutoCheckpoint(command="init", args={}, description="setup"),
    )
    store.set_current(context.name)
    history_before = store.list_checkpoints(context.name)
    original_fsync_directory = store_module._fsync_directory
    injected = False

    def fail_event_publication_once(path):
        nonlocal injected
        if path.name == "context-events" and not injected:
            injected = True
            raise OSError("injected lifecycle directory fsync failure")
        return original_fsync_directory(path)

    monkeypatch.setattr(store_module, "_fsync_directory", fail_event_publication_once)

    with pytest.raises(
        OSError,
        match="injected lifecycle directory fsync failure",
    ):
        store.delete(context.name)

    assert injected
    assert store.load_direct(context.name).to_dict() == context.to_dict()
    assert store.list_checkpoints(context.name) == history_before
    assert store.current_context_name() == context.name
    events_dir = isolated_store / "ledger" / "context-events"
    assert list(events_dir.iterdir()) == []


def test_primary_delete_unlink_failure_rolls_back_lifecycle_event(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("unlink-failure")
    store.save(context)
    original_unlink = Path.unlink

    def fail_primary_unlink(path, *args, **kwargs):
        if path.name.startswith(".context.json.delete-"):
            raise OSError("injected primary unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_primary_unlink)

    with pytest.raises(OSError, match="injected primary unlink failure"):
        store.delete(context.name)

    assert store.context_exists(context.name)
    assert store.load_direct(context.name).uid == context.uid
    assert store.list_context_lifecycle_events() == []


def test_post_unlink_cleanup_failure_keeps_committed_lifecycle_event(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("cleanup-failure")
    ops.add(context, "private checkpoint content must still be removed")
    store.save(
        context,
        AutoCheckpoint(command="add", args={}, description="setup"),
    )
    store.set_current(context.name)

    def fail_state_write(state):
        raise OSError("injected post-unlink state failure")

    monkeypatch.setattr(store, "_write_state", fail_state_write)

    with pytest.raises(
        ContextDeletionCommittedError,
        match="injected post-unlink state failure",
    ) as captured:
        store.delete(context.name)

    assert not store.context_exists(context.name)
    events = store.list_context_lifecycle_events(context_uid=context.uid)
    assert len(events) == 1
    assert events[0].kind == "CONTEXT_DELETED"
    assert captured.value.event == events[0]
    context_dir = isolated_store / "contexts" / context.name
    assert not context_dir.exists()


def test_internal_creation_rollback_does_not_record_deletion_event(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("rollback/first")
    second = ops.init("rollback/second")
    original_save_locked = store._save_locked

    def fail_second(context, *args, **kwargs):
        if context.name == second.name:
            raise OSError("injected batch creation failure")
        return original_save_locked(context, *args, **kwargs)

    monkeypatch.setattr(store, "_save_locked", fail_second)

    with pytest.raises(OSError, match="injected batch creation failure"):
        store.create_missing_contexts(((first, None), (second, None)))

    assert not store.context_exists(first.name)
    assert not store.context_exists(second.name)
    assert store.list_context_lifecycle_events() == []


def test_context_lifecycle_events_are_scoped_to_profile_store(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("profile-bound")
    store.save(context)
    event = store.delete(context.name)
    original_store_dir = store_module.STORE_DIR

    other_profile_dir = isolated_store.parent / "other-profile"
    monkeypatch.setattr(store_module, "STORE_DIR", other_profile_dir)
    # Existing Store objects retain the root selected at construction. A new
    # object observes the newly selected Profile boundary.
    assert store.list_context_lifecycle_events() == [event]
    other_store = MemoryStore()
    assert other_store.list_context_lifecycle_events() == []
    assert not (other_profile_dir / "ledger").exists()

    monkeypatch.setattr(store_module, "STORE_DIR", original_store_dir)
    assert store.list_context_lifecycle_events() == [event]


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

    event = store.delete(ctx.name)

    assert not store.context_exists(ctx.name)
    assert event.context_uid == "legacy-context-identity"


def test_delete_removes_context_scoped_analysis_and_matching_review(
    isolated_store,
):
    from memcommit.atomize import (
        AtomizeImpactReport,
        AtomizeItem,
        create_atomize_analysis,
    )
    from memcommit.atomize_workbench import create_atomize_workbench
    from memcommit.review import create_atomize_review

    store = MemoryStore()
    first = ops.init("first")
    second = ops.init("second")
    first_memory = ops.add(first, "Use the same credential.")
    store.save(first)
    store.save(second)
    first_analysis = create_atomize_analysis(
        first,
        AtomizeImpactReport(
            context_uid=first.uid,
            context_name=first.name,
            memory_count=1,
            projected_memory_count=1,
            items=(
                AtomizeItem(
                    memory=first_memory,
                    position=0,
                    classification="UNCERTAIN",
                    reason_codes=("A06_NO_HIDDEN_CONTEXT",),
                    children=(),
                    reason="The credential antecedent is unresolved.",
                    lint=(),
                ),
            ),
        ),
    )
    store.save_atomize_analysis(first_analysis)
    first_workbench = create_atomize_workbench(first_analysis)
    first_workbench.response_for(
        f"atomize:{first_memory.uid}"
    ).text = "Private workbench context."
    store.save_atomize_workbench(first_workbench)
    store.save_atomize_analysis(
        create_atomize_analysis(
            second,
            AtomizeImpactReport(
                context_uid=second.uid,
                context_name=second.name,
                memory_count=0,
                projected_memory_count=0,
                items=(),
            ),
        )
    )
    review = create_atomize_review(first, first_analysis)
    review.response_for(first_memory.uid).text = "Private local context."
    store.save_review_session(review)

    store.delete(first.name)

    assert store.load_atomize_analysis(first.uid) is None
    assert not store._atomize_workbench_path(first.uid).exists()
    assert store.load_atomize_analysis(second.uid) is not None
    assert store.load_review_session() is None
    assert store.context_exists(second.name)


def test_delete_removes_only_exact_context_atomize_grounding_artifact(
    isolated_store,
):
    store = MemoryStore()
    deleted = ops.init("deleted")
    retained = ops.init("retained")
    store.save(deleted)
    store.save(retained)
    deleted_path = store._atomize_grounding_session_path(deleted.uid)
    retained_path = store._atomize_grounding_session_path(retained.uid)
    deleted_path.parent.mkdir(parents=True)
    deleted_path.write_text(
        '{"reviewer_comment": "private context for deleted"}',
        encoding="utf-8",
    )
    retained_path.write_text(
        '{"reviewer_comment": "private context for retained"}',
        encoding="utf-8",
    )
    deleted_history = store._atomize_grounding_history_dir(deleted.uid)
    retained_history = store._atomize_grounding_history_dir(retained.uid)
    deleted_history.mkdir(parents=True)
    retained_history.mkdir()
    (deleted_history / f"{uuid.uuid4()}.json").write_text(
        '{"reviewer_comment": "archived private context for deleted"}',
        encoding="utf-8",
    )
    retained_history_file = retained_history / f"{uuid.uuid4()}.json"
    retained_history_file.write_text(
        '{"reviewer_comment": "archived private context for retained"}',
        encoding="utf-8",
    )

    store.delete(deleted.name)

    assert not deleted_path.exists()
    assert not deleted_history.exists()
    assert retained_path.is_file()
    assert retained_history_file.is_file()
    assert store.context_exists(retained.name)


def test_delete_preserves_review_bound_to_another_context(isolated_store):
    from memcommit.findings import AmbiguityReport
    from memcommit.review import create_ambiguity_review

    store = MemoryStore()
    deleted = ops.init("deleted")
    retained = ops.init("retained")
    store.save(deleted)
    store.save(retained)
    review = create_ambiguity_review(
        retained,
        AmbiguityReport(
            memory_count=0,
            findings=(),
        ),
    )
    store.save_review_session(review)

    store.delete(deleted.name)

    restored = store.load_review_session()
    assert restored is not None
    assert restored.uid == review.uid


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


def test_delete_preflights_symbolic_link_atomize_grounding_artifact(
    isolated_store,
):
    store = MemoryStore()
    ctx = ops.init("protected-grounding")
    store.save(ctx)
    grounding_path = store._atomize_grounding_session_path(ctx.uid)
    grounding_path.parent.mkdir(parents=True)
    outside = isolated_store.parent / "outside-grounding.json"
    outside.write_text("private reviewer comment", encoding="utf-8")
    grounding_path.symlink_to(outside)

    with pytest.raises(
        ValueError,
        match="Atomize grounding storage is invalid",
    ):
        store.delete(ctx.name)

    assert store.context_exists(ctx.name)
    assert grounding_path.is_symlink()
    assert outside.read_text(encoding="utf-8") == "private reviewer comment"


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


def test_checkpoint_rejects_stale_loaded_context_without_appending_history(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("checkpoint-race")
    store.save(context)
    stale = store.load_direct(context.name)

    concurrent = store.load_direct(context.name)
    ops.add(concurrent, "concurrent state")
    store.save(concurrent)
    context_after_concurrent_save = store.load_direct(context.name).to_dict()
    history_after_concurrent_save = store.list_checkpoints(context.name)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed before it could be checkpointed",
    ):
        store.checkpoint(stale, message="stale snapshot")

    assert (
        store.load_direct(context.name).to_dict()
        == context_after_concurrent_save
    )
    assert (
        store.list_checkpoints(context.name)
        == history_after_concurrent_save
    )


def test_checkpoint_rejects_unsaved_context_state(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("checkpoint-unsaved")
    store.save(context)
    history_before = store.list_checkpoints(context.name)
    ops.add(context, "not persisted")

    with pytest.raises(ValueError, match="has unsaved changes"):
        store.checkpoint(context, message="must not record")

    assert not store.load_direct(context.name).memories
    assert store.list_checkpoints(context.name) == history_before


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


def test_revert_carries_loaded_digest_into_locked_save(
    isolated_store,
    monkeypatch,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    ctx = ops.init("revert-cas")
    ops.add(ctx, "original")
    store.save(
        ctx,
        AutoCheckpoint(command="first", args={}, description="first"),
    )
    first_uid = store.list_checkpoints(ctx.name)[0]["uid"]
    ops.add(ctx, "later")
    store.save(
        ctx,
        AutoCheckpoint(command="second", args={}, description="second"),
    )
    expected = store_module.context_record_digest(
        store.load_direct(ctx.name)
    )
    observed = []
    original_save_locked = store._save_locked

    def record_expected(
        candidate,
        auto_checkpoint,
        *,
        expected_context_digest,
    ):
        observed.append(expected_context_digest)
        return original_save_locked(
            candidate,
            auto_checkpoint,
            expected_context_digest=expected_context_digest,
        )

    monkeypatch.setattr(store, "_save_locked", record_expected)

    store.revert(ctx.name, first_uid, keep_history=True)

    assert observed == [expected]
    assert [
        memory.content
        for memory in store.load_direct(ctx.name).iter_items()
    ] == ["original"]


@pytest.mark.parametrize(
    ("stale_field", "stale_value", "message"),
    [
        (
            "expected_context_uid",
            "stale-context-uid",
            "Context identity changed",
        ),
        (
            "expected_context_digest",
            "0" * 64,
            "Context content changed",
        ),
        (
            "expected_history_digest",
            "0" * 64,
            "Checkpoint history changed",
        ),
    ],
)
def test_revert_rejects_stale_reviewed_frame_before_any_mutation(
    isolated_store,
    stale_field,
    stale_value,
    message,
):
    from memcommit.context import AutoCheckpoint

    store = MemoryStore()
    context = ops.init("revert-reviewed-frame")
    ops.add(context, "earlier")
    store.save(
        context,
        AutoCheckpoint(
            command="first",
            args={},
            description="first",
        ),
    )
    target_uid = store.list_checkpoints(context.name)[0]["uid"]
    ops.add(context, "current")
    store.save(
        context,
        AutoCheckpoint(
            command="second",
            args={},
            description="second",
        ),
    )
    reviewed_context = store.load_direct(context.name)
    reviewed_history = store.list_checkpoints(context.name)
    expectations = {
        "expected_context_uid": reviewed_context.uid,
        "expected_context_digest": context_record_digest(reviewed_context),
        "expected_history_digest": checkpoint_history_digest(
            reviewed_history
        ),
    }
    expectations[stale_field] = stale_value
    context_before_revert = reviewed_context.to_dict()

    with pytest.raises(ConcurrentContextUpdateError, match=message):
        store.revert(
            context.name,
            target_uid,
            **expectations,
        )

    assert store.load_direct(context.name).to_dict() == context_before_revert
    assert store.list_checkpoints(context.name) == reviewed_history
