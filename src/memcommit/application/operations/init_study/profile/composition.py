"""Compose validated Study inputs into one participant/authority run pair."""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path

from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    canonical_grant_permissions,
)
from memcommit.application.operations.profile.model._storage import (
    ProfileError,
    StoreInspection,
    _context_records,
    inspect_store,
)
from memcommit.application.operations.profile.model.study import _STUDY_TASKS
from memcommit.application.operations.translate.view import TranslationCatalog
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef

from .model import (
    _STUDY_BUNDLE_NAMESPACE,
    _StudyProfileSource,
    _StudyTaskPackage,
)
from .package import (
    _expected_study_grant_uid,
    _study_catalogs,
    _study_packages,
    _validate_study_package_grants,
)

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


def _snapshot_legacy_scenario(
    baseline_root: Path,
    task_records: dict[int, dict[str, object]],
    destination: Path,
) -> dict[int, _StudyTaskPackage]:
    root = Path(baseline_root)
    contexts, query_refs = _context_records(root)
    if query_refs:
        raise ProfileError(
            "Study baseline granted material must be editable ordinary Contexts."
        )
    structural = {
        *(f"task-{task}" for task in _STUDY_TASKS),
        _LEGACY_SCENARIO_GRANTED_ROOT,
        *(f"{_LEGACY_SCENARIO_GRANTED_ROOT}/task-{task}" for task in _STUDY_TASKS),
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
            branch = _legacy_scenario_branch(task, authority=authority)
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
            branch = _legacy_scenario_branch(task, authority=authority)
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


def _legacy_study_packages(
    destination: Path,
) -> tuple[dict[int, _StudyTaskPackage], str]:
    """Materialize the packaged Legacy fixture through the former baseline path.

    The intermediate store is deliberately process-local. It preserves the
    exact Practice normalization and Task/authority remapping that the removed
    editable baseline used to provide without publishing an installation
    prerequisite in the Profile registry.
    """

    from memcommit.study_scenarios.legacy import LEGACY_DIGEST
    from memcommit.study_scenarios.legacy.bundle import build_all_study_bundles

    bundle_root = destination / "bundles"
    build_all_study_bundles(bundle_root)
    source_packages = _study_packages(bundle_root)
    _validate_study_package_grants(source_packages)

    baseline_root = destination / "baseline"
    _compose_legacy_scenario_store(source_packages, baseline_root)

    task_records: dict[int, dict[str, object]] = {}
    for task, package in source_packages.items():
        task_source = next(
            source for source in package.profiles if source.role == "TASK"
        )
        authority_source = next(
            source for source in package.profiles if source.role == "AUTHORITY"
        )
        task_records[task] = {
            "manifest_sha256": package.manifest_digest,
            "canonical_language": package.manifest.get("canonical_language"),
            "task_profile_name": task_source.name,
            "authority_profile_name": authority_source.name,
            "task_current_context": task_source.inspection.current_context,
            "authority_current_context": authority_source.inspection.current_context,
            "grant_templates": list(package.grant_templates),
        }

    packages = _snapshot_legacy_scenario(
        baseline_root,
        task_records,
        destination / "snapshots",
    )
    # Translation-catalog audit timestamps are intentionally created at build
    # time, so a raw staging-tree digest would make identical scenario inputs
    # look different. Manifest digests cover the reviewed task and authority
    # data; the canonical Practice records cover the only added scenario data.
    scenario_material = json.dumps(
        {
            "schema_version": 1,
            "task_manifests": [
                packages[task].manifest_digest for task in sorted(packages)
            ],
            "practice_contexts": [
                context.to_dict() for context in _study_practice_contexts()
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    scenario_digest = hashlib.sha256(scenario_material).hexdigest()
    if scenario_digest != LEGACY_DIGEST:
        raise ProfileError(
            "Legacy scenario content changed without updating its reviewed digest."
        )
    return packages, scenario_digest


def _coffee_study_packages(destination: Path) -> dict[int, _StudyTaskPackage]:
    """Materialize fresh package sources for the built-in Coffee scenario.

    These sources are transient inputs to the same two-Profile publication
    boundary used by the legacy baseline.  Their Context names are already the
    public runtime names, so composing them must not add a second ``task-N``
    prefix.
    """

    from memcommit.study_scenarios.coffee import build_coffee_scenario

    scenario = build_coffee_scenario()
    packages: dict[int, _StudyTaskPackage] = {}
    for task_spec in scenario.tasks:
        task = task_spec.task
        participant_name = f"coffee-task-{task}-participant"
        authority_name = f"coffee-task-{task}-authority"
        sources: list[_StudyProfileSource] = []
        contexts_by_role: dict[str, dict[str, Context]] = {}
        for role, name, contexts, catalogs, current in (
            (
                "TASK",
                participant_name,
                task_spec.participant_contexts,
                task_spec.participant_catalogs,
                task_spec.participant_current,
            ),
            (
                "AUTHORITY",
                authority_name,
                task_spec.authority_contexts,
                task_spec.authority_catalogs,
                task_spec.authority_current,
            ),
        ):
            store_root = destination / name
            inspection = _write_mapped_study_store(
                store_root,
                contexts=contexts,
                catalogs=catalogs,
                current_context=current,
            )
            materialized, query_refs = _context_records(store_root)
            if query_refs:
                raise ProfileError(
                    "Built-in Study scenarios cannot contain query pointers."
                )
            contexts_by_role[role] = materialized
            sources.append(
                _StudyProfileSource(
                    task=task,
                    name=name,
                    role=role,
                    store=store_root,
                    entries=(),
                    inspection=inspection,
                )
            )

        templates: list[dict[str, object]] = []
        for grant in task_spec.grants:
            authority_context = contexts_by_role["AUTHORITY"][grant.authority_context]
            attachment_context = contexts_by_role["TASK"][grant.attachment_context]
            templates.append(
                {
                    "schema_version": 1,
                    "key": grant.key,
                    "grant_uid": _expected_study_grant_uid(task, grant.key),
                    "authority_profile": authority_name,
                    "grantee_profile": participant_name,
                    "authority_context": {
                        "uid": authority_context.uid,
                        "name": authority_context.name,
                    },
                    "attachment": {
                        "kind": "GRANTEE_CONTEXT",
                        "context": {
                            "uid": attachment_context.uid,
                            "name": attachment_context.name,
                        },
                    },
                    "public_name": grant.public_name,
                    "permissions": list(grant.permissions),
                    "recursive": grant.recursive,
                    "excluded_contexts": [],
                }
            )
        template_tuple = tuple(templates)
        packages[task] = _StudyTaskPackage(
            task=task,
            schema_version=2,
            manifest={
                "canonical_language": "en",
                # Legacy bundle Contexts are task-relative and need prefixing;
                # this scenario declares the final public hierarchy directly.
                "runtime_names_pre_namespaced": True,
                "scenario_id": scenario.scenario_id,
            },
            manifest_digest=scenario.digest,
            profiles=tuple(sources),
            grant_templates=template_tuple,
            query_view_count=_query_view_count_for_baseline(
                contexts_by_role["AUTHORITY"],
                template_tuple,
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
        pre_namespaced = package.manifest.get("runtime_names_pre_namespaced") is True
        for authority in (False, True):
            role = "AUTHORITY" if authority else "TASK"
            source = next(item for item in package.profiles if item.role == role)
            source_contexts, query_refs = _context_records(source.store)
            if query_refs:
                raise ProfileError("Study run sources cannot contain query pointers.")
            mapping = {
                name: (
                    name
                    if pre_namespaced
                    or (task == 1 and not authority and _is_study_practice_name(name))
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

    first_package = packages[1]
    first_pre_namespaced = (
        first_package.manifest.get("runtime_names_pre_namespaced") is True
    )
    first_participant_source = next(
        source for source in first_package.profiles if source.role == "TASK"
    )
    participant_inspection = _write_mapped_study_store(
        participant_root,
        contexts=tuple(participant_contexts),
        catalogs=tuple(participant_catalogs),
        # Start at the Practice parent so the participant deliberately opens
        # its description before proceeding. Task-specific Contexts stay
        # intact for later explicit navigation.
        current_context=(
            first_participant_source.inspection.current_context
            if first_pre_namespaced
            else _STUDY_PRACTICE_ROOT
        ),
    )
    authority_source = next(
        source for source in packages[1].profiles if source.role == "AUTHORITY"
    )
    authority_inspection = _write_mapped_study_store(
        authority_root,
        contexts=tuple(authority_contexts),
        catalogs=tuple(authority_catalogs),
        current_context=(
            authority_source.inspection.current_context
            if first_pre_namespaced
            else f"task-1/{authority_source.inspection.current_context}"
        ),
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
                    store=(
                        authority_root
                        if source.role == "AUTHORITY"
                        else participant_root
                    ),
                    inspection=inspection,
                )
            )
        templates = (
            tuple(copy.deepcopy(raw) for raw in package.grant_templates)
            if package.manifest.get("runtime_names_pre_namespaced") is True
            else tuple(
                _prefix_study_grant_template(raw, task=task)
                for raw in package.grant_templates
            )
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
