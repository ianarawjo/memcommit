"""Whole-store profile registration and selection.

Profiles are a control-plane selector around complete MemoryStore roots.  A
single editable Study baseline deliberately namespaces all three task inputs
inside one root. ``mem init-study`` snapshots that source into one participant
Profile and one run-private authority Profile, then restores the fixture's
real grants between them. Older six-Profile Study groups remain readable.
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
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AuthorityGrant,
    GRANT_RESOURCE_CONTEXT_TREE,
    GrantContextBinding,
    ProfileConfigError,
    ProfileEntry,
    ProfileRegistry,
    STUDY_RUN_AUTHORITY_SOURCE_KIND,
    STUDY_RUN_PARTICIPANT_SOURCE_KIND,
    StudyRunIdentity,
    load_profile_registry,
    profile_control_dir,
    profile_registry_file,
    profile_registry_lock_file,
    profile_store_dir,
    profile_stores_dir,
    study_run_identity,
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
class StudyRunProfilePair:
    """One current ``init-study`` participant/authority Profile pair."""

    uid: str
    name: str
    created_at: str
    participant: ProfileEntry
    authority: ProfileEntry


@dataclass(frozen=True)
class StudyInitializationResult:
    """One isolated participant/authority pair copied from a Study baseline."""

    profile: ProfileEntry
    inspection: StoreInspection
    authority_profile: ProfileEntry
    authority_inspection: StoreInspection
    baseline_profile_name: str
    active_profile_name: str
    declared_compare_prewarms: int = 0
    installed_compare_prewarms: int = 0
    skipped_compare_prewarms: int = 0
    declared_atomize_prewarms: int = 0
    installed_atomize_prewarms: int = 0
    skipped_atomize_prewarms: int = 0
    declared_update_prewarms: int = 0
    installed_update_prewarms: int = 0
    skipped_update_prewarms: int = 0
    declared_sever_prewarms: int = 0
    installed_sever_prewarms: int = 0
    skipped_sever_prewarms: int = 0
    declared_directional_meld_prewarms: int = 0
    installed_directional_meld_prewarms: int = 0
    skipped_directional_meld_prewarms: int = 0


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
class ProfileRenameResult:
    """One stable Profile identity published under a new display name."""

    previous_name: str
    profile: ProfileEntry
    active_profile_name: str
    was_active: bool
    changed: bool


@dataclass(frozen=True)
class ProfileRemovalResult:
    """One Profile permanently deleted behind a retained identity tombstone."""

    profile: ProfileEntry
    study_name: str | None
    active_profile_name: str
    study_profile_count: int
    study_removed_count: int
    removed_grant_count: int
    deleted_store: Path


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


@dataclass(frozen=True)
class GrantedContextView:
    """One validated Context view resolved for a grantee Profile."""

    grant: AuthorityGrant
    authority: ProfileEntry
    grantee: ProfileEntry
    requested_name: str
    authority_context_name: str
    authority_root: Path


@dataclass(frozen=True)
class ShareEndpoint:
    """One grant-backed cross-Profile delivery target."""

    grant: AuthorityGrant
    authority: ProfileEntry
    sender: ProfileEntry
    public_name: str
    receiver_context_name: str
    receiver_root: Path


def default_study_bundle_root() -> Path:
    """Return the editable-checkout fixture location when it is available."""

    return Path(__file__).resolve().parents[1] / "outputs" / "study-fixtures"


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
_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT = (
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
_LEGACY_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT = (
    _STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT.replace("memcommit", "MemLab")
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
STUDY_BASELINE_PROFILE_NAME = "study-baseline"
_STUDY_BASELINE_SOURCE_KIND = "STUDY_BASELINE"
_STUDY_BASELINE_SCHEMA_VERSION = 1
_STUDY_BASELINE_GRANTED_ROOT = "granted-memory"
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
            )
            for identity in identities
        }
        if len(shared) != 1:
            raise ProfileError("Study run Profile provenance is inconsistent.")
        name, created_at, _baseline_uid, _baseline_name, _digest = next(iter(shared))
        if name.casefold() in seen_names:
            raise ProfileError("Study run names must be unique.")
        seen_names.add(name.casefold())
        participant = next(
            profile
            for profile, identity in members
            if identity.role == "PARTICIPANT"
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


def list_profiles() -> tuple[ProfileRegistry, tuple[StoreInspection, ...]]:
    registry = load_profile_registry()
    visible = registry.visible_profiles
    base = tuple(
        inspect_store(
            profile_store_dir(item),
            allowed_virtual_currents=_read_granted_public_names(
                registry,
                item.uid,
            ),
        )
        for item in visible
    )
    cache = {
        profile.uid: inspection
        for profile, inspection in zip(visible, base, strict=True)
    }
    return registry, tuple(
        _inspection_with_grants(
            registry,
            profile,
            inspection,
            cache=cache,
        )
        for profile, inspection in zip(visible, base, strict=True)
    )


def use_profile(name: str) -> tuple[ProfileRegistry, StoreInspection, bool]:
    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        target = registry.by_name(canonical)
        if target is None:
            raise ProfileError(f"Profile {canonical!r} does not exist.")
        if registry.is_removed(target):
            raise ProfileError(
                f"Profile {canonical!r} was removed from direct selection."
            )
        inspection = _inspection_with_grants(
            registry,
            target,
            inspect_store(
                profile_store_dir(target),
                allowed_virtual_currents=_read_granted_public_names(
                    registry,
                    target.uid,
                ),
            ),
        )
        if target.uid == registry.active_uid:
            return registry, inspection, False
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=target.uid,
            profiles=registry.profiles,
            grants=registry.grants,
            removed_profile_uids=registry.removed_profile_uids,
        )
        _write_registry(updated)
        return updated, inspection, True


def rename_profile(
    new_name: str,
    *,
    old_name: str | None = None,
) -> ProfileRenameResult:
    """Rename one ordinary managed Profile without changing its stable identity."""

    try:
        canonical_new = validate_profile_name(new_name)
        canonical_old = (
            validate_profile_name(old_name) if old_name is not None else None
        )
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Profile rename name is invalid.") from error

    with _registry_lock():
        registry = load_profile_registry()
        target = (
            registry.active
            if canonical_old is None
            else registry.by_name(canonical_old)
        )
        if target is None:
            raise ProfileError(f"Profile {canonical_old!r} does not exist.")
        if registry.is_removed(target):
            raise ProfileError(
                f"Profile {target.name!r} cannot be renamed while removed."
            )
        was_active = target.uid == registry.active_uid

        # An exact no-op must not become a hidden store validation or registry
        # write, including for fixed anchors that cannot actually be renamed.
        if target.name == canonical_new:
            return ProfileRenameResult(
                previous_name=target.name,
                profile=target,
                active_profile_name=registry.active.name,
                was_active=was_active,
                changed=False,
            )

        groups = study_profile_groups(registry.profiles)
        membership = next(
            (
                group
                for group in groups
                if any(
                    profile.uid == target.uid
                    for profile in (*group.profiles, *group.support_profiles)
                )
            ),
            None,
        )
        if target.kind == "AUTHORING":
            raise ProfileError("The fixed authoring Profile cannot be renamed.")
        if target.name.casefold() == STUDY_BASELINE_PROFILE_NAME.casefold():
            raise ProfileError("The fixed study-baseline Profile cannot be renamed.")
        if membership is not None:
            raise ProfileError(
                f"Profile {target.name!r} is a member of legacy Study "
                f"{membership.name!r} and cannot be renamed individually."
            )
        if canonical_new.casefold() == AUTHORING_PROFILE_NAME.casefold():
            raise ProfileError("The fixed authoring Profile name is reserved.")
        if canonical_new.casefold() == STUDY_BASELINE_PROFILE_NAME.casefold():
            raise ProfileError("The fixed study-baseline Profile name is reserved.")
        collision = next(
            (
                profile
                for profile in registry.profiles
                if profile.uid != target.uid
                and profile.name.casefold() == canonical_new.casefold()
            ),
            None,
        )
        if collision is not None:
            raise ProfileError(f"Profile {collision.name!r} already exists.")
        group_collision = next(
            (
                group
                for group in groups
                if group.name.casefold() == canonical_new.casefold()
            ),
            None,
        )
        if group_collision is not None:
            raise ProfileError(
                f"Profile name {canonical_new!r} conflicts with existing legacy "
                f"Study {group_collision.name!r}."
            )

        # Rename is a control-plane metadata mutation, but validate the live
        # target before publishing a new locator for an unsafe or missing root.
        inspect_store(profile_store_dir(target))
        renamed = replace(target, name=canonical_new)
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=tuple(
                renamed if profile.uid == target.uid else profile
                for profile in registry.profiles
            ),
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
                    "Profile rename registry state could not be confirmed; "
                    "inspect it with 'mem profile list'."
                ) from read_error
            if visible == updated:
                raise ProfileError(
                    f"Profile {target.name!r} was renamed to {renamed.name!r}, "
                    "but registry durability could not be confirmed; it remains "
                    "renamed."
                ) from error
            if visible != registry:
                raise ProfileError(
                    "Profile rename registry changed unexpectedly; inspect it "
                    "with 'mem profile list'."
                ) from error
            raise

        return ProfileRenameResult(
            previous_name=target.name,
            profile=renamed,
            active_profile_name=updated.active.name,
            was_active=was_active,
            changed=True,
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


def _profile_study_target(
    registry: ProfileRegistry,
    profile: ProfileEntry,
) -> tuple[str, str, tuple[ProfileEntry, ...]] | None:
    """Return the complete Study containing a Profile, when one exists."""

    for group in study_profile_groups(registry.profiles):
        members = (*group.profiles, *group.support_profiles)
        if any(member.uid == profile.uid for member in members):
            return group.uid, group.name, members
    for pair in study_run_profile_pairs(registry.profiles):
        members = (pair.participant, pair.authority)
        if any(member.uid == profile.uid for member in members):
            return pair.uid, pair.name, members
    return None


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


def remove_profile(
    name: str,
    *,
    expected_uid: str | None = None,
    expected_generation: int | None = None,
) -> ProfileRemovalResult:
    """Permanently delete one Profile store, including every checkpoint."""

    canonical = validate_profile_name(name)
    with _registry_lock():
        registry = load_profile_registry()
        if (
            expected_generation is not None
            and registry.generation != expected_generation
        ):
            raise ProfileError("Profile registry changed after removal review.")
        target = registry.by_name(canonical)
        if target is None:
            raise ProfileError(f"Profile {canonical!r} does not exist.")
        if expected_uid is not None and target.uid != expected_uid:
            raise ProfileError("Profile identity changed after removal review.")
        if target.kind == "AUTHORING":
            raise ProfileError("The fixed authoring Profile cannot be removed.")
        if target.name.casefold() == STUDY_BASELINE_PROFILE_NAME.casefold():
            raise ProfileError("The fixed study-baseline Profile cannot be removed.")
        if target.uid == registry.active_uid:
            raise ProfileError(
                f"Profile {target.name!r} is active; select another Profile "
                "before removing it."
            )
        store = profile_store_dir(target)
        if (
            registry.is_removed(target)
            and not store.exists()
            and not store.is_symlink()
        ):
            raise ProfileError(f"Profile {target.name!r} is already removed.")

        # Validate every byte tree before it is moved into the private deletion
        # batch. This prevents a recursive delete from following an unsafe link
        # or accepting an already-corrupt Profile as the reviewed target.
        inspect_store(
            store,
            allowed_virtual_currents=_read_granted_public_names(
                registry,
                target.uid,
            ),
        )
        study = _profile_study_target(registry, target)
        removed = frozenset((*registry.removed_profile_uids, target.uid))
        ordered_removed = tuple(
            profile.uid for profile in registry.profiles if profile.uid in removed
        )
        retained_grants = tuple(
            grant
            for grant in registry.grants
            if target.uid
            not in {grant.authority_profile_uid, grant.grantee_profile_uid}
        )
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            active_uid=registry.active_uid,
            profiles=registry.profiles,
            grants=retained_grants,
            removed_profile_uids=ordered_removed,
        )
        batch = _prepare_profile_deletion_batch((target,))
        _publish_permanent_removal(
            registry,
            updated,
            batch=batch,
            profiles=(target,),
            label=f"Profile {target.name!r}",
        )
        members = study[2] if study is not None else ()
        return ProfileRemovalResult(
            profile=target,
            study_name=study[1] if study is not None else None,
            active_profile_name=registry.active.name,
            study_profile_count=len(members),
            study_removed_count=sum(member.uid in removed for member in members),
            removed_grant_count=len(registry.grants) - len(retained_grants),
            deleted_store=store,
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
                uid
                for uid in registry.removed_profile_uids
                if uid not in grouped_uids
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
    scope = ContextScope.create(
        (resource_name,),
        include_descendants=recursive,
    )
    names = expand_lexical_context_names(scope, sorted(contexts))
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
        if name_folded == public_folded or name_folded.startswith(public_folded + "/"):
            raise ProfileError(
                f"Granted view {public_name!r} overlaps local Context {name!r}."
            )
        # A lexical local ancestor is safe and lets a borrowed view appear
        # below its task namespace. The granted leaf and its descendants must
        # still remain absent locally or local resolution would bypass grants.
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
        if registry.is_removed(authority) or registry.is_removed(grantee):
            raise ProfileError(
                "A removed Profile cannot be used to create a new Grant."
            )
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
            removed_profile_uids=registry.removed_profile_uids,
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
            removed_profile_uids=registry.removed_profile_uids,
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
            removed_profile_uids=registry.removed_profile_uids,
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


def resolve_share_endpoint(
    public_name: str,
    *,
    registry: ProfileRegistry | None = None,
) -> ShareEndpoint:
    """Resolve an exact SHARE grant without projecting receiver contents.

    SHARE is deliberately an endpoint capability rather than a readable view.
    The sender can address the public grant name, but learns no receiver data
    and cannot redirect delivery to an arbitrary Profile or Context path.
    """

    registry = registry or load_profile_registry()
    canonical = validate_grant_resource_name(public_name)
    sender = registry.active
    candidates = [
        grant
        for grant in registry.grants
        if grant.grantee_profile_uid == sender.uid
        and grant.public_name == canonical
        and "SHARE" in grant.permissions
    ]
    if not candidates:
        raise ProfileError(f"Share endpoint {canonical!r} does not exist.")
    if len(candidates) != 1:
        raise ProfileError(f"Share endpoint {canonical!r} is ambiguous.")
    grant = candidates[0]

    attachment = _context_record_at(
        profile_store_dir(sender),
        grant.attachment_context_name,
    )
    if attachment is None or attachment.uid != grant.attachment_context_uid:
        raise ProfileError("Share endpoint attachment Context identity changed.")

    authority = next(
        profile
        for profile in registry.profiles
        if profile.uid == grant.authority_profile_uid
    )
    receiver_root = profile_store_dir(authority)
    receiver = _context_record_at(receiver_root, grant.resource_name)
    if receiver is None or receiver.uid != grant.resource_uid:
        raise ProfileError("Share endpoint receiver Context identity changed.")
    if not any(
        binding.uid == receiver.uid and binding.name == receiver.name
        for binding in grant.contexts
    ):
        raise ProfileError("Share endpoint grant does not contain its receiver root.")
    return ShareEndpoint(
        grant=grant,
        authority=authority,
        sender=sender,
        public_name=canonical,
        receiver_context_name=receiver.name,
        receiver_root=receiver_root,
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
    return f"{_STUDY_BASELINE_GRANTED_ROOT}/{task_name}" if authority else task_name


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
            uid=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    "memcommit:study:practice/description:memory",
                )
            ),
            content=_STUDY_PRACTICE_DESCRIPTION_OVERVIEW_CONTENT,
        )
    )
    description.add(
        Memory(
            uid=str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    "memcommit:study:practice/description:task-memory",
                )
            ),
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
        _LEGACY_STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT: (
            _STUDY_PRACTICE_DESCRIPTION_TASK_CONTENT
        ),
    }
    needs_copy = _LEGACY_STUDY_PRACTICE_PROVENANCE_UID in description.memories or any(
        isinstance(item, Memory) and item.content in replacements
        for item in description.iter_items()
    )
    if not needs_copy:
        return contexts
    # Exact known legacy values are safe to migrate in the run snapshot. Any
    # independently edited description remains untouched and recoverable.
    sanitized = dict(contexts)
    sanitized_description = copy.deepcopy(description)
    if _LEGACY_STUDY_PRACTICE_PROVENANCE_UID in sanitized_description.memories:
        sanitized_description.remove(_LEGACY_STUDY_PRACTICE_PROVENANCE_UID)
    for item in sanitized_description.iter_items():
        if isinstance(item, Memory) and item.content in replacements:
            item.content = replacements[item.content]
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
        *(f"{_STUDY_BASELINE_GRANTED_ROOT}/task-{task}" for task in _STUDY_TASKS),
    ]
    contexts = [Context(uid=str(uuid.uuid4()), name=name) for name in structural_names]
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
            branch = _study_baseline_branch(task, authority=authority)
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


def _study_baseline_source_record(
    packages: dict[int, _StudyTaskPackage],
    *,
    imported_at: str,
    initial_digest: str,
) -> dict[str, object]:
    tasks: list[dict[str, object]] = []
    for task in _STUDY_TASKS:
        package = packages[task]
        task_source = next(
            source for source in package.profiles if source.role == "TASK"
        )
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


def refresh_study_profile(
    bundle_root: Path,
    *,
    replace_edited_baseline: bool = False,
) -> StudyImportResult:
    """Replace the registered Study baseline with current fixture packages.

    The baseline remains an intentionally editable intermediate source.  A
    refresh therefore fails closed when it has diverged from the digest saved
    at its last import, unless the caller explicitly accepts replacing those
    edits.
    """

    packages = _study_packages(bundle_root)
    _validate_study_package_grants(packages)
    imported_at = datetime.now(timezone.utc).isoformat()
    with _registry_lock():
        registry = load_profile_registry()
        baseline = registry.by_name(STUDY_BASELINE_PROFILE_NAME)
        if baseline is None:
            raise ProfileError(
                f"Profile {STUDY_BASELINE_PROFILE_NAME!r} does not exist; "
                "bootstrap it with 'mem profile import-study'."
            )
        _study_baseline_tasks(baseline)
        if any(
            baseline.uid in {grant.authority_profile_uid, grant.grantee_profile_uid}
            for grant in registry.grants
        ):
            raise ProfileError(
                f"Study baseline Profile {baseline.name!r} participates in registry "
                "grants and cannot be refreshed."
            )

        source = baseline.source
        assert isinstance(source, dict)
        initial_digest = source["initial_baseline_sha256"]
        assert isinstance(initial_digest, str)
        destination = profile_store_dir(baseline)
        current_digest = baseline_store_digest(destination)
        if current_digest != initial_digest and not replace_edited_baseline:
            raise ProfileError(
                "Study baseline has local edits. Re-run with "
                "--replace-edited-baseline to replace them with the generated bundles."
            )

        staging = profile_stores_dir() / (
            f".{baseline.uid}.study-refresh-{uuid.uuid4().hex}"
        )
        backup = profile_stores_dir() / (
            f".{baseline.uid}.study-refresh-backup-{uuid.uuid4().hex}"
        )
        replacement_visible = False
        old_store_moved = False
        registry_published = False
        try:
            inspection = _compose_study_baseline_store(packages, staging)
            refreshed_digest = baseline_store_digest(staging)
            refreshed = replace(
                baseline,
                source=_study_baseline_source_record(
                    packages,
                    imported_at=imported_at,
                    initial_digest=refreshed_digest,
                ),
            )
            updated = replace(
                registry,
                generation=max(1, registry.generation + 1),
                profiles=tuple(
                    refreshed if profile.uid == baseline.uid else profile
                    for profile in registry.profiles
                ),
            )

            # The stable Profile UID keeps selection and references intact;
            # the private backup makes the store swap reversible until the
            # matching provenance record is durably visible.
            os.replace(destination, backup)
            old_store_moved = True
            os.replace(staging, destination)
            replacement_visible = True
            try:
                _write_registry(updated)
                registry_published = True
            except Exception as error:
                try:
                    registry_published = load_profile_registry() == updated
                except (OSError, ProfileConfigError, ValueError):
                    registry_published = False
                if registry_published:
                    raise ProfileError(
                        "Study baseline was refreshed, but registry durability "
                        "could not be confirmed; the replacement remains visible."
                    ) from error
                os.replace(destination, staging)
                replacement_visible = False
                os.replace(backup, destination)
                old_store_moved = False
                raise

            shutil.rmtree(backup)
            old_store_moved = False
            return StudyImportResult(
                profiles=(refreshed,),
                inspections=(replace(inspection, root=destination),),
            )
        finally:
            if not registry_published:
                if replacement_visible and old_store_moved:
                    os.replace(destination, staging)
                    replacement_visible = False
                if old_store_moved:
                    os.replace(backup, destination)
                    old_store_moved = False
            for candidate in (staging, backup):
                if candidate.exists() and not candidate.is_symlink():
                    shutil.rmtree(candidate)


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
        if (
            raw.get("task_profile_name") != f"task-{task}"
            or raw.get("authority_profile_name") != _STUDY_AUTHORITY_PROFILE_NAMES[task]
        ):
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
            raise ProfileError(
                "Study baseline grant permissions are invalid."
            ) from error
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
        *(f"{_STUDY_BASELINE_GRANTED_ROOT}/task-{task}" for task in _STUDY_TASKS),
    }
    practice_names = {
        _STUDY_PRACTICE_ROOT,
        _STUDY_PRACTICE_DESCRIPTION,
        _STUDY_PRACTICE_SOURCE,
    }
    present_practice_names = practice_names.intersection(contexts)
    if present_practice_names and present_practice_names != practice_names:
        raise ProfileError("Study baseline practice topology is incomplete.")
    expected = set(structural)
    expected.update(present_practice_names)
    for task in _STUDY_TASKS:
        for authority in (False, True):
            branch = _study_baseline_branch(task, authority=authority)
            expected.update(name for name in contexts if name.startswith(branch + "/"))
    if set(contexts) != expected:
        extras = sorted(set(contexts) - expected)
        missing = sorted(expected - set(contexts))
        detail = extras or missing
        raise ProfileError(
            "Study baseline Context topology is invalid: " + ", ".join(detail)
        )
    catalogs = _study_catalogs(root)
    if any(name in structural for name, _language in catalogs):
        raise ProfileError(
            "Study baseline structural Contexts cannot own translations."
        )

    packages: dict[int, _StudyTaskPackage] = {}
    for task in _STUDY_TASKS:
        raw = task_records[task]
        sources: list[_StudyProfileSource] = []
        role_contexts: dict[str, dict[str, Context]] = {}
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source_name = (
                raw["authority_profile_name"] if authority else raw["task_profile_name"]
            )
            assert isinstance(source_name, str)
            branch = _study_baseline_branch(task, authority=authority)
            selected = {
                name: context
                for name, context in contexts.items()
                if name.startswith(branch + "/")
            }
            if task == 1 and not authority:
                practice = (
                    {name: contexts[name] for name in sorted(present_practice_names)}
                    if present_practice_names
                    else {
                        context.name: context for context in _study_practice_contexts()
                    }
                )
                practice = _canonicalize_study_practice_description(practice)
                selected.update(practice)
            if not selected:
                raise ProfileError(f"Study baseline branch {branch!r} is empty.")
            mapping = {
                name: (
                    name if _is_study_practice_name(name) else name[len(branch) + 1 :]
                )
                for name in selected
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


def _prefix_study_grant_template(
    raw: dict[str, object],
    *,
    task: int,
) -> dict[str, object]:
    """Map one package grant into the two-Profile run namespace."""

    result = copy.deepcopy(raw)
    prefix = f"task-{task}"

    key = result.get("key")
    if task == 1 and key == "task-1-campus-wiki-view":
        permissions = result.get("permissions")
        if isinstance(permissions, list):
            # Older editable baselines predate explicit whole-wiki query and
            # delete permissions. Keep them initializable while preserving the
            # current Task 1 operation contract in every newly created run.
            if "DELETE" not in permissions:
                permissions.append("DELETE")
            if "QUERY" not in permissions:
                permissions.append("QUERY")
            for permission in (
                "EMBED",
                "DERIVE",
                "COMBINE",
                "EXPORT",
                "ACCEPT_DERIVED",
                "SAVE_BOUND_ANALYSIS",
                "SAVE_ANALYSIS",
            ):
                if permission not in permissions:
                    permissions.append(permission)
        result.setdefault("provider", "codex_chatgpt")
    elif key in {
        "task-2-advisor1-view",
        "task-2-advisor2-view",
    }:
        permissions = result.get("permissions")
        if isinstance(permissions, list):
            # Existing baselines remain importable, but each new Study run
            # receives the current source-side derivation contract.
            for permission in (
                "EMBED",
                "DERIVE",
                "COMBINE",
                "EXPORT",
                "SAVE_BOUND_ANALYSIS",
                "SAVE_ANALYSIS",
            ):
                if permission not in permissions:
                    permissions.append(permission)

    if key == "task-3-healthcare-transmission-guidance-view":
        permissions = result.get("permissions")
        if isinstance(permissions, list) and "EMBED" not in permissions:
            # Editable baselines created before revocable links remain usable,
            # while new Study runs expose the current Task 3 source contract.
            permissions.append("EMBED")

    authority_context = result.get("authority_context")
    if isinstance(authority_context, dict) and isinstance(
        authority_context.get("name"), str
    ):
        authority_context["name"] = f"{prefix}/{authority_context['name']}"
    exclusions = result.get("excluded_contexts")
    if isinstance(exclusions, list):
        for exclusion in exclusions:
            if isinstance(exclusion, dict) and isinstance(exclusion.get("name"), str):
                exclusion["name"] = f"{prefix}/{exclusion['name']}"

    attachment = result.get("attachment")
    if isinstance(attachment, dict) and attachment.get("kind") == "GRANTEE_CONTEXT":
        context = attachment.get("context")
        if isinstance(context, dict) and isinstance(context.get("name"), str):
            context["name"] = f"{prefix}/{context['name']}"
        public_name = result.get("public_name")
        if isinstance(public_name, str):
            # The public path is deliberately task-local while the attachment
            # stays the exact participant Context required by the grant model.
            result["public_name"] = f"{prefix}/{public_name}"
    return result


def _compose_study_run_pair(
    packages: dict[int, _StudyTaskPackage],
    *,
    participant_root: Path,
    authority_root: Path,
) -> dict[int, _StudyTaskPackage]:
    """Write two run-private stores and return grant-ready package views."""

    participant_contexts: list[Context] = []
    authority_contexts: list[Context] = []
    participant_catalogs: list[TranslationCatalog] = []
    authority_catalogs: list[TranslationCatalog] = []

    for task in _STUDY_TASKS:
        package = packages[task]
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source = next(item for item in package.profiles if item.role == role)
            source_contexts, query_refs = _context_records(source.store)
            if query_refs:
                raise ProfileError("Study run sources cannot contain query pointers.")
            mapping = {
                name: (
                    name
                    if task == 1 and not authority and _is_study_practice_name(name)
                    else f"task-{task}/{name}"
                )
                for name in source_contexts
            }
            remapped = _remap_context_records(source_contexts, mapping)
            catalogs = _remap_translation_catalogs(source.store, mapping)
            if authority:
                authority_contexts.extend(remapped)
                authority_catalogs.extend(catalogs)
            else:
                participant_contexts.extend(remapped)
                participant_catalogs.extend(catalogs)

    participant_inspection = _write_mapped_study_store(
        participant_root,
        contexts=tuple(participant_contexts),
        catalogs=tuple(participant_catalogs),
        # Start at the Practice parent so the participant deliberately opens
        # its description before proceeding. Task-specific Contexts stay
        # intact for later explicit navigation.
        current_context=_STUDY_PRACTICE_ROOT,
    )
    authority_source = next(
        source for source in packages[1].profiles if source.role == "AUTHORITY"
    )
    authority_inspection = _write_mapped_study_store(
        authority_root,
        contexts=tuple(authority_contexts),
        catalogs=tuple(authority_catalogs),
        current_context=f"task-1/{authority_source.inspection.current_context}",
    )

    # _materialize_study_grants validates each original package independently.
    # Its source names remain the manifest identities, but every task now reads
    # from one of the two merged run stores.
    merged: dict[int, _StudyTaskPackage] = {}
    merged_authority_contexts = {
        context.name: context for context in authority_contexts
    }
    for task in _STUDY_TASKS:
        package = packages[task]
        sources: list[_StudyProfileSource] = []
        for source in package.profiles:
            inspection = (
                authority_inspection
                if source.role == "AUTHORITY"
                else participant_inspection
            )
            sources.append(
                replace(
                    source,
                    store=authority_root
                    if source.role == "AUTHORITY"
                    else participant_root,
                    inspection=inspection,
                )
            )
        templates = tuple(
            _prefix_study_grant_template(raw, task=task)
            for raw in package.grant_templates
        )
        merged[task] = replace(
            package,
            profiles=tuple(sources),
            grant_templates=templates,
            query_view_count=_query_view_count_for_baseline(
                merged_authority_contexts,
                templates,
            ),
        )
    return merged


def _copy_declared_study_prewarms(
    baseline_root: Path,
    participant_root: Path,
) -> None:
    """Copy only the baseline-declared semantic fixture into one new run."""

    name = "study-semantic-prewarm"
    source = baseline_root / name
    if not source.exists():
        return
    _assert_plain_tree(source, label="Study semantic prewarm fixture")
    destination = participant_root / name
    if destination.exists() or destination.is_symlink():
        raise ProfileError("Study semantic prewarm destination is occupied.")
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)


def _publish_study_run_pair(
    registry: ProfileRegistry,
    *,
    baseline: ProfileEntry,
    packages: dict[int, _StudyTaskPackage],
    study_name: str,
    study_uid: str,
    created_at: str,
    baseline_digest: str,
) -> StudyInitializationResult:
    """Publish the run's two stores and grants as one registry transaction."""

    authority_name = _study_run_authority_profile_name(study_name)
    requested_names = {study_name.casefold(), authority_name.casefold()}
    conflicts = [
        profile.name
        for profile in registry.profiles
        if profile.name.casefold() in requested_names
    ]
    if conflicts:
        raise ProfileError(f"Profile {conflicts[0]!r} already exists.")

    common_source: dict[str, object] = {
        "study_uid": study_uid,
        "study_name": study_name,
        "created_at": created_at,
        "baseline_sha256": baseline_digest,
        "baseline_profile_uid": baseline.uid,
        "baseline_profile_name": baseline.name,
    }
    participant = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=study_name,
        kind="MANAGED",
        source={"kind": _STUDY_RUN_SOURCE_KIND, **common_source},
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name=authority_name,
        kind="MANAGED",
        source={"kind": _STUDY_RUN_GRANTED_SOURCE_KIND, **common_source},
    )
    batch = profile_stores_dir() / f".{study_name}.study-run-{uuid.uuid4().hex}"
    batch.mkdir()
    participant_staging = batch / participant.uid
    authority_staging = batch / authority.uid
    published: list[tuple[Path, Path]] = []
    committed = False
    try:
        merged = _compose_study_run_pair(
            packages,
            participant_root=participant_staging,
            authority_root=authority_staging,
        )
        _copy_declared_study_prewarms(
            profile_store_dir(baseline),
            participant_staging,
        )
        profiles_by_name: dict[str, ProfileEntry] = {}
        roots_by_name: dict[str, Path] = {}
        for package in merged.values():
            for source in package.profiles:
                target = authority if source.role == "AUTHORITY" else participant
                profiles_by_name[source.name] = target
                roots_by_name[source.name] = source.store
        grants = _materialize_study_grants(
            merged,
            profiles_by_name,
            roots_by_name,
        )
        namespace = uuid.UUID(study_uid)
        grants = tuple(
            replace(grant, uid=str(uuid.uuid5(namespace, grant.uid)))
            for grant in grants
        )
        existing_grant_uids = {grant.uid for grant in registry.grants}
        if any(grant.uid in existing_grant_uids for grant in grants):
            raise ProfileError("Study grant identity already exists.")

        participant_inspection = inspect_store(participant_staging)
        authority_inspection = inspect_store(authority_staging)
        updated = ProfileRegistry(
            generation=max(1, registry.generation + 1),
            # init-study mirrors init: the complete participant/authority pair
            # and grants become visible in the same generation that selects
            # the participant side. The authority Profile is never selected.
            active_uid=participant.uid,
            profiles=(*registry.profiles, participant, authority),
            grants=(*registry.grants, *grants),
            removed_profile_uids=registry.removed_profile_uids,
        )
        participant_inspection = _inspection_with_grants(
            updated,
            participant,
            participant_inspection,
            cache={authority.uid: authority_inspection},
        )

        for profile, source in (
            (participant, participant_staging),
            (authority, authority_staging),
        ):
            destination = profile_store_dir(profile)
            if destination.exists() or destination.is_symlink():
                raise ProfileError("Managed profile destination is occupied.")
            os.replace(source, destination)
            published.append((destination, source))
        # Validate before the registry generation becomes visible. Hidden
        # receipts are persisted after releasing this lock so the new active
        # Profile and regenerated Grants are the identities they attest to.
        from memcommit.store import MemoryStore
        from memcommit.study_prewarm.atomize import (
            install_declared_atomize_prewarms,
        )
        from memcommit.study_prewarm.compare import (
            install_declared_compare_prewarms,
        )
        from memcommit.study_prewarm.update import install_declared_update_prewarms
        from memcommit.study_prewarm.sever import install_declared_sever_prewarms
        from memcommit.study_prewarm.meld_directional import (
            install_declared_directional_meld_prewarms,
        )

        install_declared_atomize_prewarms(
            store=MemoryStore(root=profile_store_dir(participant), create=False),
            profile=participant,
            registry_snapshot=updated,
            publish=False,
        )
        install_declared_compare_prewarms(
            store=MemoryStore(root=profile_store_dir(participant), create=False),
            profile=participant,
            registry_snapshot=updated,
            publish=False,
        )
        install_declared_update_prewarms(
            store=MemoryStore(root=profile_store_dir(participant), create=False),
            profile=participant,
            registry_snapshot=updated,
            publish=False,
        )
        install_declared_sever_prewarms(
            store=MemoryStore(root=profile_store_dir(participant), create=False),
            profile=participant,
            registry_snapshot=updated,
            publish=False,
        )
        install_declared_directional_meld_prewarms(
            store=MemoryStore(root=profile_store_dir(participant), create=False),
            profile=participant,
            registry_snapshot=updated,
            publish=False,
        )
        try:
            _write_registry(updated)
        except Exception as error:
            try:
                replacement_is_visible = load_profile_registry() == updated
            except (OSError, ProfileConfigError, ValueError):
                replacement_is_visible = False
            if replacement_is_visible:
                # A post-replace fsync failure may still leave the complete
                # pair and grant generation visible. Keep both stores so that
                # the registry never points at missing run data.
                committed = True
                raise ProfileError(
                    f"Study run {study_name!r} was published, but registry "
                    "durability could not be confirmed; it remains registered."
                ) from error
            raise
        committed = True
        return StudyInitializationResult(
            profile=participant,
            inspection=replace(
                participant_inspection,
                root=profile_store_dir(participant),
            ),
            authority_profile=authority,
            authority_inspection=replace(
                authority_inspection,
                root=profile_store_dir(authority),
            ),
            baseline_profile_name=baseline.name,
            active_profile_name=participant.name,
        )
    except Exception:
        if not committed:
            for destination, source in reversed(published):
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
        raise
    finally:
        if batch.exists() and not batch.is_symlink():
            shutil.rmtree(batch)


