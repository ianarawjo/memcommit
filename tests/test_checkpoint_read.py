"""CheckpointRead grants bound retained History independently from READ."""

from __future__ import annotations

import json
import uuid

import pytest

from memcommit.application.capabilities import ops
from memcommit.application.capabilities.authority.checkpoint_read import (
    CheckpointReadAuthorizationError,
    read_checkpoint_history,
)
from memcommit.application.capabilities.authority.checkpoint_read_model import (
    CheckpointRead,
)
from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    AuthorityGrant,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    GrantedContextView,
    ProfileError,
    create_authority_grant,
    update_authority_grant,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.store import MemoryStore


def _save(store: MemoryStore, context, command: str) -> str:
    store.save(
        context,
        AutoCheckpoint(command=command, args={}, description=f"Ran {command}"),
    )
    return store.list_checkpoints(context.name)[0]["uid"]


def _history_fixture():
    store = MemoryStore()
    context = ops.init("checkpoint-right")
    first_uid = _save(store, context, "init")
    ops.add(context, "Second state")
    second_uid = _save(store, context, "add")
    ops.add(context, "Third state")
    third_uid = _save(store, context, "add")
    return store, context, (first_uid, second_uid, third_uid)


def _granted_access(
    store: MemoryStore,
    context,
    checkpoint_reads: tuple[CheckpointRead, ...],
) -> ContextAccess:
    authority = ProfileEntry(uid=str(uuid.uuid4()), name="authority", kind="MANAGED")
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    attachment_uid = str(uuid.uuid4())
    grant = AuthorityGrant(
        uid=str(uuid.uuid4()),
        revision=1,
        authority_profile_uid=authority.uid,
        grantee_profile_uid=grantee.uid,
        attachment_context_uid=attachment_uid,
        attachment_context_name="attachment",
        resource_kind="CONTEXT_TREE",
        resource_uid=context.uid,
        resource_name=context.name,
        public_name=context.name,
        permissions=("READ",),
        contexts=(GrantContextBinding(uid=context.uid, name=context.name),),
        checkpoint_reads=checkpoint_reads,
    )
    return ContextAccess(
        store=store,
        context_name=context.name,
        display_name=context.name,
        attachment_name="attachment",
        permission="READ",
        view=GrantedContextView(
            grant=grant,
            authority=authority,
            grantee=grantee,
            requested_name=context.name,
            authority_context_name=context.name,
            authority_root=store.store_dir,
        ),
    )


def test_checkpoint_read_model_round_trips_reference_and_embed():
    context_uid = str(uuid.uuid4())
    checkpoint_uids = (str(uuid.uuid4()), str(uuid.uuid4()))
    reference = CheckpointRead.reference(context_uid, checkpoint_uids)
    embed = CheckpointRead.embed(context_uid, checkpoint_uids[0])

    assert CheckpointRead.from_dict(reference.to_dict()) == reference
    assert CheckpointRead.from_dict(embed.to_dict()) == embed


def test_local_context_can_read_an_exact_checkpoint_window(isolated_store):
    store, context, checkpoint_uids = _history_fixture()
    access = ContextAccess(
        store=store,
        context_name=context.name,
        display_name=context.name,
        attachment_name=None,
        permission="READ",
    )

    result = read_checkpoint_history(
        access,
        CheckpointRead.reference(context.uid, (checkpoint_uids[0], checkpoint_uids[2])),
    )

    assert [checkpoint.uid for checkpoint in result.checkpoints] == [
        checkpoint_uids[0],
        checkpoint_uids[2],
    ]
    with pytest.raises(CheckpointReadAuthorizationError, match="outside"):
        result.record(checkpoint_uids[1])


def test_granted_reference_is_an_exact_checkpoint_set(isolated_store):
    store, context, checkpoint_uids = _history_fixture()
    access = _granted_access(
        store,
        context,
        (
            CheckpointRead.reference(
                context.uid,
                (checkpoint_uids[0], checkpoint_uids[2]),
            ),
        ),
    )

    result = read_checkpoint_history(
        access,
        CheckpointRead.reference(context.uid, (checkpoint_uids[2],)),
    )

    assert [checkpoint.uid for checkpoint in result.checkpoints] == [
        checkpoint_uids[2]
    ]
    with pytest.raises(CheckpointReadAuthorizationError, match="outside the granted"):
        read_checkpoint_history(
            access,
            CheckpointRead.reference(context.uid, (checkpoint_uids[1],)),
        )
    with pytest.raises(CheckpointReadAuthorizationError, match="cannot authorize"):
        read_checkpoint_history(
            access,
            CheckpointRead.embed(context.uid, checkpoint_uids[2]),
        )


