"""Context namespace rename contracts.

Rename is an identity-preserving graph migration, not a directory-only move.
These tests keep the CLI review boundary separate from the store transaction
so pointer, history, and rollback regressions remain easy to diagnose.
"""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.command_history import build_command_stacks
from memcommit.cli import app
from memcommit.context import (
    AutoCheckpoint,
    Context,
    MemoryRef,
    QueryContextRef,
)
from memcommit.ground import (
    GroundTargetSpec,
    bind_ground_workbench,
    context_frame_digest,
    create_ground_session,
)
from memcommit.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.operations.translate.runtime import plan_translation
from memcommit.operations.translate.view import TranslationCatalog, TranslationView
from memcommit.operations.translate.view_store import (
    load_translation_catalog,
    save_translation_catalog,
)


runner = CliRunner(mix_stderr=False)


def _save_context(
    store: MemoryStore,
    name: str,
    *contents: str,
) -> Context:
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.save(
        context,
        AutoCheckpoint(
            command="init",
            args={"name": name},
            description=f"Initialized {name}",
        ),
    )
    return context


def _json_tree(root: Path) -> dict[str, bytes]:
    """Capture only durable JSON, excluding coordination lock artifacts."""
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.json"))
        if path.is_file() and not path.is_symlink()
    }


def test_cli_registers_reviewed_namespace_rename_syntax(isolated_store):
    command_help = runner.invoke(app, ["rename", "--help"])
    inventory = runner.invoke(app, ["help"])

    assert command_help.exit_code == 0, command_help.output
    assert "OLD" in command_help.output
    assert "NEW" in command_help.output
    assert "-f" in command_help.output
    assert "--force" in command_help.output
    assert "Profile" not in command_help.output
    assert inventory.exit_code == 0, inventory.output
    assert any(
        line.startswith("rename ") and "Rename an ordinary Context" in line
        for line in inventory.output.splitlines()
    )


def test_cli_force_rename_preserves_identity_content_order_and_history(
    isolated_store,
):
    store = MemoryStore()
    source = _save_context(store, "pracitce/2", "first", "second")
    store.set_current(source.name)
    source_uid = source.uid
    memory_uids = source.ordered_uids()
    original_checkpoint = store.list_checkpoints(source.name)[0]

    result = runner.invoke(
        app,
        ["rename", "pracitce/2", "practice/2", "--force"],
    )

    assert result.exit_code == 0, result.output
    assert "Renamed Context namespace 'pracitce/2'" in result.output
    assert "'practice/2'" in result.output
    assert not store.context_exists("pracitce/2")
    assert store.current_context_name() == "practice/2"
    renamed = store.load_direct("practice/2")
    assert renamed.uid == source_uid
    assert renamed.ordered_uids() == memory_uids
    assert [item.content for item in renamed.iter_items()] == ["first", "second"]

    history = store.list_checkpoints("practice/2")
    inherited = next(
        checkpoint
        for checkpoint in history
        if checkpoint["uid"] == original_checkpoint["uid"]
    )
    assert inherited == original_checkpoint
    assert any(
        checkpoint.get("command") == "rename"
        and checkpoint["snapshot"]["uid"] == source_uid
        and checkpoint["snapshot"]["name"] == "practice/2"
        for checkpoint in history
    )


def test_namespace_rename_moves_only_exact_root_and_lexical_descendants(
    isolated_store,
):
    store = MemoryStore()
    contexts = {
        name: _save_context(store, name, name)
        for name in (
            "old",
            "old/a",
            "old/a/b",
            "oldish",
            "other/old",
        )
    }
    store.set_current("old/a/b")

    result = runner.invoke(app, ["rename", "old", "new", "-f"])

    assert result.exit_code == 0, result.output
    assert store.list_context_names() == [
        "new",
        "new/a",
        "new/a/b",
        "oldish",
        "other/old",
    ]
    assert store.current_context_name() == "new/a/b"
    for old_name, new_name in (
        ("old", "new"),
        ("old/a", "new/a"),
        ("old/a/b", "new/a/b"),
    ):
        assert store.load_direct(new_name).uid == contexts[old_name].uid
    assert store.load_direct("oldish").uid == contexts["oldish"].uid
    assert store.load_direct("other/old").uid == contexts["other/old"].uid


