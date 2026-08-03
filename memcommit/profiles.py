"""Whole-store profile registration and selection.

Profiles are a control-plane selector around complete MemoryStore roots.  They
do not reinterpret Context names and they never merge task stores.  A process
resolves its selected root once when :mod:`memcommit.store` is imported; a
profile selection therefore affects the next CLI invocation while an already
running operation finishes against the store it opened.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
from typing import Iterator

from memcommit.context import Context, Memory, QueryContextRef
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_registry_lock_file,
    profile_store_dir,
    profile_stores_dir,
    validate_profile_name,
)
from memcommit.translation_view import TranslationCatalog


class ProfileError(RuntimeError):
    """A profile operation cannot complete without risking local state."""


@dataclass(frozen=True)
class StoreInspection:
    """Read-only summary of one validated complete MemoryStore."""

    root: Path
    current_context: str | None
    context_names: tuple[str, ...]
    query_source_count: int
    translation_catalog_count: int


@dataclass(frozen=True)
class StudyImportResult:
    profiles: tuple[ProfileEntry, ...]
    inspections: tuple[StoreInspection, ...]


def default_study_bundle_root() -> Path:
    """Return the editable-checkout fixture location when it is available."""

    return Path(__file__).resolve().parents[1] / "outputs" / "study-fixtures"


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, *, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ProfileError(f"{label} is missing or unsafe: {path}")
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise ProfileError(f"{label} must be a JSON object: {path}")
    return value


def _assert_plain_tree(root: Path, *, label: str) -> None:
    """Reject links and special files before a store is trusted or copied."""

    if root.is_symlink() or not root.is_dir():
        raise ProfileError(f"{label} must be a real directory: {root}")
    for directory, names, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in [*names, *filenames]:
            path = base / name
            if path.is_symlink():
                raise ProfileError(f"{label} contains a symbolic link: {path}")
            mode = path.stat(follow_symlinks=False).st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ProfileError(f"{label} contains a special file: {path}")


def _context_records(
    root: Path,
) -> tuple[dict[str, Context], dict[str, QueryContextRef]]:
    contexts_dir = root / "contexts"
    if contexts_dir.is_symlink() or not contexts_dir.is_dir():
        raise ProfileError("MemoryStore contexts directory is missing or unsafe.")
    contexts: dict[str, Context] = {}
    query_refs: dict[str, QueryContextRef] = {}
    for path in sorted(contexts_dir.rglob("context.json")):
        name = path.parent.relative_to(contexts_dir).as_posix()
        data = _read_json(path, label=f"Context {name!r}")
        try:
            context = Context.from_dict(data)
        except (KeyError, TypeError, ValueError) as error:
            raise ProfileError(f"Context {name!r} is invalid.") from error
        if context.name != name:
            raise ProfileError(
                f"Context path {name!r} does not match record {context.name!r}."
            )
        if name in contexts:
            raise ProfileError(f"Context {name!r} is duplicated.")
        contexts[name] = context
        for item in context.iter_items():
            if isinstance(item, QueryContextRef):
                previous = query_refs.get(item.target_source_uid)
                if previous is not None and previous.name != item.name:
                    raise ProfileError(
                        "One query source uid is referenced under multiple names."
                    )
                query_refs[item.target_source_uid] = item
    return contexts, query_refs


def _query_sources(root: Path) -> dict[str, str]:
    sources_dir = root / "query-sources"
    if not sources_dir.exists():
        return {}
    if sources_dir.is_symlink() or not sources_dir.is_dir():
        raise ProfileError("Query-source storage is unsafe.")
    sources: dict[str, str] = {}
    for path in sorted(sources_dir.glob("*/source.json")):
        data = _read_json(path, label="Query source")
        uid = data.get("uid")
        name = data.get("name")
        if not isinstance(uid, str) or not isinstance(name, str) or not name:
            raise ProfileError("Query source identity is invalid.")
        try:
            canonical_uid = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ProfileError("Query source uid is invalid.") from error
        if canonical_uid != uid or path.parent.name != uid:
            raise ProfileError("Query source path does not match its uid.")
        if data.get("schema_version") not in {1, 2}:
            raise ProfileError("Query source schema version is unsupported.")
        entries = data.get("entries")
        if data.get("schema_version") == 2 and (
            not isinstance(entries, list) or not entries
        ):
            raise ProfileError("Query source entries are invalid.")
        sources[uid] = name
    unexpected = [
        path
        for path in sources_dir.rglob("source.json")
        if path.parent.parent != sources_dir
    ]
    if unexpected:
        raise ProfileError("Query-source storage contains an invalid path.")
    return sources


def _translation_catalogs(
    root: Path,
    contexts: dict[str, Context],
) -> int:
    directory = root / "translation-views"
    if not directory.exists():
        return 0
    if directory.is_symlink() or not directory.is_dir():
        raise ProfileError("Translation-view storage is unsafe.")
    count = 0
    by_uid = {context.uid: context for context in contexts.values()}
    for path in sorted(directory.glob("*--catalog.json")):
        data = _read_json(path, label="Translation catalog")
        try:
            catalog = TranslationCatalog.from_dict(data)
        except (TypeError, ValueError) as error:
            raise ProfileError(f"Translation catalog is invalid: {path}") from error
        context = by_uid.get(catalog.context_uid)
        if context is None or context.name != catalog.context_name:
            raise ProfileError(
                "Translation catalog does not identify a Context in this store."
            )
        count += 1
    return count


def inspect_store(root: Path) -> StoreInspection:
    """Validate one complete store without creating or resolving content."""

    root = Path(root).absolute()
    _assert_plain_tree(root, label="MemoryStore")
    contexts, query_refs = _context_records(root)
    state = _read_json(root / "state.json", label="MemoryStore state")
    current = state.get("current")
    if current is not None and (
        not isinstance(current, str) or current not in contexts
    ):
        raise ProfileError("MemoryStore current Context is invalid.")
    sources = _query_sources(root)
    for source_uid, reference in query_refs.items():
        if sources.get(source_uid) != reference.name:
            raise ProfileError(
                f"Query-only Context {reference.name!r} has no matching source."
            )
    catalog_count = _translation_catalogs(root, contexts)
    return StoreInspection(
        root=root,
        current_context=current,
        context_names=tuple(sorted(contexts)),
        query_source_count=len(sources),
        translation_catalog_count=catalog_count,
    )


def _ensure_control_dirs() -> None:
    control = profile_control_dir()
    stores = profile_stores_dir()
    for path, label in ((control, "Profile control"), (stores, "Profile store")):
        if path.is_symlink():
            raise ProfileError(f"{label} directory cannot be a symbolic link.")
        if path.exists() and not path.is_dir():
            raise ProfileError(f"{label} storage is invalid.")
        path.mkdir(parents=True, exist_ok=True)


@contextmanager
def _registry_lock() -> Iterator[None]:
    _ensure_control_dirs()
    path = profile_registry_lock_file()
    if path.is_symlink():
        raise ProfileError("Profile registry lock cannot be a symbolic link.")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _write_registry(registry: ProfileRegistry) -> None:
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        with open(temporary, "x", encoding="utf-8") as file:
            json.dump(registry.to_dict(), file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def list_profiles() -> tuple[ProfileRegistry, tuple[StoreInspection, ...]]:
    registry = load_profile_registry()
    inspections = tuple(inspect_store(profile_store_dir(item)) for item in registry.profiles)
    return registry, inspections


def use_profile(name: str) -> tuple[ProfileRegistry, StoreInspection, bool]:
    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        target = registry.by_name(canonical)
        if target is None:
            raise ProfileError(f"Profile {canonical!r} does not exist.")
        inspection = inspect_store(profile_store_dir(target))
        if target.uid == registry.active_uid:
            return registry, inspection, False
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=target.uid,
            profiles=registry.profiles,
        )
        _write_registry(updated)
        return updated, inspection, True


def _source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_store(source: Path, destination: Path) -> StoreInspection:
    _assert_plain_tree(source, label="Source MemoryStore")
    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Profile staging path is already occupied: {destination}")
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    return inspect_store(destination)


def _source_store(path: Path) -> Path:
    source = Path(path).expanduser().absolute()
    if source.name != ".mem" and (source / ".mem").is_dir():
        source = source / ".mem"
    return source


def import_profile(
    name: str,
    source: Path,
    *,
    provenance: dict[str, object] | None = None,
) -> tuple[ProfileEntry, StoreInspection]:
    canonical = validate_profile_name(name)
    if canonical == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring profile cannot be imported.")
    source_root = _source_store(source)
    inspect_store(source_root)
    with _registry_lock():
        registry = load_profile_registry()
        if registry.by_name(canonical) is not None:
            raise ProfileError(f"Profile {canonical!r} already exists.")
        profile = ProfileEntry(
            uid=str(uuid.uuid4()),
            name=canonical,
            kind="MANAGED",
            source=provenance,
        )
        staging = profile_stores_dir() / f".{profile.uid}.staging-{uuid.uuid4().hex}"
        published = False
        try:
            inspection = _copy_store(source_root, staging)
            destination = profile_store_dir(profile)
            if destination.exists() or destination.is_symlink():
                raise ProfileError("Managed profile destination is occupied.")
            os.replace(staging, destination)
            published = True
            updated = ProfileRegistry(
                generation=max(1, registry.generation + 1),
                active_uid=registry.active_uid,
                profiles=(*registry.profiles, profile),
            )
            try:
                _write_registry(updated)
            except Exception:
                os.replace(destination, staging)
                published = False
                raise
            return profile, StoreInspection(
                root=destination,
                current_context=inspection.current_context,
                context_names=inspection.context_names,
                query_source_count=inspection.query_source_count,
                translation_catalog_count=inspection.translation_catalog_count,
            )
        finally:
            candidate = profile_store_dir(profile) if published else staging
            if not published and candidate.exists() and not candidate.is_symlink():
                shutil.rmtree(candidate)


def _study_package(
    bundle_root: Path,
    task: int,
) -> tuple[Path, dict[str, object], str]:
    package = bundle_root / f"task-{task}"
    manifest_path = package / "manifest.json"
    manifest = _read_json(manifest_path, label=f"Task {task} manifest")
    if manifest.get("task") != task:
        raise ProfileError(f"Task {task} manifest identifies a different task.")
    store = package / ".mem"
    inspection = inspect_store(store)
    expected_current = manifest.get("current_context")
    if inspection.current_context != expected_current:
        raise ProfileError(f"Task {task} package current Context is inconsistent.")
    ordinary_count = manifest.get("ordinary_count")
    query_count = manifest.get("query_only_count")
    entries = manifest.get("entries")
    if (
        not isinstance(ordinary_count, int)
        or isinstance(ordinary_count, bool)
        or not isinstance(query_count, int)
        or isinstance(query_count, bool)
        or not isinstance(entries, list)
        or len(entries) != ordinary_count + query_count
    ):
        raise ProfileError(f"Task {task} manifest counts are invalid.")
    _validate_study_manifest_content(
        store,
        entries,
        ordinary_count=ordinary_count,
        query_count=query_count,
        task=task,
    )
    return store, manifest, _source_digest(manifest_path)


def _content_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _study_catalogs(root: Path) -> dict[tuple[str, str], TranslationCatalog]:
    catalogs: dict[tuple[str, str], TranslationCatalog] = {}
    directory = root / "translation-views"
    if not directory.exists():
        return catalogs
    for path in sorted(directory.glob("*--catalog.json")):
        data = _read_json(path, label="Translation catalog")
        try:
            catalog = TranslationCatalog.from_dict(data)
        except (TypeError, ValueError) as error:
            raise ProfileError(f"Translation catalog is invalid: {path}") from error
        key = (catalog.context_name, catalog.target_language)
        if key in catalogs:
            raise ProfileError("Study package contains duplicate translation catalogs.")
        catalogs[key] = catalog
    return catalogs


def _study_query_entries(root: Path) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    directory = root / "query-sources"
    if not directory.exists():
        return entries
    for path in sorted(directory.glob("*/source.json")):
        data = _read_json(path, label="Query source")
        if data.get("schema_version") != 2:
            raise ProfileError("Study query source must use schema version 2.")
        raw_entries = data.get("entries")
        if not isinstance(raw_entries, list):
            raise ProfileError("Study query source entries are invalid.")
        for raw in raw_entries:
            if not isinstance(raw, dict):
                raise ProfileError("Study query source entry is invalid.")
            uid = raw.get("uid")
            canonical = raw.get("canonical_content")
            translations = raw.get("translations")
            korean = translations.get("ko") if isinstance(translations, dict) else None
            if (
                not isinstance(uid, str)
                or not isinstance(canonical, str)
                or not isinstance(korean, str)
                or not canonical
                or not korean
            ):
                raise ProfileError("Study query source language coverage is invalid.")
            if uid in entries:
                raise ProfileError("Study query source entry uid is duplicated.")
            entries[uid] = (canonical, korean)
    return entries


def _manifest_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProfileError(f"Study manifest {field} is invalid.")
    return value


def _validate_study_manifest_content(
    root: Path,
    entries: list[object],
    *,
    ordinary_count: int,
    query_count: int,
    task: int,
) -> None:
    """Bind every manifest hash to the exact staged runtime representation."""

    contexts, _query_refs = _context_records(root)
    catalogs = _study_catalogs(root)
    query_entries = _study_query_entries(root)
    ordinary_seen = 0
    query_seen = 0
    memory_uids: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ProfileError(f"Task {task} manifest entry is invalid.")
        uid = raw.get("memory_uid")
        if not isinstance(uid, str) or uid in memory_uids:
            raise ProfileError(f"Task {task} manifest Memory uid is invalid.")
        memory_uids.add(uid)
        english_digest = _manifest_digest(
            raw.get("english_sha256"),
            field="English digest",
        )
        korean_digest = _manifest_digest(
            raw.get("korean_sha256"),
            field="Korean digest",
        )
        query_only = raw.get("query_only")
        if query_only is True:
            query_seen += 1
            if raw.get("runtime_context") is not None or uid not in query_entries:
                raise ProfileError(f"Task {task} query manifest entry is inconsistent.")
            english, korean = query_entries[uid]
        elif query_only is False:
            ordinary_seen += 1
            owner_name = raw.get("runtime_context")
            if not isinstance(owner_name, str) or owner_name not in contexts:
                raise ProfileError(f"Task {task} ordinary manifest owner is invalid.")
            memory = contexts[owner_name].memories.get(uid)
            if not isinstance(memory, Memory):
                raise ProfileError(f"Task {task} ordinary manifest Memory is missing.")
            catalog = catalogs.get((owner_name, "ko"))
            if catalog is None:
                raise ProfileError(f"Task {task} Korean catalog is missing.")
            catalog_entry = next(
                (entry for entry in catalog.entries if entry.source_uid == uid),
                None,
            )
            if catalog_entry is None or catalog_entry.curated is None:
                raise ProfileError(f"Task {task} Korean translation is missing.")
            english = memory.content
            korean = catalog_entry.curated.translated_content
            if catalog_entry.curated.source_sha256 != english_digest:
                raise ProfileError(
                    f"Task {task} Korean translation targets stale content."
                )
        else:
            raise ProfileError(f"Task {task} manifest query flag is invalid.")
        if (
            _content_digest(english) != english_digest
            or _content_digest(korean) != korean_digest
        ):
            raise ProfileError(f"Task {task} manifest content hash does not match.")
    if ordinary_seen != ordinary_count or query_seen != query_count:
        raise ProfileError(f"Task {task} manifest content counts do not match.")


def import_study_profiles(bundle_root: Path) -> StudyImportResult:
    """Copy Task 1--3 into editable managed profiles all-or-nothing."""

    root = Path(bundle_root).expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ProfileError(f"Study bundle root is missing or unsafe: {root}")
    packages = {
        task: _study_package(root, task)
        for task in (1, 2, 3)
    }
    with _registry_lock():
        registry = load_profile_registry()
        names = {profile.name.casefold() for profile in registry.profiles}
        conflicts = [f"task-{task}" for task in (1, 2, 3) if f"task-{task}" in names]
        if conflicts:
            raise ProfileError(
                "Study profiles already exist: " + ", ".join(conflicts)
            )
        batch = profile_stores_dir() / f".study-import-{uuid.uuid4().hex}"
        batch.mkdir()
        profiles: list[ProfileEntry] = []
        inspections: list[StoreInspection] = []
        published: list[tuple[Path, Path]] = []
        try:
            for task in (1, 2, 3):
                store, manifest, digest = packages[task]
                profile = ProfileEntry(
                    uid=str(uuid.uuid4()),
                    name=f"task-{task}",
                    kind="MANAGED",
                    source={
                        "kind": "STUDY_BUNDLE",
                        "task": task,
                        "manifest_sha256": digest,
                        "canonical_language": manifest.get("canonical_language"),
                    },
                )
                staging = batch / profile.uid
                inspection = _copy_store(store, staging)
                profiles.append(profile)
                inspections.append(inspection)
            for profile in profiles:
                source = batch / profile.uid
                destination = profile_store_dir(profile)
                if destination.exists() or destination.is_symlink():
                    raise ProfileError("Managed profile destination is occupied.")
                os.replace(source, destination)
                published.append((destination, source))
            updated = ProfileRegistry(
                generation=max(1, registry.generation + 1),
                active_uid=registry.active_uid,
                profiles=(*registry.profiles, *profiles),
            )
            try:
                _write_registry(updated)
            except Exception:
                for destination, source in reversed(published):
                    os.replace(destination, source)
                published.clear()
                raise
            final_inspections = tuple(
                StoreInspection(
                    root=profile_store_dir(profile),
                    current_context=inspection.current_context,
                    context_names=inspection.context_names,
                    query_source_count=inspection.query_source_count,
                    translation_catalog_count=inspection.translation_catalog_count,
                )
                for profile, inspection in zip(profiles, inspections, strict=True)
            )
            return StudyImportResult(tuple(profiles), final_inspections)
        finally:
            if batch.exists() and not batch.is_symlink():
                shutil.rmtree(batch)
