"""Typed Profile, Context, and Memory import contracts."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.context import Context, Memory, MemoryRef
from memcommit.profile_config import load_profile_registry, profile_store_dir
from memcommit.store import MemoryStore


runner = CliRunner(mix_stderr=False)


def _write_source_store(root: Path) -> dict[str, str]:
    root_context = Context(
        uid="10000000-0000-4000-8000-000000000001",
        name="source/root",
    )
    root_memory = Memory(
        uid="20000000-0000-4000-8000-000000000001",
        content="Stable root Memory.",
    )
    child = Context(
        uid="10000000-0000-4000-8000-000000000002",
        name="source/root/child",
    )
    child_memory = Memory(
        uid="20000000-0000-4000-8000-000000000002",
        content="Stable child Memory.",
    )
    root_context.add(root_memory)
    root_context.add(Context(uid=child.uid, name=child.name))
    child.add(child_memory)
    child.add(
        MemoryRef(
            uid="30000000-0000-4000-8000-000000000001",
            target_context_uid=root_context.uid,
            target_context_name=root_context.name,
            target_memory_uid=root_memory.uid,
            target=root_memory,
        )
    )

    for context in (root_context, child):
        directory = root / "contexts" / context.name
        directory.mkdir(parents=True)
        (directory / "context.json").write_text(
            json.dumps(context.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        checkpoints = directory / "checkpoints"
        checkpoints.mkdir()
        (checkpoints / "source-history.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
    (root / "state.json").write_text(
        json.dumps({"current": root_context.name}) + "\n",
        encoding="utf-8",
    )
    return {
        "root_context_uid": root_context.uid,
        "child_context_uid": child.uid,
        "root_memory_uid": root_memory.uid,
        "child_memory_uid": child_memory.uid,
    }


def _prepare_profiles(isolated_store: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    active = MemoryStore()
    destination = Context(
        uid="40000000-0000-4000-8000-000000000001",
        name="destination",
    )
    active.save(destination)
    active.set_current(destination.name)
    source_root = tmp_path / "source-store"
    identities = _write_source_store(source_root)
    imported = runner.invoke(
        app,
        ["import", "profile", "source-profile", "--from", str(source_root)],
    )
    assert imported.exit_code == 0, imported.stderr or imported.output
    return active, identities


def test_profile_can_be_cleanly_imported_from_registered_profile(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _active, identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "import",
            "profile",
            "profile-copy",
            "--from-profile",
            "source-profile",
        ],
    )

    assert result.exit_code == 0, result.stderr or result.output
    registry = load_profile_registry()
    assert registry.active.name == "authoring"
    source = registry.by_name("source-profile")
    copied = registry.by_name("profile-copy")
    assert source is not None and copied is not None and copied.source is not None
    assert copied.source["kind"] == "PROFILE_IMPORT"
    assert copied.source["source_profile_uid"] == source.uid
    copied_root = profile_store_dir(copied)
    record = json.loads(
        (copied_root / "contexts/source/root/context.json").read_text(encoding="utf-8")
    )
    assert record["uid"] == identities["root_context_uid"]
    assert not any(copied_root.rglob("source-history.json"))


def test_scope_presets_are_rejected_for_import_kinds_without_context_scope(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _prepare_profiles(isolated_store, tmp_path, monkeypatch)

    profile = runner.invoke(
        app,
        ["import", "profile", "copy", "--from-profile", "source-profile", "-d"],
    )
    memory = runner.invoke(
        app,
        [
            "import",
            "memory",
            "20000000",
            "--from-profile",
            "source-profile",
            "--context",
            "source/root",
            "-r",
        ],
    )

    assert profile.exit_code == 1
    assert "Unsupported option(s) for this import: --direct" in profile.stderr
    assert memory.exit_code == 1
    assert "Unsupported option(s) for this import: --recursive" in memory.stderr


def test_recursive_context_import_rewrites_internal_names_and_keeps_uids(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "import",
            "context",
            "source/root",
            "--from-profile",
            "source-profile",
            "-r",
            "--as",
            "copied/root",
        ],
    )

    assert result.exit_code == 0, result.stderr or result.output
    assert "Imported 2 Context(s)" in result.output
    assert active.current_context_name() == "destination"
    imported_root = active.load_direct("copied/root")
    imported_child = active.load_direct("copied/root/child")
    assert imported_root.uid == identities["root_context_uid"]
    assert imported_child.uid == identities["child_context_uid"]
    nested = next(
        item for item in imported_root.iter_items() if isinstance(item, Context)
    )
    reference = next(
        item for item in imported_child.iter_items() if isinstance(item, MemoryRef)
    )
    assert nested.name == "copied/root/child"
    assert reference.target_context_name == "copied/root"
    assert reference.target_memory_uid == identities["root_memory_uid"]
    checkpoint = active.list_checkpoints("copied/root")[0]
    assert checkpoint["command"] == "import"
    assert checkpoint["args"]["resource_kind"] == "context"
    assert checkpoint["args"]["source_profile_name"] == "source-profile"


def test_context_import_rejects_an_open_reference_without_partial_creation(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)

    result = runner.invoke(
        app,
        [
            "import",
            "context",
            "source/root",
            "--from-profile",
            "source-profile",
            "--as",
            "incomplete/root",
        ],
    )

    assert result.exit_code == 1
    assert "outside the import set" in result.stderr
    assert not active.context_exists("incomplete/root")


def test_memory_import_preserves_uid_and_rejects_target_collision(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)
    arguments = [
        "import",
        "memory",
        identities["child_memory_uid"][:8],
        "--from-profile",
        "source-profile",
        "--context",
        "source/root/child",
        "--into",
        "destination",
    ]

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.exit_code == 0, first.stderr or first.output
    assert second.exit_code == 1
    assert "already exists" in second.stderr
    target = active.load_direct("destination")
    imported = target.memories[identities["child_memory_uid"]]
    assert isinstance(imported, Memory)
    assert imported.content == "Stable child Memory."
    assert active.current_context_name() == "destination"
    checkpoint = active.list_checkpoints("destination")[0]
    assert checkpoint["command"] == "import"
    assert checkpoint["args"]["resource_kind"] == "memory"
    assert checkpoint["args"]["source_memory_uid"] == identities["child_memory_uid"]


def test_recursive_context_collision_fails_before_creating_any_sibling(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    active, _identities = _prepare_profiles(isolated_store, tmp_path, monkeypatch)
    occupied = Context(
        uid="50000000-0000-4000-8000-000000000001",
        name="collision/root/child",
    )
    active.save(occupied)

    result = runner.invoke(
        app,
        [
            "import",
            "context",
            "source/root",
            "--from-profile",
            "source-profile",
            "--recursive",
            "--as",
            "collision/root",
        ],
    )

    assert result.exit_code == 1
    assert "destination already exists" in result.stderr
    assert not active.context_exists("collision/root")
    assert active.load_direct("collision/root/child").uid == occupied.uid
