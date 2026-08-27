"""Revocable Grant-backed Context Embed behavior."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
from memcommit.application.authority.access import GrantedReadStore, resolve_context_access
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Context, Memory
from memcommit.application.retained_history.context_snapshot import ContextSnapshotRef
from memcommit.application.operations.embed.runtime import MemoryStoreEmbedPort
from memcommit.adapters.interfaces.tui.operations.embed import build_embed_tui_setup
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    canonical_grant_permissions,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    create_authority_grant,
    delete_authority_grant,
    update_authority_grant,
)
from memcommit.application.operations.reference.application import ContextReferenceRequest
from memcommit.application.operations.reference.runtime import execute_context_reference
from memcommit.source_projection.presentation import source_display_text
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    workspace = ops.init("workspace")
    ops.add(workspace, "Owned proposal draft.")
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
    advice = ops.add(advisor, "Prefer the evidence-backed proposal.")
    private = ops.init("advisor/private")
    ops.add(private, "Concealed review note.")
    ops.embed(private, advisor)
    authority_store.save(private)
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
        permissions=("READ", "EMBED"),
        recursive=True,
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=private.name,
        attachment_name=workspace.name,
        public_name=private.name,
        permissions=("QUERY",),
        recursive=True,
    )
    return local, authority_store, workspace, advisor, advice, grant


def _granted_record(store: MemoryStore, target_name: str, child_uid: str):
    return store.load_direct(target_name).to_dict()["memories"][child_uid]


def test_embed_permission_requires_read() -> None:
    with pytest.raises(ProfileConfigError, match="EMBED requires READ"):
        canonical_grant_permissions(("EMBED",))

    assert canonical_grant_permissions(("EMBED", "READ")) == (
        "READ",
        "EMBED",
    )


def test_granted_embed_persists_only_a_live_reauthorizing_link(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority_store, workspace, advisor, advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    result = runner.invoke(app, ["embed", "advisor", "--into", "workspace"])

    assert result.exit_code == 0, result.stderr or result.output
    record = _granted_record(store, workspace.name, advisor.uid)
    assert record["type"] == "granted_context_ref"
    assert record["name"] == "advisor"
    assert record["authority_context_name"] == "advisor"
    assert advice.content not in json.dumps(record)
    resolved = store.load(workspace.name).memories[advisor.uid]
    assert isinstance(resolved, Context)
    assert [
        item.content for item in resolved.iter_items() if isinstance(item, Memory)
    ] == [advice.content]

    changed = authority_store.load_direct(advisor.name)
    changed_advice = changed.memories[advice.uid]
    assert isinstance(changed_advice, Memory)
    changed_advice.content = "Use the revised live advisor guidance."
    authority_store.save(changed)

    reloaded = store.load(workspace.name).memories[advisor.uid]
    assert isinstance(reloaded, Context)
    assert [
        item.content for item in reloaded.iter_items() if isinstance(item, Memory)
    ] == ["Use the revised live advisor guidance."]


def test_context_reference_keeps_revoked_granted_context_edge_opaque(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority_store, workspace, advisor, advice, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    destination = ops.init("destination")
    store.save(destination)
    embedded = runner.invoke(app, ["embed", advisor.name, "--into", workspace.name])
    assert embedded.exit_code == 0, embedded.output + embedded.stderr
    delete_authority_grant(grant.uid)

    authority_reads: list[str] = []
    authority_root = authority_store.store_dir.resolve()
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
    [record] = snapshot.snapshot_package["contexts"]
    opaque = record["memories"][advisor.uid]
    assert opaque["type"] == "granted_context_ref"
    assert advice.content not in json.dumps(snapshot.to_dict())
    retained_edge = snapshot.memories[advisor.uid]
    assert isinstance(retained_edge, Context)
    assert retained_edge._granted_link is not None
    assert tuple(retained_edge.iter_items()) == ()


def test_recursive_list_and_show_open_attached_read_projection(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, _advisor, advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    direct_list = runner.invoke(app, ["list", "--direct", workspace.name])
    recursive_list = runner.invoke(
        app,
        ["list", "--recursive", workspace.name],
    )
    recursive_show = runner.invoke(
        app,
        ["show", "--recursive", "--context", workspace.name],
    )
    mixed_copy = runner.invoke(
        app,
        ["list", "--recursive", "--copy", workspace.name],
    )

    assert direct_list.exit_code == 0, direct_list.output + direct_list.stderr
    assert advice.content not in direct_list.output
    assert recursive_list.exit_code == 0, recursive_list.output + recursive_list.stderr
    assert advice.content in recursive_list.output
    assert recursive_show.exit_code == 0, recursive_show.output + recursive_show.stderr
    assert "Contexts 2" in recursive_show.output
    assert "Context: advisor" in recursive_show.output
    assert advice.content in recursive_show.output
    assert "advisor/private" in recursive_show.output
    assert "Concealed review note." not in recursive_list.output
    assert "Concealed review note." not in recursive_show.output
    assert mixed_copy.exit_code == 1
    assert "mixed local and granted recursive list" in mixed_copy.stderr
    assert _advisor.uid not in store.load_direct(workspace.name).memories


def test_live_context_embed_does_not_cross_nested_read_only_override(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority_store, workspace, advisor, advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    nested_grant = next(
        grant
        for grant in load_profile_registry().grants
        if grant.public_name == "advisor/private"
    )
    update_authority_grant(nested_grant.uid, permissions=("READ",))

    # Ordinary granted browsing is still allowed to follow the narrower READ
    # override and see its contents.
    read_access = resolve_context_access(
        store,
        advisor.name,
        current_name=workspace.name,
        required_permission="READ",
    )
    readable = GrantedReadStore(read_access).load(advisor.name)
    authority_parent = authority_store.load_direct(advisor.name)
    private_pointer = next(
        item for item in authority_parent.iter_items() if isinstance(item, Context)
    )
    readable_private = readable.memories[private_pointer.uid]
    assert isinstance(readable_private, Context)
    assert [
        item.content
        for item in readable_private.iter_items()
        if isinstance(item, Memory)
    ] == ["Concealed review note."]

    embedded = runner.invoke(app, ["embed", advisor.name, "--into", workspace.name])
    assert embedded.exit_code == 0, embedded.output + embedded.stderr

    # Loading the durable live Embed uses the stricter traversal mode. The
    # parent remains readable, but its READ-only nested edge cannot inherit the
    # parent's EMBED permission.
    resolved = store.load(workspace.name).memories[advisor.uid]
    assert isinstance(resolved, Context)
    assert private_pointer.uid not in resolved.memories
    assert [
        item.content for item in resolved.iter_items() if isinstance(item, Memory)
    ] == [advice.content]


def test_recursive_find_and_search_open_attached_read_projection(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, authority, workspace, _advisor, advice, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(
        grant.uid,
        permissions=("READ", "EMBED", "DERIVE", "COMBINE"),
    )
    unrelated_workspace = ops.init("unrelated-workspace")
    store.save(unrelated_workspace)
    unrelated_advisor = ops.init("unrelated-advisor")
    ops.add(unrelated_advisor, "Unrelated authority-only review secret.")
    authority.save(unrelated_advisor)
    create_authority_grant(
        authority_name="advisor-authority",
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=unrelated_advisor.name,
        attachment_name=unrelated_workspace.name,
        public_name=unrelated_advisor.name,
        permissions=("READ", "EMBED", "DERIVE", "COMBINE"),
        recursive=True,
    )

    literal_direct = runner.invoke(
        app,
        ["find", "evidence-backed", "--direct", "--context", workspace.name],
    )
    literal_recursive = runner.invoke(
        app,
        ["find", "evidence-backed", "--recursive", "--context", workspace.name],
    )

    class Provider:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "search"
            payload = json.loads(prompt.split("FIND PAYLOAD:\n", 1)[1])
            self.payloads.append(payload)
            matches = [
                {"candidate_id": candidate["candidate_id"]}
                for candidate in payload["candidates"]
                if "evidence-backed" in candidate.get("content", "")
            ]
            return json.dumps(
                {
                    "matches": matches,
                    "related_query": "",
                    "related_matches": [],
                }
            )

    provider = Provider()
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.search.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    semantic_direct = runner.invoke(
        app,
        [
            "search",
            "evidence-backed",
            "--direct",
            "--context",
            workspace.name,
        ],
    )
    semantic_recursive = runner.invoke(
        app,
        [
            "search",
            "evidence-backed",
            "--recursive",
            "--context",
            workspace.name,
        ],
    )

    assert literal_direct.exit_code == 0, literal_direct.output
    assert "MATCHED 0" in literal_direct.output
    assert literal_recursive.exit_code == 0, literal_recursive.output
    assert advice.content in literal_recursive.output
    assert semantic_direct.exit_code == 0, (
        semantic_direct.output + semantic_direct.stderr
    )
    assert advice.content not in semantic_direct.output
    assert semantic_recursive.exit_code == 0, (
        semantic_recursive.output + semantic_recursive.stderr
    )
    assert advice.content in semantic_recursive.output
    assert len(provider.payloads) == 2
    direct_payload_text = json.dumps(provider.payloads[0])
    payload_text = json.dumps(provider.payloads[1])
    assert advice.content not in direct_payload_text
    assert advice.content in payload_text
    assert "Concealed review note." not in payload_text
    assert "Unrelated authority-only review secret." not in payload_text


def test_granted_embed_revocation_fails_recursive_load_but_keeps_pointer(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, _advice, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(app, ["embed", "advisor", "--into", "workspace"])
    assert embedded.exit_code == 0, embedded.stderr
    before = _granted_record(store, workspace.name, advisor.uid)

    update_authority_grant(grant.uid, permissions=("READ",))

    with pytest.raises(ProfileError, match="does not allow embed access"):
        store.load(workspace.name)
    after = _granted_record(store, workspace.name, advisor.uid)
    assert after == before
    assert after["type"] == "granted_context_ref"

    # Direct target edits may proceed from the opaque record, but must never
    # erase or rewrite a revoked link as a partial recursive load.
    added = runner.invoke(app, ["add", "Local note after revocation."])
    assert added.exit_code == 0, added.stderr
    assert _granted_record(store, workspace.name, advisor.uid) == before


def test_granted_embed_survives_a_revision_that_retains_same_binding(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, advice, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(app, ["embed", "advisor", "--into", "workspace"])
    assert embedded.exit_code == 0, embedded.stderr

    _registry, revised = update_authority_grant(
        grant.uid,
        permissions=("READ", "EMBED", "DERIVE"),
    )

    assert revised.revision == grant.revision + 1
    resolved = store.load(workspace.name).memories[advisor.uid]
    assert isinstance(resolved, Context)
    assert [
        item.content for item in resolved.iter_items() if isinstance(item, Memory)
    ] == [advice.content]


def test_granted_embed_rejects_missing_permission_query_override_and_granted_target(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, _advice, grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(grant.uid, permissions=("READ",))

    denied = runner.invoke(app, ["embed", "advisor", "--into", "workspace"])
    concealed = runner.invoke(
        app,
        ["embed", "advisor/private", "--into", "workspace"],
    )
    granted_target = runner.invoke(
        app,
        ["embed", "workspace", "--into", "advisor"],
    )

    assert denied.exit_code == 1
    assert "does not allow embed access" in denied.stderr
    assert concealed.exit_code == 1
    assert "does not allow embed access" in concealed.stderr
    assert granted_target.exit_code == 1
    assert "does not exist locally" in granted_target.stderr
    assert advisor.uid not in store.load_direct(workspace.name).memories


def test_missing_context_embed_child_is_not_reported_as_a_granted_view(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, _advisor, _advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    before = store.load_direct(workspace.name).ordered_uids()

    result = runner.invoke(
        app,
        ["embed", "missing-child", "--into", workspace.name],
    )

    assert result.exit_code == 1
    assert "Context 'missing-child' does not exist" in result.stderr
    assert "Granted view" not in result.stderr
    assert store.load_direct(workspace.name).ordered_uids() == before


def test_granted_embed_tui_catalog_exposes_authority_without_broadening_target(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, _advisor, _advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    setup = build_embed_tui_setup(
        MemoryStoreEmbedPort.capture(store, allow_granted_sources=True)
    )
    annotations = dict(setup.child_annotations)

    assert "advisor" in setup.child_names
    assert "advisor" in setup.child_selectable_names
    assert "advisor/private" in setup.child_names
    assert "advisor/private" not in setup.child_selectable_names
    assert setup.into_names == (workspace.name,)
    assert "EMBED" in source_display_text(annotations["advisor"])


def test_granted_embed_undo_and_redo_restore_the_typed_link(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    store, _authority, workspace, advisor, _advice, _grant = _fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    embedded = runner.invoke(app, ["embed", "advisor", "--into", "workspace"])
    assert embedded.exit_code == 0, embedded.stderr

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.stderr
    assert advisor.uid not in store.load_direct(workspace.name).memories

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.stderr
    assert _granted_record(store, workspace.name, advisor.uid)["type"] == (
        "granted_context_ref"
    )
