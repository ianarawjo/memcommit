"""Portable new Context identities with explicit legacy compatibility."""

from __future__ import annotations

import json
import shlex
import subprocess
import uuid
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import memcommit.adapters.console.commands.profiles.profile.command as profile_command
import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import AutoCheckpoint, Context
from memcommit.core.context_targeting.naming import (
    is_portable_context_name,
    validate_portable_context_name,
)
from memcommit.application.operations.profiles.profile.model import create_authority_grant
from memcommit.persistence.store import MemoryStore, validate_context_name


runner = CliRunner(mix_stderr=False)


def _seed_legacy_context(store: MemoryStore, context: Context) -> None:
    """Write one pre-portability record as if it came from an older release."""

    path = store.contexts_dir.joinpath(*context.name.split("/"), "context.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(context.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _previewed_apply_args(output: str) -> list[str]:
    command = next(
        line.removeprefix("Apply: ")
        for line in output.splitlines()
        if line.startswith("Apply: ")
    )
    argv = shlex.split(command)
    assert argv[0] == "mem"
    return argv[1:]


def test_migration_shell_receipt_escapes_display_controls_but_round_trips():
    raw_name = "scope/current\u202e"
    command = profile_command._migration_shell_join(
        ("printf", "%s", raw_name)
    )

    assert raw_name not in command
    assert r"\u202e" in command
    completed = subprocess.run(
        ["zsh", "-c", command],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert completed.stdout == raw_name


@pytest.mark.parametrize(
    "name",
    (
        "team project",
        "team/*",
        "team/$draft",
        "semi;colon",
        "-leading",
        "한글",
        "CON",
        "nul.txt",
        "trailing.",
        "deadbeef",
        "DEADBEEF",
        "12345678-1234-4234-8234-123456789abc",
    ),
)
def test_nonportable_names_remain_legacy_valid_but_cannot_be_new_names(name):
    assert validate_context_name(name) == name
    assert not is_portable_context_name(name)
    with pytest.raises(ValueError, match="not portable"):
        validate_portable_context_name(name)
    with pytest.raises(ValueError, match="not portable"):
        ops.init(name)


@pytest.mark.parametrize(
    "name",
    (
        "team",
        "team/project",
        "Team_29/project-v2",
        "release.2026",
        "team/deadbeef",
    ),
)
def test_portable_names_are_canonical_without_shell_quoting(name):
    assert validate_portable_context_name(name) == name
    assert is_portable_context_name(name)


def test_new_nonportable_context_is_rejected_without_publishing_storage(
    isolated_store,
):
    result = runner.invoke(app, ["init", "team project"])

    assert result.exit_code == 1
    assert "not portable" in result.stderr
    assert MemoryStore().list_context_names() == []


def test_new_memory_uid_shaped_context_is_rejected_at_creation(isolated_store):
    result = runner.invoke(app, ["init", "deadbeef"])

    assert result.exit_code == 1
    assert "Memory UUID or visible UID prefix" in result.stderr
    assert MemoryStore().list_context_names() == []


def test_uid_shaped_parent_batch_is_rejected_without_partial_creation(
    isolated_store,
):
    result = runner.invoke(app, ["init", "deadbeef/child", "--parents"])

    assert result.exit_code == 1
    assert "Memory UUID or visible UID prefix" in result.stderr
    assert MemoryStore().list_context_names() == []


def test_uid_shaped_legacy_context_remains_readable(isolated_store):
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="deadbeef")
    memory = ops.add(legacy, "legacy content")
    _seed_legacy_context(store, legacy)

    loaded = store.load_direct(legacy.name)

    assert loaded.memories[memory.uid].content == "legacy content"


def test_existing_legacy_context_remains_readable_and_writable(isolated_store):
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="team project")
    first = ops.add(legacy, "legacy content")
    _seed_legacy_context(store, legacy)

    loaded = store.load_direct(legacy.name)
    assert loaded.uid == legacy.uid
    assert loaded.memories[first.uid].content == "legacy content"

    added = ops.add(loaded, "compatible update")
    store.save(
        loaded,
        AutoCheckpoint(
            command="add",
            args={"content": "compatible update"},
            description="Updated a legacy Context before migration",
        ),
    )
    assert store.load_direct(legacy.name).memories[added.uid].content == (
        "compatible update"
    )
    listed = runner.invoke(app, ["contexts"])
    assert listed.exit_code == 0
    assert "team project" in listed.output
    assert "LEGACY NAME · MIGRATION REQUIRED" in listed.output


