"""Compatibility exports for the former ``resource_import.model`` path.

New code imports the resource-owning modules under
``memcommit.application.operations.mem_import`` directly.
"""

from memcommit.application.operations.mem_import.context import (
    import_context_from_profile as import_context_from_profile,
    plan_context_import as plan_context_import,
)
from memcommit.application.operations.mem_import.contracts import (
    ContextImportPlan as ContextImportPlan,
    ContextImportResult as ContextImportResult,
    MemoryImportPlan as MemoryImportPlan,
    MemoryImportResult as MemoryImportResult,
)
from memcommit.application.operations.mem_import.memory import (
    import_memory_from_profile as import_memory_from_profile,
    plan_memory_import as plan_memory_import,
)
from memcommit.application.operations.mem_import.profile import (
    import_profile_from_profile as import_profile_from_profile,
)


__all__ = [
    "ContextImportPlan",
    "ContextImportResult",
    "MemoryImportPlan",
    "MemoryImportResult",
    "import_context_from_profile",
    "import_memory_from_profile",
    "import_profile_from_profile",
    "plan_context_import",
    "plan_memory_import",
]
