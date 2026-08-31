"""Build Task 1--3 task/authority profile packages from paired fixtures.

The authoring corpus is language-partitioned, but a runtime Memory has one
canonical English body.  Korean remains a same-UID translation catalog for
ordinary Contexts.  Query-only is a grant on an authority-owned ordinary
Context, not a second concealed storage format inside the participant profile.
This builder is intentionally offline and refuses to reuse a non-empty target.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterator
import uuid

import memcommit.persistence.store as store_module
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.study_scenarios.legacy.fixtures import (
    FixtureDataset,
    FixtureMemory,
    FixtureTranslationPair,
    load_study_fixture,
    pair_fixture_translations,
)
from memcommit.application.operations.profiles.profile.config import GRANT_PERMISSIONS
from memcommit.persistence.store import MemoryStore
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TRANSLATION_ORIGIN_IMPORTED,
    TRANSLATION_REVIEW_UNREVIEWED,
)
from memcommit.persistence.store.translation_catalog import (
    save_translation_catalog,
)


_BUNDLE_NAMESPACE = uuid.UUID("50b72d54-cfbe-4f89-8f7f-1e6c785d8552")
_STORE_PATH_NAMES = (
    "STORE_DIR",
    "CONTEXTS_DIR",
    "STATE_FILE",
    "QUERY_SOURCES_DIR",
    "IMPACT_PLAN_FILE",
    "STAGED_UPDATE_FILE",
    "REVIEW_SESSION_FILE",
    "ATOMIZE_ANALYSES_DIR",
    "ATOMIZE_WORKBENCHES_DIR",
    "MELD_SESSIONS_DIR",
)


class StudyBundleError(RuntimeError):
    """A fixture package cannot be built without ambiguity or data loss."""


@dataclass(frozen=True)
class BundleDatasetSpec:
    dataset: str
    runtime_root: str
    year_month_hierarchy: bool = False


@dataclass(frozen=True)
class BundleProfileSpec:
    name: str
    role: str
    current_context: str
    datasets: tuple[BundleDatasetSpec, ...] = ()
    initial_contexts: tuple[str, ...] = ()


@dataclass(frozen=True)
class BundleGrantTemplate:
    key: str
    authority_profile: str
    grantee_profile: str
    authority_context: str
    public_name: str
    permissions: tuple[str, ...]
    grantee_parent_context: str | None = None
    parent_grant_key: str | None = None
    recursive: bool = True
    excluded_contexts: tuple[str, ...] = ()
    provider: str | None = None


@dataclass(frozen=True)
class BundleTaskSpec:
    task: int
    task_profile: BundleProfileSpec
    authority_profile: BundleProfileSpec
    grant_templates: tuple[BundleGrantTemplate, ...]

    @property
    def profiles(self) -> tuple[BundleProfileSpec, BundleProfileSpec]:
        return (self.task_profile, self.authority_profile)

    @property
    def current_context(self) -> str:
        """Retain the old task-current convenience for downstream callers."""

        return self.task_profile.current_context

    @property
    def datasets(self) -> tuple[BundleDatasetSpec, ...]:
        """Return every task dataset regardless of its owning profile."""

        return tuple(
            dataset for profile in self.profiles for dataset in profile.datasets
        )


@dataclass(frozen=True)
class BundleManifestEntry:
    task: int
    owner_profile: str
    dataset: str
    fixture_key: str
    canonical_locator: str
    runtime_context: str | None
    memory_uid: str
    query_only: bool
    purpose: str
    audiences: tuple[str, ...]
    verified: bool | None
    english_sha256: str
    korean_sha256: str
    translation_origin: str
    translation_review_status: str
    source_english: str
    source_korean: str


TASK_SPECS = {
    1: BundleTaskSpec(
        task=1,
        task_profile=BundleProfileSpec(
            name="task-1",
            role="TASK",
            current_context="participant/construction-updates",
            datasets=(
                BundleDatasetSpec("task1-description", "description"),
                BundleDatasetSpec(
                    "task1-construction-updates",
                    "participant/construction-updates",
                ),
            ),
        ),
        authority_profile=BundleProfileSpec(
            name="task-1-campus-authority",
            role="AUTHORITY",
            current_context="campus-wiki",
            datasets=(
                BundleDatasetSpec("task1-campus-wiki", "campus-wiki"),
                # The fixture locators already include construction-details
                # below campus-wiki.  Keeping the same root materializes that
                # complete subtree as ordinary authority-owned Contexts.
                BundleDatasetSpec("task1-campus-wiki-details", "campus-wiki"),
            ),
        ),
        grant_templates=(
            BundleGrantTemplate(
                key="task-1-campus-wiki-view",
                authority_profile="task-1-campus-authority",
                grantee_profile="task-1",
                authority_context="campus-wiki",
                public_name="campus-wiki",
                permissions=(
                    "CREATE",
                    "READ",
                    "UPDATE",
                    "DELETE",
                    "QUERY",
                ),
                grantee_parent_context="participant/construction-updates",
                excluded_contexts=("campus-wiki/construction-details",),
                provider="codex_chatgpt",
            ),
            BundleGrantTemplate(
                key="task-1-construction-details-query",
                authority_profile="task-1-campus-authority",
                grantee_profile="task-1",
                authority_context="campus-wiki/construction-details",
                public_name="construction-details",
                permissions=("QUERY",),
                parent_grant_key="task-1-campus-wiki-view",
                provider="codex_chatgpt",
            ),
        ),
    ),
    2: BundleTaskSpec(
        task=2,
        task_profile=BundleProfileSpec(
            name="task-2",
            role="TASK",
            current_context="participant/proposal-workspace",
            datasets=(BundleDatasetSpec("task2-description", "description"),),
            initial_contexts=("participant/proposal-workspace",),
        ),
        authority_profile=BundleProfileSpec(
            name="task-2-proposal-authority",
            role="AUTHORITY",
            current_context="advisor1",
            datasets=(
                BundleDatasetSpec("task2-advisor1", "advisor1"),
                BundleDatasetSpec("task2-advisor2", "advisor2"),
                BundleDatasetSpec(
                    "task2-proposal-guidelines",
                    "proposal-submission-guidelines",
                ),
            ),
        ),
        grant_templates=tuple(
            BundleGrantTemplate(
                key=key,
                authority_profile="task-2-proposal-authority",
                grantee_profile="task-2",
                authority_context=context,
                public_name=context,
                permissions=(
                    ("QUERY",)
                    if permission == "QUERY"
                    else ("READ",)
                ),
                grantee_parent_context="participant/proposal-workspace",
                provider=("codex_chatgpt" if permission == "QUERY" else None),
            )
            for key, context, permission in (
                ("task-2-advisor1-view", "advisor1", "READ"),
                ("task-2-advisor2-view", "advisor2", "READ"),
                (
                    "task-2-proposal-guidelines-query",
                    "proposal-submission-guidelines",
                    "QUERY",
                ),
            )
        ),
    ),
    3: BundleTaskSpec(
        task=3,
        task_profile=BundleProfileSpec(
            name="task-3",
            role="TASK",
            current_context="local/personal-memory",
            initial_contexts=("local",),
            datasets=(
                BundleDatasetSpec("task3-description", "description"),
                BundleDatasetSpec(
                    "task3-personal-memory",
                    "local/personal-memory",
                    year_month_hierarchy=True,
                ),
                BundleDatasetSpec(
                    "task3-guardrails",
                    "local/guardrails",
                ),
            ),
        ),
        authority_profile=BundleProfileSpec(
            name="task-3-healthcare-authority",
            role="AUTHORITY",
            current_context=(
                "remote/government/healthcare-agent/info-request/transmission-guidance"
            ),
            initial_contexts=(
                "remote",
                "remote/government",
                "remote/government/healthcare-agent",
                "remote/government/healthcare-agent/info-request",
            ),
            datasets=(
                BundleDatasetSpec(
                    "task3-healthcare-public-guidance",
                    "remote/government/healthcare-agent/info-request/transmission-guidance",
                ),
                BundleDatasetSpec(
                    "task3-healthcare-qna",
                    "remote/government/healthcare-agent/info-request/questions-and-answers",
                ),
            ),
        ),
        grant_templates=(
            BundleGrantTemplate(
                key="task-3-healthcare-receiver-endpoint",
                authority_profile="task-3-healthcare-authority",
                grantee_profile="task-3",
                authority_context="remote/government/healthcare-agent",
                public_name="government/healthcare-agent",
                permissions=("SHARE",),
                grantee_parent_context="local/personal-memory",
                recursive=False,
            ),
            BundleGrantTemplate(
                key="task-3-healthcare-transmission-guidance-view",
                authority_profile="task-3-healthcare-authority",
                grantee_profile="task-3",
                authority_context=(
                    "remote/government/healthcare-agent/info-request/transmission-guidance"
                ),
                public_name=(
                    "remote/government/healthcare-agent/info-request/transmission-guidance"
                ),
                permissions=("READ",),
                grantee_parent_context="local/personal-memory",
            ),
            BundleGrantTemplate(
                key="task-3-healthcare-questions-and-answers-query",
                authority_profile="task-3-healthcare-authority",
                grantee_profile="task-3",
                authority_context=(
                    "remote/government/healthcare-agent/info-request/questions-and-answers"
                ),
                public_name=(
                    "remote/government/healthcare-agent/info-request/questions-and-answers"
                ),
                permissions=("QUERY",),
                grantee_parent_context="local/personal-memory",
                provider="codex_chatgpt",
            ),
        ),
    ),
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_uid(*parts: str) -> str:
    return str(uuid.uuid5(_BUNDLE_NAMESPACE, "\0".join(parts)))


def _store_paths(root: Path) -> dict[str, Path]:
    return {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "STATE_FILE": root / "state.json",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether either resolved path contains the other.

    A bundle build replaces its destination as one directory.  Refusing both
    directions prevents a seemingly harmless export target from replacing the
    live store itself or one of its ancestors.
    """

    resolved_first = first.resolve(strict=False)
    resolved_second = second.resolve(strict=False)
    return (
        resolved_first == resolved_second
        or resolved_first.is_relative_to(resolved_second)
        or resolved_second.is_relative_to(resolved_first)
    )


