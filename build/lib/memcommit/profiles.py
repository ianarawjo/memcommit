"""Whole-store profile registration and selection.

Profiles are a control-plane selector around complete MemoryStore roots.  A
single editable Study baseline deliberately namespaces all three task inputs
inside one root, and ``mem init-study`` snapshots that complete topology into
one new ordinary Profile.  Older split Study groups remain readable registry
records, but new initialization does not create task/authority subprofiles.
A process resolves its selected root once when :mod:`memcommit.store` is
imported, so a profile selection affects the next CLI invocation while an
already running operation finishes against the store it opened.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
from typing import Iterator

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AuthorityGrant,
    GRANT_RESOURCE_CONTEXT_TREE,
    GrantContextBinding,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_registry_lock_file,
    profile_store_dir,
    profile_stores_dir,
    canonical_grant_permissions,
    validate_grant_permission,
    validate_grant_resource_name,
    validate_profile_name,
)
from memcommit.translation_view import TranslationCatalog


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


@dataclass(frozen=True)
class StudyImportResult:
    profiles: tuple[ProfileEntry, ...]
    inspections: tuple[StoreInspection, ...]


@dataclass(frozen=True)
class _StudyProfileSource:
    """One validated profile store declared by a study task package."""

    task: int
    name: str
    role: str
    store: Path
    entries: tuple[object, ...]
    inspection: StoreInspection


@dataclass(frozen=True)
class _StudyTaskPackage:
    """Manifest data that is still independent of local Profile UIDs."""

    task: int
    schema_version: int
    manifest: dict[str, object]
    manifest_digest: str
    profiles: tuple[_StudyProfileSource, ...]
    grant_templates: tuple[dict[str, object], ...]
    query_view_count: int


@dataclass(frozen=True)
class StudyProfileGroup:
    """One timestamped Study whose three tasks remain isolated Profiles."""

    uid: str
    name: str
    created_at: str
    profiles: tuple[ProfileEntry, ...]
    support_profiles: tuple[ProfileEntry, ...] = ()


@dataclass(frozen=True)
class StudyInitializationResult:
    """One ordinary Profile copied from an editable Study baseline."""

    profile: ProfileEntry
    inspection: StoreInspection
    baseline_profile_name: str
    active_profile_name: str


@dataclass(frozen=True)
class GrantedContextView:
    """One validated Context view resolved for a grantee Profile."""

    grant: AuthorityGrant
    authority: ProfileEntry
    grantee: ProfileEntry
    requested_name: str
    authority_context_name: str
    authority_root: Path


def default_study_bundle_root() -> Path:
    """Return the editable-checkout fixture location when it is available."""

    return Path(__file__).resolve().parents[1] / "outputs" / "study-fixtures"


_STUDY_TASKS = (1, 2, 3)
STUDY_BASELINE_PROFILE_NAME = "study-baseline"
_STUDY_BASELINE_SOURCE_KIND = "STUDY_BASELINE"
_STUDY_BASELINE_SCHEMA_VERSION = 1
_STUDY_BASELINE_GRANTED_ROOT = "granted-memory"
_STUDY_PROFILE_SOURCE_KIND = "STUDY_RUN_TASK"
_STUDY_AUTHORITY_SOURCE_KIND = "STUDY_RUN_AUTHORITY"
_STUDY_PROFILE_SOURCE_FIELDS = {
    "kind",
    "study_uid",
    "study_name",
    "created_at",
    "task",
    "manifest_sha256",
    "canonical_language",
}
_STUDY_PROFILE_OPTIONAL_SOURCE_FIELDS = {
    "baseline_sha256",
    "baseline_profile_uid",
    "baseline_profile_name",
}
_BASELINE_TOP_LEVEL_DIRECTORIES = (
    "query-sources",
    "translation-views",
)


def _study_task_profile_name(study_name: str, task: int) -> str:
    candidate = f"{study_name}-task-{task}"
    try:
        return validate_profile_name(candidate)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError(
            "Study name is too long to create portable Task Profile names."
        ) from error


def _study_authority_profile_name(study_name: str, source_name: str) -> str:
    try:
        return validate_profile_name(f"{study_name}-{source_name}")
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError(
            "Study name is too long to create portable authority Profile names."
        ) from error


def _timezone_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileError("Study creation timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ProfileError("Study creation timestamp is invalid.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProfileError("Study creation timestamp must include a timezone.")
    return value


def study_profile_groups(
    profiles: tuple[ProfileEntry, ...],
) -> tuple[StudyProfileGroup, ...]:
    """Validate and group Profiles created together by ``mem init-study``.

    The grouping is immutable source provenance rather than a Context
    hierarchy. This keeps every Task a complete independent MemoryStore while
    allowing Profile UIs to present the three stores under one Study heading.
    """

    grouped: dict[str, list[tuple[int, str, ProfileEntry, str, str]]] = {}
    order: list[str] = []
    for profile in profiles:
        source = profile.source
        if not isinstance(source, dict) or source.get("kind") not in {
            _STUDY_PROFILE_SOURCE_KIND,
            _STUDY_AUTHORITY_SOURCE_KIND,
        }:
            continue
        source_fields = set(source)
        if (
            not _STUDY_PROFILE_SOURCE_FIELDS.issubset(source_fields)
            or source_fields - _STUDY_PROFILE_SOURCE_FIELDS
            > _STUDY_PROFILE_OPTIONAL_SOURCE_FIELDS
        ):
            raise ProfileError("Study Profile provenance fields are invalid.")
        raw_uid = source.get("study_uid")
        try:
            study_uid = str(uuid.UUID(raw_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ProfileError("Study uid is invalid.") from error
        if raw_uid != study_uid:
            raise ProfileError("Study uid is invalid.")
        raw_name = source.get("study_name")
        try:
            study_name = validate_profile_name(raw_name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study name is invalid.") from error
        created_at = _timezone_timestamp(source.get("created_at"))
        task = source.get("task")
        if type(task) is not int or task not in _STUDY_TASKS:
            raise ProfileError("Study Task number is invalid.")
        _manifest_digest(source.get("manifest_sha256"), field="manifest digest")
        if "baseline_sha256" in source:
            _manifest_digest(source.get("baseline_sha256"), field="baseline digest")
        baseline_profile_uid = source.get("baseline_profile_uid")
        baseline_profile_name = source.get("baseline_profile_name")
        if (baseline_profile_uid is None) != (baseline_profile_name is None):
            raise ProfileError("Study baseline Profile provenance is incomplete.")
        if baseline_profile_uid is not None:
            _study_uuid(baseline_profile_uid, label="baseline Profile uid")
            try:
                validate_profile_name(baseline_profile_name)
            except (ProfileConfigError, ValueError) as error:
                raise ProfileError(
                    "Study baseline Profile provenance is invalid."
                ) from error
        canonical_language = source.get("canonical_language")
        if not isinstance(canonical_language, str) or not canonical_language:
            raise ProfileError("Study canonical language is invalid.")
        role = (
            "TASK" if source.get("kind") == _STUDY_PROFILE_SOURCE_KIND else "AUTHORITY"
        )
        expected_name = (
            _study_task_profile_name(study_name, task)
            if role == "TASK"
            else _study_authority_profile_name(
                study_name,
                _STUDY_AUTHORITY_PROFILE_NAMES[task],
            )
        )
        if profile.kind != "MANAGED" or profile.name != expected_name:
            raise ProfileError("Study Task Profile identity is inconsistent.")
        if study_uid not in grouped:
            grouped[study_uid] = []
            order.append(study_uid)
        grouped[study_uid].append((task, role, profile, study_name, created_at))

    result: list[StudyProfileGroup] = []
    seen_names: set[str] = set()
    for study_uid in order:
        members = sorted(grouped[study_uid], key=lambda item: (item[0], item[1]))
        task_members = [member for member in members if member[1] == "TASK"]
        support_members = [member for member in members if member[1] == "AUTHORITY"]
        if [task for task, _role, _profile, _name, _created in task_members] != list(
            _STUDY_TASKS
        ):
            raise ProfileError(
                "A Study must contain exactly Task 1, Task 2, and Task 3."
            )
        if support_members and [
            task for task, _role, _profile, _name, _created in support_members
        ] != list(_STUDY_TASKS):
            raise ProfileError("Study authority Profile topology is incomplete.")
        names = {name for _task, _role, _profile, name, _created in members}
        timestamps = {created for _task, _role, _profile, _name, created in members}
        if len(names) != 1 or len(timestamps) != 1:
            raise ProfileError("Study Task Profile provenance is inconsistent.")
        name = next(iter(names))
        if name.casefold() in seen_names:
            raise ProfileError("Study names must be unique.")
        seen_names.add(name.casefold())
        result.append(
            StudyProfileGroup(
                uid=study_uid,
                name=name,
                created_at=next(iter(timestamps)),
                profiles=tuple(
                    profile for _task, _role, profile, _name, _created in task_members
                ),
                support_profiles=tuple(
                    profile
                    for _task, _role, profile, _name, _created in support_members
                ),
            )
        )
    return tuple(result)


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
            f"Context path {canonical_name!r} does not match record "
            f"{context.name!r}."
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
            catalog = TranslationCatalog.from_dict(data)
        except (ProfileConfigError, TypeError, ValueError) as error:
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
            {
                item.name: item
                for item in authority_inspection.context_inventory
            }
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


@contextmanager
def authority_grant_snapshot_lock() -> Iterator[ProfileRegistry]:
    """Freeze Profile selection and grant revisions for one authorized publish."""

    with _registry_lock():
        yield load_profile_registry()


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
    base = tuple(inspect_store(profile_store_dir(item)) for item in registry.profiles)
    cache = {
        profile.uid: inspection
        for profile, inspection in zip(registry.profiles, base, strict=True)
    }
    return registry, tuple(
        _inspection_with_grants(
            registry,
            profile,
            inspection,
            cache=cache,
        )
        for profile, inspection in zip(registry.profiles, base, strict=True)
    )


def use_profile(name: str) -> tuple[ProfileRegistry, StoreInspection, bool]:
    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        target = registry.by_name(canonical)
        if target is None:
            raise ProfileError(f"Profile {canonical!r} does not exist.")
        inspection = _inspection_with_grants(
            registry,
            target,
            inspect_store(profile_store_dir(target)),
        )
        if target.uid == registry.active_uid:
            return registry, inspection, False
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=target.uid,
            profiles=registry.profiles,
            grants=registry.grants,
        )
        _write_registry(updated)
        return updated, inspection, True


def _grant_selector(
    registry: ProfileRegistry,
    selector: str,
) -> AuthorityGrant:
    matches = [grant for grant in registry.grants if grant.uid.startswith(selector)]
    if not matches:
        raise ProfileError(f"Grant {selector!r} does not exist.")
    if len(matches) > 1:
        raise ProfileError(
            f"Grant selector {selector!r} is ambiguous: "
            + ", ".join(grant.uid[:8] for grant in matches)
        )
    return matches[0]


def _grant_scope(
    contexts: dict[str, Context],
    resource_name: str,
    *,
    recursive: bool,
) -> tuple[GrantContextBinding, ...]:
    root = contexts.get(resource_name)
    if root is None:
        raise ProfileError(f"Authority Context {resource_name!r} does not exist.")
    names = [resource_name]
    if recursive:
        prefix = resource_name + "/"
        names.extend(name for name in sorted(contexts) if name.startswith(prefix))
    return tuple(
        GrantContextBinding(uid=contexts[name].uid, name=name) for name in names
    )


def _assert_grantee_attachment(
    grantee: ProfileEntry,
    attachment_name: str,
) -> Context:
    contexts, _ = _context_records(profile_store_dir(grantee))
    attachment = contexts.get(attachment_name)
    if attachment is None:
        raise ProfileError(
            f"Grantee Context {attachment_name!r} does not exist in "
            f"Profile {grantee.name!r}."
        )
    return attachment


def _assert_public_view_available(
    registry: ProfileRegistry,
    *,
    grantee: ProfileEntry,
    attachment: Context,
    public_name: str,
    replacing_uid: str | None = None,
) -> None:
    grantee_contexts, _ = _context_records(profile_store_dir(grantee))
    public_folded = public_name.casefold()
    for name in grantee_contexts:
        name_folded = name.casefold()
        if (
            name_folded == public_folded
            or name_folded.startswith(public_folded + "/")
            or public_folded.startswith(name_folded + "/")
        ):
            raise ProfileError(
                f"Granted view {public_name!r} overlaps local Context {name!r}."
            )
    for grant in registry.grants:
        if grant.uid == replacing_uid:
            continue
        if (
            grant.grantee_profile_uid == grantee.uid
            and grant.attachment_context_uid == attachment.uid
            and grant.public_name.casefold() == public_folded
        ):
            raise ProfileError(
                f"Granted view {public_name!r} already exists on {attachment.name!r}."
            )


def create_authority_grant(
    *,
    authority_name: str,
    grantee_name: str,
    resource_name: str,
    attachment_name: str,
    permissions: object,
    public_name: str | None = None,
    recursive: bool = False,
    grant_uid: str | None = None,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Create one exact cross-Profile Context view under the registry lock."""

    canonical_permissions = canonical_grant_permissions(permissions)
    with _registry_lock():
        registry = load_profile_registry()
        authority = registry.by_name(authority_name)
        grantee = registry.by_name(grantee_name)
        if authority is None:
            raise ProfileError(f"Profile {authority_name!r} does not exist.")
        if grantee is None:
            raise ProfileError(f"Profile {grantee_name!r} does not exist.")
        if authority.uid == grantee.uid:
            raise ProfileError("A Profile cannot grant a view to itself.")
        authority_contexts, _ = _context_records(profile_store_dir(authority))
        scope = _grant_scope(
            authority_contexts,
            resource_name,
            recursive=recursive,
        )
        attachment = _assert_grantee_attachment(grantee, attachment_name)
        public = public_name or resource_name
        public = validate_grant_resource_name(public)
        _assert_public_view_available(
            registry,
            grantee=grantee,
            attachment=attachment,
            public_name=public,
        )
        uid = grant_uid or str(uuid.uuid4())
        try:
            uid = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ProfileError("Grant uid must be a canonical UUID.") from error
        if grant_uid is not None and uid != grant_uid:
            raise ProfileError("Grant uid must be a canonical UUID.")
        if any(grant.uid == uid for grant in registry.grants):
            raise ProfileError(f"Grant {uid!r} already exists.")
        root = scope[0]
        grant = AuthorityGrant(
            uid=uid,
            revision=1,
            authority_profile_uid=authority.uid,
            grantee_profile_uid=grantee.uid,
            attachment_context_uid=attachment.uid,
            attachment_context_name=attachment.name,
            resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
            resource_uid=root.uid,
            resource_name=root.name,
            public_name=public,
            permissions=canonical_permissions,
            contexts=scope,
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=(*registry.grants, grant),
        )
        _write_registry(updated)
        return updated, grant


