"""Shared Profile store inspection, locking, and atomic publication primitives."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
from typing import Iterator
from memcommit.core.context import Context, Memory, QueryContextRef
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_registry_lock_file,
    profile_store_dir,
    profile_stores_dir,
    validate_grant_resource_name,
)
from memcommit.application.capabilities.authority.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)
from memcommit.core.memory_translation import TranslationCatalogError
from memcommit.persistence.store.translation_catalog import (
    decode_translation_catalog_record,
)


class ProfileError(RuntimeError):
    """A profile operation cannot complete without risking local state."""


@dataclass(frozen=True)
class ContextInventory:
    """Countable direct records for one validated ordinary Context."""

    uid: str
    name: str
    direct_memory_count: int


@dataclass(frozen=True)
class StoreInspection:
    """Read-only summary of one validated complete MemoryStore."""

    root: Path
    current_context: str | None
    context_names: tuple[str, ...]
    ordinary_memory_count: int
    query_source_count: int
    query_source_names: tuple[str, ...]
    translation_catalog_count: int
    context_inventory: tuple[ContextInventory, ...]
    granted_context_count: int = 0
    granted_memory_count: int = 0


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


def _context_record_at(root: Path, name: str) -> Context | None:
    """Load only one exact Context without inspecting sibling authority data."""

    canonical_name = validate_grant_resource_name(name)
    contexts_dir = root / "contexts"
    if contexts_dir.is_symlink() or not contexts_dir.is_dir():
        raise ProfileError("MemoryStore contexts directory is missing or unsafe.")
    context_dir = contexts_dir
    for part in canonical_name.split("/"):
        context_dir /= part
        if context_dir.is_symlink():
            raise ProfileError(f"Context {canonical_name!r} has an unsafe path.")
        if not context_dir.exists():
            return None
        if not context_dir.is_dir():
            raise ProfileError(f"Context {canonical_name!r} has an unsafe path.")
    record_path = context_dir / "context.json"
    if not record_path.exists():
        return None
    data = _read_json(record_path, label=f"Context {canonical_name!r}")
    try:
        context = Context.from_dict(data)
    except (KeyError, TypeError, ValueError) as error:
        raise ProfileError(f"Context {canonical_name!r} is invalid.") from error
    if context.name != canonical_name:
        raise ProfileError(
            f"Context path {canonical_name!r} does not match record {context.name!r}."
        )
    return context


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
            catalog = decode_translation_catalog_record(data)
        except (
            ProfileConfigError,
            TranslationCatalogError,
            TypeError,
            ValueError,
        ) as error:
            raise ProfileError(f"Translation catalog is invalid: {path}") from error
        context = by_uid.get(catalog.context_uid)
        if context is None or context.name != catalog.context_name:
            raise ProfileError(
                "Translation catalog does not identify a Context in this store."
            )
        count += 1
    return count


def inspect_store(
    root: Path,
    *,
    allowed_virtual_currents: frozenset[str] = frozenset(),
) -> StoreInspection:
    """Validate one complete store without creating or resolving content."""

    root = Path(root).absolute()
    _assert_plain_tree(root, label="MemoryStore")
    contexts, query_refs = _context_records(root)
    state = _read_json(root / "state.json", label="MemoryStore state")
    current = state.get("current")
    if current is not None and (
        not isinstance(current, str)
        or (current not in contexts and current not in allowed_virtual_currents)
    ):
        raise ProfileError("MemoryStore current Context is invalid.")
    sources = _query_sources(root)
    for source_uid, reference in query_refs.items():
        if sources.get(source_uid) != reference.name:
            raise ProfileError(
                f"Query-only Context {reference.name!r} has no matching source."
            )
    catalog_count = _translation_catalogs(root, contexts)
    context_inventory = tuple(
        ContextInventory(
            uid=context.uid,
            name=name,
            direct_memory_count=sum(
                isinstance(item, Memory) for item in context.iter_items()
            ),
        )
        for name, context in sorted(contexts.items())
    )
    return StoreInspection(
        root=root,
        current_context=current,
        context_names=tuple(sorted(contexts)),
        ordinary_memory_count=sum(
            item.direct_memory_count for item in context_inventory
        ),
        query_source_count=len(sources),
        # Only an ordinary QueryContextRef makes a source name public routing
        # metadata.  Do not surface names from orphaned concealed records.
        query_source_names=tuple(
            sorted(reference.name for reference in query_refs.values())
        ),
        translation_catalog_count=catalog_count,
        context_inventory=context_inventory,
    )


def _inspection_with_grants(
    registry: ProfileRegistry,
    profile: ProfileEntry,
    inspection: StoreInspection,
    *,
    cache: dict[str, StoreInspection] | None = None,
) -> StoreInspection:
    """Add distinct READ-granted resources without counting public aliases twice."""

    inspections = cache if cache is not None else {profile.uid: inspection}
    inspections.setdefault(profile.uid, inspection)
    profile_by_uid = {item.uid: item for item in registry.profiles}
    local_by_name = {item.name: item for item in inspection.context_inventory}
    seen_contexts: set[tuple[str, str]] = set()
    exact_authority: dict[tuple[str, str], ContextInventory] = {}
    granted_memory_count = 0

    for grant in registry.grants:
        if grant.grantee_profile_uid != profile.uid or "READ" not in grant.permissions:
            continue
        attachment = local_by_name.get(grant.attachment_context_name)
        if attachment is None or attachment.uid != grant.attachment_context_uid:
            raise ProfileError("Grant attachment Context identity changed.")
        authority = profile_by_uid[grant.authority_profile_uid]
        authority_inspection = inspections.get(authority.uid)
        authority_by_name = (
            {item.name: item for item in authority_inspection.context_inventory}
            if authority_inspection is not None
            else {}
        )
        for binding in grant.contexts:
            public_name = grant.public_name + binding.name[len(grant.resource_name) :]
            candidates = [
                candidate
                for candidate in registry.grants
                if candidate.grantee_profile_uid == profile.uid
                and candidate.attachment_context_uid == grant.attachment_context_uid
                and (
                    public_name == candidate.public_name
                    or public_name.startswith(candidate.public_name + "/")
                )
            ]
            effective = max(
                candidates,
                key=lambda candidate: len(candidate.public_name.split("/")),
            )
            if "READ" not in effective.permissions:
                continue
            granted = authority_by_name.get(binding.name)
            if granted is None and authority_inspection is None:
                cache_key = (authority.uid, binding.name)
                granted = exact_authority.get(cache_key)
                if granted is None:
                    # Selecting a task Profile needs counts only for effective
                    # READ bindings. Do not scan a sibling QUERY-only authority
                    # tree merely to render the task's inventory summary.
                    context = _context_record_at(
                        profile_store_dir(authority),
                        binding.name,
                    )
                    if context is not None:
                        granted = ContextInventory(
                            uid=context.uid,
                            name=context.name,
                            direct_memory_count=sum(
                                isinstance(item, Memory)
                                for item in context.iter_items()
                            ),
                        )
                        exact_authority[cache_key] = granted
            if granted is None or granted.uid != binding.uid:
                raise ProfileError("Grant authority Context identity changed.")
            identity = (authority.uid, granted.uid)
            if identity in seen_contexts:
                continue
            # Public aliases describe views, not additional knowledge. Count
            # each stable authority Context once even when two grants expose it.
            seen_contexts.add(identity)
            granted_memory_count += granted.direct_memory_count

    return replace(
        inspection,
        granted_context_count=len(seen_contexts),
        granted_memory_count=granted_memory_count,
    )


def _ensure_control_dirs() -> None:
    control = profile_control_dir()
    stores = profile_stores_dir()
    for path, label in ((control, "Profile control"), (stores, "Profile store")):
        if path.is_symlink():
            raise ProfileError(f"{label} directory cannot be a symbolic link.")
        if path.exists() and not path.is_dir():
            raise ProfileError(f"{label} storage is invalid.")
        try:
            ensure_private_directory(path, parents=True)
        except ValueError as error:
            raise ProfileError(str(error)) from error


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


@contextmanager
def authority_grant_snapshot_lock() -> Iterator[ProfileRegistry]:
    """Freeze Profile selection and grant revisions for one authorized publish."""

    with _registry_lock():
        yield load_profile_registry()


def _write_registry(registry: ProfileRegistry) -> None:
    path = profile_registry_file()
    ensure_private_directory(path.parent, parents=True)
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        descriptor = open_private_exclusive(temporary)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
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


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _read_granted_public_names(
    registry: ProfileRegistry,
    profile_uid: str,
) -> frozenset[str]:
    """Return public names whose effective frozen grant includes READ."""

    result: set[str] = set()
    grants = tuple(
        grant for grant in registry.grants if grant.grantee_profile_uid == profile_uid
    )
    for grant in grants:
        for binding in grant.contexts:
            public_name = grant.public_name + binding.name[len(grant.resource_name) :]
            candidates = tuple(
                candidate
                for candidate in grants
                if (
                    candidate.attachment_context_uid == grant.attachment_context_uid
                    and (
                        public_name == candidate.public_name
                        or public_name.startswith(candidate.public_name + "/")
                    )
                )
            )
            effective = max(
                candidates,
                key=lambda candidate: len(candidate.public_name.split("/")),
            )
            if "READ" in effective.permissions:
                result.add(public_name)
    return frozenset(result)


def _prepare_profile_deletion_batch(
    profiles: tuple[ProfileEntry, ...],
) -> Path:
    """Move exact managed stores aside before publishing their tombstones.

    The move and registry replacement are separate filesystem operations. A
    private same-filesystem batch makes the pre-publication half reversible:
    if the registry write fails, every canonical UID path can be restored
    before the registry lock is released. Once the registry is published, the
    batch is recursively destroyed and no mem recovery route remains.
    """

    stores = profile_stores_dir()
    batch = stores / f".permanent-profile-removal-{uuid.uuid4().hex}"
    batch.mkdir(mode=0o700)
    moved: list[ProfileEntry] = []
    try:
        for profile in profiles:
            source = profile_store_dir(profile)
            if (
                profile.kind != "MANAGED"
                or source.parent != stores
                or source.name != profile.uid
                or source.is_symlink()
                or not source.is_dir()
            ):
                raise ProfileError(
                    f"Profile {profile.name!r} store cannot be permanently deleted."
                )
            os.replace(source, batch / profile.uid)
            moved.append(profile)
        _fsync_directory(batch)
        _fsync_directory(stores)
        return batch
    except Exception as error:
        rollback_error: Exception | None = None
        for profile in reversed(moved):
            staged = batch / profile.uid
            destination = profile_store_dir(profile)
            try:
                if staged.exists() and not destination.exists():
                    os.replace(staged, destination)
            except Exception as candidate_error:  # pragma: no cover - fatal FS fault
                rollback_error = candidate_error
        try:
            if batch.exists() and not batch.is_symlink():
                batch.rmdir()
            _fsync_directory(stores)
        except Exception as candidate_error:  # pragma: no cover - fatal FS fault
            rollback_error = rollback_error or candidate_error
        if rollback_error is not None:
            raise ProfileError(
                "Profile deletion preparation rollback failed."
            ) from rollback_error
        if isinstance(error, ProfileError):
            raise
        raise ProfileError("Profile deletion could not be prepared.") from error


def _rollback_profile_deletion_batch(
    batch: Path,
    profiles: tuple[ProfileEntry, ...],
) -> None:
    """Restore a prepared batch after a registry write did not publish."""

    stores = profile_stores_dir()
    try:
        for profile in reversed(profiles):
            staged = batch / profile.uid
            destination = profile_store_dir(profile)
            if staged.exists():
                if destination.exists() or destination.is_symlink():
                    raise ProfileError(
                        f"Profile {profile.name!r} rollback destination is occupied."
                    )
                os.replace(staged, destination)
        batch.rmdir()
        _fsync_directory(stores)
    except Exception as error:
        raise ProfileError("Profile deletion rollback failed.") from error


def _destroy_profile_deletion_batch(batch: Path) -> None:
    """Permanently erase a registry-detached batch, including checkpoints."""

    stores = profile_stores_dir()
    try:
        if batch.is_symlink() or not batch.is_dir():
            raise ProfileError("Profile deletion batch is missing or unsafe.")
        shutil.rmtree(batch)
        _fsync_directory(stores)
    except Exception as error:
        raise ProfileError(
            "Profile identities were removed, but permanent store cleanup "
            "did not finish. No mem recovery route is available."
        ) from error


def _publish_permanent_removal(
    previous: ProfileRegistry,
    updated: ProfileRegistry,
    *,
    batch: Path,
    profiles: tuple[ProfileEntry, ...],
    label: str,
) -> None:
    """Publish tombstones, rolling back only before durable registry change."""

    try:
        _write_registry(updated)
    except Exception as error:
        try:
            visible = load_profile_registry()
        except (OSError, ProfileConfigError, ValueError) as read_error:
            raise ProfileError(
                f"{label} deletion registry state could not be confirmed; "
                f"prepared data remains at {batch}."
            ) from read_error
        if visible == previous:
            _rollback_profile_deletion_batch(batch, profiles)
            raise ProfileError(f"{label} was not deleted.") from error
        if visible == updated:
            _destroy_profile_deletion_batch(batch)
            raise ProfileError(
                f"{label} was permanently deleted, but registry durability "
                "could not be confirmed; it remains deleted."
            ) from error
        raise ProfileError(
            f"{label} deletion changed the registry unexpectedly; prepared "
            f"data remains at {batch}."
        ) from error
    _destroy_profile_deletion_batch(batch)


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
