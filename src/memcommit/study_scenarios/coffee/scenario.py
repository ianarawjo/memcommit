"""The built-in continuous Coffee Study scenario.

English is the canonical durable Memory text.  Korean is retained as a
same-UID imported translation catalog so changing the display language never
creates a second occurrence or changes the scenario fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid
from pathlib import Path

from memcommit.application.operations.resource_import.documents.codec import (
    read_document,
)

from memcommit.core.context import Context, Memory
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TRANSLATION_ORIGIN_IMPORTED,
)


COFFEE_SCENARIO_ID = "coffee"
# Preserve the already-published deterministic identities while simplifying
# the public scenario name. The fixed UUID replaces the former versioned seed.
_SCENARIO_NAMESPACE = uuid.UUID("1cc6d666-a735-5e4b-9cf8-412bef7819a2")
COFFEE_BASELINE_UID = str(uuid.uuid5(_SCENARIO_NAMESPACE, "baseline"))
_CATALOG_TIMESTAMP = "2026-08-25T00:00:00+00:00"


@dataclass(frozen=True)
class BilingualMemorySpec:
    """One canonical English Memory and its same-UID Korean rendering."""

    purpose: str
    en: str
    ko: str


@dataclass(frozen=True)
class ContextSpec:
    """One ordinary Context declared by the Coffee scenario."""

    name: str
    memories: tuple[BilingualMemorySpec, ...] = ()


@dataclass(frozen=True)
class ScenarioGrantSpec:
    """One public authority view or delivery endpoint."""

    key: str
    authority_context: str
    attachment_context: str
    public_name: str
    permissions: tuple[str, ...]
    recursive: bool


@dataclass(frozen=True)
class StudyScenarioTask:
    """One Task's already-public participant and authority namespaces."""

    task: int
    participant_current: str
    authority_current: str
    participant_contexts: tuple[Context, ...]
    authority_contexts: tuple[Context, ...]
    participant_catalogs: tuple[MemoryTranslationCatalog, ...]
    authority_catalogs: tuple[MemoryTranslationCatalog, ...]
    grants: tuple[ScenarioGrantSpec, ...]


@dataclass(frozen=True)
class StudyScenario:
    """One complete immutable Study input topology."""

    scenario_id: str
    baseline_uid: str
    digest: str
    tasks: tuple[StudyScenarioTask, ...]


_DATA_ROOT = Path(__file__).resolve().parent / "data"


def _context_document(role: str, language: str, name: str) -> Context:
    task, owner = role.split(":")
    validate_portable_context_name(name)
    document = read_document(
        _DATA_ROOT / task / owner / language / name / "context.json"
    )
    if not isinstance(document.value, Context) or document.value.name != name:
        raise ValueError("Coffee Context document differs from its declared placement.")
    return document.value


def _context_specs(role: str, records: list[dict]) -> tuple[ContextSpec, ...]:
    specs = []
    for record in records:
        en = _context_document(role, "en", record["name"])
        ko = _context_document(role, "ko", record["name"])
        if en.uid != ko.uid or en.order != ko.order:
            raise ValueError(
                "Coffee translation identities differ from canonical data."
            )
        english = tuple(en.iter_items())
        korean = tuple(ko.iter_items())
        if any(not isinstance(item, Memory) for item in (*english, *korean)):
            raise ValueError("Coffee authoring documents must contain owned Memories.")
        specs.append(
            ContextSpec(
                en.name,
                tuple(
                    BilingualMemorySpec(purpose, source.content, translated.content)
                    for purpose, source, translated in zip(
                        record["purposes"], english, korean, strict=True
                    )
                ),
            )
        )
    return tuple(specs)


def _task_context_specs():
    data = json.loads((_DATA_ROOT / "composition.json").read_text(encoding="utf-8"))
    return {
        task: (
            _context_specs(f"task-{task}:participant", data[str(task)]["participant"]),
            _context_specs(f"task-{task}:authority", data[str(task)]["authority"]),
            tuple(
                ScenarioGrantSpec(
                    **{**grant, "permissions": tuple(grant["permissions"])}
                )
                for grant in data[str(task)]["grants"]
            ),
        )
        for task in (1, 2, 3)
    }


_TASK_CONTEXT_SPECS = _task_context_specs()


def _stable_uid(kind: str, *parts: object) -> str:
    return str(
        uuid.uuid5(
            _SCENARIO_NAMESPACE,
            "\0".join((kind, *(str(part) for part in parts))),
        )
    )