def update_authority_grant(
    selector: str,
    *,
    permissions: object,
    recursive: bool | None = None,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Replace one grant's permissions and optionally refresh its exact scope."""

    canonical_permissions = canonical_grant_permissions(permissions)
    with _registry_lock():
        registry = load_profile_registry()
        existing = _grant_selector(registry, selector)
        authority = next(
            profile
            for profile in registry.profiles
            if profile.uid == existing.authority_profile_uid
        )
        grantee = next(
            profile
            for profile in registry.profiles
            if profile.uid == existing.grantee_profile_uid
        )
        attachment = _assert_grantee_attachment(
            grantee,
            existing.attachment_context_name,
        )
        if attachment.uid != existing.attachment_context_uid:
            raise ProfileError("Grant attachment Context identity changed.")
        authority_contexts, _ = _context_records(profile_store_dir(authority))
        if recursive is None:
            scope = existing.contexts
            for binding in scope:
                current = authority_contexts.get(binding.name)
                if current is None or current.uid != binding.uid:
                    raise ProfileError("Grant authority Context scope changed.")
        else:
            scope = _grant_scope(
                authority_contexts,
                existing.resource_name,
                recursive=recursive,
            )
        replacement = AuthorityGrant(
            uid=existing.uid,
            revision=existing.revision + 1,
            authority_profile_uid=existing.authority_profile_uid,
            grantee_profile_uid=existing.grantee_profile_uid,
            attachment_context_uid=existing.attachment_context_uid,
            attachment_context_name=existing.attachment_context_name,
            resource_kind=existing.resource_kind,
            resource_uid=scope[0].uid,
            resource_name=scope[0].name,
            public_name=existing.public_name,
            permissions=canonical_permissions,
            contexts=scope,
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=tuple(
                replacement if grant.uid == existing.uid else grant
                for grant in registry.grants
            ),
        )
        _write_registry(updated)
        return updated, replacement


def delete_authority_grant(
    selector: str,
) -> tuple[ProfileRegistry, AuthorityGrant]:
    """Revoke one exact grant without touching either Profile's data."""

    with _registry_lock():
        registry = load_profile_registry()
        removed = _grant_selector(registry, selector)
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=tuple(
                grant for grant in registry.grants if grant.uid != removed.uid
            ),
        )
        _write_registry(updated)
        return updated, removed


