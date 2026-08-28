"""Export-authorized immutable References from exact granted Memories."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import (
    MemCommitClient,
    ReferenceAuthorityError,
    ReferenceContextError,
)
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef
from memcommit.adapters.agent.reference import ReferenceAgentAdapter
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    create_authority_grant,
    update_authority_grant,
)
from memcommit.application.operations.reference.application import ReferenceRequest
from memcommit.application.operations.reference.runtime import MemoryStoreReferencePort
from memcommit.persistence.store import MemoryStore, context_record_digest


runner = CliRunner(mix_stderr=False)
_REQUIRED = ("READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS")


def _fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    workspace = ops.init("workspace")
    local_memory = ops.add(workspace, "Participant-owned note.")
    store.save(workspace)
    store.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="reference-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source = ops.init("authority/source")
    memory = ops.add(source, "Retain this exact export-authorized version.")
    authority_store.save(source)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=source.name,
        attachment_name=workspace.name,
        public_name="shared/source",
        permissions=_REQUIRED,
    )
    return (
        store,
        authority_store,
        workspace,
        local_memory,
        source,
        memory,
        grant,
    )


def _qualified(memory: Memory) -> str:
    return f"shared/source:{memory.uid[:8]}"


def test_explicit_granted_memory_reference_retains_bytes_and_grant_provenance(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, workspace, _local, source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    source_before = context_record_digest(authority_store.load_direct(source.name))

    result = runner.invoke(
        app,
        ["reference", _qualified(memory), "--into", workspace.name],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "shared/source" in result.output
    assert context_record_digest(authority_store.load_direct(source.name)) == (
        source_before
    )
    target = store.load_direct(workspace.name)
    reference = tuple(
        item for item in target.iter_items() if isinstance(item, MemoryRef)
    )[0]
    assert reference.is_snapshot and reference.is_granted
    assert reference.target is not None
    assert reference.target.content == memory.content
    assert reference.target_context_uid == source.uid
    assert reference.target_context_name == "shared/source"
    assert reference.granted_source is not None
    assert reference.granted_source.grant_uid == grant.uid
    assert reference.granted_source.authority_context_name == source.name

    record = target.to_dict()["memories"][reference.uid]
    assert record["type"] == "memory_snapshot_ref"
    assert record["grant_source"] == reference.granted_source.to_dict()
    assert record["content_sha256"] == reference.snapshot_content_sha256
    [checkpoint] = store.list_checkpoints(workspace.name)
    assert checkpoint["args"]["granted_source"] == record["grant_source"]


@pytest.mark.parametrize(
    ("permissions", "missing"),
    (
        (("READ",), "DERIVE"),
        (("READ", "DERIVE"), "EXPORT"),
        (("READ", "DERIVE", "SAVE_ANALYSIS"), "EXPORT"),
        (("READ", "DERIVE", "EXPORT"), "SAVE_ANALYSIS"),
    ),
)
def test_granted_reference_requires_export_and_retained_analysis_permissions(
    isolated_store,
    tmp_path,
    monkeypatch,
    permissions,
    missing,
):
    store, _authority, workspace, _local, _source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=permissions)
    before = store.load_direct(workspace.name).to_dict()

    result = runner.invoke(
        app,
        ["reference", _qualified(memory), "--into", workspace.name],
    )

    assert result.exit_code == 1
    assert missing in result.stderr
    assert store.load_direct(workspace.name).to_dict() == before
    assert store.list_checkpoints(workspace.name) == []


def test_granted_reference_apply_revalidates_grant_and_source_snapshot(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, workspace, _local, source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=True,
    )
    request = ReferenceRequest(
        memory.uid[:8],
        "shared/source",
        workspace.name,
    )
    grant_plan = port.freeze(request)
    update_authority_grant(grant.uid, permissions=(*_REQUIRED, "COMBINE"))

    with pytest.raises(ProfileError, match="changed during this command"):
        port.apply(grant_plan)
    assert store.list_checkpoints(workspace.name) == []
    assert not any(
        isinstance(item, MemoryRef)
        for item in store.load_direct(workspace.name).iter_items()
    )

    current_grant = update_authority_grant(
        grant.uid,
        permissions=_REQUIRED,
    )[1]
    source_port = MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=True,
    )
    source_plan = source_port.freeze(request)
    changed = authority_store.load_direct(source.name)
    changed.replace(Memory(uid=memory.uid, content="Changed after freeze."))
    authority_store.save(changed)

    with pytest.raises(RuntimeError, match="changed before it could be published"):
        # The latest Grant revision is frozen in source_plan; only authority
        # bytes drift during this second Apply attempt.
        assert current_grant.uid == grant.uid
        source_port.apply(source_plan)
    assert store.list_checkpoints(workspace.name) == []


def test_granted_reference_freeze_holds_grant_through_authority_read(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, workspace, _local, source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=True,
    )
    original_load_direct = MemoryStore.load_direct
    downgrade_processes: list[subprocess.Popen[str]] = []
    authority_read_count = 0

    def load_direct_while_downgrade_waits(self, name):
        nonlocal authority_read_count
        is_authority_source = (
            self.store_dir.resolve() == authority_store.store_dir.resolve()
            and name == source.name
        )
        if is_authority_source:
            authority_read_count += 1
        if is_authority_source and not downgrade_processes:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys\n"
                        "from memcommit.application.operations.profile.model "
                        "import update_authority_grant\n"
                        "print('DOWNGRADE STARTED', flush=True)\n"
                        "update_authority_grant("
                        "sys.argv[1], permissions=('READ',))\n"
                        "print('DOWNGRADE COMPLETE', flush=True)\n"
                    ),
                    grant.uid,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            downgrade_processes.append(process)
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "DOWNGRADE STARTED"
            # The child reached the Grant update, but the Freeze still owns
            # the registry snapshot while this authority read is in flight.
            with pytest.raises(subprocess.TimeoutExpired):
                process.wait(timeout=0.5)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", load_direct_while_downgrade_waits)
    plan = port.freeze(
        ReferenceRequest(memory.uid, "shared/source", workspace.name)
    )

    [downgrade] = downgrade_processes
    stdout, stderr = downgrade.communicate(timeout=5)
    assert downgrade.returncode == 0, stderr
    assert "DOWNGRADE COMPLETE" in stdout
    assert plan.memory_content == memory.content
    assert authority_read_count == 1

    # Once the downgrade wins a later snapshot, permission rejection happens
    # before another authority Source read can disclose the bytes.
    with pytest.raises(ProfileError, match="DERIVE|EXPORT|SAVE_ANALYSIS"):
        MemoryStoreReferencePort.capture(
            store,
            allow_granted_sources=True,
        ).freeze(ReferenceRequest(memory.uid, "shared/source", workspace.name))
    assert authority_read_count == 1

    with pytest.raises(ProfileError, match="changed during this command"):
        port.apply(plan)
    assert authority_read_count == 1
    assert store.list_checkpoints(workspace.name) == []
    assert not any(
        isinstance(item, MemoryRef)
        for item in store.load_direct(workspace.name).iter_items()
    )


def test_retained_granted_reference_survives_source_edit_and_grant_revocation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority_store, workspace, _local, source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    result = runner.invoke(
        app,
        ["reference", _qualified(memory), "--into", workspace.name],
    )
    assert result.exit_code == 0, result.stderr
    reference = next(
        item
        for item in store.load_direct(workspace.name).iter_items()
        if isinstance(item, MemoryRef)
    )

    changed = authority_store.load_direct(source.name)
    changed.replace(Memory(uid=memory.uid, content="Authority changed later."))
    authority_store.save(changed)
    update_authority_grant(grant.uid, permissions=("READ",))

    retained = store.load(workspace.name).memories[reference.uid]
    assert isinstance(retained, MemoryRef)
    assert retained.is_snapshot and retained.target is not None
    assert retained.target.content == memory.content
    shown = runner.invoke(app, ["show", reference.uid[:8]])
    assert shown.exit_code == 0, shown.stderr
    assert memory.content in shown.output
    assert "Authority changed later" not in shown.output


def test_granted_reference_requires_explicit_owner_and_owned_local_target(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority, workspace, local, _source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    bare = runner.invoke(
        app,
        ["reference", memory.uid[:8], "--into", workspace.name],
    )
    whole_context = runner.invoke(
        app,
        ["reference", "shared/source", "--direct", "--into", workspace.name],
    )
    granted_target = runner.invoke(
        app,
        [
            "reference",
            f"{workspace.name}:{local.uid[:8]}",
            "--into",
            "shared/source",
        ],
    )

    assert bare.exit_code == 1
    assert "local Context" in bare.stderr
    assert whole_context.exit_code == 1
    assert "does not exist" in whole_context.stderr
    assert granted_target.exit_code == 1
    assert "does not exist locally" in granted_target.stderr
    assert store.list_checkpoints(workspace.name) == []

    explicit_from = runner.invoke(
        app,
        [
            "reference",
            memory.uid[:8],
            "--from",
            "shared/source",
            "--into",
            workspace.name,
        ],
    )
    assert explicit_from.exit_code == 0, explicit_from.stderr


def test_public_and_agent_routes_classify_grant_denial_as_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _authority, workspace, _local, _source, memory, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=("READ",))
    client = MemCommitClient()

    with pytest.raises(ReferenceAuthorityError, match="DERIVE"):
        client.reference_memory(
            memory.uid,
            source_context="shared/source",
            into_context=workspace.name,
        )

    response = ReferenceAgentAdapter(client).invoke(
        {
            "version": 2,
            "kind": "memory",
            "memory_selector": memory.uid,
            "source_context": "shared/source",
            "into_context": workspace.name,
        }
    )
    assert response["ok"] is False
    assert response["error"]["code"] == "authority_denied"


def test_explicit_root_client_does_not_inherit_active_profile_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _authority, workspace, _local, _source, memory, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    before = store.load_direct(workspace.name).to_dict()
    client = MemCommitClient(root=store.store_dir)

    with pytest.raises(ReferenceContextError, match="does not exist"):
        client.reference_memory(
            memory.uid,
            source_context="shared/source",
            into_context=workspace.name,
        )

    assert store.load_direct(workspace.name).to_dict() == before
    assert store.list_checkpoints(workspace.name) == []

    active_result = MemCommitClient().reference_memory(
        memory.uid,
        source_context="shared/source",
        into_context=workspace.name,
    )
    assert active_result.source_name == "shared/source"
