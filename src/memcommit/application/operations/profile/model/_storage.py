"""Shared Profile store inspection and atomic publication primitives."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_store_dir,
    profile_stores_dir,
)
from memcommit.models.profile import Profile
from memcommit.persistence.store.infrastructure.storage_permissions import (
    ensure_private_directory,
    open_private_exclusive,
)


from memcommit.application.operations.profile.errors import ProfileError as ProfileError


@dataclass(frozen=True)
class ContextInventory:
    """Countable direct records for one validated ordinary Context."""

    uid: str
    name: str
    direct_memory_count: int


@dataclass(frozen=True)
class StoreInspection:
    """Read-only summary of one validated complete ProfileStore."""

    root: Path
    current_context: str | None
    context_names: tuple[str, ...]
    ordinary_memory_count: int
    context_inventory: tuple[ContextInventory, ...]


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
) -> dict[str, Context]:
    contexts_dir = root / "contexts"
    if contexts_dir.is_symlink() or not contexts_dir.is_dir():
        raise ProfileError("ProfileStore contexts directory is missing or unsafe.")
    contexts: dict[str, Context] = {}
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
    return contexts


def _context_record_at(root: Path, name: str) -> Context | None:
    """Load only one exact Context without inspecting sibling authority data."""

    from memcommit.core.context_name_validation import validate_context_name

    canonical_name = validate_context_name(name)
    contexts_dir = root / "contexts"
    if contexts_dir.is_symlink() or not contexts_dir.is_dir():
        raise ProfileError("ProfileStore contexts directory is missing or unsafe.")
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


def inspect_store(
    root: Path,
) -> StoreInspection:
    """Validate one complete store without creating or resolving content."""

    root = Path(root).absolute()
    _assert_plain_tree(root, label="ProfileStore")
    contexts = _context_records(root)
    state = _read_json(root / "state.json", label="ProfileStore state")
    current = state.get("current")
    if current is not None and (
        not isinstance(current, str) or current not in contexts
    ):
        raise ProfileError("ProfileStore current Context is invalid.")
    context_inventory = tuple(
        ContextInventory(
            uid=context.uid,
            name=name,
            direct_memory_count=sum(
                isinstance(item, Memory) for item in context.iter_memories()
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
        context_inventory=context_inventory,
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


def _write_registry(registry: ProfileRegistry) -> None:
    _ensure_control_dirs()
    path = profile_registry_file()
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


def _prepare_profile_deletion_batch(profiles: tuple[Profile, ...]) -> Path:
    """Prepare reversible sibling moves, including projects on other devices."""
    from memcommit.application.operations.profile.project_root import (
        validate_profile_marker,
    )

    _ensure_control_dirs()
    batch = profile_stores_dir() / f".permanent-profile-removal-{uuid.uuid4().hex}"
    batch.mkdir(mode=0o700)
    entries = []
    try:
        for profile in profiles:
            source = profile_store_dir(profile)
            if profile.kind != "MANAGED" or source.is_symlink() or not source.is_dir():
                raise ProfileError(f"Profile {profile.name!r} store cannot be deleted.")
            validate_profile_marker(profile)
            staged = source.parent / f".mem-removal-{uuid.uuid4().hex}"
            entries.append(
                {"uid": profile.uid, "source": str(source), "staged": str(staged)}
            )
        _write_json_file(batch / "moves.json", entries)
        for entry in entries:
            os.replace(entry["source"], entry["staged"])
            _fsync_directory(Path(entry["source"]).parent)
        _fsync_directory(batch)
        return batch
    except Exception:
        _rollback_profile_deletion_batch(batch, profiles)
        raise


def _write_json_file(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())


def _deletion_moves(batch: Path):
    path = batch / "moves.json"
    if path.is_symlink():
        raise ProfileError("Unsafe deletion manifest.")
    return json.loads(path.read_text()) if path.exists() else []


def _rollback_profile_deletion_batch(
    batch: Path, profiles: tuple[Profile, ...]
) -> None:
    expected = {p.uid: profile_store_dir(p) for p in profiles}
    for entry in reversed(_deletion_moves(batch)):
        source, staged = Path(entry["source"]), Path(entry["staged"])
        if expected.get(entry["uid"]) != source or staged.parent != source.parent:
            raise ProfileError("Invalid deletion rollback boundary.")
        if staged.exists():
            if source.exists() or source.is_symlink():
                raise ProfileError("Deletion rollback destination is occupied.")
            os.replace(staged, source)
            _fsync_directory(source.parent)
    (batch / "moves.json").unlink(missing_ok=True)
    batch.rmdir()


def _destroy_profile_deletion_batch(batch: Path) -> None:
    try:
        for entry in _deletion_moves(batch):
            source, staged = Path(entry["source"]), Path(entry["staged"])
            if (
                source.name != ".mem"
                or staged.parent != source.parent
                or not staged.name.startswith(".mem-removal-")
                or staged.is_symlink()
            ):
                raise ProfileError("Unsafe deletion cleanup boundary.")
            if staged.exists():
                shutil.rmtree(staged)
                _fsync_directory(source.parent)
        (batch / "moves.json").unlink(missing_ok=True)
        batch.rmdir()
        _fsync_directory(batch.parent)
    except Exception as error:
        raise ProfileError(
            "Profile was removed, but private Store cleanup did not finish."
        ) from error


def _publish_permanent_removal(
    previous: ProfileRegistry,
    updated: ProfileRegistry,
    *,
    batch: Path,
    profiles: tuple[Profile, ...],
    label: str,
) -> None:
    """Unregister deleted Profiles; roll back only before registry publication."""

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
            _rollback_profile_deletion_batch(batch=batch, profiles=profiles)
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


def _copy_store(source: Path, destination: Path) -> StoreInspection:
    _assert_plain_tree(source, label="Source ProfileStore")
    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Profile staging path is already occupied: {destination}")
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    return inspect_store(destination)