def list_authority_grants() -> tuple[ProfileRegistry, tuple[AuthorityGrant, ...]]:
    registry = load_profile_registry()
    return registry, registry.grants


def grants_for_attachment(
    *,
    attachment_name: str,
    registry: ProfileRegistry | None = None,
) -> tuple[AuthorityGrant, ...]:
    """Return validated grant metadata attached to one active-Profile Context."""

    registry = registry or load_profile_registry()
    grantee = registry.active
    attachment = _context_record_at(profile_store_dir(grantee), attachment_name)
    if attachment is None:
        return ()
    return tuple(
        sorted(
            (
                grant
                for grant in registry.grants
                if grant.grantee_profile_uid == grantee.uid
                and grant.attachment_context_uid == attachment.uid
                and grant.attachment_context_name == attachment.name
            ),
            key=lambda grant: grant.public_name,
        )
    )


def resolve_granted_context_view(
    requested_name: str,
    *,
    attachment_name: str,
    required_permission: str,
    registry: ProfileRegistry | None = None,
) -> GrantedContextView:
    """Resolve the most-specific grant and fail closed on narrower overrides."""

    registry = registry or load_profile_registry()
    permission = validate_grant_permission(required_permission)
    grantee = registry.active
    attached = grants_for_attachment(
        attachment_name=attachment_name,
        registry=registry,
    )
    candidates = [
        grant
        for grant in attached
        if requested_name == grant.public_name
        or requested_name.startswith(grant.public_name + "/")
    ]
    if not candidates:
        raise ProfileError(f"Granted view {requested_name!r} does not exist.")
    grant = max(candidates, key=lambda item: len(item.public_name.split("/")))
    suffix = requested_name[len(grant.public_name) :]
    authority_name = grant.resource_name + suffix
    bindings = {binding.name: binding.uid for binding in grant.contexts}
    authority_uid = bindings.get(authority_name)
    if authority_uid is None:
        raise ProfileError(
            f"Context {requested_name!r} is outside the grant's frozen scope."
        )
    if permission not in grant.permissions:
        raise ProfileError(
            f"Grant {grant.uid[:8]} does not allow {permission.lower()} access "
            f"to {requested_name!r}."
        )
    authority = next(
        profile
        for profile in registry.profiles
        if profile.uid == grant.authority_profile_uid
    )
    authority_root = profile_store_dir(authority)
    # Runtime view resolution must not inspect sibling or narrower authority
    # Contexts merely to validate one frozen binding.  This is especially
    # important when a readable parent has a query-only nested override.
    context = _context_record_at(authority_root, authority_name)
    if context is None or context.uid != authority_uid:
        raise ProfileError("Granted authority Context identity changed.")
    return GrantedContextView(
        grant=grant,
        authority=authority,
        grantee=grantee,
        requested_name=requested_name,
        authority_context_name=authority_name,
        authority_root=authority_root,
    )


