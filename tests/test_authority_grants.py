"""Cross-Profile authority grants behave as permissioned views, not forks."""
from __future__ import annotations

import json
import uuid

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.context import Memory
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, update_authority_grant
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)
PUBLIC = "The student centre remains open until 20:00."
SECRET = "The utility tunnel access code is 1937."


def _grant_fixture(isolated_store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    task_store = MemoryStore()
    task_root = ops.init("task-root")
    task_store.save(task_root)
    task_store.set_current(task_root.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="task-1-campus-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    campus = ops.init("campus-wiki")
    editable = ops.add(campus, "Original campus note.")
    public = ops.init("campus-wiki/public")
    ops.add(public, PUBLIC)
    details = ops.init("campus-wiki/construction-details")
    ops.add(details, SECRET)
    details_child = ops.init("campus-wiki/construction-details/internal")
    ops.add(details_child, "Additional concealed construction detail.")
    ops.embed(public, campus)
    ops.embed(details, campus)
    ops.embed(details_child, details)
    for context in (campus, public, details, details_child):
        authority_store.save(context)
    authority_store.set_current(campus.name)

    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
        grants=(),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(registry.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    _registry, campus_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=campus.name,
        attachment_name=task_root.name,
        public_name=campus.name,
        permissions=("READ", "CREATE", "UPDATE"),
        recursive=True,
    )
    _registry, details_grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=details.name,
        attachment_name=task_root.name,
        public_name=details.name,
        permissions=("QUERY",),
        recursive=True,
    )
    return authority_store, editable, campus_grant, details_grant


def test_ls_projects_read_view_and_masks_narrower_query_view(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority, _editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    root = runner.invoke(app, ["ls"])
    view = runner.invoke(app, ["ls", "campus-wiki", "--recursive"])
    shown = runner.invoke(app, ["show", "--context", "campus-wiki/public"])
    contexts = runner.invoke(app, ["contexts"])

    assert root.exit_code == 0, root.output
    assert "campus-wiki" in root.output
    assert "Authority views:" in root.output
    assert "task-1-campus-authority" in root.output
    assert "Permissions: CREATE + READ + UPDATE" in root.output
    assert (
        "Source boundary: DERIVE blocked · COMBINE blocked · EXPORT blocked"
        in root.output
    )
    assert (
        "Target/artifact boundary: ACCEPT_DERIVED blocked · "
        "SAVE_BOUND_ANALYSIS blocked · SAVE_ANALYSIS blocked" in root.output
    )
    assert view.exit_code == 0, view.output
    assert "Access: GRANTED VIEW · from task-1-campus-authority" in view.output
    assert f"grant {campus_grant.uid[:8]} revision 1" in view.output
    assert PUBLIC in view.output
    assert "campus-wiki/construction-details (query-only)" in view.output
    assert view.output.count("campus-wiki/construction-details") == 1
    assert SECRET not in view.output
    assert "Additional concealed construction detail" not in view.output
    assert shown.exit_code == 0, shown.output
    assert PUBLIC in shown.output
    assert contexts.exit_code == 0, contexts.output
    assert "[view create,read,update from task-1-campus-authority]" in contexts.output
    assert "[view query from task-1-campus-authority]" in contexts.output


def test_read_view_does_not_open_nested_query_authority_record(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, _editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    concealed_record = (
        authority_store.contexts_dir
        / "campus-wiki"
        / "construction-details"
        / "context.json"
    )
    concealed_record.write_text("not readable as context json\n", encoding="utf-8")

    selected = runner.invoke(app, ["profile", "use", AUTHORING_PROFILE_NAME])
    view = runner.invoke(app, ["ls", "campus-wiki", "--recursive"])

    assert selected.exit_code == 0, selected.output
    assert view.exit_code == 0, view.output
    assert PUBLIC in view.output
    assert "campus-wiki/construction-details (query-only)" in view.output


def test_granted_memory_create_and_update_write_authority_store_only(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, editable, _campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    added = runner.invoke(
        app,
        ["add", "Created through the task view.", "--context", "campus-wiki"],
    )
    edited = runner.invoke(
        app,
        [
            "edit",
            editable.uid,
            "Revised through the task view.",
            "--context",
            "campus-wiki",
        ],
    )

    assert added.exit_code == 0, added.output
    assert edited.exit_code == 0, edited.output
    authority = authority_store.load_direct("campus-wiki")
    assert [
        item.content
        for item in authority.iter_items()
        if isinstance(item, Memory)
    ] == [
        "Revised through the task view.",
        "Created through the task view.",
    ]
    task = MemoryStore().load_direct("task-root")
    assert list(task.iter_items()) == []


def test_delete_permission_and_view_revocation_fail_closed(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    denied = runner.invoke(
        app,
        ["remove", editable.uid, "--context", "campus-wiki"],
    )
    revoked = runner.invoke(
        app,
        ["profile", "grant", "delete", campus_grant.uid],
    )
    missing = runner.invoke(app, ["ls", "campus-wiki"])

    assert denied.exit_code == 1
    assert "does not allow delete access" in denied.stderr
    assert revoked.exit_code == 0, revoked.output
    assert len(load_profile_registry().grants) == 1
    assert missing.exit_code == 1
    assert "does not exist" in missing.stderr


def test_granted_delete_permission_removes_only_authority_memory(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )
    update_authority_grant(
        campus_grant.uid,
        permissions=("READ", "DELETE"),
    )

    removed = runner.invoke(
        app,
        ["remove", editable.uid, "--context", "campus-wiki"],
    )

    assert removed.exit_code == 0, removed.output
    assert editable.uid not in authority_store.load_direct("campus-wiki").memories
    assert list(MemoryStore().load_direct("task-root").iter_items()) == []


def test_profile_grant_cli_creates_and_updates_frozen_permission_record(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _store, _editable, campus_grant, _details_grant = _grant_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
    )

    updated = runner.invoke(
        app,
        [
            "profile",
            "grant",
            "update",
            campus_grant.uid[:8],
            "--allow",
            "READ",
            "--allow",
            "DELETE",
            "--root-only",
        ],
    )
    listed = runner.invoke(app, ["profile", "grant", "list"])

    assert updated.exit_code == 0, updated.output
    grant = next(
        item for item in load_profile_registry().grants if item.uid == campus_grant.uid
    )
    assert grant.revision == 2
    assert grant.permissions == ("READ", "DELETE")
    assert len(grant.contexts) == 1
    assert listed.exit_code == 0, listed.output
    assert "read,delete" in listed.output
    assert "task-1-campus-authority:campus-wiki" in listed.output