def _prepare_atomic_destination(destination: Path) -> None:
    """Validate and vacate an optional empty destination directory."""

    # Test the directory entry before resolving it.  A symlink to an empty
    # directory must not become an apparently safe publish target.
    if destination.is_symlink():
        raise StudyBundleError(
            f"Study bundle destination {destination} must not be a symlink."
        )
    live_store = Path(store_module.STORE_DIR)
    if _paths_overlap(destination, live_store):
        raise StudyBundleError(
            f"Study bundle destination {destination} overlaps the active "
            f"store {live_store}."
        )
    if not destination.exists():
        return
    if not destination.is_dir():
        raise StudyBundleError(
            f"Study bundle destination {destination} is not a directory."
        )
    if any(destination.iterdir()):
        raise StudyBundleError(f"Study bundle destination {destination} is not empty.")
    # Removing an empty placeholder is lossless and lets the completed staging
    # directory become visible with one same-filesystem rename.
    destination.rmdir()


@contextmanager
def _atomic_output_directory(destination: Path) -> Iterator[Path]:
    """Build invisibly in a sibling and publish the whole tree at once."""

    destination = Path(destination)
    _prepare_atomic_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-",
            dir=destination.parent,
        )
    )
    published = False
    try:
        yield staging
        # Do not replace an entry that appeared while the package was built.
        # In particular, os.replace would otherwise replace a symlink on some
        # platforms even though initial validation rejected one.
        if destination.is_symlink() or destination.exists():
            raise StudyBundleError(
                f"Study bundle destination {destination} appeared during the build."
            )
        os.replace(staging, destination)
        published = True
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)


