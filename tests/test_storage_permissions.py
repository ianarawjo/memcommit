"""Owner-only storage permissions and content-preserving migration."""

from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path

import pytest

import memcommit.application.operations.profile.model as profiles_module
import memcommit.persistence.store as store_module
from memcommit.application.operations.profile.config import (
    profile_control_dir,
    profile_registry_file,
    profile_stores_dir,
    virtual_authoring_registry,
)
from memcommit.persistence.store.infrastructure.storage_permissions import (
    PRIVATE_DIRECTORY_MODE,
    PRIVATE_FILE_MODE,
    StoragePermissionError,
    harden_private_storage_tree,
)
from memcommit.persistence.store import MemoryStore


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_store_creation_and_atomic_json_are_owner_only(isolated_store):
    MemoryStore()

    assert _mode(isolated_store) == PRIVATE_DIRECTORY_MODE
    assert _mode(isolated_store / "contexts") == PRIVATE_DIRECTORY_MODE
    assert _mode(isolated_store / "state.json") == PRIVATE_FILE_MODE

    exposed = isolated_store / "cache"
    exposed.mkdir(mode=0o755)
    path = exposed / "result.json"
    store_module._write_json_atomic(path, {"retained": True})

    assert _mode(exposed) == PRIVATE_DIRECTORY_MODE
    assert _mode(path) == PRIVATE_FILE_MODE


def test_profile_control_and_registry_are_owner_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    profiles_module._ensure_control_dirs()
    profiles_module._write_registry(
        replace(virtual_authoring_registry(), generation=1)
    )

    assert _mode(profile_control_dir()) == PRIVATE_DIRECTORY_MODE
    assert _mode(profile_stores_dir()) == PRIVATE_DIRECTORY_MODE
    assert _mode(profile_registry_file()) == PRIVATE_FILE_MODE


def test_permission_migration_preserves_every_byte_and_is_idempotent(tmp_path):
    root = tmp_path / "legacy-store"
    nested = root / "cache" / "nested"
    nested.mkdir(parents=True)
    first = root / "state.json"
    second = nested / "analysis.json"
    first.write_bytes(b'{"current": null}\n')
    second.write_bytes(b'{"answer": "retained"}\n')
    for directory in (root, root / "cache", nested):
        directory.chmod(0o755)
    for file in (first, second):
        file.chmod(0o644)
    before = {path: path.read_bytes() for path in (first, second)}

    report = harden_private_storage_tree(root)
    repeated = harden_private_storage_tree(root)

    assert report.directories == repeated.directories == 3
    assert report.files == repeated.files == 2
    assert all(
        _mode(path) == PRIVATE_DIRECTORY_MODE
        for path in (root, root / "cache", nested)
    )
    assert all(_mode(path) == PRIVATE_FILE_MODE for path in (first, second))
    assert {path: path.read_bytes() for path in (first, second)} == before


def test_permission_migration_preflights_symlinks_without_following_them(tmp_path):
    root = tmp_path / "store"
    root.mkdir(mode=0o755)
    outside = tmp_path / "outside.json"
    outside.write_text("outside", encoding="utf-8")
    outside.chmod(0o644)
    (root / "escape").symlink_to(outside)

    with pytest.raises(StoragePermissionError, match="symbolic link"):
        harden_private_storage_tree(root)

    assert _mode(root) == 0o755
    assert _mode(outside) == 0o644
    assert outside.read_text(encoding="utf-8") == "outside"


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode contract")
def test_missing_permission_migration_root_is_a_noop(tmp_path):
    root = tmp_path / "absent"

    report = harden_private_storage_tree(root)

    assert report.directories == 0
    assert report.files == 0
    assert not root.exists()
