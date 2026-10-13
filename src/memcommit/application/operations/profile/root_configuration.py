"""Move a Profile's Store and explicitly connected documents under one lease."""

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import shutil
import uuid

from memcommit.configuration.config import external_document_locator
from memcommit.configuration.workspace import workspace_lock
from memcommit.persistence.import_export.source import read_output_files
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.operations.mem_sync.settings_repository import SyncSettingsRepository
from memcommit.persistence.operations.mem_sync.baseline_repository import SyncBaselineRepository
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository
from .config import load_profile_registry, profile_root_dir, profile_store_dir
from .model._storage import _registry_lock, _write_registry, _copy_store, _fsync_directory, _assert_plain_tree
from .project_root import prepare_profile_root, validate_profile_marker


def _read_store_file_digests(root):
    _assert_plain_tree(root, label="Profile Store")
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def relocate_profile_root(requested_root):
    with workspace_lock(exclusive=True), _registry_lock():
        registry = load_profile_registry()
        profile = registry.active
        old_root = profile_root_dir(profile)
        if Path(requested_root).expanduser().resolve() == old_root:
            return profile
        validate_profile_marker(profile)
        moved = prepare_profile_root(profile, requested_root, registry)
        source = profile_store_dir(profile)
        target = profile_store_dir(moved)
        store = MemoryStore(root=source, create=False)
        if SyncRunRepository(store).pending():
            raise ValueError("Finish interrupted Sync before moving this Profile.")
        repository = SyncSettingsRepository(store)
        settings = repository.load()
        baselines = SyncBaselineRepository(store).load()
        managed = dict(pair for baseline in baselines.values() for pair in baseline.files)
        current = read_output_files(old_root, managed)
        if current != managed:
            raise ValueError("Managed files changed outside mem; resolve Sync before moving.")
        before = read_output_files(profile_root_dir(moved), managed)
        if any(data is not None and data != managed[path] for path, data in before.items()):
            raise ValueError("Destination contains conflicting managed documents.")
        staging = target.parent / f".mem-moving-{uuid.uuid4().hex}"
        initial = _read_store_file_digests(source)
        created_files = []
        published = False
        store_moved = False
        try:
            _copy_store(source, staging)
            if initial != _read_store_file_digests(source) or initial != _read_store_file_digests(staging):
                raise ValueError("Profile Store changed during relocation.")
            copied = SyncSettingsRepository(MemoryStore(root=staging, create=False))
            copied.save({**settings, "connections": [
                {**c, "base": external_document_locator(profile_root_dir(moved))}
                for c in settings["connections"]
            ]}, expected_revision=settings["revision"])
            # Existing equal files are adopted; conflicting files were rejected
            # before copying. Rollback removes only files created by this move.
            for path, data in managed.items():
                destination = profile_root_dir(moved) / path
                if before[path] is None:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open("xb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    created_files.append((destination, data))
            if initial != _read_store_file_digests(source) or read_output_files(old_root, managed) != current:
                raise ValueError("Relocation source changed before publication.")
            if read_output_files(profile_root_dir(moved), managed) != managed:
                raise ValueError("Relocation destination changed before publication.")
            os.replace(staging, target)
            store_moved = True
            _fsync_directory(target.parent)
            updated = replace(registry, generation=max(1, registry.generation + 1),
                profiles=tuple(moved if p.uid == profile.uid else p for p in registry.profiles))
            try:
                _write_registry(updated)
            except Exception:
                # A visible registry replacement must retain its complete data.
                try:
                    replacement_is_visible = load_profile_registry() == updated
                except (OSError, ValueError, RuntimeError):
                    # Unknown publication is not evidence that rollback is safe.
                    # Keep both copies rather than risk a registered missing Store.
                    published = True
                    raise
                if replacement_is_visible:
                    published = True
                raise
            published = True
            return moved
        finally:
            if not published:
                if staging.exists():
                    shutil.rmtree(staging)
                if store_moved and target.exists():
                    shutil.rmtree(target)
                for path, copied_bytes in created_files:
                    # An external edit after copying belongs to its author.
                    if not path.is_symlink() and path.is_file() and path.read_bytes() == copied_bytes:
                        path.unlink()
