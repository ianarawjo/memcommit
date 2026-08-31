"""Study Profile grouping and lifecycle operations."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from memcommit.application.operations.profiles.profile.config import (
    AuthorityGrant,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    StudyRunIdentity,
    load_profile_registry,
    profile_control_dir,
    profile_store_dir,
    study_run_identity,
    validate_profile_name,
)

from ._storage import (
    ProfileError as ProfileError,
    StoreInspection as StoreInspection,
    _assert_plain_tree as _assert_plain_tree,
    _context_records as _context_records,
    _fsync_directory as _fsync_directory,
    _inspection_with_grants as _inspection_with_grants,
    _prepare_profile_deletion_batch as _prepare_profile_deletion_batch,
    _publish_permanent_removal as _publish_permanent_removal,
    _read_granted_public_names as _read_granted_public_names,
    _read_json as _read_json,
    _registry_lock as _registry_lock,
    _source_digest as _source_digest,
    _source_store as _source_store,
    _write_registry as _write_registry,
    inspect_store as inspect_store,
)

from .grants import (
    _grant_scope as _grant_scope,
)


@dataclass(frozen=True)
class StudyProfileGroup:
    """One timestamped Study whose three tasks remain isolated Profiles."""

    uid: str
    name: str
    created_at: str
    profiles: tuple[ProfileEntry, ...]
    support_profiles: tuple[ProfileEntry, ...] = ()


@dataclass(frozen=True)
class StudyRunProfilePair:
    """One current ``init-study`` participant/authority Profile pair."""

    uid: str
    name: str
    created_at: str
    participant: ProfileEntry
    authority: ProfileEntry


@dataclass(frozen=True)
class StudyProviderPolicyMigrationResult:
    """One atomic pilot migration of visible current Study pairs."""

    generation: int
    migrated_study_count: int
    migrated_profile_count: int


@dataclass(frozen=True)
class LegacyStudyArchiveResult:
    """One split legacy Study detached from the live Profile selector."""

    uid: str
    name: str
    created_at: str
    profiles: tuple[ProfileEntry, ...]
    grants: tuple[AuthorityGrant, ...]
    manifest_path: Path
    active_profile_name: str


@dataclass(frozen=True)
class StudyRenameResult:
    """One stable Study identity published under a new display name."""

    uid: str
    previous_name: str
    name: str
    profiles: tuple[ProfileEntry, ...]
    active_profile_name: str
    changed: bool
    renamed_profile_count: int


@dataclass(frozen=True)
class StudyRemovalResult:
    """One complete Study whose Profile stores were permanently deleted."""

    uid: str
    name: str
    profiles: tuple[ProfileEntry, ...]
    newly_removed_count: int
    removed_grant_count: int
    deleted_stores: tuple[Path, ...]
    active_profile_name: str


_STUDY_TASKS = (1, 2, 3)

_STUDY_AUTHORITY_PROFILE_NAMES = {
    1: "task-1-campus-authority",
    2: "task-2-proposal-authority",
    3: "task-3-healthcare-authority",
}


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

_LEGACY_STUDY_ARCHIVE_SCHEMA_VERSION = 1


def _study_uuid(value: object, *, label: str) -> str:
    try:
        canonical = str(uuid.UUID(value))
    except (AttributeError, TypeError, ValueError) as error:
        raise ProfileError(f"Study manifest {label} is invalid.") from error
    if value != canonical:
        raise ProfileError(f"Study manifest {label} is invalid.")
    return canonical


def _manifest_digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProfileError(f"Study manifest {field} is invalid.")
    return value


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
    """Validate and group legacy split Study Profiles.

    Older ``mem init-study`` versions persisted immutable grouping provenance
    rather than a Context hierarchy.  The reader remains so those Profiles and
    grants stay selectable, while current initialization creates an ordinary
    single Profile that never enters this grouping path.
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


