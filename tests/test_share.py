"""Grant-backed cross-Profile delivery behavior."""

from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    GRANT_RESOURCE_CONTEXT_TREE,
    AuthorityGrant,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _study_share_topology(tmp_path, monkeypatch, *, allow_share: bool = True):
    monkeypatch.setenv("HOME", str(tmp_path))
    sender = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-task-3",
        kind="MANAGED",
    )
    receiver = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="study-granted-memory",
        kind="MANAGED",
    )
    sender_store = MemoryStore(root=profile_store_dir(sender))
    receiver_store = MemoryStore(root=profile_store_dir(receiver))

    attachment = Context(uid=str(uuid.uuid4()), name="local/personal-memory")
    sender_store.create_context(attachment)
    source = Context(
        uid=str(uuid.uuid4()),
        name="local/personal-memory/severed",
    )
    source.add(Memory(uid=str(uuid.uuid4()), content="Use a text reminder."))
    source.add(
        Memory(uid=str(uuid.uuid4()), content="Avoid appointments before 09:00.")
    )
    sender_store.create_context(
        source,
        AutoCheckpoint(
            command="sever",
            args={"sever": {"output": source.name}},
            description="Created reviewed local outbound draft; not sent.",
        ),
    )
    sender_store.set_current(source.name)

    endpoint = Context(
        uid=str(uuid.uuid4()),
        name="remote/government/healthcare-agent",
    )
    receiver_store.create_context(endpoint)
    grant = AuthorityGrant(
        uid=str(uuid.uuid4()),
        revision=1,
        authority_profile_uid=receiver.uid,
        grantee_profile_uid=sender.uid,
        attachment_context_uid=attachment.uid,
        attachment_context_name=attachment.name,
        resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
        resource_uid=endpoint.uid,
        resource_name=endpoint.name,
        public_name="government/healthcare-agent",
        permissions=(("SHARE",) if allow_share else ("QUERY",)),
        contexts=(GrantContextBinding(uid=endpoint.uid, name=endpoint.name),),
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=sender.uid,
        profiles=(authoring, sender, receiver),
        grants=(grant,),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    return sender_store, receiver_store, source, receiver


def test_share_creates_real_receiver_memories_and_is_idempotent(
    tmp_path,
    monkeypatch,
):
    _sender_store, receiver_store, source, receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )

    first = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert first.exit_code == 0, first.stderr or first.output
    assert "Shared consent unit." in first.output
    receiver_line = next(
        line for line in first.output.splitlines() if line.startswith("Receiver: ")
    )
    receiver_name = receiver_line.split(":", 2)[2]
    delivered = receiver_store.load_direct(receiver_name)
    assert [
        item.content for item in delivered.iter_items() if isinstance(item, Memory)
    ] == ["Use a text reminder.", "Avoid appointments before 09:00."]
    receipt = receiver_store.list_checkpoints(receiver_name)[0]
    assert receipt["command"] == "share-receive"
    assert receipt["args"]["share"]["sender_profile_name"] == "study-task-3"
    assert receipt["args"]["share"]["endpoint"] == "government/healthcare-agent"
    assert receiver.name in receiver_line

    second = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert second.exit_code == 0, second.stderr or second.output
    assert "already shared" in second.output
    assert second.output.count("Share: ") == 1


def test_share_requires_endpoint_capability(tmp_path, monkeypatch):
    _sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
        allow_share=False,
    )
    result = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )
    assert result.exit_code == 1
    assert (
        "Share endpoint 'government/healthcare-agent' does not exist" in result.stderr
    )


def test_share_rejects_non_sever_context(tmp_path, monkeypatch):
    sender_store, _receiver_store, _source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    ordinary = Context(uid=str(uuid.uuid4()), name="local/personal-memory/manual")
    ordinary.add("Unreviewed private content")
    sender_store.create_context(ordinary)
    result = runner.invoke(
        app,
        ["share", ordinary.name, "--to", "government/healthcare-agent"],
    )
    assert result.exit_code == 1
    assert "Only an applied Sever output can be shared" in result.stderr


def test_share_rejects_content_changed_after_sever(tmp_path, monkeypatch):
    sender_store, _receiver_store, source, _receiver = _study_share_topology(
        tmp_path,
        monkeypatch,
    )
    changed = sender_store.load_direct(source.name)
    changed.add("Added after the reviewed consent unit")
    sender_store.save(
        changed,
        AutoCheckpoint(
            command="add",
            args={"content": "Added after the reviewed consent unit"},
            description="Changed the outbound draft after review.",
        ),
    )

    result = runner.invoke(
        app,
        ["share", source.name, "--to", "government/healthcare-agent"],
    )

    assert result.exit_code == 1
    assert "Only an unchanged applied Sever output can be shared" in result.stderr
