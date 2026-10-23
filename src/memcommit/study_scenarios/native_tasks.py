"""Read paired native task documents as independent local Contexts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from memcommit.application.operations.init_study.profile.model import StudyTaskData
from memcommit.application.operations.mem_import.documents.codec import read_document
from memcommit.models.context import Context
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TRANSLATION_ORIGIN_IMPORTED,
)


def load_native_task(source: Path, *, task: int) -> StudyTaskData:
    contexts = []
    catalogs = []
    for path in sorted(source.glob("*/en/**/context.json")):
        english = read_document(path).value
        korean = read_document(Path(str(path).replace("/en/", "/ko/"))).value
        if not isinstance(english, Context) or not isinstance(korean, Context):
            raise ValueError("Study input must contain native Context documents.")
        if english.uid != korean.uid or english.order != korean.order:
            raise ValueError(
                "Study translations must preserve Memory identities and order."
            )
        # Public hierarchy is lexical; no Context is inserted into another Context.
        english.name = f"task-{task}/{english.name}"
        contexts.append(english)
        if english.memories:
            catalog = MemoryTranslationCatalog.empty(
                english, "ko", created_at="2026-10-22T00:00:00+00:00"
            )
            for memory in english.iter_memories():
                translated = korean.memories[memory.uid].content
                catalog = catalog.with_curated(
                    english,
                    memory.uid,
                    translated,
                    origin=TRANSLATION_ORIGIN_IMPORTED,
                    evidence_sha256=hashlib.sha256(
                        (memory.content + "\0" + translated).encode()
                    ).hexdigest(),
                    updated_at="2026-10-22T00:00:00+00:00",
                )
            catalogs.append(catalog)
    return StudyTaskData(task, tuple(contexts), tuple(catalogs), f"task-{task}")
