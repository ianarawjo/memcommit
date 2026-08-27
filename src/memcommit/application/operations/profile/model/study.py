"""Study Profile grouping, import, publication, and lifecycle operations."""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AuthorityGrant,
    GRANT_RESOURCE_CONTEXT_TREE,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_AUTHORITY_SOURCE_KIND,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    StudyRunIdentity,
    load_profile_registry,
    profile_control_dir,
    profile_store_dir,
    profile_stores_dir,
    study_run_identity,
    canonical_grant_permissions,
    validate_grant_resource_name,
    validate_profile_name,
)
from memcommit.application.operations.translate.view import TranslationCatalog

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

_STUDY_PRACTICE_ROOT = "practice"

_STUDY_PRACTICE_DESCRIPTION = "practice/description"

_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT = (
    "memcommit is a research prototype that provides command-line and terminal "
    "user interfaces (CLI/TUI) for managing agent memory and supporting "
    "collaboration among people and agents. Through memcommit's operations and "
    "structural concepts—including Memories, Contexts, Profiles, Grants, and "
    "Sessions—you can manage agent memories as they are collected, organized, "
    "and propagated among people and agents. In this study, you will use "
    "memcommit in three different situations, each involving a different context, "
    "goal, and kind of memory."
)

_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT = (
    "SITUATION · Before beginning the three study tasks, complete a short practice "
    "exercise to become familiar with how memcommit organizes and presents its "
    "commands. Each newline-separated editing note in `practice/source` is "
    "stored as its own Memory, preserving the boundaries between the original "
    "requests. Some notes still combine recurring constraints, rough wording, "
    "and typos."
)

_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT = (
    "TASK · Divide their underlying constraints into appropriate atomic Memories "
    "without performing the requested edits, adding instructions, or changing "
    "the intended meaning, so that each constraint can be reviewed "
    "independently. Open `mem help`, inspect the available operations, find the "
    "operation designed for atomization, and use it to atomize the notes and "
    "save the result as `practice/source-atomized`."
)

_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT = (
    "Before beginning the three study tasks, complete a short practice "
    "exercise to become familiar with how memcommit organizes and presents its "
    "commands. Each newline-separated editing note in `practice/source` is "
    "stored as its own Memory, preserving the boundaries between the original "
    "requests. Some notes still combine recurring constraints, rough wording, "
    "and typos. Divide their underlying constraints into appropriate atomic Memories "
    "without performing the requested edits, adding instructions, or changing "
    "the intended meaning, so that each constraint can be reviewed "
    "independently. Open `mem help`, inspect the available operations, find the "
    "operation designed for atomization, and use it to atomize the notes and "
    "save the result as `practice/source-atomized`."
)

_LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT = (
    _STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT.replace("memcommit", "MemLab")
)

_LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT = (
    _STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT.replace("memcommit", "MemLab")
)

_LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT = (
    _PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT.replace("memcommit", "MemLab")
)

_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_UID = str(
    uuid.uuid5(uuid.NAMESPACE_URL, "memcommit:study:practice/description:memory")
)

_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID = str(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        "memcommit:study:practice/description:situation-memory",
    )
)

_STUDY_PRACTICE_DESCRIPTION_TASK_UID = str(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        "memcommit:study:practice/description:task-memory",
    )
)

_LEGACY_STUDY_PRACTICE_PROVENANCE_UID = str(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        "memcommit:study:practice/description:reference-memory",
    )
)

_STUDY_PRACTICE_SOURCE = "practice/source"

