"""Read-only directional impact planning against a granted target."""

from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Context
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    create_authority_grant,
    delete_authority_grant,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
DETAIL_SECRET = "Concealed construction sequence must not enter impact planning."


def _setup_granted_target(
    isolated_store,
    tmp_path,
    monkeypatch,
    *,
    parent_permissions=("READ", "CREATE", "UPDATE", "DELETE", "QUERY"),
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    source = ops.init("task-root")
    ops.add(source, "Verified update: the public service desk moved east.")
    active_store.save(source)
    active_store.set_current(source.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="run-granted-memory",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    wiki = ops.init("campus-wiki")
    ops.add(wiki, "The public service desk is in the west lobby.")
    public_child = ops.init("campus-wiki/services")
    ops.add(public_child, "The service desk is open on weekdays.")
    details = ops.init("campus-wiki/construction-details")
    ops.add(details, DETAIL_SECRET)
    wiki.add(Context(uid=public_child.uid, name=public_child.name))
    wiki.add(Context(uid=details.uid, name=details.name))
    authority_store.save(public_child)
    authority_store.save(details)
    authority_store.save(wiki)
    authority_store.set_current(wiki.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, parent_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=wiki.name,
        attachment_name=source.name,
        public_name="campus-wiki",
        permissions=parent_permissions,
        recursive=True,
    )
    create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=details.name,
        attachment_name=source.name,
        public_name="campus-wiki/construction-details",
        permissions=("QUERY", "SESSION_LOG"),
        recursive=True,
    )
    return active_store, authority_store, source, wiki, parent_grant


def _empty_plan() -> str:
    return json.dumps({"edits": [], "additions": [], "removals": []})


def test_granted_impact_projects_only_readable_target_scope(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, _source, wiki, parent_grant = (
        _setup_granted_target(isolated_store, tmp_path, monkeypatch)
    )
    prompts: list[str] = []

    class Provider:
        def complete(self, prompt, **_kwargs):
            prompts.append(prompt)
            return _empty_plan()

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    result = runner.invoke(
        app,
        ["impact", "--from", "task-root", "--to", "campus-wiki"],
    )

    assert result.exit_code == 0, result.output
    assert len(prompts) == 1
    assert "The public service desk is in the west lobby." in prompts[0]
    assert "The service desk is open on weekdays." in prompts[0]
    assert DETAIL_SECRET not in prompts[0]
    session = active_store.load_impact_plan()
    assert session is not None
    assert session.to_dict()["schema_version"] == 4
    assert session.granted_target is not None
    assert session.granted_target.grant_uid == parent_grant.uid
    assert session.granted_target.permissions == (
        "CREATE",
        "READ",
        "UPDATE",
        "DELETE",
        "QUERY",
    )
    assert {context.name for context in session.target_contexts} == {
        "campus-wiki",
        "campus-wiki/services",
    }
    assert "GRANTED TARGET · campus-wiki" in result.output
    assert "REQUIRED TO APPLY · READ" in result.output
    assert "GRANT PERMISSIONS · READY" in result.output
    assert authority_store.load_direct(wiki.name).to_dict() == wiki.to_dict()


def test_granted_impact_revocation_during_provider_turn_discards_preview(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, _authority_store, _source, _wiki, parent_grant = (
        _setup_granted_target(isolated_store, tmp_path, monkeypatch)
    )

    class Provider:
        def complete(self, *_args, **_kwargs):
            delete_authority_grant(parent_grant.uid)
            return _empty_plan()

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )

    result = runner.invoke(
        app,
        ["impact", "--from", "task-root", "--to", "campus-wiki"],
    )

    assert result.exit_code == 1
    assert "no preview was saved" in result.stderr or "does not exist" in result.stderr
    assert active_store.load_impact_plan() is None


def test_granted_impact_query_only_target_fails_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _setup_granted_target(isolated_store, tmp_path, monkeypatch)
    connections = 0

    def connect():
        nonlocal connections
        connections += 1
        raise AssertionError("provider must not connect")

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        connect,
    )

    result = runner.invoke(
        app,
        [
            "impact",
            "--from",
            "task-root",
            "--to",
            "campus-wiki/construction-details",
        ],
    )

    assert result.exit_code == 1
    assert "does not allow read access" in result.stderr
    assert connections == 0
