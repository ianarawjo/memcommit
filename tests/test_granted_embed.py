"""Revocable Grant-backed Context Embed behavior."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context, Memory
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.tui.operations.embed import build_embed_tui_setup
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    canonical_grant_permissions,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    ProfileError,
    create_authority_grant,
    update_authority_grant,
)
from memcommit.source_projection.presentation import source_display_text
from memcommit.store import MemoryStore


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

    setup = build_embed_tui_setup(MemoryStoreEmbedPort.capture(store))
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