def study_run_profile_pairs(
    profiles: tuple[ProfileEntry, ...],
) -> tuple[StudyRunProfilePair, ...]:
    """Validate and group current two-Profile Study runs by provenance."""

    grouped: dict[str, list[tuple[ProfileEntry, StudyRunIdentity]]] = {}
    order: list[str] = []
    for profile in profiles:
        identity = study_run_identity(profile)
        if identity is None:
            continue
        if identity.uid not in grouped:
            grouped[identity.uid] = []
            order.append(identity.uid)
        grouped[identity.uid].append((profile, identity))

    result: list[StudyRunProfilePair] = []
    seen_names: set[str] = set()
    for study_uid in order:
        members = grouped[study_uid]
        roles = {identity.role for _profile, identity in members}
        if len(members) != 2 or roles != {"PARTICIPANT", "GRANTED_MEMORY"}:
            raise ProfileError("Study run Profile pair is incomplete.")
        identities = [identity for _profile, identity in members]
        shared = {
            (
                identity.name,
                identity.created_at,
                identity.baseline_profile_uid,
                identity.baseline_profile_name,
                identity.baseline_sha256,
                identity.provider_policy_version,
                identity.provider_policy_digest,
            )
            for identity in identities
        }
        if len(shared) != 1:
            raise ProfileError("Study run Profile provenance is inconsistent.")
        (
            name,
            created_at,
            _baseline_uid,
            _baseline_name,
            _digest,
            _provider_policy_version,
            _provider_policy_digest,
        ) = next(iter(shared))
        if name.casefold() in seen_names:
            raise ProfileError("Study run names must be unique.")
        seen_names.add(name.casefold())
        participant = next(
            profile for profile, identity in members if identity.role == "PARTICIPANT"
        )
        authority = next(
            profile
            for profile, identity in members
            if identity.role == "GRANTED_MEMORY"
        )
        result.append(
            StudyRunProfilePair(
                uid=study_uid,
                name=name,
                created_at=created_at,
                participant=participant,
                authority=authority,
            )
        )
    return tuple(result)


def _legacy_study_archives_dir() -> Path:
    return profile_control_dir() / "archives" / "studies"


def _ensure_legacy_study_archives_dir() -> Path:
    control = profile_control_dir()
    archives = control / "archives"
    studies = archives / "studies"
    for path, label in (
        (archives, "Profile archive"),
        (studies, "Legacy Study archive"),
    ):
        if path.is_symlink():
            raise ProfileError(f"{label} directory cannot be a symbolic link.")
        if path.exists() and not path.is_dir():
            raise ProfileError(f"{label} storage is invalid.")
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ProfileError(f"{label} directory is unsafe.")
        # Repeat the parent fsync even when the directory is already visible.
        # A previous process may have died after mkdir made the entry visible
        # but before that namespace change became durable.
        _fsync_directory(path.parent)
    return studies


def _legacy_study_archive_record(
    registry: ProfileRegistry,
    group: StudyProfileGroup,
    profiles: tuple[ProfileEntry, ...],
    grants: tuple[AuthorityGrant, ...],
) -> dict[str, object]:
    return {
        "schema_version": _LEGACY_STUDY_ARCHIVE_SCHEMA_VERSION,
        "kind": "LEGACY_STUDY_ARCHIVE",
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source_registry_generation": registry.generation,
        "study": {
            "uid": group.uid,
            "name": group.name,
            "created_at": group.created_at,
        },
        "profiles": [profile.to_dict() for profile in profiles],
        "grants": [grant.to_dict() for grant in grants],
        # Keep host paths out of portable archive metadata. Managed Profile
        # UIDs already resolve below the fixed control-plane stores directory.
        "stores": [
            {
                "profile_uid": profile.uid,
                "control_relative_path": f"stores/{profile.uid}",
            }
            for profile in profiles
        ],
    }


