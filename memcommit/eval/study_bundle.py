"""Build isolated Task 1--3 `.mem` stores from paired fixture languages.

The authoring corpus is language-partitioned, but a runtime Memory has one
canonical English body.  Korean remains a same-UID translation catalog for
ordinary Contexts and a concealed language variant for query-only sources.
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

import memcommit.store as store_module
from memcommit.context import AutoCheckpoint, Context, Memory, QueryContextRef
from memcommit.eval.study_fixtures import (
    FixtureDataset,
    FixtureMemory,
    FixtureTranslationPair,
    load_study_fixture,
    pair_fixture_translations,
)
from memcommit.store import MemoryStore
from memcommit.translation_view import (
    TRANSLATION_ORIGIN_IMPORTED,
    TRANSLATION_REVIEW_UNREVIEWED,
    TranslationCatalog,
)
from memcommit.translation_view_store import save_translation_catalog


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
    "ATOMIZE_GROUNDING_SESSIONS_DIR",
    "ATOMIZE_GROUNDING_HISTORY_DIR",
    "GROUND_SESSIONS_DIR",
    "MELD_SESSIONS_DIR",
)


class StudyBundleError(RuntimeError):
    """A fixture package cannot be built without ambiguity or data loss."""


@dataclass(frozen=True)
class BundleDatasetSpec:
    dataset: str
    runtime_root: str
    query_parents: tuple[str, ...] = ()


@dataclass(frozen=True)
class BundleTaskSpec:
    task: int
    current_context: str
    datasets: tuple[BundleDatasetSpec, ...]


@dataclass(frozen=True)
class BundleManifestEntry:
    task: int
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
        current_context="participant/construction-updates",
        datasets=(
            BundleDatasetSpec(
                "task1-construction-updates",
                "participant/construction-updates",
            ),
            BundleDatasetSpec(
                "task1-campus-wiki",
                "campus-wiki",
            ),
            BundleDatasetSpec(
                "task1-campus-wiki-details",
                "construction-details",
                ("campus-wiki",),
            ),
        ),
    ),
    2: BundleTaskSpec(
        task=2,
        current_context="advisor1",
        datasets=(
            BundleDatasetSpec("task2-advisor1", "advisor1"),
            BundleDatasetSpec("task2-advisor2", "advisor2"),
            BundleDatasetSpec(
                "task2-proposal-guidelines",
                "proposal-submission-guidelines",
                ("advisor1", "advisor2"),
            ),
        ),
    ),
    3: BundleTaskSpec(
        task=3,
        current_context="personal-memory",
        datasets=(
            BundleDatasetSpec("task3-personal-memory", "personal-memory"),
            BundleDatasetSpec("task3-guardrails", "guardrails"),
            BundleDatasetSpec(
                "task3-healthcare-info-request",
                "government/healthcare-agent/information-request",
                ("personal-memory", "guardrails"),
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
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
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
        raise StudyBundleError(
            f"Study bundle destination {destination} is not empty."
        )
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
                f"Study bundle destination {destination} appeared during "
                "the build."
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
) -> str:
    locator = record.canonical_locator
    if locator == authoring_root:
        return runtime_root
    prefix = authoring_root + "/"
    if not locator.startswith(prefix):
        raise StudyBundleError(
            f"Fixture locator {locator!r} is outside {authoring_root!r}."
        )
    return runtime_root + "/" + locator[len(prefix) :]


def _ensure_context(
    contexts: dict[str, Context],
    name: str,
    *,
    task: int,
) -> Context:
    context = contexts.get(name)
    if context is None:
        context = Context(
            uid=_stable_uid(f"task-{task}", "context", name),
            name=name,
        )
        contexts[name] = context
    return context


def _ensure_hierarchy(
    contexts: dict[str, Context],
    owner_name: str,
    *,
    root_name: str,
    task: int,
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
        _ensure_context(contexts, name, task=task)
    for parent_name, child_name in zip(names, names[1:]):
        parent = contexts[parent_name]
        child = contexts[child_name]
        if child.uid not in parent.memories:
            parent.add(child)
    return contexts[owner_name]


def _ordinary_dataset(
    *,
    task_spec: BundleTaskSpec,
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
        )
        if "/" not in runtime_locator:
            raise StudyBundleError(
                f"Memory locator {runtime_locator!r} has no owner Context."
            )
        owner_name = runtime_locator.rsplit("/", 1)[0]
        owner = _ensure_hierarchy(
            contexts,
            owner_name,
            root_name=dataset_spec.runtime_root,
            task=task_spec.task,
        )
        memory = Memory(
            uid=_stable_uid(
                f"task-{task_spec.task}",
                "memory",
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
    dataset: str,
    pair: FixtureTranslationPair,
    *,
    runtime_context: str | None,
    memory_uid: str,
    query_only: bool,
) -> BundleManifestEntry:
    return BundleManifestEntry(
        task=task,
        dataset=dataset,
        fixture_key=pair.canonical.identity_key,
        canonical_locator=pair.canonical.canonical_locator,
        runtime_context=runtime_context,
        memory_uid=memory_uid,
        query_only=query_only,
        purpose=pair.canonical.purpose,
        audiences=tuple(
            audience.value for audience in pair.canonical.audiences
        ),
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


def _attach_query_dataset(
    *,
    store: MemoryStore,
    task_spec: BundleTaskSpec,
    dataset_spec: BundleDatasetSpec,
    dataset: FixtureDataset,
    pairs: tuple[FixtureTranslationPair, ...],
    contexts: dict[str, Context],
) -> list[BundleManifestEntry]:
    entries = []
    manifest = []
    for pair in pairs:
        entry_uid = _stable_uid(
            f"task-{task_spec.task}",
            "query-entry",
            pair.uid_key,
        )
        entries.append(
            {
                "uid": entry_uid,
                "key": pair.canonical.identity_key,
                "canonical_content": pair.canonical.content,
                "translations": {"ko": pair.translation.content},
            }
        )
        manifest.append(
            _manifest_entry(
                task_spec.task,
                dataset.spec.name,
                pair,
                runtime_context=None,
                memory_uid=entry_uid,
                query_only=True,
            )
        )
    source = store.create_bilingual_query_source(
        dataset_spec.runtime_root,
        entries,
    )
    for parent_name in dataset_spec.query_parents:
        parent = _ensure_context(contexts, parent_name, task=task_spec.task)
        ref = QueryContextRef(
            uid=_stable_uid(
                f"task-{task_spec.task}",
                "query-ref",
                parent_name,
                dataset_spec.runtime_root,
            ),
            name=dataset_spec.runtime_root,
            target_source_uid=source.uid,
            provider="codex_chatgpt",
        )
        parent.add(ref)
    return manifest


def _save_contexts(
    store: MemoryStore,
    task_spec: BundleTaskSpec,
    contexts: dict[str, Context],
) -> None:
    entries = tuple(
        (
            context,
            AutoCheckpoint(
                command="fixture-import",
                args={
                    "schema_version": 1,
                    "task": task_spec.task,
                    "context_uid": context.uid,
                    "memory_uids": [
                        item.uid
                        for item in context.iter_items()
                        if isinstance(item, Memory)
                    ],
                },
                description=(
                    f"Imported canonical English Task {task_spec.task} "
                    f"fixture Context '{context.name}'."
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
        make_current=task_spec.current_context,
    )


def _save_korean_catalogs(
    store: MemoryStore,
    korean_by_owner: dict[str, list[tuple[Memory, FixtureTranslationPair]]],
) -> None:
    for owner_name, translations in korean_by_owner.items():
        owner = store.load_direct(owner_name)
        catalog = TranslationCatalog.empty(owner, "ko")
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
            raise StudyBundleError(
                "Fixture Context graph lock path is invalid."
            )
        graph_lock.unlink()
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
    store_root = package / ".mem"
    if package.exists() and any(package.iterdir()):
        raise StudyBundleError(
            f"Study bundle staging directory {package} is not empty."
        )
    package.mkdir(parents=True, exist_ok=True)
    root = fixture_root or (
        Path(__file__).resolve().parents[2] / "docs" / "fixtures"
    )
    contexts: dict[str, Context] = {}
    korean_by_owner: dict[
        str,
        list[tuple[Memory, FixtureTranslationPair]],
    ] = {}
    manifest: list[BundleManifestEntry] = []

    with _isolated_store_root(store_root):
        store = MemoryStore()
        for dataset_spec in task_spec.datasets:
            dataset, pairs = _load_pairs(dataset_spec.dataset, root)
            if dataset.spec.query_only:
                manifest.extend(
                    _attach_query_dataset(
                        store=store,
                        task_spec=task_spec,
                        dataset_spec=dataset_spec,
                        dataset=dataset,
                        pairs=pairs,
                        contexts=contexts,
                    )
                )
            else:
                manifest.extend(
                    _ordinary_dataset(
                        task_spec=task_spec,
                        dataset_spec=dataset_spec,
                        dataset=dataset,
                        pairs=pairs,
                        contexts=contexts,
                        korean_by_owner=korean_by_owner,
                    )
                )
        if task_spec.current_context not in contexts:
            raise StudyBundleError(
                f"Current Context {task_spec.current_context!r} was not built."
            )
        _save_contexts(store, task_spec, contexts)
        _save_korean_catalogs(store, korean_by_owner)
    # Lock files coordinate only the builder process. Shipping them would
    # imply stale ownership and add non-data artifacts to every swap package.
    _remove_transient_lock_artifacts(store_root)

    manifest_path = package / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task": task,
                "canonical_language": "en",
                "translation_languages": ["ko"],
                "current_context": task_spec.current_context,
                "ordinary_count": sum(not entry.query_only for entry in manifest),
                "query_only_count": sum(entry.query_only for entry in manifest),
                "entries": [asdict(entry) for entry in manifest],
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
    """Build Task 1--3 as independent swappable `.mem` package roots."""

    root = Path(destination)
    with _atomic_output_directory(root) as staging:
        for task in sorted(TASK_SPECS):
            _build_study_bundle_contents(
                task,
                staging / f"task-{task}",
                fixture_root=fixture_root,
            )
        (staging / "README.md").write_text(
            """# Isolated memcommit study stores

Each `task-N/` directory is a complete, independent package whose `.mem/`
directory can be copied into one editable local profile. English is the
canonical Memory content. Korean is attached to the same Memory UID as an
unreviewed imported translation view. Query-only sources contain concealed
English and Korean variants and remain accessible only through `mem query`.

Do not merge these `.mem/` directories. Run `mem profile import-study` to
register editable copies, then use `mem profile use task-N` before navigating
that task with `mem switch`. The legacy `~/.mem` remains the `authoring`
profile and package sources are never edited in place. The package manifest
records fixture identity, runtime UID, source hashes, purpose, and the
translation review boundary; audience annotations are not ACL enforcement.
""",
            encoding="utf-8",
        )
    return tuple(
        root / f"task-{task}" / "manifest.json"
        for task in sorted(TASK_SPECS)
    )


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
