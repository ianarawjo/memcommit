"""Receiver-owned Grant placements keep naming separate from authority."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.application.context_access.access import (
    GrantedReadStore,
    granted_context_link,
    load_granted_context_link,
    resolve_context_access,
)
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    PROFILE_REGISTRY_SCHEMA_VERSION,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    create_authority_grant,
    grant_placement,
)
from memcommit.application.operations.rename.application import RenameRequest
from memcommit.application.operations.rename.runtime import (
    execute_rename,
    prepare_rename,
)
from memcommit.core.context import GrantedContextLink
from memcommit.persistence.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _profile_fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="alice",
        kind="MANAGED",
    )

    grantee_store = MemoryStore()
    home = ops.init("home")
    grantee_store.save(home)
    grantee_store.set_current(home.name)

    authority_store = MemoryStore(root=profile_store_dir(authority))
    wiki = ops.init("wiki")
    ops.add(wiki, "Authority note.")
    private = ops.init("wiki/private")
    ops.add(private, "Private authority note.")
    authority_store.save(wiki)
    authority_store.save(private)
    authority_store.set_current(wiki.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")
    return grantee_store, authority, wiki, private


def test_grant_creation_uses_receiver_owned_default_placement(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority, wiki, _private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=wiki.name,
        permissions=("READ",),
    )

    placement = grant_placement(registry, grant)
    assert placement.access_name == "granted/alice/wiki"
    assert not hasattr(grant, "public_name")
    assert not hasattr(grant, "attachment_context_name")
    access = resolve_context_access(
        store,
        placement.access_name,
        current_name="home",
        required_permission="READ",
    )
    assert access.access_name == placement.access_name
    assert access.context_name == wiki.name
    assert access.view is not None
    assert access.view.placement == placement
    assert [
        memory.content
        for memory in GrantedReadStore(access)
        .load_direct(placement.access_name)
        .memories.values()
    ] == ["Authority note."]

    persisted = json.loads(profile_registry_file().read_text(encoding="utf-8"))
    assert persisted["schema_version"] == PROFILE_REGISTRY_SCHEMA_VERSION
    assert persisted["grant_placements"] == [placement.to_dict()]


def test_profile_grant_create_cli_does_not_ask_sender_for_receiver_location(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, authority, wiki, _private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    created = runner.invoke(
        app,
        [
            "profile",
            "grant",
            "create",
            authority.name,
            AUTHORING_PROFILE_NAME,
            wiki.name,
            "--allow",
            "READ",
        ],
    )

    assert created.exit_code == 0, created.output + created.stderr
    registry = load_profile_registry()
    [grant] = registry.grants
    assert grant_placement(registry, grant).access_name == "granted/alice/wiki"
    help_result = runner.invoke(app, ["profile", "grant", "create", "--help"])
    assert help_result.exit_code == 0, help_result.output + help_result.stderr
    assert "--into" not in help_result.output
    assert "--as" not in help_result.output


def test_mem_rename_moves_a_placement_subtree_without_changing_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority, wiki, private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    registry, parent = create_authority_grant(
        authority_name=authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=wiki.name,
        permissions=("READ",),
        recursive=True,
    )
    registry, child = create_authority_grant(
        authority_name=authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=private.name,
        permissions=("QUERY",),
    )
    old_name = grant_placement(registry, parent).access_name

    plan = prepare_rename(
        store,
        RenameRequest(
            old_locator=old_name,
            new_name="projects/wiki",
            current_context_name="home",
        ),
    )
    result = execute_rename(store, plan)

    assert plan.subject == "GRANT_PLACEMENT"
    assert result.renamed_placement_count == 2
    current = load_profile_registry()
    assert grant_placement(current, parent).access_name == "projects/wiki"
    assert grant_placement(current, child).access_name == "projects/wiki/private"
    assert next(item for item in current.grants if item.uid == parent.uid) == parent
    assert next(item for item in current.grants if item.uid == child.uid) == child
    with pytest.raises(FileNotFoundError):
        resolve_context_access(
            store,
            old_name,
            current_name="home",
            required_permission="READ",
        )
    moved = resolve_context_access(
        store,
        "projects/wiki",
        current_name="home",
        required_permission="READ",
    )
    assert moved.view is not None and moved.view.grant.uid == parent.uid


def test_mem_rename_presents_a_granted_context_access_without_mount_vocabulary(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, authority, wiki, _private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=wiki.name,
        permissions=("READ",),
    )
    old_name = grant_placement(registry, grant).access_name

    renamed = runner.invoke(
        app,
        ["rename", old_name, "projects/wiki", "--force"],
    )

    assert renamed.exit_code == 0, renamed.output + renamed.stderr
    assert "Renamed granted Context access" in renamed.output
    assert "mount" not in renamed.output.casefold()
    current = load_profile_registry()
    assert grant_placement(current, grant).access_name == "projects/wiki"

    contexts = runner.invoke(app, ["contexts"])
    assert contexts.exit_code == 0, contexts.output + contexts.stderr
    assert "projects/wiki" in contexts.output
    assert old_name not in contexts.output


def test_live_granted_context_link_follows_the_same_grant_after_access_rename(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, authority, wiki, _private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=AUTHORING_PROFILE_NAME,
        resource_name=wiki.name,
        permissions=("READ",),
    )
    original_name = grant_placement(registry, grant).access_name
    access = resolve_context_access(
        store,
        original_name,
        current_name="home",
        required_permission="READ",
    )
    link = granted_context_link(access, context_uid=wiki.uid)
    plan = prepare_rename(
        store,
        RenameRequest(
            old_locator=original_name,
            new_name="projects/wiki",
            current_context_name="home",
        ),
    )
    execute_rename(store, plan)

    restored = load_granted_context_link(link, active_store=store)

    assert link.access_name == original_name
    assert restored.name == "projects/wiki"
    assert restored.uid == wiki.uid
    assert restored._granted_link is not None
    assert restored._granted_link.access_name == "projects/wiki"


def test_legacy_attached_grant_registry_is_rejected_without_runtime_compatibility(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, authority, wiki, _private = _profile_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    path = profile_registry_file()
    value = json.loads(path.read_text(encoding="utf-8"))
    value["schema_version"] = 4
    value.pop("grant_placements")
    value["grants"] = [
        {
            "uid": str(uuid.uuid4()),
            "revision": 1,
            "authority_profile_uid": authority.uid,
            "grantee_profile_uid": AUTHORING_PROFILE_UID,
            "attachment_context_uid": str(uuid.uuid4()),
            "attachment_context_name": "home",
            "resource_kind": "CONTEXT_TREE",
            "resource_uid": wiki.uid,
            "resource_name": wiki.name,
            "public_name": wiki.name,
            "permissions": ["READ"],
            "contexts": [{"uid": wiki.uid, "name": wiki.name}],
            "checkpoint_reads": [],
        }
    ]
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ProfileConfigError, match="Legacy attached Grants"):
        load_profile_registry()


def test_legacy_attached_granted_link_is_rejected_without_compatibility() -> None:
    legacy = {
        "type": "granted_context_ref",
        "uid": str(uuid.uuid4()),
        "name": "shared/wiki",
        "authority_context_name": "wiki",
        "authority_profile_uid": str(uuid.uuid4()),
        "grantee_profile_uid": str(uuid.uuid4()),
        "attachment_context_uid": str(uuid.uuid4()),
        "attachment_context_name": "home",
        "grant_uid": str(uuid.uuid4()),
        "grant_revision_at_creation": 1,
        "resource_uid": str(uuid.uuid4()),
        "resource_name": "wiki",
    }

    with pytest.raises(ValueError, match="fields are invalid"):
        GrantedContextLink.from_dict(legacy)