def test_profile_context_migration_previews_then_preserves_graph_identity(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    root = Context(uid=str(uuid.uuid4()), name="team project")
    child = Context(uid=str(uuid.uuid4()), name="team project/child")
    memory = ops.add(child, "source")
    _seed_legacy_context(store, root)
    _seed_legacy_context(store, child)

    observer = ops.init("observer")
    observer.add(child)
    store.save(observer)
    store.set_current(child.name)

    preview = runner.invoke(
        app,
        ["profile", "migrate-context", "team project", "team-project"],
    )
    assert preview.exit_code == 0
    assert "PLAN ONLY · NOTHING CHANGED" in preview.output
    assert "'team project'" in preview.output
    assert store.context_exists("team project/child")
    assert not store.context_exists("team-project/child")

    applied = runner.invoke(app, _previewed_apply_args(preview.output))
    assert applied.exit_code == 0
    assert "Context name migration applied." in applied.output
    assert not store.context_exists("team project")
    assert not store.context_exists("team project/child")
    assert store.load_direct("team-project").uid == root.uid
    migrated_child = store.load_direct("team-project/child")
    assert migrated_child.uid == child.uid
    assert migrated_child.memories[memory.uid].content == "source"
    assert store.current_context_name() == "team-project/child"
    migrated_reference = store.load_direct("observer").memories[child.uid]
    assert isinstance(migrated_reference, Context)
    assert migrated_reference.uid == child.uid
    assert migrated_reference.name == "team-project/child"


def test_compatibility_migration_is_not_a_general_rename(
    isolated_store,
):
    store = MemoryStore()
    portable = ops.init("already-portable")
    store.save(portable)
    result = runner.invoke(
        app,
        ["profile", "migrate-context", "already-portable", "renamed"],
    )

    assert result.exit_code == 1
    assert "not a general rename route" in result.stderr
    assert store.load_direct("already-portable").uid == portable.uid


def test_compatibility_migration_fails_closed_on_frozen_grant_names(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="shared context")
    _seed_legacy_context(store, legacy)
    registry = SimpleNamespace(
        active=SimpleNamespace(name="authoring", uid="active-profile")
    )
    blocker = SimpleNamespace(uid="12345678-blocking-grant")
    monkeypatch.setattr(
        profile_command,
        "_context_migration_grant_blockers",
        lambda _old_name: (registry, (blocker,)),
    )
    monkeypatch.setattr(
        profile_command,
        "profile_store_dir",
        lambda _profile: isolated_store,
    )

    plan = store.plan_context_rename("shared context", "shared-context")
    result = runner.invoke(
        app,
        [
            "profile",
            "migrate-context",
            "--expect-profile",
            registry.active.uid,
            "--expect-graph",
            plan.graph_digest,
            "--apply",
            "shared context",
            "shared-context",
        ],
    )

    assert result.exit_code == 1
    assert "frozen cross-Profile Grants" in result.stderr
    assert store.load_direct("shared context").uid == legacy.uid
    assert not store.context_exists("shared-context")


def test_migration_double_dash_accepts_a_legacy_leading_option_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="-leading")
    _seed_legacy_context(store, legacy)

    preview = runner.invoke(
        app,
        ["profile", "migrate-context", "--", "-leading", "leading"],
    )
    assert preview.exit_code == 0

    result = runner.invoke(
        app,
        _previewed_apply_args(preview.output),
    )

    assert result.exit_code == 0
    assert store.load_direct("leading").uid == legacy.uid
    assert not store.context_exists("-leading")


def test_apply_receipt_rejects_a_changed_context_graph(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="stale source")
    _seed_legacy_context(store, legacy)
    preview = runner.invoke(
        app,
        ["profile", "migrate-context", "stale source", "stale-source"],
    )
    assert preview.exit_code == 0

    store.save(ops.init("concurrent-context"))
    result = runner.invoke(app, _previewed_apply_args(preview.output))

    assert result.exit_code == 1
    assert "Context graph changed" in result.stderr
    assert store.load_direct("stale source").uid == legacy.uid
    assert not store.context_exists("stale-source")


