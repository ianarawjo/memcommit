"""Stable public Python API contracts for Add."""

from __future__ import annotations

import json
import uuid

import pytest

import memcommit
import memcommit.adapters.python_api._operations.add as add_operation
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import (
    AddAuthorityError,
    AddConflictError,
    AddContextError,
    AddInputError,
    AddMemoriesResult,
    AddStorageError,
    AddedMemoryResult,
    MemCommitClient,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import create_authority_grant
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


GRANTED_ADD_ACCESS = "granted/campus-authority/campus-notes"


def _create_granted_add_fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    attachment = ops.init("task-root")
    task_store.save(attachment)
    task_store.set_current(attachment.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="campus-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    target = ops.init("campus-notes")
    authority_store.save(target)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=target.name,
        permissions=("READ", "CREATE"),
    )
    return task_store, authority_store, target, authority


def test_root_package_exports_public_add_objects() -> None:
    assert memcommit.AddMemoriesResult is AddMemoriesResult
    assert memcommit.AddedMemoryResult is AddedMemoryResult
    assert memcommit.AddInputError is AddInputError


def test_public_add_preserves_order_multiline_duplicates_and_one_checkpoint(
    isolated_store,
) -> None:
    store = MemoryStore()
    target = ops.init("notes")
    store.save(target)
    store.set_current(target.name)
    before = len(store.list_checkpoints(target.name))
    client = MemCommitClient(root=isolated_store)

    result = client.add_memories(
        ("First line.\nSecond line.", "same", "same"),
    )

    assert result == AddMemoriesResult(
        context_name="notes",
        context_uid=target.uid,
        memories=tuple(
            AddedMemoryResult(uid=memory.uid, content=memory.content)
            for memory in result.memories
        ),
        checkpoint_uid=result.checkpoint_uid,
    )
    assert [memory.content for memory in result.memories] == [
        "First line.\nSecond line.",
        "same",
        "same",
    ]
    saved = store.load_direct("notes")
    assert [memory.content for memory in saved.memories.values()] == [
        "First line.\nSecond line.",
        "same",
        "same",
    ]
    checkpoints = store.list_checkpoints("notes")
    assert len(checkpoints) == before + 1
    assert checkpoints[0]["uid"] == result.checkpoint_uid
    assert checkpoints[0]["args"]["count"] == 3
    assert checkpoints[0]["args"]["contents"] == [
        "First line.\nSecond line.",
        "same",
        "same",
    ]
    assert checkpoints[0]["args"]["memory_uids"] == [
        memory.uid for memory in result.memories
    ]
    assert "mode" not in checkpoints[0]["args"]
    assert "source" not in checkpoints[0]["args"]


def test_public_add_resolves_relative_target_from_one_current_snapshot(
    isolated_store,
) -> None:
    store = MemoryStore()
    parent = ops.init("task")
    child = ops.init("task/child")
    store.save(parent)
    store.save(child)
    store.set_current(child.name)

    result = MemCommitClient(root=isolated_store).add_memories(
        ("Parent-only note.",),
        context_name="..",
    )

    assert result.context_name == "task"
    assert [
        memory.content for memory in store.load_direct("task").memories.values()
    ] == ["Parent-only note."]
    assert store.load_direct("task/child").memories == {}


@pytest.mark.parametrize("contents", [(), ("",), ("valid", "  \n")])
def test_public_add_rejects_invalid_batch_before_opening_store(
    tmp_path,
    contents,
) -> None:
    root = tmp_path / "missing-store"
    client = MemCommitClient(root=root)

    with pytest.raises(AddInputError):
        client.add_memories(contents, context_name="notes")

    assert not root.exists()


def test_public_add_rejects_text_as_sequence(tmp_path) -> None:
    client = MemCommitClient(root=tmp_path / "store")

    with pytest.raises(AddInputError, match="sequence"):
        client.add_memories("one Memory")


def test_active_profile_client_can_add_through_create_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    task_store, authority_store, target, _authority = _create_granted_add_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    result = MemCommitClient().add_memories(
        ("Created through the public view.",),
        context_name=GRANTED_ADD_ACCESS,
    )

    assert result.context_name == GRANTED_ADD_ACCESS
    assert result.context_uid == target.uid
    assert task_store.load_direct("task-root").memories == {}
    assert [
        memory.content
        for memory in authority_store.load_direct("campus-notes").memories.values()
    ] == ["Created through the public view."]
    checkpoint = authority_store.list_checkpoints("campus-notes")[0]
    assert checkpoint["args"]["authority_grant"]["access_context"] == (
        GRANTED_ADD_ACCESS
    )


def test_explicit_root_does_not_inherit_host_create_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    _task_store, authority_store, _target, _authority = _create_granted_add_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    client = MemCommitClient(root=isolated_store)

    with pytest.raises(AddContextError, match="not found"):
        client.add_memories(
            ("Must stay local.",),
            context_name=GRANTED_ADD_ACCESS,
        )

    assert authority_store.load_direct("campus-notes").memories == {}


def test_nonactive_profile_cannot_follow_active_profile_grant(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    _task_store, authority_store, _target, authority = _create_granted_add_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    client = MemCommitClient(profile=authority.name)

    with pytest.raises(AddAuthorityError, match="active Profile"):
        client.add_memories(
            ("Must not cross Profiles.",),
            context_name=GRANTED_ADD_ACCESS,
        )

    assert authority_store.load_direct("campus-notes").memories == {}


@pytest.mark.parametrize(
    ("failure", "public_error"),
    [
        (ConcurrentContextUpdateError("changed"), AddConflictError),
        (OSError("disk path detail"), AddStorageError),
    ],
)
def test_public_add_projects_conflict_and_storage_failures(
    isolated_store,
    monkeypatch,
    failure,
    public_error,
) -> None:
    store = MemoryStore()
    target = ops.init("notes")
    store.save(target)
    store.set_current(target.name)
    client = MemCommitClient(root=isolated_store)

    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(add_operation, "run_add", fail)

    with pytest.raises(public_error):
        client.add_memories(("No receipt.",))
    assert store.load_direct("notes").memories == {}