def _source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_store(source: Path, destination: Path) -> StoreInspection:
    _assert_plain_tree(source, label="Source MemoryStore")
    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Profile staging path is already occupied: {destination}")
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    return inspect_store(destination)


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
            updated = replace(
                registry,
                generation=max(1, registry.generation + 1),
                profiles=(*registry.profiles, profile),
            )
            try:
                _write_registry(updated)
            except Exception:
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
    digest = baseline_store_digest(source_root)
    imported_at = datetime.now(timezone.utc).isoformat()
    with _registry_lock():
        registry = load_profile_registry()
        if registry.by_name(canonical) is not None:
            raise ProfileError(f"Profile {canonical!r} already exists.")
        source_record: dict[str, object] = {
            "kind": "BASELINE_IMPORT",
            "imported_at": imported_at,
            "baseline_sha256": digest,
        }
        if source_profile is not None:
            # Record the registry identity rather than an internal store path;
            # paths are implementation details and can disclose host layout.
            source_record.update(
                {
                    "kind": "PROFILE_IMPORT",
                    "source_profile_uid": source_profile.uid,
                    "source_profile_name": source_profile.name,
                }
            )
        profile = ProfileEntry(
            uid=str(uuid.uuid4()),
            name=canonical,
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
            except Exception:
                os.replace(destination, staging)
                published = False
                raise
            return profile, replace(inspection, root=destination)
        finally:
            candidate = profile_store_dir(profile) if published else staging
            if not published and candidate.exists() and not candidate.is_symlink():
                shutil.rmtree(candidate)


_STUDY_BUNDLE_NAMESPACE = uuid.UUID("50b72d54-cfbe-4f89-8f7f-1e6c785d8552")
_STUDY_AUTHORITY_PROFILE_NAMES = {
    1: "task-1-campus-authority",
    2: "task-2-proposal-authority",
    3: "task-3-healthcare-authority",
}


def _study_integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProfileError(f"Study manifest {label} is invalid.")
    return value


def _study_uuid(value: object, *, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ProfileError(f"Study manifest {label} is invalid.") from error
    if value != canonical:
        raise ProfileError(f"Study manifest {label} is invalid.")
    return canonical


def _expected_study_grant_uid(task: int, key: str) -> str:
    seed = "\0".join((f"task-{task}", "grant", key))
    return str(uuid.uuid5(_STUDY_BUNDLE_NAMESPACE, seed))


def _legacy_study_package(
    package: Path,
    manifest_path: Path,
    manifest: dict[str, object],
    task: int,
) -> _StudyTaskPackage:
    """Normalize the former one-store package when it is encountered."""

    store = package / ".mem"
    inspection = inspect_store(store)
    expected_current = manifest.get("current_context")
    if inspection.current_context != expected_current:
        raise ProfileError(f"Task {task} package current Context is inconsistent.")
    ordinary_count = _study_integer(
        manifest.get("ordinary_count"),
        label=f"Task {task} ordinary count",
    )
    query_count = _study_integer(
        manifest.get("query_only_count"),
        label=f"Task {task} query-only count",
    )
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != ordinary_count + query_count:
        raise ProfileError(f"Task {task} manifest counts are invalid.")
    if (
        inspection.ordinary_memory_count != ordinary_count
        # A bilingual QuerySource contains many concealed entries. The
        # manifest count describes those Memory-shaped entries, not the
        # number of source container files in the store.
        or len(_study_query_entries(store)) != query_count
    ):
        raise ProfileError(f"Task {task} manifest counts are invalid.")
    _validate_study_manifest_content(
        store,
        entries,
        ordinary_count=ordinary_count,
        query_count=query_count,
        task=task,
    )
    return _StudyTaskPackage(
        task=task,
        schema_version=1,
        manifest=manifest,
        manifest_digest=_source_digest(manifest_path),
        profiles=(
            _StudyProfileSource(
                task=task,
                name=f"task-{task}",
                role="TASK",
                store=store,
                entries=tuple(entries),
                inspection=inspection,
            ),
        ),
        grant_templates=(),
        query_view_count=0,
    )


def _study_package(
    bundle_root: Path,
    task: int,
) -> _StudyTaskPackage:
    """Validate one package without allocating or publishing local identities."""

    package = bundle_root / f"task-{task}"
    if package.is_symlink() or not package.is_dir():
        raise ProfileError(f"Task {task} package is missing or unsafe.")
    manifest_path = package / "manifest.json"
    manifest = _read_json(manifest_path, label=f"Task {task} manifest")
    if manifest.get("task") != task:
        raise ProfileError(f"Task {task} manifest identifies a different task.")
    schema_version = manifest.get("schema_version", 1)
    if schema_version == 1:
        return _legacy_study_package(package, manifest_path, manifest, task)
    if schema_version != 2:
        raise ProfileError(f"Task {task} manifest schema version is unsupported.")
    if manifest.get("canonical_language") != "en" or manifest.get(
        "translation_languages"
    ) != ["ko"]:
        raise ProfileError(f"Task {task} manifest language contract is invalid.")

    raw_profiles = manifest.get("profiles")
    expected_names = (
        f"task-{task}",
        _STUDY_AUTHORITY_PROFILE_NAMES[task],
    )
    if not isinstance(raw_profiles, list) or len(raw_profiles) != 2:
        raise ProfileError(f"Task {task} manifest profiles are invalid.")
    if [
        raw.get("profile_name") for raw in raw_profiles if isinstance(raw, dict)
    ] != list(expected_names):
        raise ProfileError(f"Task {task} manifest profiles are invalid.")

    profile_sources: list[_StudyProfileSource] = []
    combined_entries: list[object] = []
    for index, raw in enumerate(raw_profiles):
        if not isinstance(raw, dict):
            raise ProfileError(f"Task {task} manifest profile is invalid.")
        name = raw.get("profile_name")
        expected_name = expected_names[index]
        expected_role = "TASK" if index == 0 else "AUTHORITY"
        try:
            canonical_name = validate_profile_name(name)
        except (TypeError, ValueError) as error:
            raise ProfileError(
                f"Task {task} manifest profile name is invalid."
            ) from error
        if canonical_name != expected_name or raw.get("role") != expected_role:
            raise ProfileError(f"Task {task} manifest profile role is invalid.")
        expected_store_path = (Path("profiles") / canonical_name / ".mem").as_posix()
        if raw.get("store_path") != expected_store_path:
            raise ProfileError(f"Task {task} manifest profile path is invalid.")
        store = package / expected_store_path
        inspection = inspect_store(store)
        if inspection.current_context != raw.get("current_context"):
            raise ProfileError(
                f"Task {task} Profile {canonical_name!r} current Context is inconsistent."
            )
        context_count = _study_integer(
            raw.get("context_count"),
            label=f"Task {task} Profile context count",
        )
        ordinary_count = _study_integer(
            raw.get("ordinary_count"),
            label=f"Task {task} Profile ordinary count",
        )
        entries = raw.get("entries")
        datasets = raw.get("datasets")
        if (
            context_count != len(inspection.context_names)
            or ordinary_count != inspection.ordinary_memory_count
            or inspection.query_source_count != 0
            or not isinstance(entries, list)
            or len(entries) != ordinary_count
            or not isinstance(datasets, list)
            or any(not isinstance(dataset, str) or not dataset for dataset in datasets)
            or len(set(datasets)) != len(datasets)
        ):
            raise ProfileError(f"Task {task} manifest profile counts are invalid.")
        entry_datasets: set[str] = set()
        for entry in entries:
            if (
                not isinstance(entry, dict)
                or entry.get("owner_profile") != canonical_name
                or entry.get("query_only") is not False
                or not isinstance(entry.get("dataset"), str)
            ):
                raise ProfileError(f"Task {task} manifest profile entry is invalid.")
            entry_datasets.add(entry["dataset"])
        if entry_datasets != set(datasets):
            raise ProfileError(f"Task {task} manifest profile datasets are invalid.")
        _validate_study_manifest_content(
            store,
            entries,
            ordinary_count=ordinary_count,
            query_count=0,
            task=task,
            expected_owner_profile=canonical_name,
        )
        combined_entries.extend(entries)
        profile_sources.append(
            _StudyProfileSource(
                task=task,
                name=canonical_name,
                role=expected_role,
                store=store,
                entries=tuple(entries),
                inspection=inspection,
            )
        )

    ordinary_count = _study_integer(
        manifest.get("ordinary_count"),
        label=f"Task {task} ordinary count",
    )
    query_count = _study_integer(
        manifest.get("query_only_count"),
        label=f"Task {task} query-only count",
    )
    query_view_count = _study_integer(
        manifest.get("query_view_count"),
        label=f"Task {task} query view count",
    )
    top_entries = manifest.get("entries")
    task_current = profile_sources[0].inspection.current_context
    if (
        ordinary_count
        != sum(source.inspection.ordinary_memory_count for source in profile_sources)
        or query_count != 0
        or query_view_count > ordinary_count
        or not isinstance(top_entries, list)
        or top_entries != combined_entries
        or manifest.get("current_context") != task_current
    ):
        raise ProfileError(f"Task {task} manifest counts are invalid.")
    memory_uids = [
        entry.get("memory_uid") for entry in top_entries if isinstance(entry, dict)
    ]
    if len(memory_uids) != ordinary_count or len(set(memory_uids)) != len(memory_uids):
        raise ProfileError(f"Task {task} manifest Memory identities are invalid.")
    raw_templates = manifest.get("grant_templates")
    if not isinstance(raw_templates, list) or any(
        not isinstance(template, dict) for template in raw_templates
    ):
        raise ProfileError(f"Task {task} grant templates are invalid.")
    return _StudyTaskPackage(
        task=task,
        schema_version=2,
        manifest=manifest,
        manifest_digest=_source_digest(manifest_path),
        profiles=tuple(profile_sources),
        grant_templates=tuple(raw_templates),
        query_view_count=query_view_count,
    )


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
    expected_owner_profile: str | None = None,
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
        if (
            expected_owner_profile is not None
            and raw.get("owner_profile") != expected_owner_profile
        ):
            raise ProfileError(f"Task {task} manifest owner Profile is invalid.")
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


def _study_manifest_context(
    value: object,
    *,
    contexts: dict[str, Context],
    label: str,
) -> Context:
    if not isinstance(value, dict) or set(value) != {"uid", "name"}:
        raise ProfileError(f"Study manifest {label} identity is invalid.")
    try:
        name = validate_grant_resource_name(value.get("name"))
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError(f"Study manifest {label} name is invalid.") from error
    uid = _study_uuid(value.get("uid"), label=f"{label} uid")
    context = contexts.get(name)
    if context is None or context.uid != uid:
        raise ProfileError(f"Study manifest {label} identity does not match its store.")
    return context


def _materialize_study_grants(
    packages: dict[int, _StudyTaskPackage],
    profiles_by_name: dict[str, ProfileEntry],
    staged_roots: dict[str, Path],
) -> tuple[AuthorityGrant, ...]:
    """Resolve templates only after every imported Profile has a local UID."""

    contexts_by_profile = {
        name: _context_records(root)[0] for name, root in staged_roots.items()
    }
    sources_by_name = {
        source.name: source
        for package in packages.values()
        for source in package.profiles
    }
    all_grants: list[AuthorityGrant] = []

    for task in _STUDY_TASKS:
        package = packages[task]
        if package.schema_version == 1:
            continue
        raw_by_key: dict[str, dict[str, object]] = {}
        ordered_keys: list[str] = []
        for raw in package.grant_templates:
            key = raw.get("key")
            if not isinstance(key, str) or not key or key in raw_by_key:
                raise ProfileError(f"Task {task} grant template key is invalid.")
            raw_by_key[key] = raw
            ordered_keys.append(key)

        resolved: dict[str, AuthorityGrant] = {}
        resolving: set[str] = set()

        def resolve(key: str) -> AuthorityGrant:
            existing = resolved.get(key)
            if existing is not None:
                return existing
            raw = raw_by_key.get(key)
            if raw is None:
                raise ProfileError(f"Task {task} grant parent does not exist.")
            if key in resolving:
                raise ProfileError(f"Task {task} grant attachments contain a cycle.")
            resolving.add(key)
            try:
                expected_fields = {
                    "schema_version",
                    "key",
                    "grant_uid",
                    "authority_profile",
                    "grantee_profile",
                    "authority_context",
                    "attachment",
                    "public_name",
                    "permissions",
                    "recursive",
                    "excluded_contexts",
                }
                if "provider" in raw:
                    expected_fields.add("provider")
                if set(raw) != expected_fields or raw.get("schema_version") != 1:
                    raise ProfileError(f"Task {task} grant template is invalid.")
                authority_name = raw.get("authority_profile")
                grantee_name = raw.get("grantee_profile")
                if (
                    not isinstance(authority_name, str)
                    or not isinstance(grantee_name, str)
                    or authority_name not in profiles_by_name
                    or grantee_name not in profiles_by_name
                    or sources_by_name.get(authority_name) is None
                    or sources_by_name.get(grantee_name) is None
                    or sources_by_name[authority_name].role != "AUTHORITY"
                    or sources_by_name[grantee_name].role != "TASK"
                    or authority_name
                    not in {source.name for source in package.profiles}
                    or grantee_name not in {source.name for source in package.profiles}
                ):
                    raise ProfileError(f"Task {task} grant Profile binding is invalid.")
                authority = profiles_by_name[authority_name]
                grantee = profiles_by_name[grantee_name]
                authority_contexts = contexts_by_profile[authority_name]
                grantee_contexts = contexts_by_profile[grantee_name]
                resource = _study_manifest_context(
                    raw.get("authority_context"),
                    contexts=authority_contexts,
                    label=f"Task {task} grant authority Context",
                )

                try:
                    permissions = canonical_grant_permissions(raw.get("permissions"))
                    public_component = validate_grant_resource_name(
                        raw.get("public_name")
                    )
                except (ProfileConfigError, ValueError) as error:
                    raise ProfileError(
                        f"Task {task} grant permissions or public name are invalid."
                    ) from error
                provider = raw.get("provider")
                if "QUERY" in permissions:
                    if not isinstance(provider, str) or not provider:
                        raise ProfileError(
                            f"Task {task} QUERY grant provider is invalid."
                        )
                elif "provider" in raw:
                    raise ProfileError(
                        f"Task {task} non-QUERY grant cannot declare a provider."
                    )

                grant_uid = _study_uuid(
                    raw.get("grant_uid"),
                    label=f"Task {task} grant uid",
                )
                if grant_uid != _expected_study_grant_uid(task, key):
                    raise ProfileError(
                        f"Task {task} grant uid is not deterministic for its key."
                    )

                attachment = raw.get("attachment")
                if not isinstance(attachment, dict):
                    raise ProfileError(f"Task {task} grant attachment is invalid.")
                attachment_kind = attachment.get("kind")
                if attachment_kind == "GRANTEE_CONTEXT":
                    if set(attachment) != {"kind", "context"}:
                        raise ProfileError(
                            f"Task {task} grantee attachment is invalid."
                        )
                    attached_context = _study_manifest_context(
                        attachment.get("context"),
                        contexts=grantee_contexts,
                        label=f"Task {task} grant attachment Context",
                    )
                    attachment_uid = attached_context.uid
                    attachment_name = attached_context.name
                    public_name = public_component
                elif attachment_kind == "GRANT_VIEW":
                    if set(attachment) != {"kind", "grant_key", "grant_uid"}:
                        raise ProfileError(
                            f"Task {task} nested grant attachment is invalid."
                        )
                    parent_key = attachment.get("grant_key")
                    if not isinstance(parent_key, str):
                        raise ProfileError(
                            f"Task {task} nested grant parent is invalid."
                        )
                    parent = resolve(parent_key)
                    parent_uid = _study_uuid(
                        attachment.get("grant_uid"),
                        label=f"Task {task} parent grant uid",
                    )
                    if (
                        parent_uid != parent.uid
                        or parent.grantee_profile_uid != grantee.uid
                        or parent.authority_profile_uid != authority.uid
                        or (
                            resource.name != parent.resource_name
                            and not resource.name.startswith(parent.resource_name + "/")
                        )
                    ):
                        raise ProfileError(
                            f"Task {task} nested grant parent binding is invalid."
                        )
                    # A GRANT_VIEW is a nested public locator, not a second
                    # attachment object. Runtime grants attach to the same
                    # local Context and rely on most-specific public matching.
                    attachment_uid = parent.attachment_context_uid
                    attachment_name = parent.attachment_context_name
                    public_name = f"{parent.public_name}/{public_component}"
                else:
                    raise ProfileError(f"Task {task} grant attachment is invalid.")

                recursive = raw.get("recursive")
                raw_exclusions = raw.get("excluded_contexts")
                if not isinstance(recursive, bool) or not isinstance(
                    raw_exclusions, list
                ):
                    raise ProfileError(f"Task {task} grant scope is invalid.")
                exclusions: list[Context] = []
                for raw_exclusion in raw_exclusions:
                    exclusion = _study_manifest_context(
                        raw_exclusion,
                        contexts=authority_contexts,
                        label=f"Task {task} grant exclusion",
                    )
                    if not exclusion.name.startswith(resource.name + "/"):
                        raise ProfileError(
                            f"Task {task} grant exclusion is outside its resource."
                        )
                    exclusions.append(exclusion)
                if len({item.uid for item in exclusions}) != len(exclusions):
                    raise ProfileError(f"Task {task} grant exclusions are duplicated.")
                scope = _grant_scope(
                    authority_contexts,
                    resource.name,
                    recursive=recursive,
                )
                if exclusions and not recursive:
                    raise ProfileError(
                        f"Task {task} non-recursive grant cannot have exclusions."
                    )
                scope = tuple(
                    binding
                    for binding in scope
                    if not any(
                        binding.name == exclusion.name
                        or binding.name.startswith(exclusion.name + "/")
                        for exclusion in exclusions
                    )
                )
                if not scope or scope[0].uid != resource.uid:
                    raise ProfileError(f"Task {task} grant root was excluded.")
                grant = AuthorityGrant(
                    uid=grant_uid,
                    revision=1,
                    authority_profile_uid=authority.uid,
                    grantee_profile_uid=grantee.uid,
                    attachment_context_uid=attachment_uid,
                    attachment_context_name=attachment_name,
                    resource_kind=GRANT_RESOURCE_CONTEXT_TREE,
                    resource_uid=resource.uid,
                    resource_name=resource.name,
                    public_name=public_name,
                    permissions=permissions,
                    contexts=scope,
                )
                resolved[key] = grant
                return grant
            finally:
                resolving.discard(key)

        package_grants = tuple(resolve(key) for key in ordered_keys)
        public_keys: set[tuple[str, str, str]] = set()
        for grant in package_grants:
            public_key = (
                grant.grantee_profile_uid,
                grant.attachment_context_uid,
                grant.public_name.casefold(),
            )
            if public_key in public_keys:
                raise ProfileError(f"Task {task} grant public names are duplicated.")
            public_keys.add(public_key)
            grantee_name = next(
                name
                for name, profile in profiles_by_name.items()
                if profile.uid == grant.grantee_profile_uid
            )
            for local_name in contexts_by_profile[grantee_name]:
                if (
                    local_name == grant.public_name
                    or local_name.startswith(grant.public_name + "/")
                    or grant.public_name.startswith(local_name + "/")
                ):
                    raise ProfileError(
                        f"Task {task} granted view overlaps a local Context."
                    )

        authority_names_by_uid = {
            profile.uid: name for name, profile in profiles_by_name.items()
        }
        query_memories: set[tuple[str, str]] = set()
        for grant in package_grants:
            if "QUERY" not in grant.permissions:
                continue
            authority_name = authority_names_by_uid[grant.authority_profile_uid]
            for binding in grant.contexts:
                context = contexts_by_profile[authority_name][binding.name]
                query_memories.update(
                    (grant.authority_profile_uid, item.uid)
                    for item in context.iter_items()
                    if isinstance(item, Memory)
                )
        if len(query_memories) != package.query_view_count:
            raise ProfileError(f"Task {task} query view count is inconsistent.")
        all_grants.extend(package_grants)

    if len({grant.uid for grant in all_grants}) != len(all_grants):
        raise ProfileError("Study grant uids are duplicated across task packages.")
    return tuple(all_grants)


def _publish_study_profile_batch(
    registry: ProfileRegistry,
    packages: dict[int, _StudyTaskPackage],
    profiles_by_source_name: dict[str, ProfileEntry],
    *,
    batch_label: str,
    grant_uid_namespace: str | None = None,
) -> StudyImportResult:
    """Publish a prepared task/authority topology under one registry lock."""

    sources = tuple(
        source for task in _STUDY_TASKS for source in packages[task].profiles
    )
    if set(profiles_by_source_name) != {source.name for source in sources}:
        raise ProfileError("Study Profile allocation does not match its manifests.")
    profiles = tuple(profiles_by_source_name[source.name] for source in sources)
    if len({profile.uid for profile in profiles}) != len(profiles):
        raise ProfileError("Study Profile uids must be unique.")
    batch = profile_stores_dir() / f".{batch_label}-{uuid.uuid4().hex}"
    batch.mkdir()
    inspections: list[StoreInspection] = []
    published: list[tuple[Path, Path]] = []
    committed = False
    try:
        staged_roots: dict[str, Path] = {}
        for source, profile in zip(sources, profiles, strict=True):
            staging = batch / profile.uid
            provenance = profile.source or {}
            baseline_digest = provenance.get("baseline_sha256")
            inspections.append(
                _copy_store_baseline(
                    source.store,
                    staging,
                    expected_digest=(
                        baseline_digest if isinstance(baseline_digest, str) else None
                    ),
                )
            )
            staged_roots[source.name] = staging

        grants = _materialize_study_grants(
            packages,
            profiles_by_source_name,
            staged_roots,
        )
        if grant_uid_namespace is not None:
            try:
                namespace = uuid.UUID(grant_uid_namespace)
            except (AttributeError, TypeError, ValueError) as error:
                raise ProfileError("Study grant namespace is invalid.") from error
            # Bundle grant UIDs are deterministic fixture identities. Each
            # Study needs distinct registry identities so repeated runs can
            # preserve the same topology without colliding with one another.
            grants = tuple(
                replace(grant, uid=str(uuid.uuid5(namespace, grant.uid)))
                for grant in grants
            )
        existing_grant_uids = {grant.uid for grant in registry.grants}
        conflicts = [grant.uid for grant in grants if grant.uid in existing_grant_uids]
        if conflicts:
            raise ProfileError(
                "Study grants already exist: " + ", ".join(uid[:8] for uid in conflicts)
            )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=(*registry.profiles, *profiles),
            grants=(*registry.grants, *grants),
        )
        cache = {
            profile.uid: inspection
            for profile, inspection in zip(profiles, inspections, strict=True)
        }
        grant_aware = tuple(
            _inspection_with_grants(
                updated,
                profile,
                inspection,
                cache=cache,
            )
            for profile, inspection in zip(profiles, inspections, strict=True)
        )

        destinations = tuple(profile_store_dir(profile) for profile in profiles)
        if any(
            destination.exists() or destination.is_symlink()
            for destination in destinations
        ):
            raise ProfileError("Managed profile destination is occupied.")
        for profile in profiles:
            source = batch / profile.uid
            destination = profile_store_dir(profile)
            os.replace(source, destination)
            published.append((destination, source))
        _write_registry(updated)
        committed = True
        final_inspections = tuple(
            replace(inspection, root=profile_store_dir(profile))
            for profile, inspection in zip(profiles, grant_aware, strict=True)
        )
        return StudyImportResult(profiles, final_inspections)
    except Exception:
        if not committed:
            for destination, source in reversed(published):
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
            published.clear()
        raise
    finally:
        if batch.exists() and not batch.is_symlink():
            shutil.rmtree(batch)


def _study_packages(
    bundle_root: Path,
) -> dict[int, _StudyTaskPackage]:
    root = Path(bundle_root).expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ProfileError(f"Study bundle root is missing or unsafe: {root}")
    packages = {task: _study_package(root, task) for task in _STUDY_TASKS}
    schema_versions = {package.schema_version for package in packages.values()}
    if len(schema_versions) != 1:
        raise ProfileError("Study bundle schema versions cannot be mixed.")
    return packages


def _study_baseline_branch(task: int, *, authority: bool) -> str:
    task_name = f"task-{task}"
    return (
        f"{_STUDY_BASELINE_GRANTED_ROOT}/{task_name}"
        if authority
        else task_name
    )


def _remap_context_records(
    contexts: dict[str, Context],
    mapping: dict[str, str],
) -> tuple[Context, ...]:
    """Rename a closed Context set while preserving every durable identity."""

    remapped: list[Context] = []
    for source_name in sorted(contexts):
        source = contexts[source_name]
        target = copy.deepcopy(source)
        target.name = mapping[source_name]
        for item in target.iter_items():
            if isinstance(item, QueryContextRef):
                raise ProfileError(
                    "The editable Study baseline cannot contain concealed "
                    "query-source pointers; granted material must be ordinary "
                    "Contexts under 'granted-memory'."
                )
            if isinstance(item, Context):
                referenced = contexts.get(item.name)
                if referenced is None or referenced.uid != item.uid:
                    raise ProfileError(
                        f"Context {source_name!r} has a stale external Context ref."
                    )
                item.name = mapping[item.name]
            elif isinstance(item, MemoryRef):
                referenced = contexts.get(item.target_context_name)
                if (
                    referenced is None
                    or referenced.uid != item.target_context_uid
                    or not isinstance(
                        referenced.memories.get(item.target_memory_uid),
                        Memory,
                    )
                ):
                    raise ProfileError(
                        f"Context {source_name!r} has a stale external Memory ref."
                    )
                item.target_context_name = mapping[item.target_context_name]
        remapped.append(target)
    return tuple(remapped)


def _remap_translation_catalogs(
    root: Path,
    mapping: dict[str, str],
) -> tuple[TranslationCatalog, ...]:
    catalogs = _study_catalogs(root)
    result: list[TranslationCatalog] = []
    for (context_name, _language), catalog in sorted(catalogs.items()):
        target_name = mapping.get(context_name)
        if target_name is None:
            raise ProfileError(
                "Translation catalog names a Context outside its Profile store."
            )
        result.append(replace(catalog, context_name=target_name))
    return tuple(result)


def _materialize_study_context_parents(
    contexts: tuple[Context, ...],
) -> tuple[Context, ...]:
    """Fill every missing lexical prefix with an empty ordinary Context.

    Study packages can legitimately predate a namespace root such as
    ``participant``.  Once several packages are composed below ``task-N``, a
    missing prefix would make both ``mem switch ..`` and ``mem ls -R`` stop at
    that gap.  The clean-store write boundary is the one place shared by
    baseline bootstrap and live-baseline cloning, so completing the chain here
    preserves the invariant in both stores without inventing embed edges.
    """

    by_name = {context.name: context for context in contexts}
    if len(by_name) != len(contexts):
        raise ProfileError("Study store Context names are duplicated.")
    missing: set[str] = set()
    for name in tuple(by_name):
        parts = name.split("/")
        missing.update(
            "/".join(parts[:index])
            for index in range(1, len(parts))
            if "/".join(parts[:index]) not in by_name
        )
    # These are structural navigation nodes, not copies of source content.
    # Fresh identities keep them ordinary editable Contexts while leaving all
    # imported Context and Memory identities untouched.
    for name in sorted(missing, key=lambda value: (value.count("/"), value)):
        by_name[name] = Context(uid=str(uuid.uuid4()), name=name)
    return tuple(by_name[name] for name in sorted(by_name))


def _write_mapped_study_store(
    destination: Path,
    *,
    contexts: tuple[Context, ...],
    catalogs: tuple[TranslationCatalog, ...],
    current_context: str,
) -> StoreInspection:
    """Write one already validated clean store without operational artifacts."""

    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Study store staging path is occupied: {destination}")
    contexts = _materialize_study_context_parents(contexts)
    names = {context.name for context in contexts}
    if current_context not in names:
        raise ProfileError("Study store current Context is missing from its branch.")
    uids = [context.uid for context in contexts]
    if len(uids) != len(set(uids)):
        raise ProfileError("Study store Context identities are duplicated.")

    from memcommit.store import _write_json_atomic

    (destination / "contexts").mkdir(parents=True)
    _write_json_atomic(destination / "state.json", {"current": current_context})
    for context in contexts:
        record = destination / "contexts"
        for part in context.name.split("/"):
            record /= part
        record.mkdir(parents=True)
        _write_json_atomic(record / "context.json", context.to_dict())

    if catalogs:
        catalog_root = destination / "translation-views"
        catalog_root.mkdir()
        for catalog in catalogs:
            language_digest = hashlib.sha256(
                catalog.target_language.encode("utf-8")
            ).hexdigest()
            path = catalog_root / (
                f"{catalog.context_uid}--{language_digest}--catalog.json"
            )
            if path.exists():
                raise ProfileError("Study translation catalog identity is duplicated.")
            _write_json_atomic(path, catalog.to_dict())
    return inspect_store(destination)


def _compose_study_baseline_store(
    packages: dict[int, _StudyTaskPackage],
    destination: Path,
) -> StoreInspection:
    """Compose all editable Task inputs into one namespaced source Profile."""

    structural_names = [
        *(f"task-{task}" for task in _STUDY_TASKS),
        _STUDY_BASELINE_GRANTED_ROOT,
        *(
            f"{_STUDY_BASELINE_GRANTED_ROOT}/task-{task}"
            for task in _STUDY_TASKS
        ),
    ]
    contexts = [Context(uid=str(uuid.uuid4()), name=name) for name in structural_names]
    catalogs: list[TranslationCatalog] = []
    seen_context_uids = {context.uid for context in contexts}
    for task in _STUDY_TASKS:
        package = packages[task]
        if package.schema_version != 2:
            raise ProfileError(
                "A single editable Study baseline requires schema-v2 packages."
            )
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source = next(
                (candidate for candidate in package.profiles if candidate.role == role),
                None,
            )
            if source is None:
                raise ProfileError(f"Task {task} {role.lower()} source is missing.")
            source_contexts, query_refs = _context_records(source.store)
            if query_refs:
                raise ProfileError(
                    "Study baseline sources must materialize granted Memory as "
                    "ordinary Contexts."
                )
            branch = _study_baseline_branch(task, authority=authority)
            mapping = {
                name: f"{branch}/{name}" for name in source_contexts
            }
            remapped = _remap_context_records(source_contexts, mapping)
            duplicate_uids = seen_context_uids.intersection(
                context.uid for context in remapped
            )
            if duplicate_uids:
                raise ProfileError("Study package Context identities collide.")
            seen_context_uids.update(context.uid for context in remapped)
            contexts.extend(remapped)
            catalogs.extend(_remap_translation_catalogs(source.store, mapping))

    return _write_mapped_study_store(
        destination,
        contexts=tuple(contexts),
        catalogs=tuple(catalogs),
        current_context="task-1",
    )


def _study_baseline_source_record(
    packages: dict[int, _StudyTaskPackage],
    *,
    imported_at: str,
    initial_digest: str,
) -> dict[str, object]:
    tasks: list[dict[str, object]] = []
    for task in _STUDY_TASKS:
        package = packages[task]
        task_source = next(source for source in package.profiles if source.role == "TASK")
        authority_source = next(
            source for source in package.profiles if source.role == "AUTHORITY"
        )
        tasks.append(
            {
                "task": task,
                "manifest_sha256": package.manifest_digest,
                "canonical_language": package.manifest.get("canonical_language"),
                "task_profile_name": task_source.name,
                "authority_profile_name": authority_source.name,
                "task_current_context": task_source.inspection.current_context,
                "authority_current_context": authority_source.inspection.current_context,
                "grant_templates": list(package.grant_templates),
            }
        )
    return {
        "kind": _STUDY_BASELINE_SOURCE_KIND,
        "schema_version": _STUDY_BASELINE_SCHEMA_VERSION,
        "imported_at": imported_at,
        "initial_baseline_sha256": initial_digest,
        "tasks": tasks,
    }


def _validate_study_package_grants(
    packages: dict[int, _StudyTaskPackage],
) -> None:
    """Bind bootstrap grant templates to their exact package-owned Contexts."""

    profiles_by_name = {
        source.name: ProfileEntry(
            uid=str(uuid.uuid4()),
            name=source.name,
            kind="MANAGED",
        )
        for task in _STUDY_TASKS
        for source in packages[task].profiles
    }
    roots = {
        source.name: source.store
        for task in _STUDY_TASKS
        for source in packages[task].profiles
    }
    _materialize_study_grants(packages, profiles_by_name, roots)


def import_study_profiles(bundle_root: Path) -> StudyImportResult:
    """Bootstrap one editable source Profile from the three fixture packages."""

    packages = _study_packages(bundle_root)
    _validate_study_package_grants(packages)
    imported_at = datetime.now(timezone.utc).isoformat()
    with _registry_lock():
        registry = load_profile_registry()
        if registry.by_name(STUDY_BASELINE_PROFILE_NAME) is not None:
            raise ProfileError(
                f"Profile {STUDY_BASELINE_PROFILE_NAME!r} already exists."
            )
        profile_uid = str(uuid.uuid4())
        staging = profile_stores_dir() / (
            f".{profile_uid}.study-baseline-{uuid.uuid4().hex}"
        )
        published = False
        try:
            inspection = _compose_study_baseline_store(packages, staging)
            initial_digest = baseline_store_digest(staging)
            profile = ProfileEntry(
                uid=profile_uid,
                name=STUDY_BASELINE_PROFILE_NAME,
                kind="MANAGED",
                source=_study_baseline_source_record(
                    packages,
                    imported_at=imported_at,
                    initial_digest=initial_digest,
                ),
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
            except Exception:
                os.replace(destination, staging)
                published = False
                raise
            return StudyImportResult(
                profiles=(profile,),
                inspections=(replace(inspection, root=destination),),
            )
        finally:
            if not published and staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)


def _study_baseline_tasks(
    profile: ProfileEntry,
) -> dict[int, dict[str, object]]:
    source = profile.source
    if not isinstance(source, dict) or set(source) != {
        "kind",
        "schema_version",
        "imported_at",
        "initial_baseline_sha256",
        "tasks",
    }:
        raise ProfileError("Study baseline Profile provenance is invalid.")
    if (
        source.get("kind") != _STUDY_BASELINE_SOURCE_KIND
        or source.get("schema_version") != _STUDY_BASELINE_SCHEMA_VERSION
    ):
        raise ProfileError("Selected Profile is not an editable Study baseline.")
    _timezone_timestamp(source.get("imported_at"))
    _manifest_digest(
        source.get("initial_baseline_sha256"),
        field="initial baseline digest",
    )
    raw_tasks = source.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) != len(_STUDY_TASKS):
        raise ProfileError("Study baseline Task provenance is incomplete.")
    tasks: dict[int, dict[str, object]] = {}
    required = {
        "task",
        "manifest_sha256",
        "canonical_language",
        "task_profile_name",
        "authority_profile_name",
        "task_current_context",
        "authority_current_context",
        "grant_templates",
    }
    for raw in raw_tasks:
        if not isinstance(raw, dict) or set(raw) != required:
            raise ProfileError("Study baseline Task provenance is invalid.")
        task = raw.get("task")
        if type(task) is not int or task not in _STUDY_TASKS or task in tasks:
            raise ProfileError("Study baseline Task number is invalid.")
        _manifest_digest(raw.get("manifest_sha256"), field="manifest digest")
        if raw.get("task_profile_name") != f"task-{task}" or raw.get(
            "authority_profile_name"
        ) != _STUDY_AUTHORITY_PROFILE_NAMES[task]:
            raise ProfileError("Study baseline Profile topology is invalid.")
        for field in ("task_current_context", "authority_current_context"):
            try:
                validate_grant_resource_name(raw.get(field))
            except (ProfileConfigError, ValueError) as error:
                raise ProfileError(
                    "Study baseline current Context provenance is invalid."
                ) from error
        language = raw.get("canonical_language")
        templates = raw.get("grant_templates")
        if (
            not isinstance(language, str)
            or not language
            or not isinstance(templates, list)
            or any(not isinstance(template, dict) for template in templates)
        ):
            raise ProfileError("Study baseline Task provenance is invalid.")
        tasks[task] = raw
    if set(tasks) != set(_STUDY_TASKS):
        raise ProfileError("Study baseline Task provenance is incomplete.")
    return tasks