def test_cli_resolves_only_old_as_a_relative_context_locator(isolated_store):
    store = MemoryStore()
    parent = _save_context(store, "team/source", "parent")
    child = _save_context(store, "team/source/child", "child")
    store.set_current(child.name)

    renamed = runner.invoke(app, ["rename", "..", "archive", "--force"])

    assert renamed.exit_code == 0, renamed.output
    assert store.load_direct("archive").uid == parent.uid
    assert store.load_direct("archive/child").uid == child.uid
    assert store.current_context_name() == "archive/child"

    invalid_new = runner.invoke(
        app,
        ["rename", ".", "./revised", "--force"],
    )

    assert invalid_new.exit_code == 1
    assert "Invalid context name './revised'" in invalid_new.stderr
    assert store.context_exists("archive/child")
    assert not store.context_exists("revised")


def test_declining_cli_confirmation_changes_nothing(isolated_store):
    store = MemoryStore()
    source = _save_context(store, "source", "keep me")
    store.set_current(source.name)
    before = _json_tree(isolated_store)

    result = runner.invoke(app, ["rename", "source", "destination"], input="n\n")

    assert result.exit_code == 0, result.output
    assert "Continue?" in result.output
    assert "Rename cancelled." in result.output
    assert _json_tree(isolated_store) == before
    assert store.context_exists("source")
    assert not store.context_exists("destination")
    assert store.current_context_name() == "source"


def test_general_cli_directs_nonportable_sources_to_compatibility_migration(
    isolated_store,
):
    result = runner.invoke(
        app,
        ["rename", "legacy source", "portable-source", "--force"],
    )

    assert result.exit_code == 1
    assert "General Context rename requires a portable" in result.stderr
    assert "mem profile migrate-context" in result.stderr


