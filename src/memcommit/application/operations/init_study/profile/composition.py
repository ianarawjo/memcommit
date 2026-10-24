"""Build fresh local Memory-only Study inputs from packaged native documents."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    StoreInspection,
    inspect_store,
)
from memcommit.models.context import Context
from memcommit.core.memory_translation import MemoryTranslationCatalog
from memcommit.persistence.store.translation_catalog import (
    encode_translation_catalog_record,
)
from .model import StudyTaskData, _STUDY_BUNDLE_NAMESPACE


def _materialize_study_context_parents(
    contexts: tuple[Context, ...],
) -> tuple[Context, ...]:
    """Fill every missing lexical prefix with an empty ordinary Context.

    Study packages can legitimately predate a namespace root such as
    ``participant``.  Once several packages are composed below ``task-N``, a
    missing prefix would break ``mem switch ..`` and leave ``mem list`` without
    a materialized next-level Context row. The clean-store write boundary is shared by
    baseline bootstrap and live-baseline cloning, so completing the chain here
    preserves the invariant in the local Study Store.
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
    catalogs: tuple[MemoryTranslationCatalog, ...],
    current_context: str,
) -> StoreInspection:
    """Import one clean Study store without inherited operational history."""

    if destination.exists() or destination.is_symlink():
        raise ProfileError(f"Study store staging path is occupied: {destination}")
    contexts = _materialize_study_context_parents(contexts)
    names = {context.name for context in contexts}
    if current_context not in names:
        raise ProfileError("Study store current Context is missing from its branch.")
    uids = [context.uid for context in contexts]
    if len(uids) != len(set(uids)):
        raise ProfileError("Study store Context identities are duplicated.")

    from memcommit.persistence.store import MemoryStore, _write_json_atomic
    from memcommit.application.operations.mem_import.documents.publication import (
        import_context_records,
    )

    # Study allocates the isolated destination; resource import owns the same
    # native-data validation and require-new publication used by file imports.
    store = MemoryStore(root=destination)
    import_context_records(
        store, ((context, None) for context in contexts), make_current=current_context
    )

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
            _write_json_atomic(path, encode_translation_catalog_record(catalog))
    return inspect_store(destination)


def _legacy_study_packages(destination: Path):
    from memcommit.study_scenarios.legacy import LEGACY_DIGEST
    from memcommit.study_scenarios.legacy.practice import load_practice_contexts
    from memcommit.study_scenarios.native_tasks import load_native_task

    source = (
        Path(__file__).parents[4] / "study_scenarios" / "legacy" / "data" / "native"
    )
    tasks = {
        task: load_native_task(source / f"task-{task}", task=task) for task in (1, 2, 3)
    }
    first = tasks[1]
    tasks[1] = StudyTaskData(
        first.task,
        (*load_practice_contexts(), *first.contexts),
        first.catalogs,
        "practice",
    )
    return tasks, LEGACY_DIGEST


def _coffee_study_packages(destination: Path):
    from memcommit.study_scenarios.coffee import build_coffee_scenario

    return {
        task.task: StudyTaskData(
            task.task,
            task.contexts,
            task.catalogs,
            task.current_context,
        )
        for task in build_coffee_scenario().tasks
    }


def compose_local_study_store(packages, destination):
    contexts = tuple(
        context for task in sorted(packages) for context in packages[task].contexts
    )
    catalogs = tuple(
        catalog for task in sorted(packages) for catalog in packages[task].catalogs
    )
    return _write_mapped_study_store(
        destination,
        contexts=contexts,
        catalogs=catalogs,
        current_context=packages[1].current_context,
    )