def _query_view_count_for_baseline(
    contexts: dict[str, Context],
    templates: tuple[dict[str, object], ...],
) -> int:
    memories: set[str] = set()
    for template in templates:
        try:
            permissions = canonical_grant_permissions(template.get("permissions"))
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study baseline grant permissions are invalid.") from error
        if "QUERY" not in permissions:
            continue
        identity = template.get("authority_context")
        exclusions = template.get("excluded_contexts")
        recursive = template.get("recursive")
        if (
            not isinstance(identity, dict)
            or not isinstance(identity.get("name"), str)
            or not isinstance(exclusions, list)
            or not isinstance(recursive, bool)
        ):
            raise ProfileError("Study baseline query grant scope is invalid.")
        root = identity["name"]
        excluded_names = {
            item.get("name") for item in exclusions if isinstance(item, dict)
        }
        if len(excluded_names) != len(exclusions):
            raise ProfileError("Study baseline query exclusions are invalid.")
        selected = [
            context
            for name, context in contexts.items()
            if (name == root or (recursive and name.startswith(root + "/")))
            and not any(
                name == excluded or name.startswith(str(excluded) + "/")
                for excluded in excluded_names
            )
        ]
        if not selected or selected[0].name != root:
            raise ProfileError("Study baseline query grant root is missing.")
        memories.update(
            item.uid
            for context in selected
            for item in context.iter_items()
            if isinstance(item, Memory)
        )
    return len(memories)


