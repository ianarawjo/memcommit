"""Grant-backed exact direct Memory Embed runtime and adapter contracts."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.python_api import EmbedAuthorityError, EmbedContextError, MemCommitClient
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef
from memcommit.application.capabilities.context_snapshot import ContextSnapshotRef
from memcommit.application.capabilities.memory_issue_analysis.peer_relations.repository import comparison_analysis_path
from memcommit.application.operations.embed.application import MemoryEmbedRequest
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.agent.embed import EmbedAgentAdapter
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
    delete_authority_grant,
    update_authority_grant,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.operations.reference.application import ContextReferenceRequest
from memcommit.application.operations.reference.runtime import execute_context_reference


runner = CliRunner(mix_stderr=False)


def _fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    workspace = ops.init("workspace")
    local.save(workspace)
    local.set_current(workspace.name)

    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="advisor-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    advisor = ops.init("advisor")
    first = ops.add(advisor, "Prefer the evidence-backed proposal.")
    second = ops.add(advisor, "Keep the recommendation concise.")
    third = ops.add(advisor, "State uncertainty explicitly.")
    authority_store.save(advisor)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict(), indent=2) + "\n")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=advisor.name,
        attachment_name=workspace.name,
        public_name=advisor.name,
        permissions=("READ",),
        recursive=True,
    )
    return (
        local,
        authority_store,
        workspace,
        advisor,
        first,
        second,
        third,
        grant,
    )


@pytest.mark.parametrize("qualified", [False, True])
def test_cli_granted_memory_embed_persists_content_free_live_binding(
    isolated_store,
    tmp_path,
    monkeypatch,
    qualified,
) -> None:
    (
        store,
        authority_store,
        workspace,
        advisor,
        memory,
        _second,
        _third,
        grant,
    ) = _fixture(isolated_store, tmp_path, monkeypatch)
    source_operand = f"{advisor.name}:{memory.uid[:8]}" if qualified else memory.uid[:8]
    argv = ["embed", source_operand, "--into", workspace.name]
    if not qualified:
        argv.extend(("--from", advisor.name))

    result = runner.invoke(app, argv)

    assert result.exit_code == 0, result.output + result.stderr
    assert "Embedded Memory" in result.output
    direct = store.load_direct(workspace.name)
    link = next(iter(direct.iter_items()))
    assert isinstance(link, MemoryRef)
    record = link.to_dict()
    assert record["type"] == "granted_memory_ref"
    assert record["target_context"] == {
        "uid": advisor.uid,
        "name": advisor.name,
    }
    assert record["target_memory_uid"] == memory.uid
    assert record["grant_source"]["grant_uid"] == grant.uid
    assert memory.content not in json.dumps(record)

    resolved = store.load(workspace.name).memories[link.uid]
    assert isinstance(resolved, MemoryRef)
    assert resolved.is_granted and resolved.is_live
    assert resolved.target is not None
    assert resolved.target.content == memory.content

    changed = authority_store.load_direct(advisor.name)
    changed.replace(Memory(uid=memory.uid, content="Use the revised live guidance."))
    authority_store.save(changed)
    reloaded = store.load(workspace.name).memories[link.uid]
    assert isinstance(reloaded, MemoryRef) and reloaded.target is not None
    assert reloaded.target.content == "Use the revised live guidance."

    checkpoint = store.list_checkpoints(workspace.name)[-1]
    authority_args = checkpoint["args"]["authority_grant"]
    assert authority_args["uid"] == grant.uid
    assert authority_args["public_context"] == advisor.name


def test_granted_memory_embed_revocation_fails_closed_and_keeps_pointer(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid[:8],
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    before = store.load_direct(workspace.name).to_dict()

    update_authority_grant(grant.uid, permissions=("QUERY",))

    with pytest.raises(ProfileError, match="does not allow read access"):
        store.load(workspace.name)
    assert store.load_direct(workspace.name).to_dict() == before


def test_query_only_grant_is_denied_before_authority_memory_is_opened(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, advisor, memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=("QUERY",))

    authority_reads: list[str] = []
    original_load_direct = MemoryStore.load_direct
    authority_root = authority.store_dir.resolve()

    def track_authority_reads(self, name):
        if self.store_dir.resolve() == authority_root:
            authority_reads.append(name)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", track_authority_reads)

    denied = runner.invoke(
        app,
        [
            "embed",
            memory.uid[:8],
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )

    assert denied.exit_code == 1
    assert authority_reads == []
    assert store.load_direct(workspace.name).ordered_uids() == []
    assert store.list_checkpoints(workspace.name) == []


def test_context_embed_requires_read_before_opening_authority_record(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, advisor, _memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=("QUERY",))

    authority_reads: list[str] = []
    original_load_direct = MemoryStore.load_direct
    authority_root = authority.store_dir.resolve()

    def track_authority_reads(self, name):
        if self.store_dir.resolve() == authority_root:
            authority_reads.append(name)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", track_authority_reads)

    denied = runner.invoke(
        app,
        ["embed", advisor.name, "--into", workspace.name],
    )

    assert denied.exit_code == 1
    assert "read access" in denied.stderr
    assert authority_reads == []
    assert store.load_direct(workspace.name).ordered_uids() == []
    assert store.list_checkpoints(workspace.name) == []


def test_granted_memory_embed_rechecks_frozen_authority_source_before_publish(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, advisor, memory, *_ = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    plan = port.freeze_memory(
        MemoryEmbedRequest(memory.uid[:8], advisor.name, workspace.name)
    )
    changed = authority.load_direct(advisor.name)
    changed.replace(Memory(uid=memory.uid, content="Changed after review."))
    authority.save(changed)

    with pytest.raises(RuntimeError, match="changed before it could be published"):
        port.apply_memory(plan)
    assert store.load_direct(workspace.name).ordered_uids() == []
    assert store.list_checkpoints(workspace.name) == []


def test_granted_memory_embed_rechecks_permission_after_review(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    port = MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    plan = port.freeze_memory(
        MemoryEmbedRequest(memory.uid[:8], advisor.name, workspace.name)
    )

    update_authority_grant(grant.uid, permissions=("QUERY",))

    with pytest.raises(ProfileError, match="does not allow read access"):
        port.apply_memory(plan)
    assert store.load_direct(workspace.name).ordered_uids() == []
    assert store.list_checkpoints(workspace.name) == []


def test_public_and_agent_memory_embed_share_grant_authority_contract(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, first, second, third, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    client = MemCommitClient()

    public = client.embed_memory(
        first.uid[:8],
        source_context=advisor.name,
        into_context=workspace.name,
    )
    agent = EmbedAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "memory",
            "memory_selector": second.uid[:8],
            "source_context": advisor.name,
            "into_context": workspace.name,
        }
    )

    assert public.source_name == advisor.name
    assert agent["ok"] is True
    assert agent["result"]["source_name"] == advisor.name
    assert agent["result"]["mode"] == "LIVE"
    assert len(store.load_direct(workspace.name).ordered_uids()) == 2

    update_authority_grant(grant.uid, permissions=("QUERY",))
    with pytest.raises(EmbedAuthorityError, match="does not allow read access"):
        client.embed_memory(
            third.uid[:8],
            source_context=advisor.name,
            into_context=workspace.name,
        )
    denied = EmbedAgentAdapter(client).invoke(
        {
            "version": 1,
            "kind": "memory",
            "memory_selector": third.uid[:8],
            "source_context": advisor.name,
            "into_context": workspace.name,
        }
    )
    assert denied["ok"] is False
    assert denied["error"]["code"] == "authority_denied"
    assert len(store.load_direct(workspace.name).ordered_uids()) == 2


def test_explicit_root_client_does_not_inherit_host_profile_embed_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    client = MemCommitClient(root=store.store_dir)

    with pytest.raises(EmbedContextError, match="does not exist locally"):
        client.embed_memory(
            memory.uid[:8],
            source_context=advisor.name,
            into_context=workspace.name,
        )
    with pytest.raises(EmbedContextError, match="does not exist locally"):
        client.embed_context(advisor.name, into_context=workspace.name)

    assert store.load_direct(workspace.name).ordered_uids() == []
    assert store.list_checkpoints(workspace.name) == []


def test_active_profile_client_keeps_granted_context_embed_enabled(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    result = MemCommitClient().embed_context(
        advisor.name,
        into_context=workspace.name,
    )

    assert result.child_uid == advisor.uid
    record = store.load_direct(workspace.name).to_dict()["memories"][advisor.uid]
    assert record["type"] == "granted_context_ref"


def test_granted_memory_embed_cannot_launder_retention_through_its_local_owner(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    destination = ops.init("destination")
    store.save(destination)
    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid,
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    link = next(iter(store.load_direct(workspace.name).iter_items()))
    assert isinstance(link, MemoryRef) and link.is_granted

    copied = runner.invoke(
        app,
        ["copy", f"{workspace.name}:{link.uid}", "--into", destination.name],
    )
    referenced = runner.invoke(
        app,
        ["reference", f"{workspace.name}:{link.uid}", "--into", destination.name],
    )
    assert copied.exit_code == 1
    assert referenced.exit_code == 1
    assert "directly owned Memory" in copied.stderr
    assert "directly owned Memory" in referenced.stderr
    assert store.load_direct(destination.name).ordered_uids() == []

    # Context is the supported nesting unit, but the Embed-only edge remains
    # a content-free relationship instead of becoming a retained Memory value.
    delete_authority_grant(grant.uid)
    authority_reads: list[str] = []
    authority_root = _authority.store_dir.resolve()
    original_load_direct = MemoryStore.load_direct

    def track_authority_reads(self, name):
        if self.store_dir.resolve() == authority_root:
            authority_reads.append(name)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", track_authority_reads)
    result = execute_context_reference(
        ContextReferenceRequest(workspace.name, destination.name),
        store=store,
    )
    assert authority_reads == []
    snapshot = store.load_direct(destination.name).memories[result.reference_uid]
    assert isinstance(snapshot, ContextSnapshotRef)
    serialized = snapshot.to_dict()
    assert memory.content not in json.dumps(serialized)
    nested = next(iter(snapshot.iter_items()))
    assert isinstance(nested, MemoryRef)
    assert nested.is_granted and nested.target is None

    retained = store.load(destination.name).memories[result.reference_uid]
    assert isinstance(retained, ContextSnapshotRef)
    retained_link = next(iter(retained.iter_items()))
    assert isinstance(retained_link, MemoryRef) and retained_link.target is None


def test_compare_rejects_granted_live_embed_before_provider_connection(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    peer = ops.init("peer")
    ops.add(peer, "Local comparison claim.")
    store.save(peer)
    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid,
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search_explain.synthesize.compare.command.connect_codex_chatgpt_provider",
        lambda: pytest.fail("Compare must reject before provider connection"),
    )

    compared = runner.invoke(
        app,
        ["compare", workspace.name, peer.name, "--ledger", "--snapshot"],
    )

    assert compared.exit_code == 1
    assert "cannot use granted Memory Embed" in compared.stderr
    assert "not provider disclosure or derived work" in compared.stderr
    assert not comparison_analysis_path(
        workspace.uid,
        peer.uid,
        store=store,
    ).exists()


def test_impact_rejects_granted_live_embed_before_provider_connection(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    target = ops.init("impact-target")
    ops.add(target, "Local impact target.")
    store.save(target)
    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid,
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.semantic_updates.foundation.update.impact.connect_codex_chatgpt_provider",
        lambda: pytest.fail("Impact must reject before provider connection"),
    )

    impacted = runner.invoke(
        app,
        ["impact", "--from", workspace.name, "--to", target.name],
    )

    assert impacted.exit_code == 1
    assert "not provider disclosure or derived work" in impacted.stderr
    assert store.load_impact_plan() is None


def test_explicit_root_client_keeps_existing_granted_memory_link_opaque(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, advisor, memory, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid,
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr

    active_view = MemCommitClient().show(context_name=workspace.name)
    active_link = active_view.items[0]
    assert active_link.resolved is True
    assert active_link.content == memory.content

    authority_reads: list[str] = []
    authority_root = authority.store_dir.resolve()
    original_load_direct = MemoryStore.load_direct

    def track_authority_reads(self, name):
        if self.store_dir.resolve() == authority_root:
            authority_reads.append(name)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", track_authority_reads)
    explicit_view = MemCommitClient(root=store.store_dir).show(
        context_name=workspace.name
    )
    explicit_link = explicit_view.items[0]

    assert explicit_link.resolved is False
    assert explicit_link.content is None
    assert explicit_link.source.states == ("OPAQUE",)
    assert authority_reads == []


def test_harmless_grant_revision_keeps_exact_live_memory_binding(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, memory, *_rest, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(
        app,
        [
            "embed",
            f"{advisor.name}:{memory.uid}",
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr

    _registry, revised = update_authority_grant(
        grant.uid,
        permissions=("READ",),
    )
    assert revised.revision > grant.revision
    loaded = store.load(workspace.name)
    link = next(iter(loaded.iter_items()))
    assert isinstance(link, MemoryRef) and link.target is not None
    assert link.target.content == memory.content


def test_granted_memory_embed_restoration_receipts_stay_opaque_not_dangling(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, advisor, memory, *_rest = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    baseline = runner.invoke(app, ["add", "Local restoration baseline."])
    assert baseline.exit_code == 0, baseline.output + baseline.stderr
    baseline_checkpoint = store.list_checkpoints(workspace.name)[-1]["uid"]

    embedded = runner.invoke(
        app,
        [
            "embed",
            memory.uid,
            "--from",
            advisor.name,
            "--into",
            workspace.name,
        ],
    )
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    link = next(
        item
        for item in store.load_direct(workspace.name).iter_items()
        if isinstance(item, MemoryRef)
    )

    authority_reads: list[str] = []
    authority_root = authority.store_dir.resolve()
    original_load_direct = MemoryStore.load_direct

    def track_authority_reads(self, name):
        if self.store_dir.resolve() == authority_root:
            authority_reads.append(name)
        return original_load_direct(self, name)

    monkeypatch.setattr(MemoryStore, "load_direct", track_authority_reads)

    undone = runner.invoke(app, ["undo"])
    redone = runner.invoke(app, ["redo"])
    reverted = runner.invoke(app, ["revert", baseline_checkpoint[:8]])

    assert undone.exit_code == 0, undone.output + undone.stderr
    assert "Undid command: mem embed" in undone.output
    assert "1 Memory ref removed" in undone.output
    assert redone.exit_code == 0, redone.output + redone.stderr
    assert "Redid command: mem embed" in redone.output
    assert "1 Memory ref added" in redone.output
    assert reverted.exit_code == 0, reverted.output + reverted.stderr
    assert f"{advisor.name}:{memory.uid[:8]}" in reverted.output
    assert "GRANT · READ ONLY · OPAQUE" in reverted.output
    assert "DANGLING" not in undone.output + redone.output + reverted.output
    assert memory.content not in undone.output + redone.output + reverted.output
    assert link.uid[:8] in reverted.output
    assert authority_reads == []
