"""Path-aligned planning and atomic persistence for recursive Merge."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.authority.access import resolve_context_access
from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.merge_application import (
    MergeDecision,
    MergeReach,
    MergeRequest,
    prepare_merge,
    run_merge,
)
from memcommit.merge_runtime import MemoryStoreMergePort, execute_merge
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import ProfileError, create_authority_grant
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _create(store: MemoryStore, context: Context) -> Context:
    store.create_context(context)
    return context


def _contents(context: Context) -> list[str]:
    return [item.content for item in context.iter_items() if isinstance(item, Memory)]


def _setup_read_granted_advisors(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active = MemoryStore()
    task = _create(active, ops.init("task-2"))
    active.set_current(task.name)

    authority_entry = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="task-2-advisor-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = MemoryStore(root=profile_store_dir(authority_entry))
    for name in ("advisor1", "advisor2"):
        context = ops.init(name)
        ops.add(context, f"{name} recommendation")
        authority.create_context(context)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority_entry),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.to_dict()) + "\n",
        encoding="utf-8",
    )
    grants = []
    for name in ("advisor1", "advisor2"):
        _registry, grant = create_authority_grant(
            authority_name=authority_entry.name,
            grantee_name=authoring.name,
            resource_name=name,
            attachment_name=task.name,
            public_name=f"task-2/{name}",
            permissions=("READ",),
        )
        grants.append(grant)
    return active, tuple(grants)


def test_relative_granted_context_below_local_parent_uses_public_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, (source_grant, target_grant) = _setup_read_granted_advisors(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    source = resolve_context_access(
        store,
        "./advisor1",
        current_name="task-2",
        required_permission="READ",
    )

    assert source.is_granted is True
    assert source.display_name == "task-2/advisor1"
    assert source.view is not None
    assert source.view.grant.uid == source_grant.uid
    with pytest.raises(
        ProfileError,
        match=(
            rf"Grant {target_grant.uid[:8]} does not allow create access "
            r"to 'task-2/advisor2'\."
        ),
    ):
        resolve_context_access(
            store,
            "./advisor2",
            current_name="task-2",
            required_permission="CREATE",
        )
    with pytest.raises(
        FileNotFoundError,
        match=r"Context 'task-2/missing' does not exist\.",
    ):
        resolve_context_access(
            store,
            "./missing",
            current_name="task-2",
            required_permission="READ",
        )


def test_cli_merge_relative_granted_target_reports_permission_not_missing(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, (_source_grant, target_grant) = _setup_read_granted_advisors(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    result = runner.invoke(app, ["merge", "./advisor1", "./advisor2"])

    assert result.exit_code == 1
    assert (
        f"Grant {target_grant.uid[:8]} does not allow create access "
        "to 'task-2/advisor2'."
    ) in result.stderr
    assert "not found" not in result.stderr


def test_recursive_merge_aligns_paths_and_clones_source_only_contexts(
    isolated_store,
):
    store = MemoryStore()
    shared_uid = "00000000-0000-0000-0000-000000000001"

    source_shared = ops.init("source/shared")
    source_shared.add(Memory(uid=shared_uid, content="source revision"))
    new_shared = ops.add(source_shared, "shared source addition")
    _create(store, source_shared)
    source_only = ops.init("source/source-only")
    source_only_memory = ops.add(source_only, "source-only fact")
    _create(store, source_only)
    source_root = ops.init("source")
    root_memory = ops.add(source_root, "root source addition")
    source_root.add(Context(uid=source_shared.uid, name=source_shared.name))
    source_root.add(Context(uid=source_only.uid, name=source_only.name))
    _create(store, source_root)

    target_shared = ops.init("target/shared")
    target_shared.add(Memory(uid=shared_uid, content="target revision"))
    _create(store, target_shared)
    target_only = ops.init("target/target-only")
    target_only_memory = ops.add(target_only, "keep target-only")
    _create(store, target_only)
    target_root = ops.init("target")
    target_root.add(Context(uid=target_shared.uid, name=target_shared.name))
    _create(store, target_root)
    store.set_current(target_root.name)

    result = execute_merge(
        MergeRequest(source_locator="source", reach=MergeReach.DESCENDANTS),
        store=store,
        bulk=MergeDecision.KEEP_TARGET,
    )

    assert [context.target_name for context in result.contexts] == [
        "target",
        "target/shared",
        "target/source-only",
    ]
    assert [context.target_created for context in result.contexts] == [
        False,
        False,
        True,
    ]
    assert len(result.checkpoint_uids) == 3
    merged_root = store.load_direct("target")
    merged_shared = store.load_direct("target/shared")
    merged_source_only = store.load_direct("target/source-only")
    assert root_memory.uid in merged_root.memories
    assert merged_shared.memories[shared_uid].content == "target revision"
    assert merged_shared.memories[new_shared.uid].content == ("shared source addition")
    assert merged_source_only.uid != source_only.uid
    assert merged_source_only.memories[source_only_memory.uid].content == (
        "source-only fact"
    )
    remapped = merged_root.memories[merged_source_only.uid]
    assert isinstance(remapped, Context)
    assert (remapped.uid, remapped.name) == (
        merged_source_only.uid,
        merged_source_only.name,
    )
    assert target_only_memory.uid in store.load_direct("target/target-only").memories
    assert _contents(store.load_direct("source/shared")) == [
        "source revision",
        "shared source addition",
    ]
    assert all(
        len(store.list_checkpoints(context.target_name)) == 1
        for context in result.contexts
    )


def test_recursive_merge_matches_complete_relative_path_not_leaf_name(
    isolated_store,
):
    store = MemoryStore()
    source = _create(store, ops.init("source"))
    source_leaf = ops.init("source/alpha/leaf")
    source_memory = ops.add(source_leaf, "alpha source")
    _create(store, source_leaf)
    target = _create(store, ops.init("target"))
    different_leaf = ops.init("target/beta/leaf")
    different_memory = ops.add(different_leaf, "beta target")
    _create(store, different_leaf)
    store.set_current(target.name)

    execute_merge(
        MergeRequest(source_locator=source.name, reach=MergeReach.DESCENDANTS),
        store=store,
    )

    assert source_memory.uid in store.load_direct("target/alpha/leaf").memories
    assert different_memory.uid in store.load_direct("target/beta/leaf").memories


def test_recursive_merge_rejects_overlapping_local_trees(isolated_store):
    store = MemoryStore()
    _create(store, ops.init("tree"))
    _create(store, ops.init("tree/child"))
    store.set_current("tree/child")

    with pytest.raises(ValueError, match="disjoint"):
        execute_merge(
            MergeRequest(
                source_locator="tree",
                target_locator="tree/child",
                reach=MergeReach.DESCENDANTS,
            ),
            store=store,
        )


def test_recursive_merge_rechecks_complete_source_membership(isolated_store):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "planned root addition")
    _create(store, source)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)
    port = MemoryStoreMergePort.capture(store)
    request = MergeRequest(
        source_locator=source.name,
        reach=MergeReach.DESCENDANTS,
    )
    plan = prepare_merge(request, port=port)
    late = ops.init("source/late")
    ops.add(late, "late descendant")
    _create(store, late)

    with pytest.raises(RuntimeError, match="Source Context subtree changed"):
        run_merge(request, port=port, frozen_plan=plan)

    assert tuple(store.load_direct(target.name).iter_items()) == ()
    assert store.list_checkpoints(target.name) == []


def test_recursive_merge_rolls_back_every_written_context_on_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    root_addition = ops.add(source, "root addition")
    _create(store, source)
    source_child = ops.init("source/child")
    ops.add(source_child, "child addition")
    _create(store, source_child)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)
    original_save = store._save_locked
    call_count = 0

    def fail_second_save(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("injected recursive write failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(store, "_save_locked", fail_second_save)

    with pytest.raises(OSError, match="injected recursive write failure"):
        execute_merge(
            MergeRequest(
                source_locator=source.name,
                reach=MergeReach.DESCENDANTS,
            ),
            store=store,
        )

    assert root_addition.uid not in store.load_direct(target.name).memories
    assert not store.context_exists("target/child")
    assert store.list_checkpoints(target.name) == []


def test_recursive_merge_is_exposed_as_one_complete_undo(
    isolated_store,
):
    store = MemoryStore()
    source = ops.init("source")
    ops.add(source, "root addition")
    _create(store, source)
    child = ops.init("source/child")
    ops.add(child, "child addition")
    _create(store, child)
    target = _create(store, ops.init("target"))
    store.set_current(target.name)
    execute_merge(
        MergeRequest(source_locator=source.name, reach=MergeReach.DESCENDANTS),
        store=store,
    )

    undo = runner.invoke(app, ["undo"])

    assert undo.exit_code == 0, undo.output + undo.stderr
    assert "Affected Contexts: 2" in undo.output
    assert _contents(store.load_direct("target")) == []
    assert not store.context_exists("target/child")


def test_recursive_merge_copies_a_read_granted_subtree_as_local_values(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active = MemoryStore()
    attachment = _create(active, ops.init("task-root"))
    target = _create(active, ops.init("accumulator"))
    active.set_current(target.name)

    authority_entry = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="recursive-merge-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = MemoryStore(root=profile_store_dir(authority_entry))
    child = ops.init("advisor/child")
    child_memory = ops.add(child, "advisor child fact")
    authority.create_context(child)
    root = ops.init("advisor")
    root_memory = ops.add(root, "advisor root fact")
    root.add(Context(uid=child.uid, name=child.name))
    authority.create_context(root)
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority_entry),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict()) + "\n",
        encoding="utf-8",
    )
    create_authority_grant(
        authority_name=authority_entry.name,
        grantee_name=authoring.name,
        resource_name=root.name,
        attachment_name=attachment.name,
        public_name="advisor",
        permissions=("READ", "DERIVE", "EXPORT"),
        recursive=True,
    )

    result = execute_merge(
        MergeRequest(source_locator="advisor", reach=MergeReach.DESCENDANTS),
        store=active,
    )

    assert result.cross_profile_memory_only is True
    assert root_memory.uid in active.load_direct("accumulator").memories
    local_child = active.load_direct("accumulator/child")
    assert child_memory.uid in local_child.memories
    assert local_child.uid != child.uid
    assert not any(
        isinstance(item, Context)
        for item in active.load_direct("accumulator").iter_items()
    )