def init_study_profile(
    baseline_profile_name: str = STUDY_BASELINE_PROFILE_NAME,
    *,
    name: str | None = None,
) -> StudyInitializationResult:
    """Create one isolated participant Profile and one authority Profile."""

    try:
        baseline_name = validate_profile_name(baseline_profile_name)
    except (ProfileConfigError, ValueError) as error:
        raise ProfileError("Study baseline Profile name is invalid.") from error

    generated_uid = uuid.uuid4()
    created = datetime.now(timezone.utc)
    if name is None:
        profile_name = generate_study_profile_name(
            created=created,
            generated_uid=generated_uid,
        )
    else:
        try:
            profile_name = validate_profile_name(name)
        except (ProfileConfigError, ValueError) as error:
            raise ProfileError("Study Profile name is invalid.") from error
    if profile_name == AUTHORING_PROFILE_NAME:
        raise ProfileError("The fixed authoring name cannot identify a Study Profile.")

    with _registry_lock():
        registry = load_profile_registry()
        baseline = registry.by_name(baseline_name)
        if baseline is None:
            bootstrap = (
                "; bootstrap it with 'mem profile import-study'"
                if baseline_name == STUDY_BASELINE_PROFILE_NAME
                else ""
            )
            raise ProfileError(
                f"Study baseline Profile {baseline_name!r} does not exist{bootstrap}."
            )
        if any(
            group.name.casefold() == profile_name.casefold()
            for group in study_profile_groups(registry.profiles)
        ):
            raise ProfileError(
                f"Profile name {profile_name!r} conflicts with an existing legacy "
                "Study group."
            )
        if any(
            baseline.uid in {grant.authority_profile_uid, grant.grantee_profile_uid}
            for grant in registry.grants
        ):
            # Grants are registry relationships, not owned baseline content.
            # Holding the same lock through publication makes the self-contained
            # source check part of the exact registry generation being copied.
            raise ProfileError(
                f"Study baseline Profile {baseline.name!r} participates in registry "
                "grants and cannot be copied as one self-contained Profile."
            )

        task_records = _study_baseline_tasks(baseline)
        source_root = profile_store_dir(baseline)
        before = baseline_store_digest(source_root)
        staging = profile_stores_dir() / (
            f".{profile_name}.study-source-{uuid.uuid4().hex}"
        )
        try:
            packages = _snapshot_study_baseline(baseline, task_records, staging)
            after = baseline_store_digest(source_root)
            if before != after:
                raise ProfileError("Study baseline changed during initialization.")
            initialization = _publish_study_run_pair(
                registry,
                baseline=baseline,
                packages=packages,
                study_name=profile_name,
                study_uid=str(generated_uid),
                created_at=created.isoformat(),
                baseline_digest=before,
            )
        finally:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)

    # The new registry generation is now visible and the outer registry guard
    # has been released. Revalidate current identities and Grants, then write
    # only hidden entry-key receipts. Ordinary operation state is materialized
    # through each command's durable boundary on first explicit use.
    from memcommit.store import MemoryStore
    from memcommit.study_prewarm.atomize import install_declared_atomize_prewarms
    from memcommit.study_prewarm.compare import install_declared_compare_prewarms
    from memcommit.study_prewarm.update import install_declared_update_prewarms
    from memcommit.study_prewarm.sever import install_declared_sever_prewarms
    from memcommit.study_prewarm.meld_directional import (
        install_declared_directional_meld_prewarms,
    )

    try:
        participant_store = MemoryStore(
            root=profile_store_dir(initialization.profile),
            create=False,
        )
        current_registry = load_profile_registry()
        compare_prewarms = install_declared_compare_prewarms(
            store=participant_store,
            profile=initialization.profile,
            registry_snapshot=current_registry,
        )
        atomize_prewarms = install_declared_atomize_prewarms(
            store=participant_store,
            profile=initialization.profile,
            registry_snapshot=current_registry,
        )
        update_prewarms = install_declared_update_prewarms(
            store=participant_store,
            profile=initialization.profile,
            registry_snapshot=current_registry,
        )
        sever_prewarms = install_declared_sever_prewarms(
            store=participant_store,
            profile=initialization.profile,
            registry_snapshot=current_registry,
        )
        directional_meld_prewarms = install_declared_directional_meld_prewarms(
            store=participant_store,
            profile=initialization.profile,
            registry_snapshot=current_registry,
        )
    except Exception as error:
        raise ProfileError(
            f"Study run {profile_name!r} was created, but its declared semantic "
            f"prewarm could not be installed: {error}"
        ) from error
    return replace(
        initialization,
        declared_compare_prewarms=compare_prewarms.declared,
        installed_compare_prewarms=compare_prewarms.installed,
        skipped_compare_prewarms=compare_prewarms.skipped_configuration,
        declared_atomize_prewarms=atomize_prewarms.declared,
        installed_atomize_prewarms=atomize_prewarms.installed,
        skipped_atomize_prewarms=atomize_prewarms.skipped_configuration,
        declared_update_prewarms=update_prewarms.declared,
        installed_update_prewarms=update_prewarms.installed,
        skipped_update_prewarms=update_prewarms.skipped_configuration,
        declared_sever_prewarms=sever_prewarms.declared,
        installed_sever_prewarms=sever_prewarms.installed,
        skipped_sever_prewarms=sever_prewarms.skipped_configuration,
        declared_directional_meld_prewarms=directional_meld_prewarms.declared,
        installed_directional_meld_prewarms=directional_meld_prewarms.installed,
        skipped_directional_meld_prewarms=(
            directional_meld_prewarms.skipped_configuration
        ),
    )


def generate_study_profile_name(
    *,
    created: datetime | None = None,
    generated_uid: uuid.UUID | None = None,
) -> str:
    """Return the editable timestamp-and-UUID default for one Study run."""
    timestamp = created or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Study name timestamps must be timezone-aware.")
    timestamp = timestamp.astimezone(timezone.utc)
    suffix = generated_uid or uuid.uuid4()
    return f"study-{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{str(suffix)[:8]}"