_STUDY_PRACTICE_SOURCE_CONTENTS = (
    "When I ask “How does this read?”, I really want an opinion, so don't edit "
    "the draft immediately; first check the sentence order and paragraph "
    "division.",
    "If I later ask for polishing, preserve the overall strucutre and "
    "citation-needed markers, and change only wording that causes a problem.",
    "When I ask to change one expression, leave almost everything else as it "
    "is, including technical or project-specific terms that I selected. Um... "
    "for example, use distribute, not divide, when material is absorbed into "
    "two parts.",
    "If a passage is supposed to make four points, keep all four while removing "
    "parts that are too redundent and stating repeated content only once.",
    "When the draft has to fit a shorter fixed limit, aim to cut around 20–30% "
    "from redundant or unnecessary material.",
    "But don't shorten sentences so aggressively that a claim sounds more "
    "categorical; keep enough wording to preserve its original strength and "
    "conditions.",
    "If the next idea is merely related and does not broaden the scope, don't "
    "use More "
    "broadly; use In relation to this or another accurate connector without "
    "adding a new claim merely to make two paragraphs connect.",
    "For any titlle about interaction with AI agent memory, keep the exact "
    "terminology and intended words: use interaction and management and AI "
    "agent memory rather than agent memory.",
    "By default, format a document title in sentence case rather than title "
    "case. An explicitly named style guide may override only that capitalization "
    "default; always keep for whenever it is part of the intended wording.",
    "If titles of works use quotation marks in some places and italics in "
    "others, make them consistently italic throughout the document by default; "
    "an explicitly named style guide may override only this work-title format.",
    "When I say that content looks wrong, find accurate information before "
    "proposing a correction by reading the original paper, book, or guide, not "
    "only an abstract or a short snippet.",
    "Before adding or reusing citations and refferences, verify that each source "
    "exists and supports the exact claim after reviewing the complete source. "
    "Don't invent quotations or evidence or overstate an author's contribution "
    "or a paper's status. If I asked only for review, report a verification "
    "problem first instead of silently rewriting the draft.",
)

_LEGACY_SCENARIO_GRANTED_ROOT = "granted-memory"

_STUDY_PROFILE_SOURCE_KIND = "STUDY_RUN_TASK"

_STUDY_AUTHORITY_SOURCE_KIND = "STUDY_RUN_AUTHORITY"

_STUDY_RUN_SOURCE_KIND = STUDY_RUN_PARTICIPANT_SOURCE_KIND

_STUDY_RUN_GRANTED_SOURCE_KIND = STUDY_RUN_AUTHORITY_SOURCE_KIND

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

_BASELINE_TOP_LEVEL_DIRECTORIES = (
    "query-sources",
    # Unlike ordinary runtime caches, this directory is an explicitly
    # declared Study fixture whose exact artifacts are rebound to each new
    # run's authority before participant interaction.
    "study-semantic-prewarm",
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


def _study_run_authority_profile_name(study_name: str) -> str:
    """Return the visible run-private authority Profile name."""

    try:
        return validate_profile_name(f"{study_name}-granted-memory")
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError(
            "Study name is too long to create its granted-memory Profile."
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
        # Record the registry identity rather than an internal store path;
        # paths are implementation details and can disclose host layout.
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
                # os.replace() may have committed the registry before its
                # directory fsync reported failure. Removing the store then
                # would leave a durable registry pointing at missing data.
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
                if local_name == grant.public_name or local_name.startswith(
                    grant.public_name + "/"
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
            removed_profile_uids=registry.removed_profile_uids,
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
    except BaseException:
        # First-generation cache work can run for minutes. Cancellation must
        # roll the already-moved private stores back just like provider failure
        # instead of leaving unregistered run directories behind.
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


def _legacy_scenario_branch(task: int, *, authority: bool) -> str:
    task_name = f"task-{task}"
    return f"{_LEGACY_SCENARIO_GRANTED_ROOT}/{task_name}" if authority else task_name


def _study_practice_contexts() -> tuple[Context, ...]:
    """Return the stable participant-only Atomize rehearsal fixture."""

    root = Context(
        uid=str(uuid.uuid5(uuid.NAMESPACE_URL, "memcommit:study:practice")),
        name=_STUDY_PRACTICE_ROOT,
    )
    description = Context(
        uid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "memcommit:study:practice/description",
            )
        ),
        name=_STUDY_PRACTICE_DESCRIPTION,
    )
    description.add(
        Memory(
            uid=_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_UID,
            content=_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
        )
    )
    description.add(
        Memory(
            uid=_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID,
            content=_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
        )
    )
    description.add(
        Memory(
            uid=_STUDY_PRACTICE_DESCRIPTION_TASK_UID,
            content=_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT,
        )
    )
    source = Context(
        uid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "memcommit:study:practice/source",
            )
        ),
        name=_STUDY_PRACTICE_SOURCE,
    )
    for index, content in enumerate(_STUDY_PRACTICE_SOURCE_CONTENTS, start=1):
        source.add(
            Memory(
                uid=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"memcommit:study:practice/source:memory:{index:02d}",
                    )
                ),
                content=content,
            )
        )
    return root, description, source


