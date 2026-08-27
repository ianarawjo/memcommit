"""Grant-aware direct-Memory Copy and fail-closed Move contracts."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.adapters.python_api import (
    MemCommitClient,
    MemoryTransferAuthorityError as PublicMemoryTransferAuthorityError,
    MemoryTransferContextError,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Memory
from memcommit.interfaces.agent.memory_transfer import MemoryTransferAgentAdapter
from memcommit.memory_transfer_application import (
    CopyMemoriesRequest,
    MemoryTransferAuthorityError,
    MemoryTransferError,
    MemoryTransferStalePlanError,
    MoveMemoriesRequest,
    run_copy,
    run_move,
)
from memcommit.memory_transfer_runtime import MemoryStoreMemoryTransferPort
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    ProfileError,
    create_authority_grant,
    create_profile,
    delete_authority_grant,
    update_authority_grant,
)
from memcommit.store import MemoryStore, context_record_digest


_COPY_PERMISSIONS = ("READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS")
runner = CliRunner(mix_stderr=False)


def _grant_fixture(
    tmp_path,
    monkeypatch,
    *,
    permissions=_COPY_PERMISSIONS,
    source_contents=("Export-authorized source",),
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    attachment = ops.init("task-root")
    active_store.save(attachment)
    active_store.set_current(attachment.name)
    target = ops.init("task-root/target")
    active_store.save(target)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="copy-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memories = tuple(ops.add(source, content) for content in source_contents)
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        attachment_name=attachment.name,
        public_name="shared/source",
        permissions=permissions,
    )
    return (
        active_store,
        authority_store,
        source,
        memories,
        target,
        grant,
    )


def _granted_port(store: MemoryStore) -> MemoryStoreMemoryTransferPort:
    return MemoryStoreMemoryTransferPort.capture(
        store,
        allow_granted_sources=True,
    )


def test_granted_copy_creates_fresh_retained_memory_and_checkpoint_provenance(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, source, (memory,), target, grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    source_digest = context_record_digest(authority_store.load_direct(source.name))

    result = run_copy(
        CopyMemoriesRequest(
            (f"shared/source:{memory.uid[:8]}",),
            into_locator=target.name,
        ),
        port=_granted_port(store),
    )

    copied = tuple(store.load_direct(target.name).iter_items())
    assert len(copied) == 1
    assert isinstance(copied[0], Memory)
    assert copied[0].content == memory.content
    assert copied[0].uid != memory.uid
    assert result.items[0].source_context_name == "shared/source"
    assert result.items[0].source_context_uid == source.uid
    assert result.items[0].into_memory_uid == copied[0].uid
    assert context_record_digest(authority_store.load_direct(source.name)) == (
        source_digest
    )

    checkpoint = store.list_checkpoints(target.name)[-1]
    row = checkpoint["args"]["memory_transfer"]["items"][0]
    authority = row["source_authority"]
    assert row["source_context_digest"] == source_digest
    assert row["source_memory_uid"] == memory.uid
    assert row["output_memory_uid"] == copied[0].uid
    assert authority["public_name"] == "shared/source"
    assert authority["grant"]["uid"] == grant.uid
    assert authority["grant"]["revision"] == grant.revision
    assert authority["authority_profile_uid"] == grant.authority_profile_uid
    assert authority["grantee_profile_uid"] == grant.grantee_profile_uid
    assert authority["resource"] == {
        "uid": grant.resource_uid,
        "name": grant.resource_name,
    }
    assert authority["authority_context_name"] == source.name
    assert str(authority_store.store_dir) not in json.dumps(authority)


def test_granted_copy_requires_retained_analysis_permission_without_publication(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
        permissions=("READ", "DERIVE", "EXPORT"),
    )

    with pytest.raises(ProfileError, match="SAVE_ANALYSIS"):
        run_copy(
            CopyMemoriesRequest(
                (f"shared/source:{memory.uid}",),
                into_locator=target.name,
            ),
            port=_granted_port(store),
        )

    assert store.load_direct(target.name).memories == {}
    assert store.list_checkpoints(target.name) == []


def test_granted_copy_requires_an_explicit_public_owner(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(MemoryTransferError, match="any local Context"):
        run_copy(
            CopyMemoriesRequest(
                (memory.uid,),
                into_locator=target.name,
            ),
            port=_granted_port(store),
        )

    assert store.load_direct(target.name).memories == {}


def test_mixed_local_and_granted_copy_requires_combine(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (granted,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    local = ops.init("task-root/local-source")
    local_memory = ops.add(local, "Locally owned contributor")
    store.save(local)

    with pytest.raises(ProfileError, match="COMBINE"):
        run_copy(
            CopyMemoriesRequest(
                (
                    f"shared/source:{granted.uid}",
                    f"{local.name}:{local_memory.uid}",
                ),
                into_locator=target.name,
            ),
            port=_granted_port(store),
        )

    assert store.load_direct(target.name).memories == {}


def test_mixed_copy_with_combine_preserves_reviewed_order(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (granted,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
        permissions=(*_COPY_PERMISSIONS, "COMBINE"),
    )
    local = ops.init("task-root/local-source")
    local_memory = ops.add(local, "Locally owned contributor")
    store.save(local)

    result = run_copy(
        CopyMemoriesRequest(
            (
                f"shared/source:{granted.uid}",
                f"{local.name}:{local_memory.uid}",
            ),
            into_locator=target.name,
        ),
        port=_granted_port(store),
    )

    assert [
        item.content for item in store.load_direct(target.name).iter_items()
    ] == [granted.content, local_memory.content]
    assert [item.source_context_name for item in result.items] == [
        "shared/source",
        local.name,
    ]


def test_qualified_grant_does_not_broaden_later_bare_uid_resolution(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (granted,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
        permissions=(*_COPY_PERMISSIONS, "COMBINE"),
    )
    local = ops.init("task-root/local-source")
    # Deliberately reuse the authority Memory UID across ownership domains. A
    # bare lookup must see only this local occurrence even though the preceding
    # qualified operand caused the granted frame to be frozen for the batch.
    local_memory = Memory(
        uid=granted.uid,
        content="Bare UID must resolve only in the local graph",
    )
    local.add(local_memory)
    store.save(local)

    result = run_copy(
        CopyMemoriesRequest(
            (
                f"shared/source:{granted.uid}",
                local_memory.uid,
            ),
            into_locator=target.name,
        ),
        port=_granted_port(store),
    )

    assert [item.source_context_name for item in result.items] == [
        "shared/source",
        local.name,
    ]
    assert [
        item.content for item in store.load_direct(target.name).iter_items()
    ] == [granted.content, local_memory.content]


def test_grant_revision_is_revalidated_after_copy_freeze(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (memory,), target, grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    port = _granted_port(store)
    request = CopyMemoriesRequest(
        (f"shared/source:{memory.uid}",),
        into_locator=target.name,
    )
    plan = port.freeze_copy(request)
    update_authority_grant(grant.uid, permissions=_COPY_PERMISSIONS)

    with pytest.raises(ProfileError, match="grant changed"):
        port.apply_copy(plan)

    assert store.load_direct(target.name).memories == {}
    assert store.list_checkpoints(target.name) == []


def test_authority_content_drift_after_freeze_publishes_nothing(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    port = _granted_port(store)
    request = CopyMemoriesRequest(
        (f"shared/source:{memory.uid}",),
        into_locator=target.name,
    )
    plan = port.freeze_copy(request)
    changed = authority_store.load_for_update(source.name)
    changed.replace(Memory(uid=memory.uid, content="Changed after review"))
    authority_store.save(changed)

    with pytest.raises(MemoryTransferStalePlanError, match="nothing was copied"):
        port.apply_copy(plan)

    assert store.load_direct(target.name).memories == {}
    assert store.list_checkpoints(target.name) == []


def test_granted_move_is_explicitly_rejected_before_any_change(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
        permissions=(*_COPY_PERMISSIONS, "DELETE"),
    )
    source_before = context_record_digest(authority_store.load_direct(source.name))

    with pytest.raises(
        MemoryTransferAuthorityError,
        match="EXPORT permits a retained Copy, not deletion",
    ):
        run_move(
            MoveMemoriesRequest(
                (f"shared/source:{memory.uid}",),
                into_locator=target.name,
            ),
            port=_granted_port(store),
        )

    assert context_record_digest(authority_store.load_direct(source.name)) == (
        source_before
    )
    assert store.load_direct(target.name).memories == {}
    assert store.list_checkpoints(target.name) == []


def test_granted_copy_survives_revocation_and_its_local_result_can_move(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority_store, _source, (memory,), target, grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    destination = ops.init("task-root/moved")
    store.save(destination)
    copied = run_copy(
        CopyMemoriesRequest(
            (f"shared/source:{memory.uid}",),
            into_locator=target.name,
        ),
        port=_granted_port(store),
    )
    copied_uid = copied.items[0].into_memory_uid
    delete_authority_grant(grant.uid)

    retained = store.load_direct(target.name).memories[copied_uid]
    assert isinstance(retained, Memory)
    assert retained.content == memory.content
    moved = run_move(
        MoveMemoriesRequest(
            (f"{target.name}:{copied_uid}",),
            into_locator=destination.name,
        ),
        port=MemoryStoreMemoryTransferPort.capture(store),
    )

    assert moved.items[0].into_memory_uid == copied_uid
    assert store.load_direct(target.name).memories == {}
    assert store.load_direct(destination.name).memories[copied_uid].content == (
        memory.content
    )


def test_grantee_cannot_regrant_public_view_but_can_grant_retained_copy(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority_store, _source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    downstream = create_profile("downstream").profile
    downstream_store = MemoryStore(root=profile_store_dir(downstream))
    attachment = ops.init("receiver")
    downstream_store.save(attachment)
    before = load_profile_registry()

    # A public Grant name is a process-local authority view, not a Context
    # owned by the grantee Profile and therefore not a valid Grant resource.
    with pytest.raises(
        ProfileError,
        match="Authority Context 'shared/source' does not exist",
    ):
        create_authority_grant(
            authority_name=AUTHORING_PROFILE_NAME,
            grantee_name=downstream.name,
            resource_name="shared/source",
            attachment_name=attachment.name,
            public_name="forwarded/source",
            permissions=("READ",),
        )
    # Grant resources are Context trees. An exact granted Memory locator
    # cannot be smuggled through the Context-name field as a second grant.
    with pytest.raises(ValueError, match="not portable"):
        create_authority_grant(
            authority_name=AUTHORING_PROFILE_NAME,
            grantee_name=downstream.name,
            resource_name=f"shared/source:{memory.uid}",
            attachment_name=attachment.name,
            public_name="forwarded/memory",
            permissions=("READ",),
        )
    assert load_profile_registry().grants == before.grants

    copied = run_copy(
        CopyMemoriesRequest(
            (f"shared/source:{memory.uid}",),
            into_locator=target.name,
        ),
        port=_granted_port(store),
    )
    _registry, forwarded = create_authority_grant(
        authority_name=AUTHORING_PROFILE_NAME,
        grantee_name=downstream.name,
        resource_name=target.name,
        attachment_name=attachment.name,
        public_name="forwarded/source",
        permissions=("READ",),
    )

    assert forwarded.resource_uid == target.uid
    assert forwarded.authority_profile_uid == AUTHORING_PROFILE_UID
    copied_memory = store.load_direct(target.name).memories[
        copied.items[0].into_memory_uid
    ]
    assert isinstance(copied_memory, Memory)
    assert copied_memory.content == memory.content


def test_cli_routes_enable_explicit_granted_copy_and_explain_granted_move(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority, _source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    locator = f"shared/source:{memory.uid}"

    copied = runner.invoke(app, ["copy", locator, "--into", target.name])
    denied = runner.invoke(app, ["move", locator, "--into", target.name])

    assert copied.exit_code == 0, copied.output + copied.stderr
    assert len(store.load_direct(target.name).memories) == 1
    assert denied.exit_code == 1
    assert "EXPORT permits a retained Copy, not deletion" in denied.stderr
    assert "Copy it into a local Context first" in denied.stderr


def test_public_and_agent_routes_preserve_authority_category_and_root_isolation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority, _source, (memory,), target, _grant = _grant_fixture(
        tmp_path,
        monkeypatch,
    )
    client = MemCommitClient()
    locator = f"shared/source:{memory.uid}"

    receipt = client.copy_memories((locator,), into_context=target.name)
    assert receipt.items[0].source_context_name == "shared/source"
    with pytest.raises(
        PublicMemoryTransferAuthorityError,
        match="EXPORT permits a retained Copy, not deletion",
    ):
        client.move_memories((locator,), into_context=target.name)

    agent = MemoryTransferAgentAdapter(client).move(
        {
            "version": 2,
            "memory_locators": [locator],
            "into_context": target.name,
        }
    )
    assert agent["ok"] is False
    assert agent["error"]["code"] == "authority_denied"
    assert "Copy it into a local Context first" in agent["error"]["message"]

    explicit_root = MemCommitClient(root=store.store_dir)
    with pytest.raises(MemoryTransferContextError, match="does not exist locally"):
        explicit_root.copy_memories((locator,), into_context=target.name)
