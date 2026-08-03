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

from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.profiles as profiles_module
from memcommit.cli import app
from memcommit.context import AutoCheckpoint
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.profile_config import (
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import (
    STUDY_BASELINE_PROFILE_NAME,
    baseline_store_digest,
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
    store.save(ops.init("authoring-notes"))
    store.set_current("authoring-notes")


def _bootstrap_study_baseline(bundles: Path):
    result = runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    )
    assert result.exit_code == 0, result.stderr or result.output
    return result


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
    assert "Contexts 130 owned + 0 granted" in selected.output
    assert "Memories 1278 owned + 0 granted" in selected.output
    contexts = _subprocess_mem(tmp_path, "contexts")
    assert contexts.returncode == 0, contexts.stderr
    assert "* task-1" in contexts.stdout
    assert "task-1/participant/construction-updates" in contexts.stdout
    assert "granted-memory/task-1/campus-wiki" in contexts.stdout
    assert "[view " not in contexts.stdout
    assert "authoring-notes" not in contexts.stdout

    profile_list = runner.invoke(app, ["profile", "list"])
    assert profile_list.exit_code == 0
    assert "* profile-view" in profile_list.output
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


def test_init_study_creates_one_complete_ordinary_profile(
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
    assert "Initialized Study Profile 'pilot-001'." in result.output
    assert "Baseline Profile: study-baseline" in result.output
    assert "Contexts 130 · Memories 1278 · current=task-1" in result.output
    assert (
        "complete baseline Context topology was copied without splitting"
        in result.output
    )
    assert "Task 1 ·" not in result.output
    assert "Authority Profiles:" not in result.output
    assert "Active Profile unchanged: authoring" in result.output
    assert "Use it with: mem profile pilot-001" in result.output
    assert _tree_digest(bundle_root) == source_digest

    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        "study-baseline",
        "pilot-001",
    ]
    assert registry.grants == ()
    assert study_profile_groups(registry.profiles) == ()
    baseline = registry.by_name("study-baseline")
    copied = registry.by_name("pilot-001")
    assert baseline is not None and copied is not None and copied.source is not None
    assert copied.source["kind"] == "PROFILE_IMPORT"
    assert copied.source["source_profile_uid"] == baseline.uid
    assert copied.source["source_profile_name"] == baseline.name
    assert re.fullmatch(r"[0-9a-f]{64}", copied.source["baseline_sha256"])
    baseline_root = profile_store_dir(baseline)
    copied_root = profile_store_dir(copied)
    assert copied_root != baseline_root
    assert baseline_store_digest(copied_root) == baseline_store_digest(baseline_root)
    baseline_store = MemoryStore(root=baseline_root, create=False)
    copied_store = MemoryStore(root=copied_root, create=False)
    assert copied_store.list_context_names() == baseline_store.list_context_names()
    assert copied_store.current_context_name() == baseline_store.current_context_name()
    for context_name in baseline_store.list_context_names():
        assert (
            copied_store.load_direct(context_name).to_dict()
            == baseline_store.load_direct(context_name).to_dict()
        )
    assert not any(copied_root.rglob("checkpoints/*.json"))


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
    assert len(names) == 2
    assert names[0] != names[1]
    assert all(re.fullmatch(r"study-\d{8}T\d{6}Z-[0-9a-f]{8}", name) for name in names)
    assert study_profile_groups(load_profile_registry().profiles) == ()


def test_profile_inventory_shows_initialized_study_as_one_ordinary_profile(
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
    assert "Contexts 130 owned + 0 granted" in profile_line
    assert "Memories 1278 owned + 0 granted" in profile_line
    assert "STUDY pilot-002" not in result.output
    assert "pilot-002-task-" not in result.output
    assert "Authority 1" not in result.output


def test_initialized_study_picker_shows_one_ordinary_profile(
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
    assert baseline is not None and published is not None
    assert profile_store_dir(published).is_dir()
    assert baseline_store_digest(profile_store_dir(published)) == baseline_store_digest(
        profile_store_dir(baseline)
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


def test_repeated_init_study_profiles_are_independent_complete_copies(
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
    second_profile = registry.by_name("pilot-v2-b")
    assert (
        baseline is not None
        and first_profile is not None
        and second_profile is not None
    )
    assert len({baseline.uid, first_profile.uid, second_profile.uid}) == 3
    assert registry.grants == ()
    assert study_profile_groups(registry.profiles) == ()

    baseline_root = profile_store_dir(baseline)
    first_root = profile_store_dir(first_profile)
    second_root = profile_store_dir(second_profile)
    assert baseline_store_digest(first_root) == baseline_store_digest(baseline_root)
    assert baseline_store_digest(second_root) == baseline_store_digest(baseline_root)

    first_store = MemoryStore(root=first_root, create=False)
    first_context = first_store.load_direct("task-1")
    ops.add(first_context, "Only the first initialized Profile changes.")
    first_store.save(first_context)
    assert baseline_store_digest(first_root) != baseline_store_digest(baseline_root)
    assert baseline_store_digest(second_root) == baseline_store_digest(baseline_root)

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


def test_init_study_can_copy_an_explicit_self_contained_profile(
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

    assert result.exit_code == 0, result.stderr or result.output
    registry = load_profile_registry()
    source = registry.by_name("custom-baseline")
    copied = registry.by_name("custom-run")
    assert source is not None and copied is not None and copied.source is not None
    assert copied.source["source_profile_uid"] == source.uid
    copied_store = MemoryStore(root=profile_store_dir(copied), create=False)
    copied_context = copied_store.load_direct(context.name)
    assert copied_context.uid == context.uid
    assert [item.uid for item in copied_context.iter_items()] == [memory.uid]
    assert copied_store.current_context_name() == context.name
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
