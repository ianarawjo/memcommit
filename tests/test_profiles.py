"""Whole-store profile selection and study-profile import contracts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.eval.study_bundle import build_all_study_bundles
from memcommit.profile_config import (
    load_profile_registry,
    profile_registry_file,
    profile_store_dir,
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
    assert "1 Contexts" in result.output
    assert "current=authoring-notes" in result.output
    assert not profile_registry_file().exists()


def test_import_study_registers_editable_isolated_copies_and_keeps_authoring(
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
    assert "Imported editable study profiles." in result.output
    assert "task-1: 14 ordinary Contexts" in result.output
    assert "task-2: 34 ordinary Contexts" in result.output
    assert "task-3: 42 ordinary Contexts" in result.output
    assert _tree_digest(bundles) == source_digest
    assert _tree_digest(isolated_store) == authoring_digest

    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    assert [profile.name for profile in registry.profiles] == [
        "authoring",
        "task-1",
        "task-2",
        "task-3",
    ]
    expected = {
        "task-1": (14, "participant/construction-updates"),
        "task-2": (34, "advisor1"),
        "task-3": (42, "personal-memory"),
    }
    for profile in registry.profiles[1:]:
        root = profile_store_dir(profile)
        assert root.is_dir()
        contexts = tuple((root / "contexts").rglob("context.json"))
        state = json.loads((root / "state.json").read_text(encoding="utf-8"))
        assert (len(contexts), state["current"]) == expected[profile.name]


def test_profile_use_changes_the_next_process_and_keeps_query_only_hidden(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    assert runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    ).exit_code == 0

    selected = runner.invoke(app, ["profile", "use", "task-1"])

    assert selected.exit_code == 0, selected.output
    assert "Selected profile 'task-1'." in selected.output
    assert "14 ordinary Contexts" in selected.output
    contexts = _subprocess_mem(tmp_path, "contexts")
    assert contexts.returncode == 0, contexts.stderr
    assert "* participant/construction-updates" in contexts.stdout
    assert "participant/campus-wiki-fork/building-access" in contexts.stdout
    assert "campus-wiki\n" not in contexts.stdout
    assert "authoring-notes" not in contexts.stdout

    profile_list = runner.invoke(app, ["profile", "list"])
    assert profile_list.exit_code == 0
    assert "* task-1" in profile_list.output
    assert "authoring" in profile_list.output


def test_managed_profile_edits_persist_across_profile_selection(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HOME", str(tmp_path))
    _prepare_authoring(isolated_store)
    bundles = tmp_path / "bundles"
    build_all_study_bundles(bundles)
    source_digest = _tree_digest(bundles / "task-1")
    assert runner.invoke(
        app,
        ["profile", "import-study", "--from", str(bundles)],
    ).exit_code == 0
    assert runner.invoke(app, ["profile", "use", "task-1"]).exit_code == 0

    added = _subprocess_mem(tmp_path, "add", "A locally revised study Memory.")
    assert added.returncode == 0, added.stderr
    assert runner.invoke(app, ["profile", "use", "authoring"]).exit_code == 0
    authoring = _subprocess_mem(tmp_path, "contexts")
    assert "* authoring-notes" in authoring.stdout
    assert "participant/construction-updates" not in authoring.stdout
    assert runner.invoke(app, ["profile", "use", "task-1"]).exit_code == 0
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
    entry = next(item for item in manifest["entries"] if not item["query_only"])
    context_path = (
        bundles
        / "task-1"
        / ".mem"
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