@contextmanager
def _isolated_store_root(root: Path) -> Iterator[None]:
    """Temporarily point store globals at one new package in this process.

    MemoryStore predates injectable roots. The builder runs synchronously and
    restores every module global even on failure; this narrow adapter avoids
    writing study data into the person's real `~/.mem` without changing all
    normal command paths.
    """

    prior = {name: getattr(store_module, name) for name in _STORE_PATH_NAMES}
    try:
        for name, value in _store_paths(root).items():
            setattr(store_module, name, value)
        yield
    finally:
        for name, value in prior.items():
            setattr(store_module, name, value)


def _load_pairs(
    dataset_name: str,
    fixture_root: Path,
) -> tuple[FixtureDataset, tuple[FixtureTranslationPair, ...]]:
    english = load_study_fixture(
        dataset_name,
        language="en",
        root=fixture_root,
    )
    korean = load_study_fixture(
        dataset_name,
        language="ko",
        root=fixture_root,
    )
    return english, pair_fixture_translations(english, korean)


def _runtime_locator(
    record: FixtureMemory,
    *,
    authoring_root: str,
    runtime_root: str,
    year_month_hierarchy: bool = False,
) -> str:
    locator = record.canonical_locator
    if locator == authoring_root:
        return runtime_root
    prefix = authoring_root + "/"
    if not locator.startswith(prefix):
        raise StudyBundleError(
            f"Fixture locator {locator!r} is outside {authoring_root!r}."
        )
    relative = locator[len(prefix) :]
    if year_month_hierarchy:
        bucket, separator, leaf = relative.partition("/")
        year, dash, month = bucket.partition("-")
        if (
            not separator
            or dash != "-"
            or len(year) != 4
            or not year.isdigit()
            or len(month) != 2
            or not month.isdigit()
            or not 1 <= int(month) <= 12
            or not leaf
        ):
            raise StudyBundleError(
                f"Fixture locator {locator!r} is not a YYYY-MM/leaf path."
            )
        # Keep the authoring locator as the stable fixture identity while the
        # runtime gains real year parents. This lets a topology-only change
        # preserve the Memory UIDs used by existing Study baselines.
        relative = f"{year}/{month}/{leaf}"
    return runtime_root + "/" + relative


