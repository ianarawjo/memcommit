"""Read-only directional impact planning against a granted target."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Context
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
    authority_name="run-granted-memory",
    authority_source=None,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    source = ops.init("task-root")
    ops.add(source, "Verified update: the public service desk moved east.")
    active_store.save(source)
    active_store.set_current(source.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=authority_name,
        kind="MANAGED",
        source=authority_source,
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


def _edit_and_add_plan(prompt: str) -> str:
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = next(
        item
        for item in payload["target"]["memories"]
        if "west lobby" in item["content"]
    )
    services = next(
        item
        for item in payload["target"]["contexts"]
        if item["name"].endswith("/services")
    )
    return json.dumps(
        {
            "edits": [
                {
                    "target_id": target["target_id"],
                    "new_content": "The public service desk is in the east lobby.",
                    "source_ids": [source_id],
                    "reason": "The verified move supersedes the west-lobby location.",
                }
            ],
            "additions": [
                {
                    "target_context_id": services["context_id"],
                    "new_content": "Visitors should follow signs to the east lobby.",
                    "source_ids": [source_id],
                    "reason": "The relocated desk needs visitor guidance.",
                }
            ],
            "removals": [],
        }
    )


def _removal_plan(prompt: str) -> str:
    payload = json.loads(prompt.split("UPDATE PAYLOAD:\n", 1)[1])
    source_id = payload["source"]["memories"][0]["source_id"]
    target = next(
        item
        for item in payload["target"]["memories"]
        if "west lobby" in item["content"]
    )
    return json.dumps(
        {
            "edits": [],
            "additions": [],
            "removals": [
                {
                    "target_id": target["target_id"],
                    "source_ids": [source_id],
                    "reason": "The verified move makes the standalone old location obsolete.",
                }
            ],
        }
    )
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


def test_switch_to_read_grant_makes_it_current_without_materializing_copy(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ",),
    )
    assert active.current_context_name() == source.name
    assert not active.context_exists(wiki.name)

    switched = runner.invoke(app, ["switch", wiki.name])
    listed = runner.invoke(app, ["ls"])
    status = runner.invoke(app, ["status"])
    contexts = runner.invoke(app, ["contexts"])
    profile_current = runner.invoke(app, ["profile", "current"])
    switched_child = runner.invoke(app, ["switch", "campus-wiki/services"])
    switched_parent = runner.invoke(app, ["switch", ".."])
    blocked_add = runner.invoke(app, ["add", "must not persist"])
    blocked_query_switch = runner.invoke(
        app,
        ["switch", "campus-wiki/construction-details"],
    )

    assert switched.exit_code == 0, switched.output
    assert "Switched to context 'campus-wiki'" in switched.output
    assert active.current_context_name() == wiki.name
    assert not active.context_exists(wiki.name)
    assert listed.exit_code == 0, listed.output
    assert "The public service desk is in the west lobby." in listed.output
    assert status.exit_code == 0, status.output
    assert "On context: campus-wiki" in status.output
    assert "Granted view: read only" in status.output
    assert contexts.exit_code == 0, contexts.output
    assert "* campus-wiki  [grant READ]" in contexts.output
    assert profile_current.exit_code == 0, profile_current.output
    assert "Current Context: campus-wiki" in profile_current.output
    assert switched_child.exit_code == 0, switched_child.output
    assert switched_parent.exit_code == 0, switched_parent.output
    assert active.current_context_name() == wiki.name
    assert blocked_add.exit_code == 1
    assert "does not allow create access" in blocked_add.stderr
    assert blocked_query_switch.exit_code == 1
    assert "does not allow read access" in blocked_query_switch.stderr
    assert authority.load_direct(wiki.name).name == wiki.name


def test_granted_impact_then_update_changes_only_run_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    source_before = active_store.load_direct(source.name).to_dict()
    details_before = authority_store.load_direct(
        "campus-wiki/construction-details"
    ).to_dict()
    provider_calls = 0

    class Provider:
        def complete(self, prompt, **_kwargs):
            nonlocal provider_calls
            provider_calls += 1
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    monkeypatch.setattr(
        "memcommit.commands.update.connect_codex_chatgpt_provider",
        lambda: pytest.fail("the matching impact plan must be reused"),
    )

    impact = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )
    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )
    repeated = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert impact.exit_code == 0, impact.output
    assert update.exit_code == 0, update.output
    assert repeated.exit_code == 0, repeated.output
    assert "Updated granted authority target campus-wiki" in update.output
    assert "already applied locally" in repeated.output
    assert provider_calls == 1
    assert active_store.load_direct(source.name).to_dict() == source_before
    assert authority_store.load_direct(
        "campus-wiki/construction-details"
    ).to_dict() == details_before
    authority_root = authority_store.load_direct(wiki.name)
    assert any(
        getattr(item, "content", "")
        == "The public service desk is in the east lobby."
        for item in authority_root.iter_items()
    )
    authority_services = authority_store.load_direct("campus-wiki/services")
    assert any(
        getattr(item, "content", "")
        == "Visitors should follow signs to the east lobby."
        for item in authority_services.iter_items()
    )
    applied = active_store.load_staged_update()
    assert applied.status == "applied"
    assert applied.granted_target is not None
    assert len(applied.application.checkpoints) == 2
    assert len(authority_store.list_checkpoints(wiki.name)) == 1
    assert len(authority_store.list_checkpoints("campus-wiki/services")) == 1


def test_granted_diff_revalidates_authority_and_keeps_public_names(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, _authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0

    result = runner.invoke(app, ["diff", "--stat"])

    assert result.exit_code == 0, result.output
    assert "Applied granted update" in result.stdout
    assert "task-root → campus-wiki" in result.stdout
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "STALE" not in result.stderr
    assert "REVOKED" not in result.stderr


def test_granted_diff_remains_inspectable_after_revocation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, _authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    delete_authority_grant(grant.uid)

    result = runner.invoke(app, ["diff", "--stat"])

    assert result.exit_code == 1
    assert "Applied granted update" in result.stdout
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "REVOKED" in result.stderr
    assert "remains inspectable" in result.stderr


def test_granted_diff_marks_authority_drift_stale_but_keeps_receipts(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    changed = authority.load_direct(wiki.name)
    ops.add(changed, "A later authority correction.")
    authority.save(changed)

    result = runner.invoke(app, ["diff", "--verbose", "--stat"])

    assert result.exit_code == 1
    assert "STALE" in result.stderr
    assert "2 changes · 1 edited · 1 added" in result.stdout
    assert "Checkpoint  campus-wiki" in result.stdout
    assert "Checkpoint  campus-wiki/services" in result.stdout


def test_revoked_granted_update_cannot_be_undone_by_participant(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    authority_after = {
        name: authority.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }
    delete_authority_grant(grant.uid)

    result = runner.invoke(app, ["undo"])

    assert result.exit_code == 1
    assert "Undo error" in result.stderr
    assert {
        name: authority.load_direct(name).to_dict()
        for name in authority_after
    } == authority_after


def test_granted_undo_does_not_substitute_newer_authority_command(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    later = authority.load_direct(wiki.name)
    ops.add(later, "A later independent authority command.")
    authority.save(
        later,
        AutoCheckpoint(
            command="add",
            args={},
            description="Later authority addition.",
        ),
    )
    authority_before_undo = authority.load_direct(wiki.name).to_dict()

    result = runner.invoke(app, ["undo"])

    assert result.exit_code == 1
    assert "not the next Context command to undo" in result.stderr
    assert authority.load_direct(wiki.name).to_dict() == authority_before_undo


def test_granted_update_undo_and_redo_restore_exact_authority_unit(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, authority, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    root_before = authority.load_direct(wiki.name).to_dict()
    services_before = authority.load_direct("campus-wiki/services").to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    root_after = authority.load_direct(wiki.name).to_dict()
    services_after = authority.load_direct("campus-wiki/services").to_dict()

    undone = runner.invoke(app, ["undo"])

    assert undone.exit_code == 0, undone.output
    assert "Undid command: mem update" in undone.stdout
    assert "Affected Context: campus-wiki" in undone.stdout
    assert authority.load_direct(wiki.name).to_dict() == root_before
    assert (
        authority.load_direct("campus-wiki/services").to_dict()
        == services_before
    )

    redone = runner.invoke(app, ["redo"])

    assert redone.exit_code == 0, redone.output
    assert "Redid command: mem update" in redone.stdout
    assert "Affected Context: campus-wiki/services" in redone.stdout
    assert authority.load_direct(wiki.name).to_dict() == root_after
    assert (
        authority.load_direct("campus-wiki/services").to_dict()
        == services_after
    )


def test_granted_update_checks_create_permission_before_first_write(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "UPDATE", "DELETE", "QUERY"),
    )
    authority_before = {
        name: authority_store.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 1
    assert "does not contain every permission" in update.stderr
    assert {
        name: authority_store.load_direct(name).to_dict()
        for name in authority_before
    } == authority_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert authority_store.list_checkpoints("campus-wiki/services") == []
    assert active_store.load_staged_update().status == "staged"


def test_granted_update_requires_explicit_delete_for_removal(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        parent_permissions=("READ", "CREATE", "UPDATE", "QUERY"),
    )
    root_before = authority_store.load_direct(wiki.name).to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _removal_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    impact = runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    )
    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert impact.exit_code == 0, impact.output
    assert "REQUIRED TO APPLY · READ + DELETE" in impact.output
    assert "GRANT PERMISSIONS · BLOCKED" in impact.output
    assert update.exit_code == 1
    assert "does not contain every permission" in update.stderr
    assert authority_store.load_direct(wiki.name).to_dict() == root_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert active_store.load_staged_update().status == "staged"


def test_granted_update_rejects_fixed_study_baseline_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
        authority_name="study-baseline",
        authority_source={"kind": "STUDY_BASELINE", "schema_version": 1},
    )
    root_before = authority_store.load_direct(wiki.name).to_dict()

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 1
    assert "study-baseline Profile cannot be updated" in update.stderr
    assert authority_store.load_direct(wiki.name).to_dict() == root_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert active_store.load_staged_update().status == "staged"


def test_granted_multi_owner_write_failure_rolls_back_authority(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active_store, authority_store, source, wiki, _grant = _setup_granted_target(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    class Provider:
        def complete(self, prompt, **_kwargs):
            return _edit_and_add_plan(prompt)

    monkeypatch.setattr(
        "memcommit.commands.impact.connect_codex_chatgpt_provider",
        lambda: Provider(),
    )
    assert runner.invoke(
        app,
        ["impact", "--from", source.name, "--to", wiki.name],
    ).exit_code == 0
    authority_before = {
        name: authority_store.load_direct(name).to_dict()
        for name in (wiki.name, "campus-wiki/services")
    }
    original_save_locked = MemoryStore._save_locked
    writes = 0

    def fail_second_write(self, context, auto_checkpoint, **kwargs):
        nonlocal writes
        if auto_checkpoint is not None and auto_checkpoint.command == "update":
            writes += 1
            if writes == 2:
                raise OSError("simulated granted second-owner failure")
        return original_save_locked(self, context, auto_checkpoint, **kwargs)

    monkeypatch.setattr(MemoryStore, "_save_locked", fail_second_write)

    update = runner.invoke(
        app,
        ["update", "--from", source.name, "--to", wiki.name],
    )

    assert update.exit_code == 1
    assert "simulated granted second-owner failure" in update.stderr
    assert {
        name: authority_store.load_direct(name).to_dict()
        for name in authority_before
    } == authority_before
    assert authority_store.list_checkpoints(wiki.name) == []
    assert authority_store.list_checkpoints("campus-wiki/services") == []
    assert active_store.load_staged_update().status == "staged"
