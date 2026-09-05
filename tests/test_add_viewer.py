"""Add's Viewer reads only authorized direct Memories."""

import json
import uuid

import pytest

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.commands.add.command import load_add_memories
from memcommit.application.operations.add.application import AddRequest
from memcommit.application.operations.add.runtime import execute_add
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.persistence.store import MemoryStore
from tests.grant_placement_support import create_authority_grant_with_placement


def test_viewer_is_exact_direct_read_only_and_preserves_complete_content(
    isolated_store,
):
    store = MemoryStore()
    parent = ops.init("project")
    first = ops.add(parent, "First\ncomplete Memory")
    second = ops.add(parent, "Second")
    store.save(parent)
    child = ops.init("project/child")
    ops.add(child, "Excluded descendant")
    store.save(child)
    store.set_current("project/child")
    before = store.list_checkpoints("project")
    memories = load_add_memories(
        "project", store=store, current_context_name="project/child"
    )
    assert [(m.uid, m.content) for m in memories] == [
        (first.uid, first.content),
        (second.uid, second.content),
    ]
    assert store.list_checkpoints("project") == before
    assert store.current_context_name() == "project/child"


@pytest.mark.parametrize("can_read", [True, False])
def test_granted_viewer_reads_read_grants_and_rejects_query_only(
    isolated_store,
    tmp_path,
    monkeypatch,
    can_read,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    store.save(ops.init("workspace"))
    store.set_current("workspace")
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID, name=AUTHORING_PROFILE_NAME, kind="AUTHORING"
    )
    authority = ProfileEntry(uid=str(uuid.uuid4()), name="owner", kind="MANAGED")
    owner = MemoryStore(root=profile_store_dir(authority))
    context = ops.init("inbox")
    hidden = ops.add(context, "Owner Memory")
    owner.save(context)
    registry = ProfileRegistry(
        generation=1, active_uid=grantee.uid, profiles=(grantee, authority), grants=()
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()))
    create_authority_grant_with_placement(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name="inbox",
        access_name="inbox",
        permissions=("READ", "CREATE") if can_read else ("QUERY",),
    )
    if can_read:
        rows = load_add_memories("inbox", store=store, current_context_name="workspace")
        assert [(m.uid, m.content) for m in rows] == [(hidden.uid, hidden.content)]
    else:
        with pytest.raises((RuntimeError, ValueError)):
            load_add_memories("inbox", store=store, current_context_name="workspace")
    if can_read:
        result = execute_add(
            AddRequest(context_locator="inbox", contents=("New",)), store=store
        )
        assert result.context_name == "inbox"
        assert [m.content for m in owner.load_direct("inbox").memories.values()] == [
            "Owner Memory",
            "New",
        ]
    else:
        with pytest.raises((RuntimeError, ValueError)):
            execute_add(
                AddRequest(context_locator="inbox", contents=("New",)), store=store
            )
        assert [m.content for m in owner.load_direct("inbox").memories.values()] == [
            "Owner Memory"
        ]