def _ensure_context(
    contexts: dict[str, Context],
    name: str,
    *,
    task: int,
    identity_name: str | None = None,
) -> Context:
    expected_uid = _stable_uid(
        f"task-{task}",
        "context",
        identity_name or name,
    )
    context = contexts.get(name)
    if context is None:
        context = Context(
            uid=expected_uid,
            name=name,
        )
        contexts[name] = context
    elif context.uid != expected_uid:
        raise StudyBundleError(
            f"Runtime Context {name!r} received conflicting stable identities."
        )
    return context


def _ensure_hierarchy(
    contexts: dict[str, Context],
    owner_name: str,
    *,
    root_name: str,
    task: int,
    identity_names: dict[str, str] | None = None,
) -> Context:
    if owner_name != root_name and not owner_name.startswith(root_name + "/"):
        raise StudyBundleError(
            f"Runtime owner {owner_name!r} escapes root {root_name!r}."
        )
    relative = owner_name[len(root_name) :].lstrip("/")
    names = [root_name]
    if relative:
        parts = relative.split("/")
        names.extend(
            root_name + "/" + "/".join(parts[:index])
            for index in range(1, len(parts) + 1)
        )
    for name in names:
        _ensure_context(
            contexts,
            name,
            task=task,
            identity_name=(identity_names or {}).get(name),
        )
    for parent_name, child_name in zip(names, names[1:]):
        parent = contexts[parent_name]
        child = contexts[child_name]
        if child.uid not in parent.memories:
            parent.add(child)
    return contexts[owner_name]


def _ordinary_dataset(
    *,
    task_spec: BundleTaskSpec,
    profile_spec: BundleProfileSpec,
    dataset_spec: BundleDatasetSpec,
    dataset: FixtureDataset,
    pairs: tuple[FixtureTranslationPair, ...],
    contexts: dict[str, Context],
    korean_by_owner: dict[str, list[tuple[Memory, FixtureTranslationPair]]],
) -> list[BundleManifestEntry]:
    authoring_root = dataset.spec.context_name
    manifest: list[BundleManifestEntry] = []
    for pair in pairs:
        runtime_locator = _runtime_locator(
            pair.canonical,
            authoring_root=authoring_root,
            runtime_root=dataset_spec.runtime_root,
            year_month_hierarchy=dataset_spec.year_month_hierarchy,
        )
        if "/" not in runtime_locator:
            raise StudyBundleError(
                f"Memory locator {runtime_locator!r} has no owner Context."
            )
        owner_name = runtime_locator.rsplit("/", 1)[0]
        identity_names = None
        if dataset_spec.year_month_hierarchy:
            # The month Context moves under a new structural year parent, but
            # it remains the same reviewed fixture bucket and keeps its UID.
            authored_owner = pair.canonical.canonical_locator.rsplit("/", 1)[0]
            identity_names = {owner_name: authored_owner}
        owner = _ensure_hierarchy(
            contexts,
            owner_name,
            root_name=dataset_spec.runtime_root,
            task=task_spec.task,
            identity_names=identity_names,
        )
        memory = Memory(
            uid=_stable_uid(
                f"task-{task_spec.task}",
                # Moving a historical query-only fixture into an ordinary
                # authority Context must not assign its stable entry a new
                # identity merely because QUERY is now a grant/view mode.
                "query-entry" if dataset.spec.query_only else "memory",
                pair.uid_key,
            ),
            content=pair.canonical.content,
        )
        if memory.uid in owner.memories:
            raise StudyBundleError(
                f"Duplicate runtime Memory UID for {pair.uid_key!r}."
            )
        owner.add(memory)
        korean_by_owner.setdefault(owner_name, []).append((memory, pair))
        manifest.append(
            _manifest_entry(
                task_spec.task,
                profile_spec.name,
                dataset.spec.name,
                pair,
                runtime_context=owner_name,
                memory_uid=memory.uid,
                query_only=False,
            )
        )
    return manifest


