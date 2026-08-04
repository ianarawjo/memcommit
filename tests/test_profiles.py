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

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.profiles as profiles_module
from memcommit.cli import app
from memcommit.commands.switch import _granted_picker_state, _granted_picker_views
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.profile_config import (
    GRANT_RESOURCE_CONTEXT_TREE,
    AuthorityGrant,
    GrantContextBinding,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    ProfileError,
    STUDY_BASELINE_PROFILE_NAME,
    create_authority_grant,
    resolve_granted_context_view,
    study_profile_groups,
)
from memcommit.query_sessions import load_authority_query_catalog
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
    store.save(ops.init("authoring-notes"))
    store.set_current("authoring-notes")


def _bootstrap_study_baseline(bundles: Path):
    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )
    assert result.exit_code == 0, result.stderr or result.output
    return result


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
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    assert (
        runner.invoke(
            app,
            ["profile", "import-study", "--from", str(bundles)],
        ).exit_code
        == 0
    )
    observed: dict[str, object] = {}

    def select(entries, *, current):
        observed["names"] = [entry.name for entry in entries]
        observed["current"] = current
        return STUDY_BASELINE_PROFILE_NAME

    monkeypatch.setattr(
        "memcommit.commands.profile._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        select,
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert "Selected profile 'study-baseline'." in result.output
    assert observed == {
        "names": ["authoring", STUDY_BASELINE_PROFILE_NAME],
        "current": "authoring",
    }
    assert load_profile_registry().active.name == STUDY_BASELINE_PROFILE_NAME


def test_bare_profile_cancel_preserves_active_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    monkeypatch.setattr(
        "memcommit.commands.profile._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        lambda entries, *, current: None,
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
        "memcommit.commands.profile._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        lambda entries, *, current: "missing",
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
        "memcommit.commands.profile.choose_profile",
        unexpected_picker,
    )

    result = runner.invoke(app, ["profile", "use", "authoring"])

    assert result.exit_code == 0
    assert "Already using profile 'authoring'." in result.output
    assert not profile_registry_file().exists()


def test_import_study_registers_one_editable_baseline_and_keeps_authoring(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    source_digest = _tree_digest(bundles)
    authoring_digest = _tree_digest(isolated_store)

    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )

    assert result.exit_code == 0, result.output
    assert "Imported editable Study baseline." in result.output
    assert "study-baseline: Contexts 130 owned + 0 granted" in result.output
    assert "Memories 1278 owned + 0 granted" in result.output
    assert _tree_digest(bundles) == source_digest
    assert _tree_digest(isolated_store) == authoring_digest

    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        STUDY_BASELINE_PROFILE_NAME,
    ]
    assert registry.grants == ()
    baseline = registry.profiles[1]
    root = profile_store_dir(baseline)
    assert root.is_dir()
    store = MemoryStore(root=root, create=False)
    names = set(store.list_context_names())
    assert all(
        "/".join(name.split("/")[:index]) in names
        for name in names
        for index in range(1, len(name.split("/")))
    )
    assert store.current_context_name() == "task-1"
    assert {
        "task-1",
        "task-1/participant",
        "task-2",
        "task-2/participant",
        "task-3",
        "granted-memory",
        "granted-memory/task-1",
        "granted-memory/task-2",
        "granted-memory/task-3",
        "granted-memory/task-3/government",
        "granted-memory/task-3/government/healthcare-agent",
    }.issubset(names)
    assert "task-1/participant/construction-updates" in names
    assert "granted-memory/task-1/campus-wiki" in names
    assert "task-2/participant/proposal-workspace" in names
    assert "granted-memory/task-2/advisor1" in names
    assert "task-3/personal-memory" in names
    assert "task-3/personal-memory/2024" in names
    assert "task-3/personal-memory/2024/01" in names
    assert "task-3/personal-memory/2024-01" not in names
    assert "granted-memory/task-3/guardrails" in names

    selected = runner.invoke(
        app,
        ["profile", "use", STUDY_BASELINE_PROFILE_NAME],
    )
    assert selected.exit_code == 0, selected.output
    recursive = _subprocess_mem(tmp_path, "ls", "-R", "task-1")
    assert recursive.returncode == 0, recursive.stderr
    assert "task-1/participant" in recursive.stdout
    assert "task-1/participant/construction-updates" in recursive.stdout
    assert "The indoor route that passed through" in recursive.stdout

    leaf = _subprocess_mem(
        tmp_path,
        "switch",
        "task-1/participant/construction-updates/route-changes",
    )
    first_parent = _subprocess_mem(tmp_path, "switch", "..")
    second_parent = _subprocess_mem(tmp_path, "switch", "..")
    assert leaf.returncode == 0, leaf.stderr
    assert first_parent.returncode == 0, first_parent.stderr
    assert second_parent.returncode == 0, second_parent.stderr
    assert "task-1/participant'" in second_parent.stdout


