"""memcommit — a git-like memory store."""

from importlib import import_module

from memcommit.context import (
    Checkpoint,
    Context,
    Information,
    Memory,
    MemoryRef,
    QueryContextRef,
)
from memcommit.store import MemoryStore
from memcommit import ops


# Preserve the documented root imports without assembling the complete public
# client whenever an unrelated ``memcommit.*`` submodule is imported.
_LAZY_API_EXPORTS = {
    name: ("memcommit.api", name)
    for name in (
        "AddAuthorityError",
        "AddConflictError",
        "AddContextError",
        "AddError",
        "AddExecutionError",
        "AddInputError",
        "AddMemoriesResult",
        "AddStorageError",
        "AddedMemoryResult",
        "AtomizeGroundingApplyResult",
        "AtomizeGroundingConflictError",
        "AtomizeGroundingContextError",
        "AtomizeGroundingError",
        "AtomizeGroundingExecutionError",
        "AtomizeGroundingInputError",
        "AtomizeGroundingProposalResult",
        "AtomizeGroundingProviderFailure",
        "AtomizeGroundingQuestionResult",
        "AtomizeGroundingSessionResult",
        "AtomizeGroundingStorageError",
        "AtomizeAnalysisResult",
        "AtomizeAppliedItemResult",
        "AtomizeChildResult",
        "AtomizeConflictError",
        "AtomizeContextError",
        "AtomizeError",
        "AtomizeExecutionError",
        "AtomizeInputError",
        "AtomizeIssueResult",
        "AtomizeItemResult",
        "AtomizeOverviewResult",
        "AtomizeOverviewSectionResult",
        "AtomizeProviderFailure",
        "AtomizeReadingResult",
        "AtomizeReviewUpdateResult",
        "AtomizeReviewedApplyResult",
        "AtomizeSaveAsApplyResult",
        "AtomizeStorageError",
        "AtomizeStructuralApplyResult",
        "GrantedQueryResult",
        "MemCommitClient",
        "MemCommitError",
        "OrdinaryQueryResult",
        "QueryAuthorityError",
        "QueryCatalogEntry",
        "QueryCitation",
        "QueryConfigurationError",
        "QueryContextError",
        "QueryError",
        "QueryExecutionError",
        "QueryInputError",
        "QueryProviderConfig",
        "QueryProviderFailure",
        "QueryStorageError",
        "ReferenceQueryResult",
    )
}


def __getattr__(name: str):
    target = _LAZY_API_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

__all__ = [
    "AddAuthorityError",
    "AddConflictError",
    "AddContextError",
    "AddError",
    "AddExecutionError",
    "AddInputError",
    "AddMemoriesResult",
    "AddStorageError",
    "AddedMemoryResult",
    "AtomizeGroundingApplyResult",
    "AtomizeGroundingConflictError",
    "AtomizeGroundingContextError",
    "AtomizeGroundingError",
    "AtomizeGroundingExecutionError",
    "AtomizeGroundingInputError",
    "AtomizeGroundingProposalResult",
    "AtomizeGroundingProviderFailure",
    "AtomizeGroundingQuestionResult",
    "AtomizeGroundingSessionResult",
    "AtomizeGroundingStorageError",
    "AtomizeAnalysisResult",
    "AtomizeAppliedItemResult",
    "AtomizeChildResult",
    "AtomizeConflictError",
    "AtomizeContextError",
    "AtomizeError",
    "AtomizeExecutionError",
    "AtomizeInputError",
    "AtomizeIssueResult",
    "AtomizeItemResult",
    "AtomizeOverviewResult",
    "AtomizeOverviewSectionResult",
    "AtomizeProviderFailure",
    "AtomizeReadingResult",
    "AtomizeReviewUpdateResult",
    "AtomizeReviewedApplyResult",
    "AtomizeSaveAsApplyResult",
    "AtomizeStorageError",
    "AtomizeStructuralApplyResult",
    "Context",
    "Memory",
    "MemoryRef",
    "QueryContextRef",
    "Information",
    "Checkpoint",
    "MemoryStore",
    "GrantedQueryResult",
    "MemCommitClient",
    "MemCommitError",
    "OrdinaryQueryResult",
    "QueryAuthorityError",
    "QueryCatalogEntry",
    "QueryCitation",
    "QueryConfigurationError",
    "QueryContextError",
    "QueryError",
    "QueryExecutionError",
    "QueryInputError",
    "QueryProviderConfig",
    "QueryProviderFailure",
    "QueryStorageError",
    "ReferenceQueryResult",
    "ops",
]