def _manifest_entry(
    task: int,
    owner_profile: str,
    dataset: str,
    pair: FixtureTranslationPair,
    *,
    runtime_context: str | None,
    memory_uid: str,
    query_only: bool,
) -> BundleManifestEntry:
    return BundleManifestEntry(
        task=task,
        owner_profile=owner_profile,
        dataset=dataset,
        fixture_key=pair.canonical.identity_key,
        canonical_locator=pair.canonical.canonical_locator,
        runtime_context=runtime_context,
        memory_uid=memory_uid,
        query_only=query_only,
        purpose=pair.canonical.purpose,
        audiences=tuple(audience.value for audience in pair.canonical.audiences),
        verified=pair.canonical.verified,
        english_sha256=_digest(pair.canonical.content),
        korean_sha256=_digest(pair.translation.content),
        source_english=(
            f"{pair.canonical.source_path.parent.name}/"
            f"{pair.canonical.source_path.name}"
        ),
        source_korean=(
            f"{pair.translation.source_path.parent.name}/"
            f"{pair.translation.source_path.name}"
        ),
        translation_origin=TRANSLATION_ORIGIN_IMPORTED,
        translation_review_status=TRANSLATION_REVIEW_UNREVIEWED,
    )


def _save_contexts(
    store: MemoryStore,
    task_spec: BundleTaskSpec,
    profile_spec: BundleProfileSpec,
    contexts: dict[str, Context],
) -> None:
    entries = tuple(
        (
            context,
            AutoCheckpoint(
                command="fixture-import",
                args={
                    "schema_version": 2,
                    "task": task_spec.task,
                    "profile": profile_spec.name,
                    "context_uid": context.uid,
                    "memory_uids": [
                        item.uid
                        for item in context.iter_items()
                        if isinstance(item, Memory)
                    ],
                },
                description=(
                    f"Imported canonical English Task {task_spec.task} "
                    f"fixture Context '{context.name}' into profile "
                    f"'{profile_spec.name}'."
                ),
            ),
        )
        # Child-first creation makes a partially inspected package easier to
        # understand, although references do not require this ordering.
        for context in sorted(
            contexts.values(),
            key=lambda item: (-item.name.count("/"), item.name),
        )
    )
    store.create_missing_contexts(
        entries,
        make_current=profile_spec.current_context,
    )


def _save_korean_catalogs(
    store: MemoryStore,
    korean_by_owner: dict[str, list[tuple[Memory, FixtureTranslationPair]]],
) -> None:
    for owner_name, translations in korean_by_owner.items():
        owner = store.load_direct(owner_name)
        catalog = MemoryTranslationCatalog.empty(owner, "ko")
        required: dict[str, str] = {}
        for memory, pair in translations:
            evidence = hashlib.sha256(
                pair.translation.source_path.read_bytes()
            ).hexdigest()
            catalog = catalog.with_curated(
                owner,
                memory.uid,
                pair.translation.content,
                origin=TRANSLATION_ORIGIN_IMPORTED,
                review_status=TRANSLATION_REVIEW_UNREVIEWED,
                evidence_sha256=evidence,
            )
            required[memory.uid] = _digest(memory.content)
        save_translation_catalog(
            store,
            catalog,
            expected_record_digest=None,
            required_source_digests=required,
        )