def test_profile_use_selects_the_initialized_complete_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    initialized = runner.invoke(app, ["init-study", "profile-view"])
    assert initialized.exit_code == 0, initialized.stderr or initialized.output

    selected = runner.invoke(app, ["profile", "use", "profile-view"])

    assert selected.exit_code == 0, selected.output
    assert "Selected profile 'profile-view'." in selected.output
    assert "Contexts 47 owned + 52 granted" in selected.output
    assert "Memories 375 owned + 675 granted" in selected.output
    contexts = _subprocess_mem(tmp_path, "contexts")
    assert contexts.returncode == 0, contexts.stderr
    assert "* task-1" in contexts.stdout
    assert "task-1/participant/construction-updates" in contexts.stdout
    assert "task-1/campus-wiki" in contexts.stdout
    assert (
        "[view create,read,update,delete,query from profile-view-granted-memory]"
        in contexts.stdout
    )
    assert "task-1/campus-wiki/construction-details" in contexts.stdout
    assert (
        "[view query,session_log from profile-view-granted-memory]" in contexts.stdout
    )
    assert "authoring-notes" not in contexts.stdout

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
    query_catalog = load_authority_query_catalog(query_view, language="en")
    assert len(query_catalog) == 78
    assert all(entry.placeholder_lines for entry in query_catalog)

    wiki_query_view = resolve_granted_context_view(
        "task-1/campus-wiki",
        attachment_name="task-1/participant/construction-updates",
        required_permission="QUERY",
    )
    assert len(load_authority_query_catalog(wiki_query_view, language="en")) == 300
    with pytest.raises(ProfileError, match="does not allow session_log access"):
        resolve_granted_context_view(
            "task-1/campus-wiki",
            attachment_name="task-1/participant/construction-updates",
            required_permission="SESSION_LOG",
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
    baseline = registry.by_name("study-baseline")
    authority = registry.by_name("profile-view-granted-memory")
    assert baseline is not None and authority is not None
    run_context = MemoryStore(
        root=profile_store_dir(authority), create=False
    ).load_direct("task-1/campus-wiki")
    baseline_context = MemoryStore(
        root=profile_store_dir(baseline), create=False
    ).load_direct("granted-memory/task-1/campus-wiki")
    assert run_only_text in [
        item.content for item in run_context.iter_items() if isinstance(item, Memory)
    ]
    assert run_only_text not in [
        item.content
        for item in baseline_context.iter_items()
        if isinstance(item, Memory)
    ]

    switched = _subprocess_mem(
        tmp_path,
        "switch",
        "task-2/participant/proposal-workspace",
    )
    assert switched.returncode == 0, switched.stderr
    task_two_contexts = _subprocess_mem(tmp_path, "contexts")
    assert "task-2/advisor1" in task_two_contexts.stdout
    assert "[view read from profile-view-granted-memory]" in task_two_contexts.stdout
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
    assert len(load_authority_query_catalog(task_two_query, language="en")) == 75

    virtual_names, annotations = _granted_picker_views()
    assert "task-1/campus-wiki" in virtual_names
    assert "task-1/campus-wiki/route-changes" in virtual_names
    assert annotations["task-1/campus-wiki"] == (
        "[grant CREATE + READ + UPDATE + DELETE + QUERY]"
    )
    assert annotations["task-2/advisor1"] == "[grant READ]"
    assert annotations["task-2/proposal-submission-guidelines"] == (
        "[grant QUERY + SESSION_LOG]"
    )
    picker_state = _granted_picker_state()
    assert "task-2/advisor1" in picker_state.selectable_names
    assert (
        "task-2/proposal-submission-guidelines"
        not in picker_state.selectable_names
    )
    assert not any(
        name.startswith("task-2/proposal-submission-guidelines/")
        for name in virtual_names
    )

    profile_list = runner.invoke(app, ["profile", "list"])
    assert profile_list.exit_code == 0
    assert "* profile-view" in profile_list.output
    assert "profile-view-granted-memory" in profile_list.output
    assert "52 granted" in profile_list.output
    assert "STUDY profile-view" not in profile_list.output
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


def test_live_baseline_edits_are_copied_into_the_next_initialized_study(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    source_digest = _tree_digest(bundles / "task-1")
    _bootstrap_study_baseline(bundles)
    assert (
        runner.invoke(app, ["profile", "use", STUDY_BASELINE_PROFILE_NAME]).exit_code
        == 0
    )
    switched = _subprocess_mem(
        tmp_path,
        "switch",
        "task-1/participant/construction-updates",
    )
    assert switched.returncode == 0, switched.stderr

    added = _subprocess_mem(tmp_path, "add", "A locally revised study Memory.")
    assert added.returncode == 0, added.stderr
    initialized = runner.invoke(app, ["init-study", "edited-baseline"])
    assert initialized.exit_code == 0, initialized.stderr or initialized.output
    assert runner.invoke(app, ["profile", "use", "edited-baseline"]).exit_code == 0
    listing = _subprocess_mem(tmp_path, "ls")

    assert listing.returncode == 0, listing.stderr
    assert "A locally revised study Memory." in listing.stdout
    assert _tree_digest(bundles / "task-1") == source_digest


def test_study_import_is_all_or_nothing_when_one_manifest_is_invalid(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    manifest_path = bundles / "task-2" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ordinary_count"] += 1
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )

    assert result.exit_code == 1
    assert "Task 2 manifest counts are invalid" in result.stderr
    assert not profile_registry_file().exists()
    assert not list((tmp_path / ".mem-profiles" / "stores").glob("[0-9a-f]*"))
    assert MemoryStore().list_context_names() == ["authoring-notes"]


def test_study_import_rejects_content_that_no_longer_matches_the_manifest(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    manifest = json.loads(
        (bundles / "task-1" / "manifest.json").read_text(encoding="utf-8")
    )
    entry = next(
        item
        for item in manifest["entries"]
        if item["owner_profile"] == "task-1-campus-authority"
    )
    owner = next(
        profile
        for profile in manifest["profiles"]
        if profile["profile_name"] == entry["owner_profile"]
    )
    context_path = (
        bundles
        / "task-1"
        / owner["store_path"]
        / "contexts"
        / entry["runtime_context"]
        / "context.json"
    )
    context = json.loads(context_path.read_text(encoding="utf-8"))
    context["memories"][entry["memory_uid"]]["content"] = "Tampered content."
    context_path.write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )

    assert result.exit_code == 1
    assert "manifest content hash does not match" in result.stderr
    assert not profile_registry_file().exists()


def test_study_import_rejects_a_grant_identity_before_publishing_any_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    manifest_path = bundles / "task-1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["grant_templates"][0]["authority_context"]["uid"] = (
        "00000000-0000-0000-0000-000000000099"
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )

    assert result.exit_code == 1
    assert "identity does not match its store" in result.stderr
    assert not profile_registry_file().exists()
    stores = tmp_path / ".mem-profiles" / "stores"
    assert not stores.exists() or not list(stores.iterdir())


def test_study_import_rolls_back_all_six_stores_when_registry_publish_fails(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)

    def fail_registry_write(_registry):
        raise OSError("simulated registry failure")

    monkeypatch.setattr("memcommit.profiles._write_registry", fail_registry_write)
    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )

    assert result.exit_code == 1
    assert "simulated registry failure" in result.stderr
    assert not profile_registry_file().exists()
    stores = tmp_path / ".mem-profiles" / "stores"
    assert stores.is_dir()
    assert not list(stores.iterdir())


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
    bundle_root = tmp_path / "bundles"
    build_all_study_bundles(bundle_root)
    assert any(bundle_root.rglob("checkpoints/*.json"))
    source_digest = _tree_digest(bundle_root)
    _bootstrap_study_baseline(bundle_root)

    result = runner.invoke(
        app,
        ["init-study", "pilot-001"],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Initialized Study run 'pilot-001'." in result.output
    assert "Baseline Profile: study-baseline" in result.output
    assert "Participant Profile: pilot-001" in result.output
    assert "Granted-memory Profile: pilot-001-granted-memory" in result.output
    assert "Contexts 47 · Memories 375" in result.output
    assert "Granted Contexts 52 · Granted Memories 675" in result.output
    assert "Active Profile unchanged: authoring" in result.output
    assert "Use it with: mem profile pilot-001" in result.output
    assert _tree_digest(bundle_root) == source_digest

    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        "study-baseline",
        "pilot-001",
        "pilot-001-granted-memory",
    ]
    assert len(registry.grants) == 7
    assert study_profile_groups(registry.profiles) == ()
    baseline = registry.by_name("study-baseline")
    copied = registry.by_name("pilot-001")
    authority = registry.by_name("pilot-001-granted-memory")
    assert (
        baseline is not None
        and copied is not None
        and authority is not None
        and copied.source is not None
        and authority.source is not None
    )
    assert copied.source["kind"] == "STUDY_RUN"
    assert authority.source["kind"] == "STUDY_RUN_GRANTED_MEMORY"
    assert copied.source["study_uid"] == authority.source["study_uid"]
    assert copied.source["baseline_profile_uid"] == baseline.uid
    assert copied.source["baseline_profile_name"] == baseline.name
    assert re.fullmatch(r"[0-9a-f]{64}", copied.source["baseline_sha256"])
    baseline_root = profile_store_dir(baseline)
    copied_root = profile_store_dir(copied)
    authority_root = profile_store_dir(authority)
    assert copied_root != baseline_root
    baseline_store = MemoryStore(root=baseline_root, create=False)
    copied_store = MemoryStore(root=copied_root, create=False)
    authority_store = MemoryStore(root=authority_root, create=False)
    assert len(copied_store.list_context_names()) == 47
    assert len(authority_store.list_context_names()) == 82
    assert copied_store.current_context_name() == (
        "task-1/participant/construction-updates"
    )
    assert authority_store.current_context_name() == "task-1/campus-wiki"
    assert "granted-memory/task-1/campus-wiki" in baseline_store.list_context_names()
    assert "task-1/campus-wiki" in authority_store.list_context_names()
    assert not any(copied_root.rglob("checkpoints/*.json"))
    assert not any(authority_root.rglob("checkpoints/*.json"))