def _publish_legacy_study_archive(
    destination: Path,
    record: dict[str, object],
) -> Path:
    parent = _ensure_legacy_study_archives_dir()
    if destination.parent != parent:
        raise ProfileError("Legacy Study archive destination is invalid.")
    staging = parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    published = False
    try:
        staging.mkdir(mode=0o700)
        manifest = staging / "manifest.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(manifest, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(record, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        _fsync_directory(staging)
        os.replace(staging, destination)
        published = True
        _fsync_directory(parent)
        return destination / "manifest.json"
    except Exception:
        # Once the canonical manifest is visible, retain it as a prepared
        # transaction. Deleting it in place could itself fail halfway and
        # leave a non-resumable destination while the registry remains live.
        candidate = None if published else staging
        try:
            if (
                candidate is not None
                and candidate.exists()
                and not candidate.is_symlink()
            ):
                shutil.rmtree(candidate)
                _fsync_directory(parent)
        except Exception as rollback_error:
            raise ProfileError(
                "Legacy Study archive publication rollback failed."
            ) from rollback_error
        raise


def _reuse_legacy_study_archive(
    destination: Path,
    expected: dict[str, object],
) -> Path:
    """Resume a manifest-first archive interrupted before registry detach."""

    parent = _ensure_legacy_study_archives_dir()
    if destination.parent != parent:
        raise ProfileError("Legacy Study archive destination is invalid.")
    if destination.is_symlink() or not destination.is_dir():
        raise ProfileError(
            f"Legacy Study archive destination is occupied: {destination}"
        )
    children = tuple(destination.iterdir())
    if len(children) != 1 or children[0].name != "manifest.json":
        raise ProfileError(
            f"Legacy Study archive destination is occupied: {destination}"
        )
    manifest_path = destination / "manifest.json"
    actual = _read_json(manifest_path, label="Legacy Study archive manifest")
    if set(actual) != {
        "schema_version",
        "kind",
        "archived_at",
        "source_registry_generation",
        "study",
        "profiles",
        "grants",
        "stores",
    }:
        raise ProfileError("Existing legacy Study archive manifest is invalid.")
    _timezone_timestamp(actual["archived_at"])
    source_generation = actual["source_registry_generation"]
    current_generation = expected["source_registry_generation"]
    if (
        not isinstance(source_generation, int)
        or isinstance(source_generation, bool)
        or not isinstance(current_generation, int)
        or source_generation < 1
        or source_generation > current_generation
    ):
        raise ProfileError("Existing legacy Study archive manifest is invalid.")
    for field in (
        "schema_version",
        "kind",
        "study",
        "profiles",
        "grants",
        "stores",
    ):
        if actual[field] != expected[field]:
            raise ProfileError(
                "Legacy Study archive destination contains different records."
            )

    # The prior process may have died after publishing the directory entry but
    # before fsyncing its parent. Re-establish the whole manifest-first boundary
    # before registry detach, even though the JSON file was already durable.
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(manifest_path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(destination)
    _fsync_directory(parent)
    return manifest_path


def _prepare_legacy_study_archive(
    destination: Path,
    record: dict[str, object],
) -> Path:
    if destination.exists() or destination.is_symlink():
        return _reuse_legacy_study_archive(destination, record)
    return _publish_legacy_study_archive(destination, record)


def migrate_visible_study_provider_policy(
    *,
    target_version: str,
    target_digest: str,
    accepted_sources: frozenset[tuple[str | None, str | None]],
) -> StudyProviderPolicyMigrationResult:
    """Atomically repin every visible current Study pair during the pilot.

    Removed Profile tombstones retain their historical provenance. Every
    visible participant/authority pair must be complete and must share one
    explicitly accepted source condition before any registry replacement.
    """

    if not target_version or len(target_version) > 128:
        raise ProfileError("Study provider policy version is invalid.")
    if (
        not isinstance(target_digest, str)
        or len(target_digest) != 64
        or any(character not in "0123456789abcdef" for character in target_digest)
    ):
        raise ProfileError("Study provider policy digest is invalid.")
    if not accepted_sources:
        raise ProfileError("Study provider migration has no accepted source.")

    target = (target_version, target_digest)
    with _registry_lock():
        registry = load_profile_registry()
        removed = frozenset(registry.removed_profile_uids)
        groups: dict[str, list[tuple[ProfileEntry, StudyRunIdentity]]] = {}
        for profile in registry.profiles:
            if profile.uid in removed:
                continue
            identity = study_run_identity(profile)
            if identity is None:
                continue
            groups.setdefault(identity.uid, []).append((profile, identity))

        migrated_uids: set[str] = set()
        migrated_studies = 0
        for study_uid, members in groups.items():
            roles = {identity.role for _profile, identity in members}
            conditions = {
                (
                    identity.provider_policy_version,
                    identity.provider_policy_digest,
                )
                for _profile, identity in members
            }
            if len(members) != 2 or roles != {"PARTICIPANT", "GRANTED_MEMORY"}:
                raise ProfileError(
                    f"Visible Study {study_uid!r} does not contain one complete pair."
                )
            if len(conditions) != 1:
                raise ProfileError(
                    f"Visible Study {study_uid!r} has inconsistent provider policy."
                )
            current = next(iter(conditions))
            if current == target:
                continue
            if current not in accepted_sources:
                raise ProfileError(
                    f"Visible Study {study_uid!r} has an unaccepted provider policy."
                )
            migrated_studies += 1
            migrated_uids.update(profile.uid for profile, _identity in members)

        if not migrated_uids:
            return StudyProviderPolicyMigrationResult(
                generation=registry.generation,
                migrated_study_count=0,
                migrated_profile_count=0,
            )

        profiles: list[ProfileEntry] = []
        for profile in registry.profiles:
            if profile.uid not in migrated_uids:
                profiles.append(profile)
                continue
            assert profile.source is not None
            source = dict(profile.source)
            source["provider_policy_version"] = target_version
            source["provider_policy_digest"] = target_digest
            profiles.append(replace(profile, source=source))

        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=tuple(profiles),
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
        )
        _write_registry(updated)
        return StudyProviderPolicyMigrationResult(
            generation=updated.generation,
            migrated_study_count=migrated_studies,
            migrated_profile_count=len(migrated_uids),
        )