def _snapshot_study_baseline(
    baseline: ProfileEntry,
    task_records: dict[int, dict[str, object]],
    destination: Path,
) -> dict[int, _StudyTaskPackage]:
    root = profile_store_dir(baseline)
    contexts, query_refs = _context_records(root)
    if query_refs:
        raise ProfileError(
            "Study baseline granted material must be editable ordinary Contexts."
        )
    structural = {
        *(f"task-{task}" for task in _STUDY_TASKS),
        _STUDY_BASELINE_GRANTED_ROOT,
        *(
            f"{_STUDY_BASELINE_GRANTED_ROOT}/task-{task}"
            for task in _STUDY_TASKS
        ),
    }
    expected = set(structural)
    for task in _STUDY_TASKS:
        for authority in (False, True):
            branch = _study_baseline_branch(task, authority=authority)
            expected.update(
                name for name in contexts if name.startswith(branch + "/")
            )
    if set(contexts) != expected:
        extras = sorted(set(contexts) - expected)
        missing = sorted(expected - set(contexts))
        detail = extras or missing
        raise ProfileError(
            "Study baseline Context topology is invalid: " + ", ".join(detail)
        )
    catalogs = _study_catalogs(root)
    if any(name in structural for name, _language in catalogs):
        raise ProfileError("Study baseline structural Contexts cannot own translations.")

    packages: dict[int, _StudyTaskPackage] = {}
    for task in _STUDY_TASKS:
        raw = task_records[task]
        sources: list[_StudyProfileSource] = []
        role_contexts: dict[str, dict[str, Context]] = {}
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source_name = (
                raw["authority_profile_name"]
                if authority
                else raw["task_profile_name"]
            )
            assert isinstance(source_name, str)
            branch = _study_baseline_branch(task, authority=authority)
            selected = {
                name: context
                for name, context in contexts.items()
                if name.startswith(branch + "/")
            }
            if not selected:
                raise ProfileError(f"Study baseline branch {branch!r} is empty.")
            mapping = {
                name: name[len(branch) + 1 :] for name in selected
            }
            remapped = _remap_context_records(selected, mapping)
            branch_catalogs = tuple(
                replace(catalog, context_name=mapping[name])
                for (name, _language), catalog in sorted(catalogs.items())
                if name in selected
            )
            current_field = (
                "authority_current_context" if authority else "task_current_context"
            )
            current = raw[current_field]
            assert isinstance(current, str)
            store_root = destination / source_name
            inspection = _write_mapped_study_store(
                store_root,
                contexts=remapped,
                catalogs=branch_catalogs,
                current_context=current,
            )
            role_contexts[role] = {context.name: context for context in remapped}
            sources.append(
                _StudyProfileSource(
                    task=task,
                    name=source_name,
                    role=role,
                    store=store_root,
                    entries=(),
                    inspection=inspection,
                )
            )
        templates = tuple(copy.deepcopy(raw["grant_templates"]))
        packages[task] = _StudyTaskPackage(
            task=task,
            schema_version=2,
            manifest={"canonical_language": raw["canonical_language"]},
            manifest_digest=str(raw["manifest_sha256"]),
            profiles=tuple(sources),
            grant_templates=templates,
            query_view_count=_query_view_count_for_baseline(
                role_contexts["AUTHORITY"],
                templates,
            ),
        )
    return packages