def test_rename_migrates_ordinary_context_and_memory_refs_by_target_uid(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save_context(store, "old/child", "live target")
    source_memory = next(iter(source.iter_items()))
    observer = ops.init("observer")
    observer.add(source)
    memory_ref = ops.embed_memory(source_memory, source, observer)
    query_ref = QueryContextRef(
        uid=str(uuid.uuid4()),
        name="old/child",
        target_source_uid=str(uuid.uuid4()),
        provider="codex_chatgpt",
    )
    observer.add(query_ref)
    store.save(
        observer,
        AutoCheckpoint(
            command="setup",
            args={},
            description="Saved ordinary and query-only pointers",
        ),
    )

    def forbidden_query_open(*args, **kwargs):
        raise AssertionError("rename opened query-only source content")

    monkeypatch.setattr(MemoryStore, "load_query_source", forbidden_query_open)
    plan = store.plan_context_rename("old/child", "new/child")
    assert plan.reference_count == 2
    store.rename_contexts(plan)

    direct = store.load_direct("observer")
    context_ref = direct.memories[source.uid]
    migrated_memory_ref = direct.memories[memory_ref.uid]
    unchanged_query_ref = direct.memories[query_ref.uid]
    assert isinstance(context_ref, Context)
    assert context_ref.uid == source.uid
    assert context_ref.name == "new/child"
    assert isinstance(migrated_memory_ref, MemoryRef)
    assert migrated_memory_ref.target_context_uid == source.uid
    assert migrated_memory_ref.target_context_name == "new/child"
    assert isinstance(unchanged_query_ref, QueryContextRef)
    assert unchanged_query_ref.name == "old/child"
    assert unchanged_query_ref.target_source_uid == query_ref.target_source_uid

    resolved = store.load("observer")
    resolved_context = resolved.memories[source.uid]
    resolved_memory_ref = resolved.memories[memory_ref.uid]
    assert isinstance(resolved_context, Context)
    assert [item.content for item in resolved_context.iter_items()] == [
        "live target"
    ]
    assert isinstance(resolved_memory_ref, MemoryRef)
    assert resolved_memory_ref.target is not None
    assert resolved_memory_ref.target.content == "live target"


def test_context_ref_loader_never_retargets_a_reused_name_to_a_new_uid():
    original = ops.init("stable-name")
    owner = ops.init("owner")
    owner.add(original)
    replacement = ops.init("stable-name")

    restored = Context.from_dict(
        owner.to_dict(),
        loader=lambda name: replacement,
    )

    assert original.uid not in restored.memories


def test_rename_rejects_new_per_owner_ordinary_query_selector_collision(
    isolated_store,
):
    store = MemoryStore()
    source = _save_context(store, "ordinary", "ordinary target")
    observer = ops.init("observer")
    observer.add(source)
    observer.add(
        QueryContextRef(
            uid=str(uuid.uuid4()),
            name="query-name",
            target_source_uid=str(uuid.uuid4()),
            provider="codex_chatgpt",
        )
    )
    store.save(observer)
    before = _json_tree(isolated_store)

    with pytest.raises(ValueError, match="ordinary and query-only child"):
        store.plan_context_rename("ordinary", "query-name")

    assert _json_tree(isolated_store) == before
    assert store.context_exists("ordinary")
    assert not store.context_exists("query-name")


def test_renamed_checkpoint_pointers_restore_against_the_new_locator(
    isolated_store,
):
    store = MemoryStore()
    source = _save_context(store, "old", "version one")
    source_memory = next(iter(source.iter_items()))
    observer = ops.init("observer")
    observer.add(source)
    memory_ref = ops.embed_memory(source_memory, source, observer)
    pointer_checkpoint = store.save(
        observer,
        AutoCheckpoint(
            command="reference",
            args={"historical_note": "the old locator was old"},
            description="Saved pointers before rename",
        ),
    )
    assert pointer_checkpoint is not None

    observer.remove(source.uid)
    observer.remove(memory_ref.uid)
    removed_checkpoint = store.save(
        observer,
        AutoCheckpoint(
            command="remove",
            args={},
            description="Removed pointers",
        ),
    )
    assert removed_checkpoint is not None

    store.rename_contexts(store.plan_context_rename("old", "new"))

    migrated_checkpoint = next(
        checkpoint
        for checkpoint in store.list_checkpoints("observer")
        if checkpoint["uid"] == pointer_checkpoint.uid
    )
    assert migrated_checkpoint["snapshot"]["memories"][source.uid]["name"] == (
        "new"
    )
    assert migrated_checkpoint["snapshot"]["memories"][memory_ref.uid][
        "target_context"
    ] == {"uid": source.uid, "name": "new"}
    # Free text and command evidence are historical records, not locators.
    assert migrated_checkpoint["args"]["historical_note"] == (
        "the old locator was old"
    )
    migrated_remove = next(
        checkpoint
        for checkpoint in store.list_checkpoints("observer")
        if checkpoint["uid"] == removed_checkpoint.uid
    )
    assert migrated_remove["command_before"]["memories"][source.uid]["name"] == (
        "new"
    )
    assert migrated_remove["command_before"]["memories"][memory_ref.uid][
        "target_context"
    ] == {"uid": source.uid, "name": "new"}
    assert build_command_stacks(store).undo[-1].command == "remove"

    store.revert("observer", pointer_checkpoint.uid, keep_history=True)
    restored = store.load("observer")
    restored_context = restored.memories[source.uid]
    restored_memory_ref = restored.memories[memory_ref.uid]
    assert isinstance(restored_context, Context)
    assert restored_context.name == "new"
    assert isinstance(restored_memory_ref, MemoryRef)
    assert restored_memory_ref.target is not None
    assert restored_memory_ref.target.content == "version one"


def test_undo_and_redo_survive_renamed_checkpoint_preimages(isolated_store):
    store = MemoryStore()
    source = _save_context(store, "old", "version one")
    source_memory = next(iter(source.iter_items()))
    observer = ops.init("observer")
    observer.add(source)
    memory_ref = ops.embed_memory(source_memory, source, observer)
    pointer_checkpoint = store.save(
        observer,
        AutoCheckpoint(
            command="reference",
            args={},
            description="Saved pointers",
        ),
    )
    assert pointer_checkpoint is not None
    observer.remove(source.uid)
    observer.remove(memory_ref.uid)
    store.save(
        observer,
        AutoCheckpoint(
            command="remove",
            args={},
            description="Removed pointers",
        ),
    )

    store.rename_contexts(store.plan_context_rename("old", "new"))

    undone = store.restore_recent_context_command("undo")
    assert undone.unit.command == "remove"
    restored = store.load("observer")
    assert restored.memories[source.uid].name == "new"
    assert restored.memories[memory_ref.uid].target_context_name == "new"

    redone = store.restore_recent_context_command("redo")
    assert redone.unit.uid == undone.unit.uid
    assert not store.load_direct("observer").memories


def test_undo_and_redo_survive_rename_inside_revert_log_snapshot(isolated_store):
    store = MemoryStore()
    source = _save_context(store, "old", "version one")
    source_memory = next(iter(source.iter_items()))
    observer = ops.init("observer")
    observer.add(source)
    memory_ref = ops.embed_memory(source_memory, source, observer)
    pointer_checkpoint = store.save(
        observer,
        AutoCheckpoint(
            command="reference",
            args={},
            description="Saved pointers",
        ),
    )
    assert pointer_checkpoint is not None
    observer.remove(source.uid)
    observer.remove(memory_ref.uid)
    store.save(
        observer,
        AutoCheckpoint(
            command="remove",
            args={},
            description="Removed pointers",
        ),
    )
    store.revert("observer", pointer_checkpoint.uid, keep_history=False)

    store.rename_contexts(store.plan_context_rename("old", "new"))

    assert build_command_stacks(store).undo[-1].command == "revert"
    undone = store.restore_recent_context_command("undo")
    assert undone.unit.command == "revert"
    assert not store.load_direct("observer").memories

    store.restore_recent_context_command("redo")
    restored = store.load("observer")
    assert restored.memories[source.uid].name == "new"
    assert restored.memories[memory_ref.uid].target_context_name == "new"


def test_reviewed_plan_is_rejected_if_context_graph_changes(isolated_store):
    store = MemoryStore()
    source = _save_context(store, "source", "reviewed state")
    store.set_current(source.name)
    plan = store.plan_context_rename("source", "destination")

    changed = store.load_direct("source")
    ops.add(changed, "concurrent change")
    store.save(changed)

    with pytest.raises(
        ConcurrentContextUpdateError,
        match="changed after the rename was reviewed",
    ):
        store.rename_contexts(plan)

    assert store.context_exists("source")
    assert not store.context_exists("destination")
    assert store.current_context_name() == "source"
    assert [item.content for item in store.load_direct("source").iter_items()] == [
        "reviewed state",
        "concurrent change",
    ]


def test_write_exception_rolls_back_namespace_records_history_and_state(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = _save_context(store, "source", "target")
    observer = ops.init("observer")
    observer.add(source)
    store.save(
        observer,
        AutoCheckpoint(
            command="embed",
            args={},
            description="External inbound reference",
        ),
    )
    store.set_current("source")
    plan = store.plan_context_rename("source", "destination")
    before = _json_tree(isolated_store)

    original_atomic_write = store_module._write_json_atomic
    write_count = 0

    def fail_after_one_write(*args, **kwargs):
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("injected rename write failure")
        return original_atomic_write(*args, **kwargs)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_after_one_write,
    )

    with pytest.raises(OSError, match="injected rename write failure"):
        store.rename_contexts(plan)

    assert write_count == 2
    assert _json_tree(isolated_store) == before
    assert store.context_exists("source")
    assert not store.context_exists("destination")
    assert store.current_context_name() == "source"


def test_rename_migrates_fresh_ground_frames_without_revising_the_ground(
    isolated_store,
):
    store = MemoryStore()
    raw = _save_context(store, "old", "Raw evidence")
    derived = _save_context(store, "work/derived", "Derived evidence")
    target = _save_context(store, "work/target", "Target evidence")
    session = bind_ground_workbench(
        create_ground_session("rename-ground", goal="Review evidence."),
        description="Review one rename migration.",
        raw_context=raw,
        derived_context=derived,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish one reviewed result.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)

    store.rename_contexts(store.plan_context_rename("old", "new"))

    migrated = store.load_ground_session("rename-ground")
    assert migrated is not None
    assert migrated.uid == session.uid
    assert migrated.revision == session.revision
    raw_frame = next(
        frame for frame in migrated.frames if frame.context_uid == raw.uid
    )
    assert raw_frame.context_name == "new"
    assert raw_frame.context_digest == context_frame_digest(
        store.load_direct("new")
    )


def test_rename_migrates_translation_catalog_context_identity(
    isolated_store,
):
    store = MemoryStore()
    source = _save_context(store, "old", "\uc6d0\ubb38")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("TRANSLATE PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "translations": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "translated_content": "translated",
                        }
                        for candidate in payload["memories"]
                    ]
                }
            )

    translation_plan = plan_translation(
        source,
        "English",
        Provider,
        allocate_operation_uid=False,
    )
    view = TranslationView.from_translation_plan(translation_plan, source)
    catalog = TranslationCatalog.from_legacy_views(
        source,
        "English",
        (view,),
    )
    assert catalog is not None
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=None,
    )

    store.rename_contexts(store.plan_context_rename("old", "new"))

    migrated = load_translation_catalog(source.uid, "English")
    assert migrated is not None
    assert migrated.context_uid == source.uid
    assert migrated.context_name == "new"
    assert migrated.entries == catalog.entries
