"""Clean whole-Profile imports for ``mem import profile``."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import uuid

from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_store_dir,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    StoreInspection,
    _assert_plain_tree,
    _registry_lock,
    _source_store,
    _write_registry,
    inspect_store,
)

from ._shared import source_profile as _resolve_source_profile


_BASELINE_TOP_LEVEL_DIRECTORIES = (
    "query-sources",
    "translation-views",
)


def _baseline_store_files(root: Path) -> tuple[Path, ...]:
    """Return the explicit durable baseline allowlist for one MemoryStore.

    A clean Profile copy needs stable Context/Memory identities and declared
    content views, but it must not inherit checkpoints, command receipts,
    sessions, caches, locks, lifecycle events, or write-protection state.
    Selecting files rather than deleting known runtime names makes future
    operational artifacts fail safely closed outside the imported baseline.
    """

    source = Path(root).absolute()
    inspect_store(source)
    files: list[Path] = [source / "state.json"]
    files.extend(sorted((source / "contexts").rglob("context.json")))
    for name in _BASELINE_TOP_LEVEL_DIRECTORIES:
        directory = source / name
        if directory.exists():
            files.extend(
                sorted(path for path in directory.rglob("*") if path.is_file())
            )
    return tuple(sorted(files, key=lambda path: path.relative_to(source).as_posix()))


def baseline_store_digest(root: Path) -> str:
    """Digest exactly the files admitted by clean baseline import."""

    source = Path(root).absolute()
    digest = hashlib.sha256()
    for path in _baseline_store_files(source):
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _copy_store_baseline(
    source: Path,
    destination: Path,
    *,
    expected_digest: str | None = None,
) -> StoreInspection:
    """Import durable baseline data while starting operational history empty."""

    source = Path(source).absolute()
    _assert_plain_tree(source, label="Source MemoryStore")
    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Profile staging path is already occupied: {destination}")
    before = baseline_store_digest(source)
    if expected_digest is not None and before != expected_digest:
        raise ProfileError("Source MemoryStore baseline changed before import.")
    destination.mkdir()
    (destination / "contexts").mkdir()
    for path in _baseline_store_files(source):
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    after = baseline_store_digest(source)
    imported = baseline_store_digest(destination)
    if before != after or imported != before:
        raise ProfileError("Source MemoryStore baseline changed during import.")
    return inspect_store(destination)


def _baseline_import_provenance(
    source_root: Path,
    *,
    source_profile: ProfileEntry | None,
) -> tuple[str, dict[str, object]]:
    """Freeze the digest and path-free provenance for one clean copy."""

    digest = baseline_store_digest(source_root)
    source_record: dict[str, object] = {
        "kind": "BASELINE_IMPORT",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "baseline_sha256": digest,
    }
    if source_profile is not None:
        # Registry identity is durable provenance; an internal path may expose
        # host layout and cannot identify the source after relocation.
        source_record.update(
            {
                "kind": "PROFILE_IMPORT",
                "source_profile_uid": source_profile.uid,
                "source_profile_name": source_profile.name,
            }
        )
    return digest, source_record


def _publish_baseline_profile_locked(
    registry: ProfileRegistry,
    *,
    name: str,
    source_root: Path,
    digest: str,
    source_record: dict[str, object],
) -> tuple[ProfileEntry, StoreInspection]:
    """Publish one clean copy while the caller holds the registry lock."""

    if any(profile.name.casefold() == name.casefold() for profile in registry.profiles):
        raise ProfileError(f"Profile {name!r} already exists.")
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=name,
        kind="MANAGED",
        source=source_record,
    )
    staging = profile_stores_dir() / f".{profile.uid}.staging-{uuid.uuid4().hex}"
    published = False
    try:
        inspection = _copy_store_baseline(
            source_root,
            staging,
            expected_digest=digest,
        )
        destination = profile_store_dir(profile)
        if destination.exists() or destination.is_symlink():
            raise ProfileError("Managed profile destination is occupied.")
        os.replace(staging, destination)
        published = True
        updated = replace(
            registry,
            generation=max(1, registry.generation + 1),
            profiles=(*registry.profiles, profile),
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                replacement_is_visible = load_profile_registry() == updated
            except (OSError, ProfileConfigError, ValueError):
                replacement_is_visible = False
            if replacement_is_visible:
                # A registry replace can commit before directory fsync reports
                # failure. Keep the store so visible metadata never points at
                # missing Profile content.
                raise ProfileError(
                    f"Profile {name!r} was published, but registry durability "
                    "could not be confirmed; it remains registered."
                ) from error
            os.replace(destination, staging)
            published = False
            raise
        return profile, replace(inspection, root=destination)
    finally:
        candidate = profile_store_dir(profile) if published else staging
        if not published and candidate.exists() and not candidate.is_symlink():
            shutil.rmtree(candidate)


def import_baseline_profile(
    name: str,
    source: Path,
    *,
    source_profile: ProfileEntry | None = None,
) -> tuple[ProfileEntry, StoreInspection]:
    """Create a managed Profile from content baseline without run history."""

    canonical = validate_profile_name(name)
    if canonical == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring profile cannot be imported.")
    source_root = _source_store(source)
    digest, source_record = _baseline_import_provenance(
        source_root,
        source_profile=source_profile,
    )
    with _registry_lock():
        registry = load_profile_registry()
        if source_profile is not None:
            frozen_source = registry.by_name(source_profile.name)
            if (
                frozen_source is None
                or registry.is_removed(frozen_source)
                or frozen_source.uid != source_profile.uid
                or profile_store_dir(frozen_source).absolute() != source_root
            ):
                raise ProfileError(
                    "Source Profile identity changed while import was starting."
                )
        return _publish_baseline_profile_locked(
            registry,
            name=canonical,
            source_root=source_root,
            digest=digest,
            source_record=source_record,
        )


def import_profile_from_profile(
    name: str,
    source_profile_name: str,
    *,
    expected_source_profile_uid: str | None = None,
) -> tuple[ProfileEntry, StoreInspection]:
    """Create one clean Profile from another registered Profile."""

    registry = load_profile_registry()
    source = _resolve_source_profile(registry, source_profile_name)
    if (
        expected_source_profile_uid is not None
        and source.uid != expected_source_profile_uid
    ):
        raise ProfileError("Source Profile identity changed after import review.")
    return import_baseline_profile(
        name,
        profile_store_dir(source),
        source_profile=source,
    )