def _remove_transient_lock_artifacts(store_root: Path) -> None:
    """Exclude process-coordination files from a portable fixture package."""
    graph_lock = store_root / "context-graph.lock"
    if graph_lock.is_symlink():
        raise StudyBundleError("Fixture Context graph lock path is unsafe.")
    if graph_lock.exists():
        if not graph_lock.is_file():
            raise StudyBundleError("Fixture Context graph lock path is invalid.")
        graph_lock.unlink()
    command_lock = store_root / "context-command-write.lock"
    if command_lock.is_symlink():
        raise StudyBundleError("Fixture command lock path is unsafe.")
    if command_lock.exists():
        if not command_lock.is_file():
            raise StudyBundleError("Fixture command lock path is invalid.")
        command_lock.unlink()
    state_lock = store_root / "state-write.lock"
    if state_lock.is_symlink():
        raise StudyBundleError("Fixture state lock path is unsafe.")
    if state_lock.exists():
        if not state_lock.is_file():
            raise StudyBundleError("Fixture state lock path is invalid.")
        state_lock.unlink()
    context_locks = store_root / "context-write-locks"
    if context_locks.is_symlink():
        raise StudyBundleError("Fixture Context lock directory is unsafe.")
    if not context_locks.exists():
        return
    if not context_locks.is_dir():
        raise StudyBundleError("Fixture Context lock directory is invalid.")
    for path in context_locks.iterdir():
        if path.is_symlink() or not path.is_file() or path.suffix != ".lock":
            raise StudyBundleError(
                "Fixture Context lock directory contains an unexpected entry."
            )
        path.unlink()
    context_locks.rmdir()


_GRANT_PERMISSIONS = GRANT_PERMISSIONS


def _profile_store_path(package: Path, profile_name: str) -> Path:
    return package / "profiles" / profile_name / ".mem"


def _build_profile_contents(
    task_spec: BundleTaskSpec,
    profile_spec: BundleProfileSpec,
    package: Path,
    *,
    fixture_root: Path,
) -> tuple[dict[str, object], tuple[BundleManifestEntry, ...], frozenset[str]]:
    """Build one owned store; grant views are installed only during import."""

    store_root = _profile_store_path(package, profile_spec.name)
    contexts: dict[str, Context] = {}
    korean_by_owner: dict[
        str,
        list[tuple[Memory, FixtureTranslationPair]],
    ] = {}
    manifest: list[BundleManifestEntry] = []
    for context_name in profile_spec.initial_contexts:
        _ensure_context(contexts, context_name, task=task_spec.task)

    with _isolated_store_root(store_root):
        store = MemoryStore()
        for dataset_spec in profile_spec.datasets:
            dataset, pairs = _load_pairs(dataset_spec.dataset, fixture_root)
            # A fixture's historical query_only flag describes the task-facing
            # interaction.  The authority profile owns the same records as
            # ordinary Contexts so its operator can inspect and maintain them.
            manifest.extend(
                _ordinary_dataset(
                    task_spec=task_spec,
                    profile_spec=profile_spec,
                    dataset_spec=dataset_spec,
                    dataset=dataset,
                    pairs=pairs,
                    contexts=contexts,
                    korean_by_owner=korean_by_owner,
                )
            )
        # Only real zero-Memory Contexts provide structural namespace rows.
        # Link any explicitly materialized direct parent after all datasets
        # are loaded; the picker itself never invents a missing prefix.
        for child_name in sorted(contexts, key=lambda name: (name.count("/"), name)):
            parent_name, separator, _leaf = child_name.rpartition("/")
            if not separator or parent_name not in contexts:
                continue
            parent = contexts[parent_name]
            child = contexts[child_name]
            if child.uid not in parent.memories:
                parent.add(child)
        if profile_spec.current_context not in contexts:
            raise StudyBundleError(
                f"Current Context {profile_spec.current_context!r} was not "
                f"built for profile {profile_spec.name!r}."
            )
        _save_contexts(store, task_spec, profile_spec, contexts)
        _save_korean_catalogs(store, korean_by_owner)

    # Lock files coordinate only the builder process. Shipping them would
    # imply stale ownership and add non-data artifacts to every profile.
    _remove_transient_lock_artifacts(store_root)
    entries = tuple(manifest)
    return (
        {
            "profile_name": profile_spec.name,
            "role": profile_spec.role,
            "store_path": (Path("profiles") / profile_spec.name / ".mem").as_posix(),
            "current_context": profile_spec.current_context,
            "context_count": len(contexts),
            "ordinary_count": len(entries),
            "datasets": [dataset.dataset for dataset in profile_spec.datasets],
            "entries": [asdict(entry) for entry in entries],
        },
        entries,
        frozenset(contexts),
    )


def _grant_uid(task: int, key: str) -> str:
    return _stable_uid(f"task-{task}", "grant", key)


def _context_manifest_identity(task: int, name: str) -> dict[str, str]:
    return {
        "uid": _stable_uid(f"task-{task}", "context", name),
        "name": name,
    }