def _build_contexts(
    role: str,
    specs: tuple[ContextSpec, ...],
) -> tuple[tuple[Context, ...], tuple[MemoryTranslationCatalog, ...]]:
    contexts: list[Context] = []
    catalogs: list[MemoryTranslationCatalog] = []
    for spec in specs:
        context = _context_document(role, "en", spec.name)
        if context.uid != _stable_uid("context", role, spec.name):
            raise ValueError("Coffee Context identity changed.")
        translations: list[tuple[Memory, BilingualMemorySpec]] = []
        for index, (memory, memory_spec) in enumerate(
            zip(context.iter_items(), spec.memories, strict=True), start=1
        ):
            if (
                not isinstance(memory, Memory)
                or memory.uid
                != _stable_uid(
                    "memory",
                    role,
                    spec.name,
                    index,
                    memory_spec.purpose,
                )
                or memory.content != memory_spec.en
            ):
                raise ValueError(
                    "Coffee Memory identity or content changed after loading."
                )
            translations.append((memory, memory_spec))
        contexts.append(context)
        if translations:
            catalog = MemoryTranslationCatalog.empty(
                context,
                "ko",
                created_at=_CATALOG_TIMESTAMP,
            )
            for memory, memory_spec in translations:
                evidence = hashlib.sha256(
                    (memory_spec.en + "\0" + memory_spec.ko).encode("utf-8")
                ).hexdigest()
                catalog = catalog.with_curated(
                    context,
                    memory.uid,
                    memory_spec.ko,
                    origin=TRANSLATION_ORIGIN_IMPORTED,
                    evidence_sha256=evidence,
                    updated_at=_CATALOG_TIMESTAMP,
                )
            catalogs.append(catalog)
    return tuple(contexts), tuple(catalogs)


def _scenario_digest() -> str:
    payload: dict[str, object] = {
        "scenario_id": COFFEE_SCENARIO_ID,
        "canonical_language": "en",
        "translation_languages": ["ko"],
        "tasks": [],
    }
    raw_tasks = payload["tasks"]
    assert isinstance(raw_tasks, list)
    for task in (1, 2, 3):
        participant_specs, authority_specs, grants = _TASK_CONTEXT_SPECS[task]
        raw_tasks.append(
            {
                "task": task,
                "participant": [
                    {
                        "name": spec.name,
                        "memories": [
                            {
                                "purpose": item.purpose,
                                "en": item.en,
                                "ko": item.ko,
                            }
                            for item in spec.memories
                        ],
                    }
                    for spec in participant_specs
                ],
                "authority": [
                    {
                        "name": spec.name,
                        "memories": [
                            {
                                "purpose": item.purpose,
                                "en": item.en,
                                "ko": item.ko,
                            }
                            for item in spec.memories
                        ],
                    }
                    for spec in authority_specs
                ],
                "grants": [grant.__dict__ for grant in grants],
            }
        )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


COFFEE_DIGEST = "d00cdd0c419c20a7295d57338ba608130074afc3c67a03e23bbf5fea9f213589"
if _scenario_digest() != COFFEE_DIGEST:
    # The concise public name still identifies one pinned experiment. A data
    # change must deliberately refresh the recorded digest.
    raise RuntimeError("coffee data changed without updating its pinned digest.")


def build_coffee_scenario() -> StudyScenario:
    """Return fresh mutable Context objects for one Coffee Study run."""

    tasks: list[StudyScenarioTask] = []
    for task in (1, 2, 3):
        participant_specs, authority_specs, grants = _TASK_CONTEXT_SPECS[task]
        participant_contexts, participant_catalogs = _build_contexts(
            f"task-{task}:participant",
            participant_specs,
        )
        authority_contexts, authority_catalogs = _build_contexts(
            f"task-{task}:authority",
            authority_specs,
        )
        tasks.append(
            StudyScenarioTask(
                task=task,
                participant_current=("practice" if task == 1 else f"task-{task}"),
                authority_current=authority_specs[0].name,
                participant_contexts=participant_contexts,
                authority_contexts=authority_contexts,
                participant_catalogs=participant_catalogs,
                authority_catalogs=authority_catalogs,
                grants=grants,
            )
        )
    return StudyScenario(
        scenario_id=COFFEE_SCENARIO_ID,
        baseline_uid=COFFEE_BASELINE_UID,
        digest=COFFEE_DIGEST,
        tasks=tuple(tasks),
    )