def _study_target(
    registry: ProfileRegistry,
    name: str,
) -> tuple[str, str, tuple[ProfileEntry, ...]]:
    """Resolve one legacy or current Study to its stable member identities."""

    canonical = validate_profile_name(name)
    matches: list[tuple[str, str, tuple[ProfileEntry, ...]]] = []
    matches.extend(
        (
            group.uid,
            group.name,
            (*group.profiles, *group.support_profiles),
        )
        for group in study_profile_groups(registry.profiles)
        if group.name.casefold() == canonical.casefold()
    )
    matches.extend(
        (
            pair.uid,
            pair.name,
            (pair.participant, pair.authority),
        )
        for pair in study_run_profile_pairs(registry.profiles)
        if pair.name.casefold() == canonical.casefold()
    )
    if not matches:
        raise ProfileError(f"Study {canonical!r} does not exist.")
    if len(matches) != 1:
        raise ProfileError(f"Study selector {canonical!r} is ambiguous.")
    return matches[0]


def rename_study(
    old_name: str,
    new_name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> StudyRenameResult:
    """Rename one complete Study without changing its stable identity.

    Current two-Profile runs keep their independently editable Profile display
    names. Legacy split Studies encoded the Study name into every member name,
    so that compatibility topology is renamed as one atomic registry change.
    """

    try:
        canonical_old = validate_profile_name(old_name)
        canonical_new = validate_profile_name(new_name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Study rename name is invalid.") from error

    with _registry_lock():
        registry = load_profile_registry()
        if (
            expected_generation is not None
            and registry.generation != expected_generation
        ):
            raise ProfileError(
                "Profile registry changed after Study rename selection; review "
                "the current Profile list and try again."
            )
        study_uid, study_name, members = _study_target(registry, canonical_old)
        if expected_uid is not None and study_uid != expected_uid:
            raise ProfileError(
                f"Study {study_name!r} identity changed after rename selection; "
                "nothing was renamed."
            )
        if all(registry.is_removed(profile) for profile in members):
            raise ProfileError(f"Study {study_name!r} is already removed.")
        if study_name == canonical_new:
            return StudyRenameResult(
                uid=study_uid,
                previous_name=study_name,
                name=study_name,
                profiles=members,
                active_profile_name=registry.active.name,
                changed=False,
                renamed_profile_count=0,
            )

        studies = (
            *study_profile_groups(registry.profiles),
            *study_run_profile_pairs(registry.profiles),
        )
        collision = next(
            (
                study
                for study in studies
                if study.uid != study_uid
                and study.name.casefold() == canonical_new.casefold()
            ),
            None,
        )
        if collision is not None:
            raise ProfileError(f"Study {collision.name!r} already exists.")

        legacy_group = next(
            (
                group
                for group in study_profile_groups(registry.profiles)
                if group.uid == study_uid
            ),
            None,
        )
        renamed_by_uid: dict[str, ProfileEntry] = {}
        for profile in members:
            source = profile.source
            if not isinstance(source, dict):
                raise ProfileError("Study Profile provenance is invalid.")
            renamed_source = dict(source)
            renamed_source["study_name"] = canonical_new
            renamed_name = profile.name
            if legacy_group is not None:
                task = source.get("task")
                if type(task) is not int or task not in _STUDY_TASKS:
                    raise ProfileError("Study Task number is invalid.")
                if source.get("kind") == _STUDY_PROFILE_SOURCE_KIND:
                    renamed_name = _study_task_profile_name(canonical_new, task)
                elif source.get("kind") == _STUDY_AUTHORITY_SOURCE_KIND:
                    renamed_name = _study_authority_profile_name(
                        canonical_new,
                        _STUDY_AUTHORITY_PROFILE_NAMES[task],
                    )
                else:
                    raise ProfileError("Study Profile provenance is invalid.")
            renamed_by_uid[profile.uid] = replace(
                profile,
                name=renamed_name,
                source=renamed_source,
            )

        if legacy_group is not None:
            member_uids = set(renamed_by_uid)
            existing_names = {
                profile.name.casefold()
                for profile in registry.profiles
                if profile.uid not in member_uids
            }
            generated_names = [
                profile.name.casefold() for profile in renamed_by_uid.values()
            ]
            if len(generated_names) != len(set(generated_names)):
                raise ProfileError("Renamed legacy Study Profile names collide.")
            generated_collision = next(
                (
                    profile.name
                    for profile in renamed_by_uid.values()
                    if profile.name.casefold() in existing_names
                ),
                None,
            )
            if generated_collision is not None:
                raise ProfileError(f"Profile {generated_collision!r} already exists.")

        updated_profiles = tuple(
            renamed_by_uid.get(profile.uid, profile) for profile in registry.profiles
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=updated_profiles,
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                visible = load_profile_registry()
            except (OSError, ProfileConfigError, ValueError) as read_error:
                raise ProfileError(
                    "Study rename registry state could not be confirmed; inspect "
                    "it with 'mem profile list'."
                ) from read_error
            if visible == updated:
                raise ProfileError(
                    f"Study {study_name!r} was renamed to {canonical_new!r}, but "
                    "registry durability could not be confirmed; it remains "
                    "renamed."
                ) from error
            if visible != registry:
                raise ProfileError(
                    "Study rename registry changed unexpectedly; inspect it "
                    "with 'mem profile list'."
                ) from error
            raise

        renamed_members = tuple(renamed_by_uid[profile.uid] for profile in members)
        return StudyRenameResult(
            uid=study_uid,
            previous_name=study_name,
            name=canonical_new,
            profiles=renamed_members,
            active_profile_name=updated.active.name,
            changed=True,
            renamed_profile_count=(len(members) if legacy_group is not None else 0),
        )


def remove_study(
    name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> StudyRemovalResult:
    """Permanently delete every Profile store in one Study."""

    with _registry_lock():
        registry = load_profile_registry()
        if (
            expected_generation is not None
            and registry.generation != expected_generation
        ):
            raise ProfileError("Profile registry changed after removal review.")
        study_uid, study_name, profiles = _study_target(registry, name)
        if expected_uid is not None and study_uid != expected_uid:
            raise ProfileError("Study identity changed after removal review.")
        member_uids = {profile.uid for profile in profiles}
        if registry.active_uid in member_uids:
            raise ProfileError(
                f"Study {study_name!r} contains the active Profile; select "
                "another Profile before removing it."
            )
        existing_removed = frozenset(registry.removed_profile_uids)
        stores_to_delete = tuple(
            profile
            for profile in profiles
            if profile_store_dir(profile).exists()
            or profile_store_dir(profile).is_symlink()
        )
        if not stores_to_delete:
            raise ProfileError(f"Study {study_name!r} is already removed.")
        for profile in stores_to_delete:
            inspect_store(
                profile_store_dir(profile),
                allowed_virtual_currents=_read_granted_public_names(
                    registry,
                    profile.uid,
                ),
            )
        removed = existing_removed | member_uids
        ordered_removed = tuple(
            profile.uid for profile in registry.profiles if profile.uid in removed
        )
        retained_grants = tuple(
            grant
            for grant in registry.grants
            if not member_uids.intersection(
                {grant.authority_profile_uid, grant.grantee_profile_uid}
            )
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=retained_grants,
            removed_profile_uids=ordered_removed,
        )
        batch = _prepare_profile_deletion_batch(stores_to_delete)
        _publish_permanent_removal(
            registry,
            updated,
            batch=batch,
            profiles=stores_to_delete,
            label=f"Study {study_name!r}",
        )
        return StudyRemovalResult(
            uid=study_uid,
            name=study_name,
            profiles=profiles,
            newly_removed_count=len(stores_to_delete),
            removed_grant_count=len(registry.grants) - len(retained_grants),
            deleted_stores=tuple(
                profile_store_dir(profile) for profile in stores_to_delete
            ),
            active_profile_name=registry.active.name,
        )


def archive_legacy_study(name: str) -> LegacyStudyArchiveResult:
    """Detach one complete split Study while preserving every store in place."""

    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        matches = [
            group
            for group in study_profile_groups(registry.profiles)
            if group.name.casefold() == canonical.casefold()
        ]
        if not matches:
            raise ProfileError(f"Legacy Study {canonical!r} does not exist.")
        if len(matches) != 1:
            raise ProfileError(f"Legacy Study selector {canonical!r} is ambiguous.")
        group = matches[0]
        grouped_uids = {
            profile.uid for profile in (*group.profiles, *group.support_profiles)
        }
        profiles = tuple(
            profile for profile in registry.profiles if profile.uid in grouped_uids
        )
        if registry.active_uid in grouped_uids:
            raise ProfileError(
                f"Legacy Study {group.name!r} contains the active Profile; "
                "select another Profile before archiving it."
            )

        incident = tuple(
            grant
            for grant in registry.grants
            if grant.authority_profile_uid in grouped_uids
            or grant.grantee_profile_uid in grouped_uids
        )
        crossing = tuple(
            grant
            for grant in incident
            if (grant.authority_profile_uid in grouped_uids)
            != (grant.grantee_profile_uid in grouped_uids)
        )
        if crossing:
            raise ProfileError(
                f"Legacy Study {group.name!r} has a grant crossing its Profile "
                f"boundary: {crossing[0].uid[:8]}."
            )
        internal_grants = tuple(
            grant
            for grant in incident
            if grant.authority_profile_uid in grouped_uids
            and grant.grantee_profile_uid in grouped_uids
        )

        # Archiving is a control-plane detach, not a data move. Validate each
        # root first, then leave its stable UID path untouched so a process
        # that already resolved that root can finish safely.
        for profile in profiles:
            inspect_store(profile_store_dir(profile))

        archive_root = _legacy_study_archives_dir() / group.uid
        record = _legacy_study_archive_record(
            registry,
            group,
            profiles,
            internal_grants,
        )
        manifest_path = _prepare_legacy_study_archive(
            archive_root,
            record,
        )
        internal_grant_uids = {grant.uid for grant in internal_grants}
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=tuple(
                profile
                for profile in registry.profiles
                if profile.uid not in grouped_uids
            ),
            grants=tuple(
                grant
                for grant in registry.grants
                if grant.uid not in internal_grant_uids
            ),
            removed_profile_uids=tuple(
                uid for uid in registry.removed_profile_uids if uid not in grouped_uids
            ),
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                visible = load_profile_registry()
            except (OSError, ProfileConfigError, ValueError) as read_error:
                raise ProfileError(
                    f"Legacy Study {group.name!r} archive registry state could "
                    f"not be confirmed; its manifest remains at {manifest_path}."
                ) from read_error
            if visible == updated:
                raise ProfileError(
                    f"Legacy Study {group.name!r} was archived, but registry "
                    "durability could not be confirmed; it remains archived."
                ) from error
            if visible != registry:
                raise ProfileError(
                    f"Legacy Study {group.name!r} archive registry changed "
                    f"unexpectedly; its manifest remains at {manifest_path}."
                ) from error
            raise ProfileError(
                f"Legacy Study {group.name!r} was not detached; its prepared "
                f"manifest remains for retry at {manifest_path}."
            ) from error

        return LegacyStudyArchiveResult(
            uid=group.uid,
            name=group.name,
            created_at=group.created_at,
            profiles=profiles,
            grants=internal_grants,
            manifest_path=manifest_path,
            active_profile_name=registry.active.name,
        )


_INIT_STUDY_PROFILE_COMPAT_EXPORTS = {
    "StudyImportResult": "model",
    "_StudyProfileSource": "model",
    "_StudyTaskPackage": "model",
    "_STUDY_BUNDLE_NAMESPACE": "model",
    "_study_run_authority_profile_name": "model",
    "_study_integer": "package",
    "_expected_study_grant_uid": "package",
    "_legacy_study_package": "package",
    "_study_package": "package",
    "_content_digest": "package",
    "_study_catalogs": "package",
    "_study_query_entries": "package",
    "_validate_study_manifest_content": "package",
    "_study_manifest_context": "package",
    "_study_packages": "package",
    "_validate_study_package_grants": "package",
    "_STUDY_PRACTICE_ROOT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT": "composition",
    "_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT": "composition",
    "_LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT": "composition",
    "_LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT": "composition",
    "_LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_UID": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID": "composition",
    "_STUDY_PRACTICE_DESCRIPTION_TASK_UID": "composition",
    "_LEGACY_STUDY_PRACTICE_PROVENANCE_UID": "composition",
    "_STUDY_PRACTICE_SOURCE": "composition",
    "_STUDY_PRACTICE_SOURCE_CONTENTS": "composition",
    "_LEGACY_SCENARIO_GRANTED_ROOT": "composition",
    "_legacy_scenario_branch": "composition",
    "_study_practice_contexts": "composition",
    "_is_study_practice_name": "composition",
    "_canonicalize_study_practice_description": "composition",
    "_remap_context_records": "composition",
    "_remap_translation_catalogs": "composition",
    "_materialize_study_context_parents": "composition",
    "_write_mapped_study_store": "composition",
    "_compose_legacy_scenario_store": "composition",
    "_STUDY_RUN_SOURCE_KIND": "publication",
    "_STUDY_RUN_GRANTED_SOURCE_KIND": "publication",
    "_materialize_study_grants": "publication",
    "_publish_study_profile_batch": "publication",
}


def __getattr__(name: str):
    """Lazily preserve init-study construction names at their former path."""

    module_name = _INIT_STUDY_PROFILE_COMPAT_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(
        f"memcommit.application.operations.system_study_tools.init_study.profile.{module_name}"
    )
    value = getattr(module, name)
    globals()[name] = value
    return value