def test_init_study_without_name_generates_unique_timestamped_name(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)

    first = runner.invoke(app, ["init-study"])
    second = runner.invoke(app, ["init-study"])

    assert first.exit_code == 0, first.stderr or first.output
    assert second.exit_code == 0, second.stderr or second.output
    names = [
        profile.name
        for profile in load_profile_registry().profiles
        if profile.name not in {"authoring", "study-baseline"}
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


def test_profile_inventory_shows_run_pair_and_real_granted_counts(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    assert (
        runner.invoke(
            app,
            ["init-study", "pilot-002"],
        ).exit_code
        == 0
    )

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0, result.output
    profile_line = next(
        line for line in result.output.splitlines() if "pilot-002" in line
    )
    assert "Contexts 47 owned + 52 granted" in profile_line
    assert "Memories 375 owned + 675 granted" in profile_line
    authority_line = next(
        line
        for line in result.output.splitlines()
        if "pilot-002-granted-memory" in line
    )
    assert "Contexts 82 owned + 0 granted" in authority_line
    assert "Memories 903 owned + 0 granted" in authority_line
    assert "STUDY pilot-002" not in result.output
    assert "pilot-002-task-" not in result.output
    assert "Authority 1" not in result.output


def test_initialized_study_picker_shows_participant_and_authority_profiles(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    initialized = runner.invoke(
        app,
        ["init-study", "pilot-picker"],
    )
    assert initialized.exit_code == 0, initialized.output
    observed: list[tuple[str, str | None]] = []

    def select(entries, *, current):
        assert current == "authoring"
        observed.extend((entry.name, entry.study_role) for entry in entries)
        return "pilot-picker"

    monkeypatch.setattr(
        "memcommit.commands.profile._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.profile.choose_profile",
        select,
    )

    result = runner.invoke(app, ["profile"])

    assert result.exit_code == 0, result.output
    assert observed == [
        ("authoring", None),
        ("study-baseline", None),
        ("pilot-picker", None),
        ("pilot-picker-granted-memory", None),
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
    _bootstrap_study_baseline(bundles)
    assert (
        runner.invoke(
            app,
            ["init-study", "pilot-003"],
        ).exit_code
        == 0
    )
    before = load_profile_registry()
    before_roots = tuple(profile_store_dir(profile) for profile in before.profiles[1:])

    result = runner.invoke(
        app,
        ["init-study", "pilot-003"],
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

    case_collision = runner.invoke(
        app,
        [
            "import",
            "profile",
            "PILOT-003",
            "--from-profile",
            "study-baseline",
        ],
    )
    assert case_collision.exit_code == 1
    assert "Profile 'PILOT-003' already exists" in case_collision.stderr
    assert load_profile_registry() == before


def test_init_study_preserves_a_store_after_visible_registry_replacement(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    real_write_registry = profiles_module._write_registry

    def fail_after_visible_replace(updated):
        real_write_registry(updated)
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(
        profiles_module,
        "_write_registry",
        fail_after_visible_replace,
    )

    result = runner.invoke(app, ["init-study", "durability-visible"])

    assert result.exit_code == 1
    assert "was published" in result.stderr
    assert "remains registered" in result.stderr
    registry = load_profile_registry()
    baseline = registry.by_name("study-baseline")
    published = registry.by_name("durability-visible")
    authority = registry.by_name("durability-visible-granted-memory")
    assert baseline is not None and published is not None and authority is not None
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
        == 7
    )
    assert registry.active.name == "authoring"


def test_init_study_is_all_or_nothing_when_source_store_is_invalid(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    registry_before = load_profile_registry()
    baseline = registry_before.by_name(STUDY_BASELINE_PROFILE_NAME)
    assert baseline is not None
    broken = (
        profile_store_dir(baseline)
        / "contexts"
        / "granted-memory"
        / "task-2"
        / "advisor1"
        / "context.json"
    )
    broken.write_text("{not-json\n", encoding="utf-8")

    result = runner.invoke(app, ["init-study", "pilot-invalid"])

    assert result.exit_code == 1
    assert "pilot-invalid" not in {
        profile.name for profile in load_profile_registry().profiles
    }
    assert load_profile_registry() == registry_before
    stores = [
        item
        for item in (tmp_path / ".mem-profiles" / "stores").iterdir()
        if not item.name.startswith(".")
    ]
    assert stores == [profile_store_dir(baseline)]


def test_repeated_init_study_run_pairs_are_independent(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)

    first = runner.invoke(
        app,
        ["init-study", "pilot-v2-a"],
    )
    second = runner.invoke(
        app,
        ["init-study", "pilot-v2-b"],
    )

    assert first.exit_code == 0, first.stderr or first.output
    assert second.exit_code == 0, second.stderr or second.output
    registry = load_profile_registry()
    baseline = registry.by_name("study-baseline")
    first_profile = registry.by_name("pilot-v2-a")
    first_authority = registry.by_name("pilot-v2-a-granted-memory")
    second_profile = registry.by_name("pilot-v2-b")
    second_authority = registry.by_name("pilot-v2-b-granted-memory")
    assert (
        baseline is not None
        and first_profile is not None
        and first_authority is not None
        and second_profile is not None
        and second_authority is not None
    )
    assert (
        len(
            {
                baseline.uid,
                first_profile.uid,
                first_authority.uid,
                second_profile.uid,
                second_authority.uid,
            }
        )
        == 5
    )
    assert len(registry.grants) == 14
    assert study_profile_groups(registry.profiles) == ()

    baseline_root = profile_store_dir(baseline)
    baseline_store = MemoryStore(root=baseline_root, create=False)
    first_store = MemoryStore(root=profile_store_dir(first_authority), create=False)
    second_store = MemoryStore(root=profile_store_dir(second_authority), create=False)
    first_context = first_store.load_direct("task-1/campus-wiki")
    added = ops.add(first_context, "Only the first run authority copy changes.")
    first_store.save(first_context)
    assert added.uid in first_store.load_direct("task-1/campus-wiki").memories
    assert added.uid not in second_store.load_direct("task-1/campus-wiki").memories
    assert (
        added.uid
        not in baseline_store.load_direct("granted-memory/task-1/campus-wiki").memories
    )

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
        line.startswith("* pilot-v2-a")
        for line in current_inventory.output.splitlines()
    )


def test_init_study_rejects_a_non_study_baseline_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    source_root = tmp_path / "custom-source"
    source_store = MemoryStore(root=source_root)
    context = ops.init("custom/topology/leaf")
    memory = ops.add(context, "Custom Study Memory.")
    source_store.save(context)
    source_store.set_current(context.name)
    imported = runner.invoke(
        app,
        ["profile", "import", "custom-baseline", "--from", str(source_root)],
    )
    assert imported.exit_code == 0, imported.stderr or imported.output

    result = runner.invoke(
        app,
        [
            "init-study",
            "custom-run",
            "--from-profile",
            "custom-baseline",
        ],
    )

    assert result.exit_code == 1
    assert "Study baseline Profile provenance is invalid" in result.stderr
    registry = load_profile_registry()
    source = registry.by_name("custom-baseline")
    copied = registry.by_name("custom-run")
    assert source is not None and copied is None
    assert memory.uid in source_store.load_direct(context.name).memories
    assert registry.active.name == "authoring"


def test_init_study_missing_source_publishes_nothing(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    before = load_profile_registry()

    result = runner.invoke(
        app,
        ["init-study", "missing-run", "--from-profile", "missing-source"],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.stderr
    assert "profile import-study" not in result.stderr
    assert load_profile_registry() == before
    stores = tmp_path / ".mem-profiles" / "stores"
    assert not stores.exists() or not list(stores.iterdir())

    default_result = runner.invoke(app, ["init-study", "default-missing-run"])
    assert default_result.exit_code == 1
    assert "bootstrap it with 'mem profile import-study'" in default_result.stderr
    assert load_profile_registry() == before


def test_init_study_rejects_a_source_with_registry_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    create_authority_grant(
        authority_name="study-baseline",
        grantee_name="authoring",
        resource_name="task-1",
        attachment_name="authoring-notes",
        permissions=["READ"],
        public_name="baseline-view",
        recursive=True,
    )
    before = load_profile_registry()

    result = runner.invoke(app, ["init-study", "grant-bearing-run"])

    assert result.exit_code == 1
    assert "participates in registry grants" in result.stderr
    assert load_profile_registry() == before
    assert before.by_name("grant-bearing-run") is None


def test_archive_legacy_study_preserves_stores_and_allows_merged_replacement(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
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

    initialized = runner.invoke(app, ["init-study", "legacy-run"])
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
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    _bootstrap_study_baseline(bundles)
    before = profile_registry_file().read_bytes()

    result = runner.invoke(
        app,
        ["profile", "archive-study", STUDY_BASELINE_PROFILE_NAME],
    )

    assert result.exit_code == 1
    assert "Legacy Study 'study-baseline' does not exist" in result.stderr
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
