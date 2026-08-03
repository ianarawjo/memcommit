"""Profile display-name changes preserve stable store and grant identity."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.profiles as profiles_module
from memcommit.cli import app
from memcommit.profile_config import (
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    create_authority_grant,
    study_profile_groups,
)
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _subprocess_mem(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "memcommit.cli", *args],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _prepare_authoring(isolated_store: Path) -> None:
    store = MemoryStore()
    context = ops.init("authoring-notes")
    ops.add(context, "Authoring Memory.")
    store.save(context)
    store.set_current(context.name)


@pytest.fixture()
def profile_home(isolated_store, tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    return tmp_path


def _register_profile(
    name: str,
    *,
    source: dict[str, object] | None = None,
    context_name: str = "profile-root",
    content: str | None = None,
) -> ProfileEntry:
    registry = load_profile_registry()
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=name,
        kind="MANAGED",
        source=source,
    )
    store = MemoryStore(root=profile_store_dir(profile))
    context = ops.init(context_name)
    ops.add(context, content or f"Memory owned by {name}.")
    store.save(context)
    store.set_current(context.name)
    profiles_module._write_registry(
        ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=(*registry.profiles, profile),
            grants=registry.grants,
        )
    )
    return profile


def _install_legacy_split_study(
    name: str = "legacy-run",
) -> tuple[str, tuple[ProfileEntry, ...]]:
    registry = load_profile_registry()
    study_uid = str(uuid.uuid4())
    authority_suffixes = {
        1: "task-1-campus-authority",
        2: "task-2-proposal-authority",
        3: "task-3-healthcare-authority",
    }
    allocated: list[ProfileEntry] = []
    for task in (1, 2, 3):
        for role in ("TASK", "AUTHORITY"):
            profile = ProfileEntry(
                uid=str(uuid.uuid4()),
                name=(
                    f"{name}-task-{task}"
                    if role == "TASK"
                    else f"{name}-{authority_suffixes[task]}"
                ),
                kind="MANAGED",
                source={
                    "kind": (
                        "STUDY_RUN_TASK" if role == "TASK" else "STUDY_RUN_AUTHORITY"
                    ),
                    "study_uid": study_uid,
                    "study_name": name,
                    "created_at": "2026-08-03T18:50:46.360105+00:00",
                    "task": task,
                    "manifest_sha256": str(task) * 64,
                    "canonical_language": "en",
                },
            )
            context_name = "task-root" if role == "TASK" else "authority-root"
            store = MemoryStore(root=profile_store_dir(profile))
            context = ops.init(context_name)
            ops.add(context, f"Legacy {role.lower()} Memory for Task {task}.")
            store.save(context)
            store.set_current(context.name)
            allocated.append(profile)
    profiles = tuple(allocated)
    profiles_module._write_registry(
        ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=(*registry.profiles, *profiles),
            grants=registry.grants,
        )
    )
    assert study_profile_groups(load_profile_registry().profiles)[-1].uid == study_uid
    return study_uid, profiles


def test_rename_inactive_ordinary_study_changes_only_its_registry_name(
    profile_home,
):
    original = _register_profile("study-run", context_name="study/root")
    before = load_profile_registry()
    original_index = next(
        index
        for index, profile in enumerate(before.profiles)
        if profile.uid == original.uid
    )
    root = profile_store_dir(original)
    digest = _tree_digest(root)

    result = runner.invoke(
        app,
        ["profile", "rename", "study-run", "renamed-study"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Renamed Profile 'study-run' to 'renamed-study'." in result.output
    after = load_profile_registry()
    renamed = after.by_name("renamed-study")
    assert renamed is not None
    assert after.by_name("study-run") is None
    assert after.generation == before.generation + 1
    assert after.active_uid == before.active_uid
    assert (
        next(
            index
            for index, profile in enumerate(after.profiles)
            if profile.uid == renamed.uid
        )
        == original_index
    )
    assert renamed.uid == original.uid
    assert renamed.kind == original.kind
    assert renamed.source == original.source
    assert after.grants == before.grants
    assert profile_store_dir(renamed) == root
    assert _tree_digest(root) == digest
    assert MemoryStore(root=root, create=False).current_context_name() == "study/root"


def test_one_argument_rename_keeps_the_active_profile_and_next_process_store(
    profile_home,
):
    profile = _register_profile(
        "active-old",
        context_name="active-context",
        content="Active Profile Memory.",
    )
    selected = runner.invoke(app, ["profile", "use", profile.name])
    assert selected.exit_code == 0, selected.stderr or selected.output
    before = load_profile_registry()
    root = profile_store_dir(profile)
    digest = _tree_digest(root)

    result = runner.invoke(app, ["profile", "rename", "active-new"])

    assert result.exit_code == 0, result.stderr or result.output
    assert "Renamed active Profile 'active-old' to 'active-new'." in result.output
    after = load_profile_registry()
    assert after.generation == before.generation + 1
    assert after.active_uid == profile.uid
    assert after.active.name == "active-new"
    assert profile_store_dir(after.active) == root
    assert _tree_digest(root) == digest
    listing = _subprocess_mem(profile_home, "ls")
    assert listing.returncode == 0, listing.stderr
    assert "Context: active-context" in listing.stdout
    assert "Active Profile Memory." in listing.stdout


def test_profile_lock_remains_attached_to_the_same_store_after_rename(
    profile_home,
):
    profile = _register_profile("locked-old")
    root = profile_store_dir(profile)
    store = MemoryStore(root=root, create=False)
    assert store.set_profile_write_protection(protected=True)

    result = runner.invoke(
        app,
        ["profile", "rename", "locked-old", "locked-new"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    renamed = load_profile_registry().by_name("locked-new")
    assert renamed is not None and renamed.uid == profile.uid
    assert profile_store_dir(renamed) == root
    assert (
        MemoryStore(
            root=root,
            create=False,
        )
        .write_protection_state()
        .profile_is_protected()
    )


@pytest.mark.parametrize("endpoint", ["authority", "grantee"])
def test_rename_preserves_grant_records_and_updates_live_endpoint_labels(
    profile_home,
    endpoint,
):
    authority = _register_profile(
        "authority-old",
        context_name="authority-root",
        content="Authority Memory.",
    )
    grantee = _register_profile("grantee-old", context_name="task-root")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name="authority-root",
        attachment_name="task-root",
        public_name="authority-view",
        permissions=("READ",),
    )
    before = load_profile_registry()
    target = authority if endpoint == "authority" else grantee
    renamed_name = f"{endpoint}-new"
    root = profile_store_dir(target)
    digest = _tree_digest(root)

    result = runner.invoke(
        app,
        ["profile", "rename", target.name, renamed_name],
    )

    assert result.exit_code == 0, result.stderr or result.output
    after = load_profile_registry()
    renamed = after.by_name(renamed_name)
    assert renamed is not None and renamed.uid == target.uid
    assert after.grants == before.grants == (grant,)
    assert profile_store_dir(renamed) == root
    assert _tree_digest(root) == digest
    grants = runner.invoke(app, ["profile", "grant", "list"])
    assert grants.exit_code == 0, grants.stderr or grants.output
    assert renamed_name in grants.output
    assert target.name not in grants.output


def test_fixed_authoring_profile_cannot_be_renamed(profile_home, isolated_store):
    before_digest = _tree_digest(isolated_store)
    assert not profile_registry_file().exists()

    result = runner.invoke(app, ["profile", "rename", "renamed-authoring"])

    assert result.exit_code == 1
    assert "fixed authoring Profile cannot be renamed" in result.stderr
    assert not profile_registry_file().exists()
    assert _tree_digest(isolated_store) == before_digest


def test_authoring_name_is_reserved_case_insensitively(profile_home):
    profile = _register_profile("ordinary")
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", profile.name, "Authoring"],
    )

    assert result.exit_code == 1
    assert "authoring Profile name is reserved" in result.stderr
    assert profile_registry_file().read_bytes() == before


def test_fixed_study_baseline_cannot_be_renamed(profile_home):
    baseline = _register_profile("study-baseline")
    before = profile_registry_file().read_bytes()
    digest = _tree_digest(profile_store_dir(baseline))

    result = runner.invoke(
        app,
        ["profile", "rename", "study-baseline", "new-baseline"],
    )

    assert result.exit_code == 1
    assert "fixed study-baseline Profile cannot be renamed" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert _tree_digest(profile_store_dir(baseline)) == digest


def test_study_baseline_name_is_reserved_case_insensitively(profile_home):
    profile = _register_profile("ordinary")
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", profile.name, "Study-Baseline"],
    )

    assert result.exit_code == 1
    assert "study-baseline Profile name is reserved" in result.stderr
    assert profile_registry_file().read_bytes() == before


def test_legacy_split_member_cannot_be_renamed_individually(profile_home):
    _study_uid, profiles = _install_legacy_split_study()
    member = profiles[0]
    before = profile_registry_file().read_bytes()
    digests = {
        profile.uid: _tree_digest(profile_store_dir(profile)) for profile in profiles
    }

    result = runner.invoke(
        app,
        ["profile", "rename", member.name, "detached-task"],
    )

    assert result.exit_code == 1
    assert "member of legacy Study 'legacy-run'" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert (
        study_profile_groups(load_profile_registry().profiles)[0].name == "legacy-run"
    )
    assert {
        profile.uid: _tree_digest(profile_store_dir(profile)) for profile in profiles
    } == digests


def test_ordinary_profile_cannot_take_a_live_legacy_group_name(profile_home):
    ordinary = _register_profile("ordinary")
    _study_uid, profiles = _install_legacy_split_study()
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", ordinary.name, "LEGACY-RUN"],
    )

    assert result.exit_code == 1
    assert "conflicts with existing legacy Study 'legacy-run'" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archived_legacy_group_name_can_be_reused_by_an_ordinary_profile(
    profile_home,
):
    ordinary = _register_profile("ordinary")
    study_uid, legacy_profiles = _install_legacy_split_study()
    archived = runner.invoke(app, ["profile", "archive-study", "legacy-run"])
    assert archived.exit_code == 0, archived.stderr or archived.output
    manifest = (
        profile_home
        / ".mem-profiles"
        / "archives"
        / "studies"
        / study_uid
        / "manifest.json"
    )
    archive_bytes = manifest.read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", ordinary.name, "legacy-run"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    renamed = load_profile_registry().by_name("legacy-run")
    assert renamed is not None and renamed.uid == ordinary.uid
    assert manifest.read_bytes() == archive_bytes
    assert all(profile_store_dir(profile).is_dir() for profile in legacy_profiles)


def test_casefold_collision_fails_without_mutating_either_profile(profile_home):
    alpha = _register_profile("alpha")
    beta = _register_profile("Beta")
    before = profile_registry_file().read_bytes()
    digests = {
        alpha.uid: _tree_digest(profile_store_dir(alpha)),
        beta.uid: _tree_digest(profile_store_dir(beta)),
    }

    result = runner.invoke(app, ["profile", "rename", "alpha", "bETA"])

    assert result.exit_code == 1
    assert "Profile 'Beta' already exists" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert {
        alpha.uid: _tree_digest(profile_store_dir(alpha)),
        beta.uid: _tree_digest(profile_store_dir(beta)),
    } == digests


def test_case_only_rename_is_a_real_registry_change_with_the_same_identity(
    profile_home,
):
    profile = _register_profile(
        "Pilot",
        source={"kind": "TEST_PROVENANCE", "source_profile_name": "Original"},
    )
    before = load_profile_registry()
    root = profile_store_dir(profile)
    digest = _tree_digest(root)

    result = runner.invoke(app, ["profile", "rename", "Pilot", "pilot"])

    assert result.exit_code == 0, result.stderr or result.output
    after = load_profile_registry()
    renamed = after.by_name("pilot")
    assert renamed is not None
    assert after.by_name("Pilot") is None
    assert after.generation == before.generation + 1
    assert renamed.uid == profile.uid
    assert renamed.source == profile.source
    assert profile_store_dir(renamed) == root
    assert _tree_digest(root) == digest


def test_exact_noop_does_not_validate_the_store_or_write_the_registry(
    profile_home,
    monkeypatch,
):
    profile = _register_profile("unchanged")
    before = profile_registry_file().read_bytes()
    root = profile_store_dir(profile)
    backup = root.with_name(root.name + ".missing")
    root.rename(backup)

    def unexpected_write(_registry):
        raise AssertionError("exact no-op must not write the registry")

    monkeypatch.setattr(profiles_module, "_write_registry", unexpected_write)
    result = runner.invoke(
        app,
        ["profile", "rename", "unchanged", "unchanged"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "already has that name" in result.output
    assert profile_registry_file().read_bytes() == before
    assert not root.exists()
    assert backup.is_dir()


def test_invalid_new_name_fails_before_any_registry_or_store_mutation(profile_home):
    profile = _register_profile("valid-old")
    before = profile_registry_file().read_bytes()
    root = profile_store_dir(profile)
    digest = _tree_digest(root)

    result = runner.invoke(
        app,
        ["profile", "rename", "valid-old", "invalid/name"],
    )

    assert result.exit_code == 1
    assert "Profile rename name is invalid" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert _tree_digest(root) == digest


def test_missing_store_blocks_a_real_rename_without_repairing_or_deleting_it(
    profile_home,
):
    profile = _register_profile("missing-old")
    root = profile_store_dir(profile)
    backup = root.with_name(root.name + ".missing")
    digest = _tree_digest(root)
    root.rename(backup)
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", "missing-old", "missing-new"],
    )

    assert result.exit_code == 1
    assert "MemoryStore must be a real directory" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert not root.exists()
    assert backup.is_dir()
    assert _tree_digest(backup) == digest


def test_invalid_store_blocks_a_real_rename_without_rewriting_the_record(
    profile_home,
):
    profile = _register_profile("invalid-old")
    root = profile_store_dir(profile)
    state = root / "state.json"
    state.write_text("{not-json\n", encoding="utf-8")
    invalid = state.read_bytes()
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "rename", "invalid-old", "invalid-new"],
    )

    assert result.exit_code == 1
    assert "MemoryStore state is invalid JSON" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert state.read_bytes() == invalid


def test_registry_failure_before_replace_leaves_the_old_name_authoritative(
    profile_home,
    monkeypatch,
):
    profile = _register_profile("before-old")
    before = load_profile_registry()
    root = profile_store_dir(profile)
    digest = _tree_digest(root)

    def fail_registry_write(_registry):
        raise OSError("simulated registry failure")

    monkeypatch.setattr(profiles_module, "_write_registry", fail_registry_write)
    result = runner.invoke(
        app,
        ["profile", "rename", "before-old", "before-new"],
    )

    assert result.exit_code == 1
    assert "simulated registry failure" in result.stderr
    assert load_profile_registry() == before
    assert _tree_digest(root) == digest


def test_registry_failure_after_visible_replace_keeps_the_renamed_identity(
    profile_home,
    monkeypatch,
):
    profile = _register_profile("visible-old")
    before = load_profile_registry()
    root = profile_store_dir(profile)
    digest = _tree_digest(root)
    real_write_registry = profiles_module._write_registry

    def fail_after_visible_replace(updated):
        real_write_registry(updated)
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(
        profiles_module,
        "_write_registry",
        fail_after_visible_replace,
    )
    result = runner.invoke(
        app,
        ["profile", "rename", "visible-old", "visible-new"],
    )

    assert result.exit_code == 1
    assert "durability could not be confirmed" in result.stderr
    assert "it remains renamed" in result.stderr
    after = load_profile_registry()
    renamed = after.by_name("visible-new")
    assert renamed is not None and renamed.uid == profile.uid
    assert after.by_name("visible-old") is None
    assert after.generation == before.generation + 1
    assert after.active_uid == before.active_uid
    assert profile_store_dir(renamed) == root
    assert _tree_digest(root) == digest
