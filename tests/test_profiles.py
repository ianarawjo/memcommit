"""Whole-store profile selection and study-profile import contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

import click
import pytest
from typer.testing import CliRunner

import memcommit.application.ops as ops
import memcommit.application.operations.init_study.publication as init_study_publication_module
import memcommit.application.operations.profile.model as profiles_module
from memcommit.adapters.console.entrypoint import app
from memcommit.commands.switch.command import (
    _granted_picker_state,
    _granted_picker_views,
)
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.study_scenarios.legacy.bundle import build_all_study_bundles
from memcommit.study_scenarios.legacy import LEGACY_BASELINE_UID
from memcommit.study_scenarios.legacy import LEGACY_DIGEST
from memcommit.providers.policy import (
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
)
from memcommit.adapters.interfaces.console.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.operations.profile.config import (
    GRANT_RESOURCE_CONTEXT_TREE,
    AuthorityGrant,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    canonical_grant_permissions,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    create_authority_grant,
    resolve_granted_context_view,
    study_profile_groups,
)
from memcommit.application.operations.query.granted_source import (
    load_authority_query_source,
)
from memcommit.persistence.store import MemoryStore
from memcommit.source_projection.presentation import source_display_text
from memcommit.persistence.command_ledger.study_actions import StudyActionLedger


runner = CliRunner(mix_stderr=False)


def test_legacy_session_log_permission_normalizes_to_one_shot_query():
    assert canonical_grant_permissions(("QUERY", "SESSION_LOG")) == ("QUERY",)
    assert canonical_grant_permissions(("SESSION_LOG",)) == ("QUERY",)


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
        [sys.executable, "-m", "memcommit.adapters.console.entrypoint", *args],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _prepare_authoring(isolated_store: Path) -> None:
    store = MemoryStore()
    store.save(ops.init("authoring-notes"))
    store.set_current("authoring-notes")


def _install_legacy_split_study(
    name: str = "legacy-run",
) -> tuple[str, tuple[ProfileEntry, ...], tuple[AuthorityGrant, ...]]:
    """Recreate the complete split topology written by the former init-study."""

    registry = load_profile_registry()
    study_uid = str(uuid.uuid4())
    created_at = "2026-08-03T18:50:46.360105+00:00"
    authority_suffixes = {
        1: "task-1-campus-authority",
        2: "task-2-proposal-authority",
        3: "task-3-healthcare-authority",
    }
    allocated: list[tuple[int, str, ProfileEntry]] = []
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
                    "created_at": created_at,
                    "task": task,
                    "manifest_sha256": str(task) * 64,
                    "canonical_language": "en",
                },
            )
            allocated.append((task, role, profile))

    contexts: dict[tuple[int, str], Context] = {}
    for task, role, profile in allocated:
        context = ops.init("task-root" if role == "TASK" else "authority-root")
        ops.add(context, f"Legacy {role.lower()} Memory for Task {task}.")
        store = MemoryStore(root=profile_store_dir(profile))
        store.save(context)
        store.set_current(context.name)
        contexts[(task, role)] = context

    grants: list[AuthorityGrant] = []
    grant_counts = {1: 2, 2: 3, 3: 2}
    for task, count in grant_counts.items():
        task_profile = next(
            profile
            for candidate_task, role, profile in allocated
            if candidate_task == task and role == "TASK"
        )
        authority_profile = next(
            profile
            for candidate_task, role, profile in allocated
            if candidate_task == task and role == "AUTHORITY"
        )
        task_context = contexts[(task, "TASK")]
        authority_context = contexts[(task, "AUTHORITY")]
        for index in range(1, count + 1):
            grants.append(
                AuthorityGrant(
                    uid=str(uuid.uuid4()),
                    revision=1,
                    authority_profile_uid=authority_profile.uid,
                    grantee_profile_uid=task_profile.uid,
                    attachment_context_uid=task_context.uid,
                    attachment_context_name=task_context.name,
                    resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
                    resource_uid=authority_context.uid,
                    resource_name=authority_context.name,
                    public_name=f"view-{task}-{index}",
                    permissions=("READ",),
                    contexts=(
                        GrantContextBinding(
                            uid=authority_context.uid,
                            name=authority_context.name,
                        ),
                    ),
                )
            )

    profiles = tuple(profile for _task, _role, profile in allocated)
    profiles_module._write_registry(
        ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=(*registry.profiles, *profiles),
            grants=(*registry.grants, *grants),
        )
    )
    return study_uid, profiles, tuple(grants)


def _legacy_archive_manifest(study_uid: str) -> Path:
    return profile_control_dir() / "archives" / "studies" / study_uid / "manifest.json"


def test_absent_registry_preserves_legacy_authoring_without_writing_metadata(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "* authoring" in result.output
    assert "Contexts 1 owned + 0 granted" in result.output
    assert "Memories 0 owned + 0 granted" in result.output
    assert "current=authoring-notes" in result.output
    assert not profile_registry_file().exists()


def test_bare_profile_prints_inventory_in_non_tty_mode(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert "* authoring" in result.output
    assert "CURRENT" in result.output
    assert "Contexts 1 owned + 0 granted" in result.output
    assert "Memories 0 owned + 0 granted" in result.output
    assert "Usage:" not in result.output


def test_profile_inventory_does_not_expose_an_unrouted_query_source_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    MemoryStore().create_query_source(
        "concealed-unrouted-name",
        "CONTENT THAT MUST NOT APPEAR",
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert "1 query-only" in result.output
    assert "concealed-unrouted-name" not in result.output
    assert "CONTENT THAT MUST NOT APPEAR" not in result.output


def test_bare_profile_uses_interactive_picker_result(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    assert runner.invoke(app, ["profile", "create", "picker-target"]).exit_code == 0
    observed: dict[str, object] = {}

    def select(entries, *, current, registry_generation, apply_removal):
        assert callable(apply_removal)
        observed["names"] = [entry.name for entry in entries]
        observed["current"] = current
        observed["generation"] = registry_generation
        return "picker-target"

    monkeypatch.setattr(
        "memcommit.commands.profile.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.command.choose_profile",
        select,
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert "Selected profile 'picker-target'." in result.output
    assert observed == {
        "names": ["authoring", "picker-target"],
        "current": "authoring",
        "generation": 1,
    }
    assert load_profile_registry().active.name == "picker-target"


def test_bare_profile_cancel_preserves_active_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    monkeypatch.setattr(
        "memcommit.commands.profile.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.command.choose_profile",
        lambda entries, *, current, registry_generation, apply_removal: None,
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0
    assert "Profile selection cancelled." in result.output
    assert load_profile_registry().active.name == "authoring"
    assert not profile_registry_file().exists()


def test_bare_profile_revalidates_picker_result_before_selection(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    monkeypatch.setattr(
        "memcommit.commands.profile.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.command.choose_profile",
        lambda entries, *, current, registry_generation, apply_removal: "missing",
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 1
    assert "does not exist" in result.stderr
    assert load_profile_registry().active.name == "authoring"
    assert not profile_registry_file().exists()


def test_explicit_profile_use_does_not_open_picker(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)

    def unexpected_picker(*args, **kwargs):
        raise AssertionError("explicit profile use must not open the picker")

    monkeypatch.setattr(
        "memcommit.commands.profile.command.choose_profile",
        unexpected_picker,
    )

    result = runner.invoke(app, ["profile", "use", "authoring"])

    assert result.exit_code == 0
    assert "Already using profile 'authoring'." in result.output
    assert not profile_registry_file().exists()


def test_init_study_selects_the_initialized_complete_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    initialized = runner.invoke(
        app,
        ["init-study", "profile-view", "--scenario", "legacy"],
    )
    assert initialized.exit_code == 0, initialized.stderr or initialized.output

    selected = runner.invoke(app, ["profile", "use", "profile-view"])

    assert selected.exit_code == 0, selected.output
    assert "Already using profile 'profile-view'." in selected.output
    contexts = _subprocess_mem(tmp_path, "contexts")
    assert contexts.returncode == 0, contexts.stderr
    assert "*        practice" in contexts.stdout
    assert "task-1/participant/construction-updates" in contexts.stdout
    assert "task-1/campus-wiki" in contexts.stdout
    assert (
        "GRANT  task-1/campus-wiki  READ + QUERY + EDIT + DELETE + EXPORT"
        in contexts.stdout
    )
    assert "task-1/campus-wiki/construction-details" in contexts.stdout
    assert "GRANT  task-1/campus-wiki/construction-details  QUERY" in contexts.stdout
    assert "PERMISSIONS" not in contexts.stdout
    assert "FROM profile-view-granted-memory" in contexts.stdout
    assert "authoring-notes" not in contexts.stdout
    context_lines = contexts.stdout.splitlines()
    participant_index = next(
        index
        for index, line in enumerate(context_lines)
        if line.strip() == "task-1/participant"
    )
    campus_index = next(
        index
        for index, line in enumerate(context_lines)
        if "GRANT  task-1/campus-wiki  " in line
    )
    task_two_index = next(
        index for index, line in enumerate(context_lines) if line.strip() == "task-2"
    )
    assert participant_index < campus_index < task_two_index

    task_one = _subprocess_mem(
        tmp_path,
        "switch",
        "task-1/participant/construction-updates",
    )
    assert task_one.returncode == 0, task_one.stderr
    readable = _subprocess_mem(
        tmp_path,
        "ls",
        "-R",
        "task-1/campus-wiki",
    )
    assert readable.returncode == 0, readable.stderr
    assert "event information agent" in readable.stdout
    query_only = _subprocess_mem(
        tmp_path,
        "ls",
        "task-1/campus-wiki/construction-details",
    )
    assert query_only.returncode == 1
    assert "does not allow read access" in query_only.stderr

    query_view = resolve_granted_context_view(
        "task-1/campus-wiki/construction-details",
        attachment_name="task-1/participant/construction-updates",
        required_permission="QUERY",
    )
    query_source = load_authority_query_source(query_view, language="en")
    assert query_source.name == "task-1/campus-wiki/construction-details"
    assert query_source.content

    wiki_query_view = resolve_granted_context_view(
        "task-1/campus-wiki",
        attachment_name="task-1/participant/construction-updates",
        required_permission="QUERY",
    )
    wiki_query_source = load_authority_query_source(wiki_query_view, language="en")
    assert wiki_query_source.name == "task-1/campus-wiki"
    assert wiki_query_source.content
    with pytest.raises(ProfileError, match="does not allow share access"):
        resolve_granted_context_view(
            "task-1/campus-wiki",
            attachment_name="task-1/participant/construction-updates",
            required_permission="SHARE",
        )

    run_only_text = "Participant edit stored only in this Study run."
    granted_add = _subprocess_mem(
        tmp_path,
        "add",
        run_only_text,
        "--context",
        "task-1/campus-wiki",
    )
    assert granted_add.returncode == 0, granted_add.stderr
    registry = load_profile_registry()
    authority = registry.by_name("profile-view-granted-memory")
    assert registry.by_name("study-baseline") is None
    assert authority is not None
    run_context = MemoryStore(
        root=profile_store_dir(authority), create=False
    ).load_direct("task-1/campus-wiki")
    assert run_only_text in [
        item.content for item in run_context.iter_items() if isinstance(item, Memory)
    ]

    switched = _subprocess_mem(
        tmp_path,
        "switch",
        "task-2/participant/proposal-workspace",
    )
    assert switched.returncode == 0, switched.stderr
    task_two_contexts = _subprocess_mem(tmp_path, "contexts")
    assert "task-2/advisor1" in task_two_contexts.stdout
    assert "GRANT  task-2/advisor1  READ + EXPORT" in task_two_contexts.stdout
    read_only_add = _subprocess_mem(
        tmp_path,
        "add",
        "This write must be rejected.",
        "--context",
        "task-2/advisor1",
    )
    assert read_only_add.returncode == 1
    assert "does not allow create access" in read_only_add.stderr

    task_two_query = resolve_granted_context_view(
        "task-2/proposal-submission-guidelines",
        attachment_name="task-2/participant/proposal-workspace",
        required_permission="QUERY",
    )
    task_two_source = load_authority_query_source(task_two_query, language="en")
    assert task_two_source.name == "task-2/proposal-submission-guidelines"
    assert task_two_source.content

    virtual_names, annotations = _granted_picker_views()
    assert "task-1/campus-wiki" in virtual_names
    assert "task-1/campus-wiki/route-changes" in virtual_names
    assert source_display_text(annotations["task-1/campus-wiki"]) == (
        "GRANT · READ + QUERY + EDIT + DELETE + EXPORT"
    )
    assert source_display_text(annotations["task-2/advisor1"]) == (
        "GRANT · READ + EXPORT"
    )
    assert (
        source_display_text(annotations["task-2/proposal-submission-guidelines"])
        == "GRANT · QUERY"
    )
    picker_state = _granted_picker_state()
    assert "task-2/advisor1" in picker_state.selectable_names
    assert "task-2/proposal-submission-guidelines" not in picker_state.selectable_names
    assert not any(
        name.startswith("task-2/proposal-submission-guidelines/")
        for name in virtual_names
    )

    profile_list = runner.invoke(app, ["profile", "list"])
    assert profile_list.exit_code == 0
    assert re.search(
        r"^    ├─ \* Participant\s+CURRENT profile=profile-view",
        profile_list.output,
        re.MULTILINE,
    )
    assert "profile-view-granted-memory" in profile_list.output
    assert "43 granted" in profile_list.output
    assert re.search(
        r"^  profile-view\s+STUDY\s+created=",
        profile_list.output,
        re.MULTILINE,
    )
    assert "authoring" in profile_list.output


def test_profile_inventory_counts_distinct_read_grants_without_alias_inflation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    authority_root = tmp_path / "authority-store"
    authority_store = MemoryStore(root=authority_root)
    knowledge = ops.init("knowledge")
    ops.add(knowledge, "One authority Memory.")
    authority_store.save(knowledge)
    child = ops.init("knowledge/child")
    ops.add(child, "A child Memory.")
    ops.add(child, "Another child Memory.")
    authority_store.save(child)
    query_resource = ops.init("query-resource")
    ops.add(query_resource, "A QUERY-only grant must not enter READ counts.")
    authority_store.save(query_resource)
    imported = runner.invoke(
        app,
        ["profile", "import", "authority", "--from", str(authority_root)],
    )
    assert imported.exit_code == 0, imported.output

    for public_name in ("shared-campus", "campus-alias"):
        create_authority_grant(
            authority_name="authority",
            grantee_name="authoring",
            resource_name="knowledge",
            attachment_name="authoring-notes",
            permissions=["READ"],
            public_name=public_name,
            recursive=True,
        )
    create_authority_grant(
        authority_name="authority",
        grantee_name="authoring",
        resource_name="query-resource",
        attachment_name="authoring-notes",
        permissions=["QUERY"],
        public_name="updates-query",
        recursive=True,
    )

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0, result.output
    authoring_line = next(
        line for line in result.output.splitlines() if line.startswith("* authoring")
    )
    assert "Contexts 1 owned + 2 granted" in authoring_line
    assert "Memories 0 owned + 3 granted" in authoring_line


def test_profile_import_rejects_a_symlinked_store_without_registering_it(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    source = tmp_path / "source"
    source.mkdir()
    (source / ".mem").symlink_to(isolated_store, target_is_directory=True)

    result = runner.invoke(
        app,
        ["profile", "import", "unsafe", "--from", str(source)],
    )

    assert result.exit_code == 1
    assert "real directory" in result.stderr
    assert not profile_registry_file().exists()


def test_mem_import_creates_clean_baseline_profile_without_run_history(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    source_root = tmp_path / "baseline-source"
    source_store = MemoryStore(root=source_root)
    context = ops.init("baseline")
    ops.add(context, "Stable imported Memory.")
    source_store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={"source": "authoring"},
            description="authoring history must not cross the import boundary",
        ),
    )
    source_store.set_current(context.name)
    (source_root / "query-sessions").mkdir()
    (source_root / "query-sessions" / "old.json").write_text(
        '{"private":"old transcript"}\n',
        encoding="utf-8",
    )
    (source_root / "impact-plan.json").write_text("{}\n", encoding="utf-8")
    (source_root / "ledger" / "context-events").mkdir(parents=True)
    (source_root / "ledger" / "context-events" / "old.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    source_digest = _tree_digest(source_root)

    result = runner.invoke(
        app,
        ["import", "fresh-baseline", "--from", str(source_root)],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Imported clean baseline Profile 'fresh-baseline'." in result.output
    assert (
        "history, sessions, caches, locks, and run logs were not imported"
        in result.output
    )
    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    profile = registry.by_name("fresh-baseline")
    assert profile is not None
    assert profile.source is not None
    assert profile.source["kind"] == "BASELINE_IMPORT"
    assert datetime.fromisoformat(profile.source["imported_at"]).utcoffset() is not None
    assert re.fullmatch(r"[0-9a-f]{64}", profile.source["baseline_sha256"])
    imported_root = profile_store_dir(profile)
    imported_store = MemoryStore(root=imported_root, create=False)
    imported_context = imported_store.load_direct("baseline")
    assert imported_context.uid == context.uid
    assert [item.content for item in imported_context.iter_items()] == [
        "Stable imported Memory."
    ]
    assert imported_store.current_context_name() == "baseline"
    assert imported_store.list_checkpoints("baseline") == []
    assert not (imported_root / "query-sessions").exists()
    assert not (imported_root / "impact-plan.json").exists()
    assert not (imported_root / "ledger").exists()
    assert _tree_digest(source_root) == source_digest


def test_profile_import_remains_an_explicit_archival_copy_with_history(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    source_root = tmp_path / "archive-source"
    source_store = MemoryStore(root=source_root)
    context = ops.init("archived")
    ops.add(context, "Memory with retained authoring history.")
    source_store.save(
        context,
        AutoCheckpoint(
            command="add",
            args={},
            description="history intentionally retained by archival import",
        ),
    )
    source_store.set_current(context.name)

    result = runner.invoke(
        app,
        ["profile", "import", "archival", "--from", str(source_root)],
    )

    assert result.exit_code == 0, result.stderr or result.output
    profile = load_profile_registry().by_name("archival")
    assert profile is not None
    imported_store = MemoryStore(root=profile_store_dir(profile), create=False)
    assert len(imported_store.list_checkpoints("archived")) == 1


def test_init_study_creates_isolated_participant_and_authority_profiles(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    monkeypatch.delenv("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG", raising=False)

    result = runner.invoke(
        app,
        ["init-study", "pilot-001", "--scenario", "legacy"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Initialized Study run 'pilot-001'." in result.output
    assert "Scenario: legacy" in result.output
    assert "Baseline Profile" not in result.output
    assert "Participant Profile: pilot-001" in result.output
    assert "Granted-memory Profile: pilot-001-granted-memory" in result.output
    assert (
        f"Provider config: {STUDY_PROVIDER_POLICY_VERSION} · locked · "
        f"sha256 {STUDY_PROVIDER_POLICY_DIGEST}" in result.output
    )
    assert "Contexts 65 · Memories 471 · current=practice" in result.output
    assert "Granted Contexts 43 · Granted Memories 625" in result.output
    assert "Active Profile: pilot-001" in result.output

    registry = load_profile_registry()
    assert registry.active.name == "pilot-001"
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        "pilot-001",
        "pilot-001-granted-memory",
    ]
    assert len(registry.grants) == 8
    assert study_profile_groups(registry.profiles) == ()
    copied = registry.by_name("pilot-001")
    authority = registry.by_name("pilot-001-granted-memory")
    assert (
        copied is not None
        and authority is not None
        and copied.source is not None
        and authority.source is not None
    )
    assert copied.source["kind"] == "STUDY_RUN"
    assert authority.source["kind"] == "STUDY_RUN_GRANTED_MEMORY"
    assert copied.source["study_uid"] == authority.source["study_uid"]
    assert copied.source["baseline_profile_uid"] == LEGACY_BASELINE_UID
    assert copied.source["baseline_profile_name"] == "legacy"
    assert re.fullmatch(r"[0-9a-f]{64}", copied.source["baseline_sha256"])
    assert (
        copied.source["provider_policy_version"]
        == authority.source["provider_policy_version"]
        == STUDY_PROVIDER_POLICY_VERSION
    )
    assert (
        copied.source["provider_policy_digest"]
        == authority.source["provider_policy_digest"]
        == STUDY_PROVIDER_POLICY_DIGEST
    )
    copied_root = profile_store_dir(copied)
    authority_root = profile_store_dir(authority)
    assert copied_root != authority_root
    participant_actions = StudyActionLedger(copied).list()
    authority_actions = StudyActionLedger(authority).list()
    assert [event.action for event in reversed(participant_actions)] == [
        "STUDY_CREATED",
        "PROFILE_ENTERED",
    ]
    assert [event.action for event in authority_actions] == ["STUDY_CREATED"]
    assert participant_actions[0].attempt_uid == authority_actions[0].attempt_uid

    profile_list = _subprocess_mem(tmp_path, "profile", "list")
    assert profile_list.returncode == 0, profile_list.stderr
    assert re.search(
        r"^  pilot-001\s+STUDY\s+created=",
        profile_list.stdout,
        re.MULTILINE,
    )
    assert "Participant" in profile_list.stdout
    assert "Granted memory" in profile_list.stdout
    actions = _subprocess_mem(tmp_path, "log", "--actions")
    assert actions.returncode == 0, actions.stderr
    assert "Study actions · recent first" in actions.stdout
    assert "STUDY_CREATED" in actions.stdout
    assert "COMMAND_STARTED" in actions.stdout
    assert "COMMAND_ENTERED" in actions.stdout
    assert "command=mem profile list" in actions.stdout
    assert "private" not in actions.stdout

    copied_store = MemoryStore(root=copied_root, create=False)
    authority_store = MemoryStore(root=authority_root, create=False)
    assert len(copied_store.list_context_names()) == 65
    assert len(authority_store.list_context_names()) == 75
    assert copied_store.current_context_name() == "practice"
    assert authority_store.current_context_name() == "task-1/campus-wiki"
    assert "task-1/campus-wiki" in authority_store.list_context_names()
    assert "practice" in copied_store.list_context_names()
    assert "practice/description" in copied_store.list_context_names()
    assert "practice/source" in copied_store.list_context_names()
    assert "practice" not in authority_store.list_context_names()
    practice = copied_store.load_direct("practice/description")
    practice_memories = [
        item for item in practice.iter_items() if isinstance(item, Memory)
    ]
    assert [item.content for item in practice_memories] == [
        profiles_module._STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
        profiles_module._STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
        profiles_module._STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT,
    ]
    practice_source = copied_store.load_direct("practice/source")
    source_memories = [
        item for item in practice_source.iter_items() if isinstance(item, Memory)
    ]
    assert [item.content for item in source_memories] == list(
        profiles_module._STUDY_PRACTICE_SOURCE_CONTENTS
    )
    public_guidance = authority_store.load_direct(
        "task-3/remote/government/healthcare-agent/info-request/"
        "transmission-guidance/public-guidance"
    )
    public_memories = [
        item for item in public_guidance.iter_items() if isinstance(item, Memory)
    ]
    assert len(public_memories) == 25
    assert public_memories[0].content.startswith(
        "This Context is a synthetic, publicly distributable summary"
    )
    assert public_memories[-1].content.endswith("that the user approved transmission.")
    assert not any(
        "official-guidance" in name for name in authority_store.list_context_names()
    )
    assert not any(copied_root.rglob("checkpoints/*.json"))
    assert not any(authority_root.rglob("checkpoints/*.json"))


def test_study_practice_source_matches_instruction_refinement_topic():
    overview = profiles_module._STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT
    situation = profiles_module._STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT
    source_memories = profiles_module._STUDY_PRACTICE_SOURCE_CONTENTS
    task = profiles_module._STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT

    assert source_memories == (
        "When I ask “How does this read?”, I really want an opinion, so don't edit "
        "the draft immediately; first check the sentence order and paragraph "
        "division.",
        "If I later ask for polishing, preserve the overall strucutre and "
        "citation-needed markers, and change only wording that causes a problem.",
        "When I ask to change one expression, leave almost everything else as it "
        "is, including technical or project-specific terms that I selected. Um... "
        "for example, use distribute, not divide, when material is absorbed into "
        "two parts.",
        "If a passage is supposed to make four points, keep all four while removing "
        "parts that are too redundent and stating repeated content only once.",
        "When the draft has to fit a shorter fixed limit, aim to cut around 20–30% "
        "from redundant or unnecessary material.",
        "But don't shorten sentences so aggressively that a claim sounds more "
        "categorical; keep enough wording to preserve its original strength and "
        "conditions.",
        "If the next idea is merely related and does not broaden the scope, don't "
        "use More "
        "broadly; use In relation to this or another accurate connector without "
        "adding a new claim merely to make two paragraphs connect.",
        "For any titlle about interaction with AI agent memory, keep the exact "
        "terminology and intended words: use interaction and management and AI "
        "agent memory rather than agent memory.",
        "By default, format a document title in sentence case rather than title "
        "case. An explicitly named style guide may override only that capitalization "
        "default; always keep for whenever it is part of the intended wording.",
        "If titles of works use quotation marks in some places and italics in "
        "others, make them consistently italic throughout the document by default; "
        "an explicitly named style guide may override only this work-title format.",
        "When I say that content looks wrong, find accurate information before "
        "proposing a correction by reading the original paper, book, or guide, not "
        "only an abstract or a short snippet.",
        "Before adding or reusing citations and refferences, verify that each source "
        "exists and supports the exact claim after reviewing the complete source. "
        "Don't invent quotations or evidence or overstate an author's contribution "
        "or a paper's status. If I asked only for review, report a verification "
        "problem first instead of silently rewriting the draft.",
    )
    assert overview.startswith("memcommit is a research prototype")
    assert "MemLab" not in overview
    assert situation.startswith("SITUATION ·")
    assert "MemLab" not in situation
    assert task.startswith("TASK ·")
    assert "MemLab" not in task
    assert "Each newline-separated editing note" in situation
    assert "stored as its own Memory" in situation
    assert "rough wording, and typos" in situation
    assert "without performing the requested edits" in task
    assert "changing the intended meaning" in task
    assert "use it to atomize the notes" in task
    assert "preview its Impact" not in task


def test_init_study_without_name_generates_unique_timestamped_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)

    first = runner.invoke(app, ["init-study"])
    second = runner.invoke(app, ["init-study"])

    assert first.exit_code == 0, first.stderr or first.output
    assert second.exit_code == 0, second.stderr or second.output
    names = [
        profile.name
        for profile in load_profile_registry().profiles
        if profile.name != "authoring"
    ]
    assert len(names) == 4
    participant_names = [name for name in names if not name.endswith("-granted-memory")]
    assert len(participant_names) == 2
    assert participant_names[0] != participant_names[1]
    assert all(
        re.fullmatch(r"study-\d{8}T\d{6}Z-[0-9a-f]{8}", name)
        for name in participant_names
    )
    assert {f"{name}-granted-memory" for name in participant_names}.issubset(names)
    assert study_profile_groups(load_profile_registry().profiles) == ()


def test_init_study_without_name_uses_the_tty_edited_default(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    defaults: list[str] = []

    monkeypatch.setattr(
        "memcommit.commands.init_study.command._is_interactive_terminal",
        lambda: True,
    )

    def choose(default: str) -> str:
        defaults.append(default)
        return "edited-study-name"

    monkeypatch.setattr(
        "memcommit.commands.init_study.command.choose_study_profile_name",
        choose,
    )

    result = runner.invoke(app, ["init-study"])

    assert result.exit_code == 0, result.stderr or result.output
    assert re.fullmatch(r"study-\d{8}T\d{6}Z-[0-9a-f]{8}", defaults[0])
    assert "Initialized Study run 'edited-study-name'." in result.output
    registry = load_profile_registry()
    assert registry.by_name("edited-study-name") is not None
    assert registry.by_name("edited-study-name-granted-memory") is not None


def test_profile_inventory_shows_run_pair_and_real_granted_counts(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    assert (
        runner.invoke(
            app,
            ["init-study", "pilot-002", "--scenario", "legacy"],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0, result.output
    profile_line = next(
        line
        for line in result.output.splitlines()
        if "Participant" in line and "profile=pilot-002 " in line
    )
    assert "Contexts 65 owned + 43 granted" in profile_line
    assert "Memories 471 owned + 625 granted" in profile_line
    authority_line = next(
        line
        for line in result.output.splitlines()
        if "pilot-002-granted-memory" in line
    )
    assert "Contexts 75 owned + 0 granted" in authority_line
    assert "Memories 853 owned + 0 granted" in authority_line
    assert re.search(
        r"^  pilot-002\s+STUDY\s+created=",
        result.output,
        re.MULTILINE,
    )
    assert "pilot-002-task-" not in result.output
    assert "Authority 1" not in result.output

    inventory_rows = [
        line
        for line in result.output.splitlines()
        if any(
            token in line
            for token in (
                " authoring",
                " pilot-002 ",
                " Participant ",
                " Granted memory ",
            )
        )
    ]
    action_columns = [
        next(
            line.index(token) for token in ("CURRENT", "USE", "STUDY") if token in line
        )
        for line in inventory_rows
    ]
    assert len(set(action_columns)) == 1
    assert profile_line.startswith("    ├─ * Participant")
    assert authority_line.startswith("    └─   Granted memory")

    colored = runner.invoke(app, ["profile", "list"], color=True)
    plain = runner.invoke(app, ["profile", "list"])
    assert colored.exit_code == plain.exit_code == 0
    assert click.unstyle(colored.output) == plain.output
    for token, role in (
        ("CURRENT", SemanticColorRole.PROFILE_CURRENT),
        ("USE", SemanticColorRole.PROFILE_USE),
        ("STUDY", SemanticColorRole.PROFILE_STUDY),
    ):
        assert (
            click.style(
                token,
                fg=semantic_color_rgb(role),
                bold=True,
            )
            in colored.output
        )


def test_initialized_study_picker_shows_participant_and_authority_profiles(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    initialized = runner.invoke(
        app,
        ["init-study", "pilot-picker", "--scenario", "legacy"],
    )
    assert initialized.exit_code == 0, initialized.output
    observed: list[tuple[str, str | None]] = []

    def select(entries, *, current, registry_generation, apply_removal):
        assert current == "pilot-picker"
        assert registry_generation >= 1
        assert callable(apply_removal)
        observed.extend((entry.name, entry.study_role) for entry in entries)
        return "pilot-picker"

    monkeypatch.setattr(
        "memcommit.commands.profile.command._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.command.choose_profile",
        select,
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert observed == [
        ("authoring", None),
        ("pilot-picker", "PARTICIPANT"),
        ("pilot-picker-granted-memory", "GRANTED_MEMORY"),
    ]
    assert load_profile_registry().active.name == "pilot-picker"


def test_init_study_name_collision_preserves_existing_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    assert (
        runner.invoke(
            app,
            ["init-study", "pilot-003", "--scenario", "legacy"],
        ).exit_code
        == 0
    )
    before = load_profile_registry()
    before_roots = tuple(profile_store_dir(profile) for profile in before.profiles[1:])

    result = runner.invoke(
        app,
        ["init-study", "pilot-003", "--scenario", "legacy"],
    )

    assert result.exit_code == 1
    assert "Profile 'pilot-003' already exists" in result.stderr
    after = load_profile_registry()
    assert after == before
    assert (
        tuple(profile_store_dir(profile) for profile in after.profiles[1:])
        == before_roots
    )
    assert all(root.is_dir() for root in before_roots)


def test_init_study_preserves_a_store_after_visible_registry_replacement(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    real_write_registry = init_study_publication_module._write_registry

    def fail_after_visible_replace(updated):
        real_write_registry(updated)
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(
        init_study_publication_module,
        "_write_registry",
        fail_after_visible_replace,
    )

    result = runner.invoke(
        app,
        ["init-study", "durability-visible", "--scenario", "legacy"],
    )

    assert result.exit_code == 1
    assert "was published" in result.stderr
    assert "remains registered" in result.stderr
    registry = load_profile_registry()
    published = registry.by_name("durability-visible")
    authority = registry.by_name("durability-visible-granted-memory")
    assert published is not None and authority is not None
    assert profile_store_dir(published).is_dir()
    assert profile_store_dir(authority).is_dir()
    assert (
        len(
            [
                grant
                for grant in registry.grants
                if grant.grantee_profile_uid == published.uid
            ]
        )
        == 8
    )
    assert registry.active.name == "durability-visible"


def test_repeated_init_study_run_pairs_are_independent(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)

    first = runner.invoke(
        app,
        ["init-study", "pilot-v2-a", "--scenario", "legacy"],
    )
    second = runner.invoke(
        app,
        ["init-study", "pilot-v2-b", "--scenario", "legacy"],
    )

    assert first.exit_code == 0, first.stderr or first.output
    assert second.exit_code == 0, second.stderr or second.output
    registry = load_profile_registry()
    first_profile = registry.by_name("pilot-v2-a")
    first_authority = registry.by_name("pilot-v2-a-granted-memory")
    second_profile = registry.by_name("pilot-v2-b")
    second_authority = registry.by_name("pilot-v2-b-granted-memory")
    assert (
        first_profile is not None
        and first_authority is not None
        and second_profile is not None
        and second_authority is not None
    )
    assert (
        len(
            {
                first_profile.uid,
                first_authority.uid,
                second_profile.uid,
                second_authority.uid,
            }
        )
        == 4
    )
    assert first_profile.source is not None and second_profile.source is not None
    assert (
        first_profile.source["baseline_sha256"]
        == second_profile.source["baseline_sha256"]
        == LEGACY_DIGEST
    )
    assert len(registry.grants) == 16
    assert study_profile_groups(registry.profiles) == ()

    first_store = MemoryStore(root=profile_store_dir(first_authority), create=False)
    second_store = MemoryStore(root=profile_store_dir(second_authority), create=False)
    assert (
        first_store.load_direct("task-1").uid == second_store.load_direct("task-1").uid
    )
    first_context = first_store.load_direct("task-1/campus-wiki")
    added = ops.add(first_context, "Only the first run authority copy changes.")
    first_store.save(first_context)
    assert added.uid in first_store.load_direct("task-1/campus-wiki").memories
    assert added.uid not in second_store.load_direct("task-1/campus-wiki").memories

    inventory = runner.invoke(app, ["profile", "list"])
    assert inventory.exit_code == 0, inventory.output
    assert "pilot-v2-a" in inventory.output
    assert "pilot-v2-b" in inventory.output
    assert "pilot-v2-a-task-" not in inventory.output

    selected = runner.invoke(app, ["profile", "use", "pilot-v2-a"])
    assert selected.exit_code == 0, selected.output
    current_inventory = runner.invoke(app, ["profile", "list"])
    assert current_inventory.exit_code == 0, current_inventory.output
    assert any(
        "* Participant" in line and "profile=pilot-v2-a " in line
        for line in current_inventory.output.splitlines()
    )


def test_archive_legacy_study_preserves_stores_and_allows_merged_replacement(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    study_uid, profiles, grants = _install_legacy_split_study("legacy-run")
    before = load_profile_registry()
    roots = {profile.uid: profile_store_dir(profile) for profile in profiles}
    digests = {uid: _tree_digest(root) for uid, root in roots.items()}

    archived = runner.invoke(
        app,
        ["profile", "archive-study", "legacy-run"],
    )

    assert archived.exit_code == 0, archived.stderr or archived.output
    assert "Archived legacy Study 'legacy-run'." in archived.output
    assert "Profiles removed from selector: 6" in archived.output
    assert "Internal grants recorded in archive: 7" in archived.output
    assert "No Memory data was moved or deleted." in archived.output
    after = load_profile_registry()
    archived_uids = {profile.uid for profile in profiles}
    assert after.generation == before.generation + 1
    assert after.active_uid == before.active_uid
    assert all(profile.uid not in archived_uids for profile in after.profiles)
    assert all(grant.uid not in {item.uid for item in grants} for grant in after.grants)
    assert study_profile_groups(after.profiles) == ()

    manifest_path = _legacy_archive_manifest(study_uid)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "LEGACY_STUDY_ARCHIVE"
    assert manifest["source_registry_generation"] == before.generation
    assert manifest["study"] == {
        "uid": study_uid,
        "name": "legacy-run",
        "created_at": "2026-08-03T18:50:46.360105+00:00",
    }
    assert manifest["profiles"] == [profile.to_dict() for profile in profiles]
    assert manifest["grants"] == [grant.to_dict() for grant in grants]
    assert manifest["stores"] == [
        {
            "profile_uid": profile.uid,
            "control_relative_path": f"stores/{profile.uid}",
        }
        for profile in profiles
    ]
    assert all(root.is_dir() for root in roots.values())
    assert {uid: _tree_digest(root) for uid, root in roots.items()} == digests

    initialized = runner.invoke(
        app,
        ["init-study", "legacy-run", "--scenario", "legacy"],
    )
    assert initialized.exit_code == 0, initialized.stderr or initialized.output
    current = load_profile_registry()
    replacement = current.by_name("legacy-run")
    assert replacement is not None
    assert replacement.uid not in archived_uids
    assert study_profile_groups(current.profiles) == ()
    inventory = runner.invoke(app, ["profile", "list"])
    assert inventory.exit_code == 0, inventory.output
    assert "STUDY legacy-run" not in inventory.output
    assert "legacy-run-task-" not in inventory.output
    assert "legacy-run" in inventory.output


def test_archive_legacy_study_rejects_an_active_member(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    registry = load_profile_registry()
    profiles_module._write_registry(
        ProfileRegistry(
            generation=registry.generation + 1,
            active_uid=profiles[0].uid,
            profiles=registry.profiles,
            grants=registry.grants,
        )
    )
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "contains the active Profile" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert not _legacy_archive_manifest(study_uid).exists()
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_resumes_a_prepared_manifest(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, grants = _install_legacy_split_study()
    registry = load_profile_registry()
    group = study_profile_groups(registry.profiles)[0]
    record = profiles_module._legacy_study_archive_record(
        registry,
        group,
        profiles,
        grants,
    )
    destination = _legacy_archive_manifest(study_uid).parent
    manifest_path = profiles_module._publish_legacy_study_archive(
        destination,
        record,
    )
    prepared = manifest_path.read_bytes()
    digests = {
        profile.uid: _tree_digest(profile_store_dir(profile)) for profile in profiles
    }

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 0, result.stderr or result.output
    assert manifest_path.read_bytes() == prepared
    assert tuple(path.name for path in destination.iterdir()) == ("manifest.json",)
    current = load_profile_registry()
    archived_uids = {profile.uid for profile in profiles}
    assert current.generation == registry.generation + 1
    assert current.active_uid == registry.active_uid
    assert all(profile.uid not in archived_uids for profile in current.profiles)
    assert all(
        grant.uid not in {item.uid for item in grants} for grant in current.grants
    )
    assert {
        profile.uid: _tree_digest(profile_store_dir(profile)) for profile in profiles
    } == digests


def test_archive_legacy_study_rejects_a_modified_prepared_manifest(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, grants = _install_legacy_split_study()
    registry = load_profile_registry()
    group = study_profile_groups(registry.profiles)[0]
    destination = _legacy_archive_manifest(study_uid).parent
    manifest_path = profiles_module._publish_legacy_study_archive(
        destination,
        profiles_module._legacy_study_archive_record(
            registry,
            group,
            profiles,
            grants,
        ),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stores"][0]["control_relative_path"] = "stores/different"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    modified = manifest_path.read_bytes()
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "destination contains different records" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert manifest_path.read_bytes() == modified
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_keeps_a_reused_manifest_on_registry_failure(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, grants = _install_legacy_split_study()
    registry = load_profile_registry()
    group = study_profile_groups(registry.profiles)[0]
    destination = _legacy_archive_manifest(study_uid).parent
    manifest_path = profiles_module._publish_legacy_study_archive(
        destination,
        profiles_module._legacy_study_archive_record(
            registry,
            group,
            profiles,
            grants,
        ),
    )
    prepared = manifest_path.read_bytes()

    def fail_registry_write(_registry):
        raise OSError("simulated resumed registry failure")

    monkeypatch.setattr(profiles_module, "_write_registry", fail_registry_write)
    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "was not detached" in result.stderr
    assert "prepared manifest remains for retry" in result.stderr
    assert load_profile_registry() == registry
    assert manifest_path.read_bytes() == prepared
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_rejects_a_missing_member_store(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    missing_root = profile_store_dir(profiles[0])
    backup = missing_root.with_name(missing_root.name + ".missing")
    missing_digest = _tree_digest(missing_root)
    healthy_digests = {
        profile.uid: _tree_digest(profile_store_dir(profile))
        for profile in profiles[1:]
    }
    missing_root.rename(backup)
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "MemoryStore must be a real directory" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert not _legacy_archive_manifest(study_uid).exists()
    assert not missing_root.exists()
    assert backup.is_dir()
    assert _tree_digest(backup) == missing_digest
    assert {
        profile.uid: _tree_digest(profile_store_dir(profile))
        for profile in profiles[1:]
    } == healthy_digests


def test_archive_legacy_study_rejects_a_symlink_member_store(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    unsafe_root = profile_store_dir(profiles[0])
    backup = unsafe_root.with_name(unsafe_root.name + ".backup")
    digest = _tree_digest(unsafe_root)
    unsafe_root.rename(backup)
    unsafe_root.symlink_to(backup, target_is_directory=True)
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "MemoryStore must be a real directory" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert not _legacy_archive_manifest(study_uid).exists()
    assert unsafe_root.is_symlink()
    assert backup.is_dir()
    assert _tree_digest(backup) == digest
    assert all(profile_store_dir(profile).is_dir() for profile in profiles[1:])


def test_archive_legacy_study_does_not_target_an_ordinary_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    registry = load_profile_registry()
    profiles_module._write_registry(
        ProfileRegistry(
            generation=1,
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=registry.grants,
        )
    )
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "archive-study", "authoring"],
    )

    assert result.exit_code == 1
    assert "Legacy Study 'authoring' does not exist" in result.stderr
    assert profile_registry_file().read_bytes() == before


@pytest.mark.parametrize("direction", ["outgoing", "incoming"])
def test_archive_legacy_study_rejects_cross_boundary_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
    direction,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    task_profile = next(
        profile for profile in profiles if profile.name == "legacy-run-task-1"
    )
    authority_profile = next(
        profile
        for profile in profiles
        if profile.name == "legacy-run-task-1-campus-authority"
    )
    if direction == "outgoing":
        create_authority_grant(
            authority_name=authority_profile.name,
            grantee_name="authoring",
            resource_name="authority-root",
            attachment_name="authoring-notes",
            permissions=["READ"],
            public_name="external-legacy-view",
        )
    else:
        create_authority_grant(
            authority_name="authoring",
            grantee_name=task_profile.name,
            resource_name="authoring-notes",
            attachment_name="task-root",
            permissions=["READ"],
            public_name="external-authoring-view",
        )
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "crossing its Profile boundary" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert not _legacy_archive_manifest(study_uid).exists()
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_rejects_an_occupied_archive_destination(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    destination = _legacy_archive_manifest(study_uid).parent
    destination.mkdir(parents=True)
    sentinel = destination / "keep.txt"
    sentinel.write_text("existing archive\n", encoding="utf-8")
    before = profile_registry_file().read_bytes()

    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "archive destination is occupied" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert sentinel.read_text(encoding="utf-8") == "existing archive\n"
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_keeps_manifest_when_registry_write_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, _grants = _install_legacy_split_study()
    before = profile_registry_file().read_bytes()

    def fail_registry_write(_registry):
        raise OSError("simulated registry failure")

    monkeypatch.setattr(profiles_module, "_write_registry", fail_registry_write)
    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "was not detached" in result.stderr
    assert "prepared manifest remains for retry" in result.stderr
    assert profile_registry_file().read_bytes() == before
    assert _legacy_archive_manifest(study_uid).is_file()
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)


def test_archive_legacy_study_keeps_visible_commit_after_fsync_failure(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    study_uid, profiles, grants = _install_legacy_split_study()
    real_write_registry = profiles_module._write_registry

    def fail_after_visible_replace(updated):
        real_write_registry(updated)
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(
        profiles_module,
        "_write_registry",
        fail_after_visible_replace,
    )
    result = runner.invoke(app, ["profile", "archive-study", "legacy-run"])

    assert result.exit_code == 1
    assert "remains archived" in result.stderr
    registry = load_profile_registry()
    archived_uids = {profile.uid for profile in profiles}
    assert all(profile.uid not in archived_uids for profile in registry.profiles)
    assert all(
        grant.uid not in {item.uid for item in grants} for grant in registry.grants
    )
    assert _legacy_archive_manifest(study_uid).is_file()
    assert all(profile_store_dir(profile).is_dir() for profile in profiles)