def init_study_profile(
    baseline_profile_name: str = STUDY_BASELINE_PROFILE_NAME,
    *,
    name: str | None = None,
) -> StudyInitializationResult:
    """Copy one complete editable baseline into an ordinary Profile.

    The baseline's namespaced task and granted-memory branches are the Study
    topology.  Keeping that topology intact avoids treating a still-changing
    corpus as six independently stable stores.  The clean-import boundary also
    prevents authoring history from becoming participant-run state.
    """

    try:
        baseline_name = validate_profile_name(baseline_profile_name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Study baseline Profile name is invalid.") from error

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is None:
        profile_name = (
            f"study-{created.strftime('%Y%m%dT%H%M%SZ')}-{str(generated_uid)[:8]}"
        )
    else:
        try:
            profile_name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if profile_name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    registry = load_profile_registry()
    baseline = registry.by_name(baseline_name)
    if baseline is None:
        raise ProfileError(
            f"Study baseline Profile {baseline_name!r} does not exist; "
            "bootstrap it with 'mem profile import-study'."
        )
    if any(
        existing.name.casefold() == profile_name.casefold()
        for existing in registry.profiles
    ):
        raise ProfileError(f"Profile {profile_name!r} already exists.")
    if any(
        group.name.casefold() == profile_name.casefold()
        for group in study_profile_groups(registry.profiles)
    ):
        raise ProfileError(
            f"Profile name {profile_name!r} conflicts with an existing legacy "
            "Study group."
        )
    if any(
        baseline.uid
        in {grant.authority_profile_uid, grant.grantee_profile_uid}
        for grant in registry.grants
    ):
        # Grants are registry relationships, not owned baseline content.  Failing
        # closed avoids presenting a single-Profile copy with silently different
        # capabilities from its source.
        raise ProfileError(
            f"Study baseline Profile {baseline.name!r} participates in registry "
            "grants and cannot be copied as one self-contained Profile."
        )

    profile, inspection = import_baseline_profile(
        profile_name,
        profile_store_dir(baseline),
        source_profile=baseline,
    )
    return StudyInitializationResult(
        profile=profile,
        inspection=inspection,
        baseline_profile_name=baseline.name,
        active_profile_name=registry.active.name,
    )
