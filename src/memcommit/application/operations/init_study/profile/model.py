"""Fresh local data needed to construct an isolated Study Profile."""

from dataclasses import dataclass
import uuid

from memcommit.models.context import Context
from memcommit.core.memory_translation import MemoryTranslationCatalog

_STUDY_BUNDLE_NAMESPACE = uuid.UUID("50b72d54-cfbe-4f89-8f7f-1e6c785d8552")


@dataclass(frozen=True)
class StudyTaskData:
    task: int
    contexts: tuple[Context, ...]
    catalogs: tuple[MemoryTranslationCatalog, ...]
    current_context: str
