"""Read and validate packaged inputs for init-study Profile creation."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    ProfileEntry,
    validate_grant_resource_name,
    validate_profile_name,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    _context_records,
    _read_json,
    _source_digest,
    inspect_store,
)
from memcommit.core.context import Context, Memory
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TranslationCatalogError,
)
from memcommit.persistence.store.translation_catalog import (
    decode_translation_catalog_record,
)
from memcommit.persistence.store.infrastructure.atomic_io import _canonical_json_digest

from .model import (
    _STUDY_TASKS,
    _STUDY_AUTHORITY_PROFILE_NAMES,
    _STUDY_BUNDLE_NAMESPACE,
    _StudyProfileSource,
    _StudyTaskPackage,
)


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


def _study_integer(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProfileError(f"Study manifest {label} is invalid.")
    return value


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
        if "context_records_sha256" in raw:
            contexts, _query_refs = _context_records(store)
            actual_digest = _canonical_json_digest({
                name: context.to_dict() for name, context in contexts.items()
            })
            if raw["context_records_sha256"] != actual_digest:
                raise ProfileError(f"Task {task} native Context records changed after packaging.")
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


def _study_catalogs(
    root: Path,
) -> dict[tuple[str, str], MemoryTranslationCatalog]:
    catalogs: dict[tuple[str, str], MemoryTranslationCatalog] = {}
    directory = root / "translation-views"
    if not directory.exists():
        return catalogs
    for path in sorted(directory.glob("*--catalog.json")):
        data = _read_json(path, label="Translation catalog")
        try:
            catalog = decode_translation_catalog_record(data)
        except (TranslationCatalogError, TypeError, ValueError) as error:
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


def _validate_study_package_grants(
    packages: dict[int, _StudyTaskPackage],
) -> None:
    """Bind bootstrap grant templates to their exact package-owned Contexts."""

    from .publication import _materialize_study_grants

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