def _grant_template_records(
    task_spec: BundleTaskSpec,
    contexts_by_profile: dict[str, frozenset[str]],
) -> list[dict[str, object]]:
    """Validate and serialize import-time authority-owned grant templates."""

    profile_names = {profile.name for profile in task_spec.profiles}
    templates_by_key = {
        template.key: template for template in task_spec.grant_templates
    }
    if len(templates_by_key) != len(task_spec.grant_templates):
        raise StudyBundleError("Study grant template keys must be unique.")

    result: list[dict[str, object]] = []
    for template in task_spec.grant_templates:
        if (
            template.authority_profile not in profile_names
            or template.grantee_profile not in profile_names
        ):
            raise StudyBundleError(
                f"Grant template {template.key!r} names an unknown profile."
            )
        authority_contexts = contexts_by_profile[template.authority_profile]
        if template.authority_context not in authority_contexts:
            raise StudyBundleError(
                f"Grant template {template.key!r} names a missing authority Context."
            )
        permissions = template.permissions
        if (
            not permissions
            or len(set(permissions)) != len(permissions)
            or any(permission not in _GRANT_PERMISSIONS for permission in permissions)
        ):
            raise StudyBundleError(
                f"Grant template {template.key!r} has invalid permissions."
            )
        if ("QUERY" in permissions) != (template.provider is not None):
            raise StudyBundleError(
                f"Grant template {template.key!r} has an invalid provider."
            )
        has_context_parent = template.grantee_parent_context is not None
        has_grant_parent = template.parent_grant_key is not None
        if has_context_parent == has_grant_parent:
            raise StudyBundleError(
                f"Grant template {template.key!r} must have exactly one parent."
            )
        if has_context_parent:
            assert template.grantee_parent_context is not None
            if (
                template.grantee_parent_context
                not in contexts_by_profile[template.grantee_profile]
            ):
                raise StudyBundleError(
                    f"Grant template {template.key!r} names a missing grantee "
                    "parent Context."
                )
            attachment: dict[str, object] = {
                "kind": "GRANTEE_CONTEXT",
                "context": _context_manifest_identity(
                    task_spec.task,
                    template.grantee_parent_context,
                ),
            }
        else:
            assert template.parent_grant_key is not None
            parent = templates_by_key.get(template.parent_grant_key)
            if parent is None or parent.grantee_profile != template.grantee_profile:
                raise StudyBundleError(
                    f"Grant template {template.key!r} has an invalid parent grant."
                )
            attachment = {
                "kind": "GRANT_VIEW",
                "grant_key": template.parent_grant_key,
                "grant_uid": _grant_uid(
                    task_spec.task,
                    template.parent_grant_key,
                ),
            }

        excluded: list[dict[str, str]] = []
        for name in template.excluded_contexts:
            if name not in authority_contexts or not name.startswith(
                template.authority_context + "/"
            ):
                raise StudyBundleError(
                    f"Grant template {template.key!r} has an invalid exclusion."
                )
            excluded.append(_context_manifest_identity(task_spec.task, name))

        record: dict[str, object] = {
            "schema_version": 1,
            "key": template.key,
            "grant_uid": _grant_uid(task_spec.task, template.key),
            # Import allocates local Profile UIDs first, then resolves these
            # package keys without trusting a mutable display lookup later.
            "authority_profile": template.authority_profile,
            "grantee_profile": template.grantee_profile,
            "authority_context": _context_manifest_identity(
                task_spec.task,
                template.authority_context,
            ),
            "attachment": attachment,
            "public_name": template.public_name,
            "permissions": list(permissions),
            "recursive": template.recursive,
            "excluded_contexts": excluded,
        }
        if template.provider is not None:
            record["provider"] = template.provider
        result.append(record)
    return result


def _query_view_count(
    entries: tuple[BundleManifestEntry, ...],
    templates: tuple[BundleGrantTemplate, ...],
) -> int:
    roots = tuple(
        (template.authority_profile, template.authority_context)
        for template in templates
        if "QUERY" in template.permissions
    )
    return sum(
        any(
            entry.owner_profile == profile
            and entry.runtime_context is not None
            and (
                entry.runtime_context == root
                or entry.runtime_context.startswith(root + "/")
            )
            for profile, root in roots
        )
        for entry in entries
    )