def test_apply_receipt_rejects_an_active_profile_switch(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="profile source")
    _seed_legacy_context(store, legacy)
    registry = {
        "value": SimpleNamespace(
            active=SimpleNamespace(name="first", uid="first-profile")
        )
    }
    monkeypatch.setattr(
        profile_command,
        "_context_migration_grant_blockers",
        lambda _old_name: (registry["value"], ()),
    )
    monkeypatch.setattr(
        profile_command,
        "profile_store_dir",
        lambda _profile: isolated_store,
    )
    preview = runner.invoke(
        app,
        ["profile", "migrate-context", "profile source", "profile-source"],
    )
    assert preview.exit_code == 0

    registry["value"] = SimpleNamespace(
        active=SimpleNamespace(name="second", uid="second-profile")
    )
    result = runner.invoke(app, _previewed_apply_args(preview.output))

    assert result.exit_code == 1
    assert "active Profile changed" in result.stderr
    assert store.load_direct("profile source").uid == legacy.uid
    assert not store.context_exists("profile-source")


def test_apply_requires_a_previewed_exact_receipt(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="manual source")
    _seed_legacy_context(store, legacy)

    result = runner.invoke(
        app,
        [
            "profile",
            "migrate-context",
            "--apply",
            "manual source",
            "manual-source",
        ],
    )

    assert result.exit_code == 1
    assert "Preview this migration first" in result.stderr
    assert store.load_direct("manual source").uid == legacy.uid


def test_namespace_migration_reports_and_then_retires_legacy_descendants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    root = Context(uid=str(uuid.uuid4()), name="old root")
    child = Context(uid=str(uuid.uuid4()), name="old root/bad child")
    _seed_legacy_context(store, root)
    _seed_legacy_context(store, child)

    preview = runner.invoke(
        app,
        ["profile", "migrate-context", "old root", "old-root"],
    )
    assert preview.exit_code == 0
    assert "Remaining legacy descendants: 1" in preview.output

    first = runner.invoke(app, _previewed_apply_args(preview.output))
    assert first.exit_code == 0
    assert "old-root/bad child" in first.output
    assert store.load_direct("old-root/bad child").uid == child.uid

    child_preview = runner.invoke(
        app,
        [
            "profile",
            "migrate-context",
            "old-root/bad child",
            "old-root/bad-child",
        ],
    )
    assert child_preview.exit_code == 0
    second = runner.invoke(app, _previewed_apply_args(child_preview.output))
    assert second.exit_code == 0
    assert store.load_direct("old-root/bad-child").uid == child.uid
    assert all(
        is_portable_context_name(name) for name in store.list_context_names()
    )


def test_migration_detects_authority_and_attachment_grant_incidents(
    monkeypatch,
):
    active = SimpleNamespace(uid="active-profile")
    authority_blocker = SimpleNamespace(
        uid="authority-blocker",
        authority_profile_uid=active.uid,
        grantee_profile_uid="other-profile",
        resource_name="unrelated",
        attachment_context_name="attachment",
        contexts=(SimpleNamespace(name="legacy root/child"),),
    )
    attachment_blocker = SimpleNamespace(
        uid="attachment-blocker",
        authority_profile_uid="other-profile",
        grantee_profile_uid=active.uid,
        resource_name="resource",
        attachment_context_name="legacy root",
        contexts=(SimpleNamespace(name="resource"),),
    )
    unrelated = SimpleNamespace(
        uid="unrelated",
        authority_profile_uid="other-profile",
        grantee_profile_uid="third-profile",
        resource_name="legacy root",
        attachment_context_name="legacy root",
        contexts=(SimpleNamespace(name="legacy root"),),
    )
    registry = SimpleNamespace(
        active=active,
        grants=(authority_blocker, attachment_blocker, unrelated),
    )
    monkeypatch.setattr(
        profile_command,
        "load_profile_registry",
        lambda: registry,
    )

    frozen, blockers = profile_command._context_migration_grant_blockers(
        "legacy root"
    )

    assert frozen is registry
    assert [grant.uid for grant in blockers] == [
        "authority-blocker",
        "attachment-blocker",
    ]


@pytest.mark.parametrize(
    ("resource_name", "attachment_name"),
    (("legacy source", "attachment"), ("source", "legacy attachment")),
)
def test_new_grants_reject_legacy_resource_or_attachment_names_before_io(
    resource_name,
    attachment_name,
):
    with pytest.raises(ValueError, match="not portable"):
        create_authority_grant(
            authority_name="missing-authority",
            grantee_name="missing-grantee",
            resource_name=resource_name,
            attachment_name=attachment_name,
            permissions=("READ",),
        )
