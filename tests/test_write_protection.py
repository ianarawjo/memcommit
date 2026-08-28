"""Persistent Context and direct-Memory write-protection contracts."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.application.operations.ground.model import create_ground_session
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.application.capabilities.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionState,
)


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def _all_output(result) -> str:
    """Support both merged and split-stderr Click/Typer test runners."""
    try:
        stderr = result.stderr
    except ValueError:
        stderr = ""
    return result.output + (stderr if stderr not in result.output else "")


def _first_memory(store: MemoryStore, name: str) -> Memory:
    item = next(iter(store.load_direct(name).iter_items()))
    assert isinstance(item, Memory)
    return item


def test_help_exposes_bare_recursive_context_memory_and_profile_targets():
    inventory = invoke("help")
    lock_help = invoke("lock", "--help")
    context_help = invoke("lock", "context", "--help")

    assert inventory.exit_code == 0
    assert any(
        line.startswith("lock ") and "current Context" in line
        for line in inventory.output.splitlines()
    )
    assert lock_help.exit_code == 0
    assert "[TARGET]" in lock_help.output
    assert "--recursive" in lock_help.output
    assert "--memory" in lock_help.output
    assert "--profile" in lock_help.output
    assert "context" in lock_help.output
    assert "memory" in lock_help.output
    assert "profile" in lock_help.output
    assert context_help.exit_code == 0
    assert "--recursive" in context_help.output


def test_auto_target_cli_classifies_context_and_unique_direct_memory(
    isolated_store,
):
    assert invoke("init", "target/context").exit_code == 0
    assert invoke("add", "protected memory").exit_code == 0
    store = MemoryStore()
    context = store.load_direct("target/context")
    memory = _first_memory(store, "target/context")
    assert invoke("init", "other").exit_code == 0

    locked_context = invoke("lock", "target/context")
    assert locked_context.exit_code == 0
    assert "Locked Context 'target/context'" in locked_context.output
    assert store.write_protection_state().context_is_protected(context.uid)
    assert invoke("unlock", "target/context").exit_code == 0

    locked_memory = invoke("lock", memory.uid[:7])
    assert locked_memory.exit_code == 0
    assert "Locked Memory" in locked_memory.output
    assert memory.uid in store.write_protection_state().protected_memory_uids(
        context.uid
    )
    assert (
        invoke(
            "unlock",
            f"target/context:{memory.uid[:8]}",
        ).exit_code
        == 0
    )


def test_explicit_target_options_cover_short_memory_prefix_and_profile(
    isolated_store,
):
    assert invoke("init", "protected").exit_code == 0
    assert invoke("add", "keep").exit_code == 0
    store = MemoryStore()
    context = store.load_direct("protected")
    memory = _first_memory(store, "protected")

    assert (
        invoke(
            "lock",
            "--memory",
            memory.uid[:4],
            "--context",
            "protected",
        ).exit_code
        == 0
    )
    assert memory.uid in store.write_protection_state().protected_memory_uids(
        context.uid
    )
    assert (
        invoke(
            "unlock",
            "--memory",
            memory.uid[:4],
            "--context",
            "protected",
        ).exit_code
        == 0
    )

    assert invoke("lock", "--context", "protected").exit_code == 0
    assert store.write_protection_state().context_is_protected(context.uid)
    assert invoke("unlock", "--context", "protected").exit_code == 0

    assert invoke("lock", "--profile").exit_code == 0
    assert store.write_protection_state().profile_is_protected()
    assert invoke("unlock", "--profile").exit_code == 0
    assert not store.write_protection_state().profile_is_protected()


def test_auto_memory_target_remains_unique_after_branch(
    isolated_store,
):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "shared lineage").exit_code == 0
    store = MemoryStore()
    memory = _first_memory(store, "source")
    assert invoke("branch", "working").exit_code == 0

    locked = invoke("lock", memory.uid[:8])
    assert locked.exit_code == 0, _all_output(locked)
    source = store.load_direct("source")
    working = store.load_direct("working")
    working_memory = _first_memory(store, "working")
    assert working_memory.uid != memory.uid
    assert memory.uid in store.write_protection_state().protected_memory_uids(
        source.uid
    )
    assert working_memory.uid not in (
        store.write_protection_state().protected_memory_uids(working.uid)
    )


def test_context_scope_flags_reject_auto_memory_target_without_mutation(
    isolated_store,
):
    assert invoke("init", "protected").exit_code == 0
    assert invoke("add", "keep").exit_code == 0
    store = MemoryStore()
    memory = _first_memory(store, "protected")

    result = invoke("lock", memory.uid[:8], "--recursive")
    assert result.exit_code == 2
    assert "apply only to a Context target" in _all_output(result)
    assert "_target" not in _all_output(result)
    assert store.write_protection_state().is_empty


def test_context_lock_cli_blocks_changes_but_allows_checkpoint_and_branch(
    isolated_store,
):
    assert invoke("init", "protected").exit_code == 0

    locked = invoke("lock")
    assert locked.exit_code == 0
    assert "Locked Context 'protected'" in locked.output
    repeated = invoke("lock", "context", "protected")
    assert repeated.exit_code == 0
    assert "already locked" in repeated.output

    blocked = invoke("add", "must not be saved")
    assert blocked.exit_code == 1
    assert "Context 'protected' is locked against changes" in _all_output(blocked)
    assert invoke("checkpoint", "protected snapshot").exit_code == 0
    # Branching reads the source but creates a separate Context identity.
    assert invoke("branch", "protected/working-copy").exit_code == 0
    assert invoke("add", "branch remains writable").exit_code == 0

    assert invoke("switch", "protected").exit_code == 0
    unlocked = invoke("unlock")
    assert unlocked.exit_code == 0
    assert "Unlocked Context 'protected'" in unlocked.output
    assert invoke("add", "now writable").exit_code == 0
    assert not (isolated_store / "write-protection.json").exists()


def test_context_lock_failures_share_one_plain_cli_error_surface(isolated_store):
    assert invoke("init", "protected").exit_code == 0
    assert invoke("add", "existing").exit_code == 0
    store = MemoryStore()
    memory = _first_memory(store, "protected")
    assert invoke("lock").exit_code == 0

    expected = (
        "Error: Context 'protected' is locked against changes. "
        "Unlock that Context first.\n"
    )
    blocked = (
        invoke("add", "must not be saved"),
        invoke("delete", memory.uid[:8]),
        invoke("remove", memory.uid[:8]),
    )

    for result in blocked:
        assert result.exit_code == 1
        assert _all_output(result) == expected
        assert "╭─ Error" not in _all_output(result)
    assert memory.uid in store.load_direct("protected").memories


def test_recursive_context_lock_uses_a_frozen_existing_namespace_snapshot(
    isolated_store,
):
    assert invoke("init", "tree").exit_code == 0
    assert invoke("init", "tree/child").exit_code == 0
    assert invoke("init", "tree/child/deep").exit_code == 0
    assert invoke("init", "unrelated").exit_code == 0
    assert invoke("switch", "tree").exit_code == 0

    locked = invoke("lock", "-r")

    assert locked.exit_code == 0
    assert "3 Contexts, 3 changed" in locked.output
    store = MemoryStore()
    state = store.write_protection_state()
    for name in ("tree", "tree/child", "tree/child/deep"):
        assert state.context_is_protected(store.load_direct(name).uid)
    assert not state.context_is_protected(store.load_direct("unrelated").uid)

    assert invoke("switch", "tree/child").exit_code == 0
    assert invoke("add", "blocked").exit_code == 1
    assert invoke("switch", "unrelated").exit_code == 0
    assert invoke("add", "still writable").exit_code == 0

    # Recursive Context protection is a reviewed snapshot, not an inherited
    # namespace policy. Profile protection is the option that also blocks
    # future Context creation.
    assert invoke("init", "tree/later").exit_code == 0
    later = store.load_direct("tree/later")
    assert not store.write_protection_state().context_is_protected(later.uid)

    assert invoke("switch", "tree").exit_code == 0
    unlocked = invoke("unlock", "tree", "-r")
    assert unlocked.exit_code == 0
    assert "4 Contexts, 3 changed" in unlocked.output
    assert not store.write_protection_state().context_uids


def test_profile_lock_blocks_profile_writes_but_allows_reads_and_switching(
    isolated_store,
):
    assert invoke("init", "kept-locked").exit_code == 0
    assert invoke("add", "existing").exit_code == 0
    assert invoke("lock", "context", "kept-locked").exit_code == 0
    assert invoke("init", "ordinary").exit_code == 0

    locked = invoke("lock", "profile")

    assert locked.exit_code == 0
    assert "Locked Profile" in locked.output
    assert invoke("contexts").exit_code == 0
    assert invoke("list").exit_code == 0
    assert invoke("switch", "kept-locked").exit_code == 0

    blocked_add = invoke("add", "must not persist")
    blocked_checkpoint = invoke("checkpoint", "must not persist")
    blocked_create = invoke("init", "new-context")
    for result in (blocked_add, blocked_checkpoint, blocked_create):
        assert result.exit_code == 1
        assert "Profile is locked against writes" in _all_output(result)
    assert not MemoryStore().context_exists("new-context")

    unlocked = invoke("unlock", "profile")
    assert unlocked.exit_code == 0
    assert "Unlocked Profile" in unlocked.output
    # Profile unlock restores the narrower policy rather than clearing it.
    still_blocked = invoke("add", "still Context-blocked")
    assert still_blocked.exit_code == 1
    assert "Context 'kept-locked' is locked" in _all_output(still_blocked)
    assert invoke("switch", "ordinary").exit_code == 0
    assert invoke("add", "writable again").exit_code == 0


def test_profile_lock_blocks_non_context_profile_artifacts(isolated_store):
    store = MemoryStore()
    assert store.set_profile_write_protection(protected=True)

    with pytest.raises(WriteProtectionError, match="Profile is locked"):
        store.save_impact_plan(object())
    with pytest.raises(WriteProtectionError, match="Profile is locked"):
        store.save_ground_session(
            create_ground_session("locked-ground", goal="Keep this read-only")
        )
    with pytest.raises(WriteProtectionError, match="Profile is locked"):
        store.create_query_source("locked-source", "must not persist")
    # The failed guard runs before validation or storage creation.
    assert not (isolated_store / "impact-plan.json").exists()
    assert not (isolated_store / "ground-sessions").exists()
    assert not (isolated_store / "query-sources").exists()


def test_v1_registry_remains_readable_and_upgrades_on_next_change(
    isolated_store,
):
    assert invoke("init", "legacy-policy").exit_code == 0
    context = MemoryStore().load_direct("legacy-policy")
    path = isolated_store / "write-protection.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contexts": [context.uid],
                "memories": [],
            }
        ),
        encoding="utf-8",
    )

    state = MemoryStore().write_protection_state()
    assert state == WriteProtectionState(context_uids=frozenset({context.uid}))
    assert invoke("lock", "profile").exit_code == 0
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 2


def test_context_lock_uses_existing_context_locator_snapshot(isolated_store):
    assert invoke("init", "tree").exit_code == 0
    assert invoke("init", "tree/child").exit_code == 0

    locked = invoke("lock", "context", "..")

    assert locked.exit_code == 0
    store = MemoryStore()
    parent = store.load_direct("tree")
    child = store.load_direct("tree/child")
    state = store.write_protection_state()
    assert state.context_is_protected(parent.uid)
    assert not state.context_is_protected(child.uid)
    assert invoke("unlock", "context", "..").exit_code == 0


def test_memory_lock_blocks_only_that_direct_occurrence(isolated_store):
    assert invoke("init", "memories").exit_code == 0
    assert invoke("add", "first").exit_code == 0
    assert invoke("add", "second").exit_code == 0
    store = MemoryStore()
    context = store.load_direct("memories")
    first, second = [item for item in context.iter_items() if isinstance(item, Memory)]

    locked = invoke("lock", "memory", first.uid[:8])
    assert locked.exit_code == 0
    assert f"Locked Memory [{first.uid[:8]}]" in locked.output

    edited = invoke("edit", first.uid[:8], "changed first")
    assert edited.exit_code == 1
    assert f"Memory [{first.uid[:8]}]" in _all_output(edited)
    assert "locked against changes" in _all_output(edited)
    assert invoke("remove", first.uid[:8]).exit_code == 1
    assert invoke("clear", "memories", "--force").exit_code == 1
    assert invoke("delete", "memories", "--force").exit_code == 1

    # Other direct Memories and additions remain independently writable.
    assert invoke("edit", second.uid[:8], "changed second").exit_code == 0
    assert invoke("add", "third").exit_code == 0
    current = store.load_direct("memories")
    assert isinstance(current.memories[first.uid], Memory)
    assert current.memories[first.uid].content == "first"
    assert current.memories[second.uid].content == "changed second"

    assert invoke("unlock", "memory", first.uid[:8]).exit_code == 0
    assert invoke("remove", first.uid[:8]).exit_code == 0


def test_context_and_memory_protections_are_independent(isolated_store):
    assert invoke("init", "layered").exit_code == 0
    assert invoke("add", "keep this").exit_code == 0
    store = MemoryStore()
    memory = _first_memory(store, "layered")

    assert invoke("lock", "memory", memory.uid).exit_code == 0
    assert invoke("lock", "context", "layered").exit_code == 0
    assert invoke("unlock", "context", "layered").exit_code == 0

    assert invoke("add", "context-level changes are enabled").exit_code == 0
    assert invoke("edit", memory.uid, "still forbidden").exit_code == 1
    state = store.write_protection_state()
    context = store.load_direct("layered")
    assert not state.context_is_protected(context.uid)
    assert memory.uid in state.protected_memory_uids(context.uid)


def test_memory_lock_does_not_follow_uid_copy_into_branch(isolated_store):
    assert invoke("init", "source").exit_code == 0
    assert invoke("add", "shared lineage").exit_code == 0
    store = MemoryStore()
    memory = _first_memory(store, "source")
    assert invoke("lock", "memory", memory.uid).exit_code == 0

    assert invoke("branch", "working").exit_code == 0
    working_memory = _first_memory(store, "working")
    assert working_memory.uid != memory.uid
    assert invoke("edit", working_memory.uid, "branch edit").exit_code == 0
    assert store.load_direct("working").memories[working_memory.uid].content == (
        "branch edit"
    )

    assert invoke("switch", "source").exit_code == 0
    assert invoke("edit", f"source:{memory.uid}", "source edit").exit_code == 1
    assert store.load_direct("source").memories[memory.uid].content == (
        "shared lineage"
    )


def test_context_lock_blocks_relocation_while_memory_lock_survives_relocation(
    isolated_store,
):
    assert invoke("init", "rename-me").exit_code == 0
    assert invoke("lock", "context", "rename-me").exit_code == 0
    store = MemoryStore()
    with pytest.raises(WriteProtectionError, match="locked against changes"):
        store.rename_contexts(store.plan_context_rename("rename-me", "renamed"))

    assert invoke("unlock", "context", "rename-me").exit_code == 0
    assert invoke("add", "identity follows rename").exit_code == 0
    memory = _first_memory(store, "rename-me")
    assert invoke("lock", "memory", memory.uid).exit_code == 0
    store.rename_contexts(store.plan_context_rename("rename-me", "renamed"))

    assert invoke("edit", memory.uid, "blocked after rename").exit_code == 1
    assert (
        invoke(
            "unlock",
            "memory",
            memory.uid,
            "--context",
            "renamed",
        ).exit_code
        == 0
    )
    assert invoke("edit", memory.uid, "allowed after unlock").exit_code == 0


def test_relocation_cannot_rewrite_a_locked_inbound_reference_owner(
    isolated_store,
):
    store = MemoryStore()
    target = ops.init("rename-target")
    owner = ops.init("locked-owner")
    ops.embed(target, owner)
    store.save(target)
    store.save(owner)
    store.set_current(owner.name)
    assert invoke("lock", "context", owner.name).exit_code == 0

    with pytest.raises(
        WriteProtectionError,
        match="Context 'locked-owner' is locked against changes",
    ):
        store.rename_contexts(store.plan_context_rename(target.name, "renamed-target"))
    assert store.context_exists(target.name)
    assert not store.context_exists("renamed-target")


def test_store_boundary_blocks_programmatic_save_and_delete(isolated_store):
    store = MemoryStore()
    context = ops.init("boundary")
    memory = ops.add(context, "before")
    store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"memory_uids": [memory.uid]},
            description="setup",
        ),
    )
    store.set_current(context.name)
    changed = store.set_context_write_protection(
        context.name,
        protected=True,
        expected_context_uid=context.uid,
        expected_context_digest=context_record_digest(context),
    )
    assert changed is True

    edited = store.load_direct(context.name)
    edited.replace(Memory(uid=memory.uid, content="after"))
    with pytest.raises(WriteProtectionError, match="locked against changes"):
        store.save(edited)
    with pytest.raises(WriteProtectionError, match="locked against changes"):
        store.delete(context.name)


def test_context_lock_blocks_cli_undo_of_an_earlier_command(isolated_store):
    assert invoke("init", "undo-boundary").exit_code == 0
    assert invoke("add", "recorded addition").exit_code == 0
    assert invoke("lock", "context").exit_code == 0

    # Lock changes are intentionally outside Context command history, so Undo
    # reaches the earlier add but still cannot cross the current protection.
    undone = invoke("undo")
    assert undone.exit_code == 1
    assert "locked against changes" in _all_output(undone)


def test_protection_registry_is_scoped_to_each_profile_store(tmp_path):
    first_store = MemoryStore(root=tmp_path / "first")
    second_store = MemoryStore(root=tmp_path / "second")
    first = Context(uid="first-context", name="shared-name")
    second = Context(uid="second-context", name="shared-name")
    first_store.save(first)
    second_store.save(second)
    first_store.set_context_write_protection(
        first.name,
        protected=True,
        expected_context_uid=first.uid,
        expected_context_digest=context_record_digest(first),
    )

    editable = second_store.load_direct(second.name)
    editable.add("only the second Profile changes")
    second_store.save(editable)

    assert first_store.write_protection_state().context_is_protected(first.uid)
    assert second_store.write_protection_state().is_empty
    assert len(second_store.load_direct(second.name).memories) == 1


def test_invalid_registry_fails_closed_with_a_cli_error(isolated_store):
    assert invoke("init", "invalid-policy").exit_code == 0
    (isolated_store / "write-protection.json").write_text(
        "{not-json",
        encoding="utf-8",
    )

    result = invoke("add", "must fail closed")

    assert result.exit_code == 1
    assert "Write-protection storage is invalid JSON" in _all_output(result)
    assert "Traceback" not in _all_output(result)
    assert MemoryStore().load_direct("invalid-policy").memories == {}


def test_symlinked_registry_fails_closed_without_touching_target(
    isolated_store,
    tmp_path,
):
    assert invoke("init", "unsafe-policy").exit_code == 0
    outside = tmp_path / "outside-policy.json"
    outside.write_text("sentinel", encoding="utf-8")
    (isolated_store / "write-protection.json").symlink_to(outside)

    result = invoke("add", "must not follow registry link")

    assert result.exit_code == 1
    assert "cannot be a symbolic link" in _all_output(result)
    assert outside.read_text(encoding="utf-8") == "sentinel"
    assert MemoryStore().load_direct("unsafe-policy").memories == {}