def _build_study_bundle_contents(
    task: int,
    package: Path,
    *,
    fixture_root: Path | None = None,
) -> Path:
    """Populate one private staging directory and return its manifest."""

    try:
        task_spec = TASK_SPECS[task]
    except KeyError as error:
        raise StudyBundleError(f"Unsupported study task {task!r}.") from error
    package = Path(package)
    if package.exists() and any(package.iterdir()):
        raise StudyBundleError(
            f"Study bundle staging directory {package} is not empty."
        )
    package.mkdir(parents=True, exist_ok=True)
    root = fixture_root or Path(__file__).resolve().parent / "data"
    profile_records: list[dict[str, object]] = []
    manifest: list[BundleManifestEntry] = []
    contexts_by_profile: dict[str, frozenset[str]] = {}
    for profile_spec in task_spec.profiles:
        profile_record, profile_entries, context_names = _build_profile_contents(
            task_spec,
            profile_spec,
            package,
            fixture_root=root,
        )
        profile_records.append(profile_record)
        manifest.extend(profile_entries)
        contexts_by_profile[profile_spec.name] = context_names
    all_entries = tuple(manifest)
    if len({entry.memory_uid for entry in all_entries}) != len(all_entries):
        raise StudyBundleError("Study profile stores contain duplicate Memory UIDs.")
    grant_templates = _grant_template_records(task_spec, contexts_by_profile)

    manifest_path = package / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "task": task,
                "canonical_language": "en",
                "translation_languages": ["ko"],
                "current_context": task_spec.current_context,
                "ordinary_count": len(all_entries),
                "query_only_count": 0,
                "query_view_count": _query_view_count(
                    all_entries,
                    task_spec.grant_templates,
                ),
                "profiles": profile_records,
                "grant_templates": grant_templates,
                # Keep a task-wide join surface for spreadsheet and hash tools;
                # owner_profile identifies the store containing each Memory.
                "entries": [asdict(entry) for entry in all_entries],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def build_study_bundle(
    task: int,
    destination: Path,
    *,
    fixture_root: Path | None = None,
) -> Path:
    """Atomically build one new package and return its manifest path."""

    package = Path(destination)
    # Validate unsupported tasks before touching even an empty destination.
    if task not in TASK_SPECS:
        raise StudyBundleError(f"Unsupported study task {task!r}.")
    with _atomic_output_directory(package) as staging:
        _build_study_bundle_contents(
            task,
            staging,
            fixture_root=fixture_root,
        )
    return package / "manifest.json"


def build_all_study_bundles(
    destination: Path,
    *,
    fixture_root: Path | None = None,
) -> tuple[Path, ...]:
    """Build three task packages, each with task and authority stores."""

    root = Path(destination)
    with _atomic_output_directory(root) as staging:
        for task in sorted(TASK_SPECS):
            _build_study_bundle_contents(
                task,
                staging / f"task-{task}",
                fixture_root=fixture_root,
            )
        (staging / "README.md").write_text(
            """# Isolated memcommit study profile packages

Each `task-N/` directory contains two complete stores below `profiles/`: the
participant task profile and its switchable task-specific authority profile.
The task manifest declares authority-owned grant templates that the importer
binds only after allocating both local Profile UIDs. Do not merge or copy
authority Contexts into the task store.

All fixture data, including material exposed through a QUERY grant, is stored
as ordinary authority-owned Contexts. English is canonical Memory content and
Korean is attached to the same Memory UID as an unreviewed imported
translation view. A task profile sees only the READ, CREATE, UPDATE, or QUERY
views declared in its grant templates. QUERY answers remain process-local and
are never retained by the study Profile.
Audience annotations remain review metadata and are not automatically
interpreted as ACL rules.

`mem init-study --scenario legacy` validates these packages inside a private
staging directory and directly publishes an isolated participant/authority
pair. No editable baseline Profile or separate import step is required, and
the packaged scenario sources are never edited in place.
""",
            encoding="utf-8",
        )
    return tuple(root / f"task-{task}" / "manifest.json" for task in sorted(TASK_SPECS))


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build isolated English+Korean memcommit study stores."
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--task",
        type=int,
        choices=sorted(TASK_SPECS),
        help="Build one task instead of all three.",
    )
    parser.add_argument("--fixture-root", type=Path)
    args = parser.parse_args()
    if args.task is None:
        manifests = build_all_study_bundles(
            args.destination,
            fixture_root=args.fixture_root,
        )
    else:
        manifests = (
            build_study_bundle(
                args.task,
                args.destination,
                fixture_root=args.fixture_root,
            ),
        )
    for manifest in manifests:
        print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