def test_granted_embed_grows_from_its_same_context_anchor(isolated_store):
    store, context, checkpoint_uids = _history_fixture()
    access = _granted_access(
        store,
        context,
        (CheckpointRead.embed(context.uid, checkpoint_uids[1]),),
    )

    reference = read_checkpoint_history(
        access,
        CheckpointRead.reference(
            context.uid,
            (checkpoint_uids[1], checkpoint_uids[2]),
        ),
    )
    embedded = read_checkpoint_history(
        access,
        CheckpointRead.embed(context.uid, checkpoint_uids[2]),
    )

    assert [checkpoint.uid for checkpoint in reference.checkpoints] == [
        checkpoint_uids[1],
        checkpoint_uids[2],
    ]
    assert [checkpoint.uid for checkpoint in embedded.checkpoints] == [
        checkpoint_uids[2]
    ]
    with pytest.raises(CheckpointReadAuthorizationError, match="outside the granted"):
        read_checkpoint_history(
            access,
            CheckpointRead.reference(context.uid, (checkpoint_uids[0],)),
        )


def test_granted_read_alone_does_not_open_checkpoint_history(isolated_store):
    store, context, checkpoint_uids = _history_fixture()
    access = _granted_access(store, context, ())

    class StoreProbe:
        def __init__(self):
            self.checkpoint_reads = 0

        def load_direct(self, name):
            return store.load_direct(name)

        def list_checkpoints(self, name):
            self.checkpoint_reads += 1
            return store.list_checkpoints(name)

    probe = StoreProbe()
    access = ContextAccess(
        store=probe,  # type: ignore[arg-type]
        context_name=access.context_name,
        display_name=access.display_name,
        attachment_name=access.attachment_name,
        permission=access.permission,
        view=access.view,
    )

    with pytest.raises(CheckpointReadAuthorizationError, match="does not expose"):
        read_checkpoint_history(
            access,
            CheckpointRead.reference(context.uid, (checkpoint_uids[0],)),
        )
    assert probe.checkpoint_reads == 0


def test_profile_registry_v4_persists_checkpoint_reads_and_v3_loads_empty(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(uid=str(uuid.uuid4()), name="authority", kind="MANAGED")
    context_uid = str(uuid.uuid4())
    checkpoint_read = CheckpointRead.embed(context_uid, str(uuid.uuid4()))
    grant = AuthorityGrant(
        uid=str(uuid.uuid4()),
        revision=1,
        authority_profile_uid=authority.uid,
        grantee_profile_uid=authoring.uid,
        attachment_context_uid=str(uuid.uuid4()),
        attachment_context_name="attachment",
        resource_kind="CONTEXT_TREE",
        resource_uid=context_uid,
        resource_name="source",
        public_name="source",
        permissions=("READ",),
        contexts=(GrantContextBinding(uid=context_uid, name="source"),),
        checkpoint_reads=(checkpoint_read,),
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(grant,),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True)
    record = registry.to_dict()
    path.write_text(json.dumps(record), encoding="utf-8")

    assert load_profile_registry().grants[0].checkpoint_reads == (checkpoint_read,)

    record["schema_version"] = 3
    record["grants"][0].pop("checkpoint_reads")
    path.write_text(json.dumps(record), encoding="utf-8")

    assert load_profile_registry().grants[0].checkpoint_reads == ()


def test_grant_lifecycle_validates_checkpoint_read_scope_and_read_dependency(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    grantee_store = MemoryStore()
    attachment = ops.init("attachment")
    grantee_store.save(attachment)
    authority = ProfileEntry(uid=str(uuid.uuid4()), name="authority", kind="MANAGED")
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("source")
    checkpoint_uid = _save(authority_store, source, "init")
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")

    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        attachment_name=attachment.name,
        permissions=("READ",),
        checkpoint_reads=(
            CheckpointRead.reference(source.uid, (checkpoint_uid,)),
        ),
    )

    assert grant.checkpoint_reads[0].context_uid == source.uid
    with pytest.raises(ProfileError, match="require READ"):
        update_authority_grant(grant.uid, permissions=("QUERY",))
    _registry, revised = update_authority_grant(
        grant.uid,
        permissions=("QUERY",),
        checkpoint_reads=(),
    )
    assert revised.checkpoint_reads == ()

    with pytest.raises(ProfileError, match="does not name retained"):
        update_authority_grant(
            revised.uid,
            permissions=("READ",),
            checkpoint_reads=(
                CheckpointRead.embed(source.uid, str(uuid.uuid4())),
            ),
        )

    with pytest.raises(ProfileError, match="outside its Grant scope"):
        update_authority_grant(
            revised.uid,
            permissions=("READ",),
            checkpoint_reads=(
                CheckpointRead.embed(str(uuid.uuid4()), checkpoint_uid),
            ),
        )