def _is_study_practice_name(name: str) -> bool:
    return name == _STUDY_PRACTICE_ROOT or name.startswith(_STUDY_PRACTICE_ROOT + "/")


def _canonicalize_study_practice_description(
    contexts: dict[str, Context],
) -> dict[str, Context]:
    """Apply exact Practice compatibility edits without changing the baseline."""

    description = contexts.get(_STUDY_PRACTICE_DESCRIPTION)
    if description is None:
        return contexts
    replacements = {
        _LEGACY_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT: (
            _STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT
        ),
        _LEGACY_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT: (
            _STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT
        ),
    }
    pre_split_contents = {
        _PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT,
        _LEGACY_PRE_SPLIT_STUDY_PRACTICE_DESCRIPTION_CONTENT,
    }
    needs_copy = _LEGACY_STUDY_PRACTICE_PROVENANCE_UID in description.memories or any(
        isinstance(item, Memory)
        and (item.content in replacements or item.content in pre_split_contents)
        for item in description.iter_items()
    )
    if not needs_copy:
        return contexts
    # Exact known legacy values are safe to migrate in the run snapshot. Any
    # independently edited description remains untouched and recoverable.
    sanitized = dict(contexts)
    sanitized_description = copy.deepcopy(description)
    sanitized_description.clear()
    for source_item in description.iter_items():
        if source_item.uid == _LEGACY_STUDY_PRACTICE_PROVENANCE_UID:
            continue
        item = copy.deepcopy(source_item)
        if isinstance(item, Memory) and item.content in pre_split_contents:
            # The old combined row owned the task identity. Keep that UID for
            # the executable instruction while inserting a new stable
            # Situation immediately before it, so existing history continues
            # to name the instruction rather than its surrounding narrative.
            sanitized_description.add(
                Memory(
                    uid=_STUDY_PRACTICE_DESCRIPTION_SITUATION_UID,
                    content=_STUDY_PRACTICE_DESCRIPTION_SITUATION_CONTENT,
                )
            )
            item.content = _STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT
        elif isinstance(item, Memory) and item.content in replacements:
            item.content = replacements[item.content]
        sanitized_description.add(item)
    sanitized[_STUDY_PRACTICE_DESCRIPTION] = sanitized_description
    return sanitized


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
    # Their name-derived identities keep a packaged scenario reproducible
    # across runs while leaving imported Context and Memory identities intact.
    for name in sorted(missing, key=lambda value: (value.count("/"), value)):
        by_name[name] = Context(
            uid=str(
                uuid.uuid5(
                    _STUDY_BUNDLE_NAMESPACE,
                    f"structural-context\0{name}",
                )
            ),
            name=name,
        )
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

    from memcommit.persistence.store import _write_json_atomic

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


def _compose_legacy_scenario_store(
    packages: dict[int, _StudyTaskPackage],
    destination: Path,
) -> StoreInspection:
    """Compose all editable Task inputs into one namespaced source Profile."""

    structural_names = [
        *(f"task-{task}" for task in _STUDY_TASKS),
        _LEGACY_SCENARIO_GRANTED_ROOT,
        *(f"{_LEGACY_SCENARIO_GRANTED_ROOT}/task-{task}" for task in _STUDY_TASKS),
    ]
    contexts = [
        Context(
            uid=str(
                uuid.uuid5(
                    _STUDY_BUNDLE_NAMESPACE,
                    f"legacy-scenario-context\0{name}",
                )
            ),
            name=name,
        )
        for name in structural_names
    ]
    contexts.extend(_study_practice_contexts())
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
            branch = _legacy_scenario_branch(task, authority=authority)
            mapping = {name: f"{branch}/{name}" for name in source_contexts}
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
