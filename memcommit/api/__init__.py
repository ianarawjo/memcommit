"""Stable public Python API for MemCommit.

The public names remain available from this module, but resolving one DTO or
client must not eagerly assemble every operation implementation.
"""

from importlib import import_module

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
    "GrantedQueryResult",
    "MemCommitClient",
    "MemCommitError",
    "MeldApplyResult",
    "MeldAuthorityError",
    "MeldConflictError",
    "MeldContextError",
    "MeldError",
    "MeldExecutionError",
    "MeldInputError",
    "MeldIssueResult",
    "MeldOptionResult",
    "MeldProposalResult",
    "MeldProviderFailure",
    "MeldSessionResult",
    "MeldStorageError",
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
    "QueryPublicationError",
    "QuerySessionReceipt",
    "QueryStorageError",
    "ReferenceQueryResult",
    "DistillApplyResult",
    "DistillProposal",
    "DistillRuleProposal",
    "ElaborateCaseProposal",
    "ElaborateProposal",
    "ElaborateRuleProposal",
    "FitJudgmentResult",
    "FitPropositionInput",
    "SemanticAuthorityError",
    "SemanticConflictError",
    "SemanticContextError",
    "SemanticError",
    "SemanticExecutionError",
    "SemanticInputError",
    "SemanticProviderFailure",
    "SemanticStorageError",
]


_LAZY_EXPORTS = {
    "AddMemoriesResult": ("memcommit.api.add", "AddMemoriesResult"),
    "AddedMemoryResult": ("memcommit.api.add", "AddedMemoryResult"),
    "AtomizeGroundingApplyResult": (
        "memcommit.api.atomize_grounding",
        "AtomizeGroundingApplyResult",
    ),
    "AtomizeGroundingProposalResult": (
        "memcommit.api.atomize_grounding",
        "AtomizeGroundingProposalResult",
    ),
    "AtomizeGroundingQuestionResult": (
        "memcommit.api.atomize_grounding",
        "AtomizeGroundingQuestionResult",
    ),
    "AtomizeGroundingSessionResult": (
        "memcommit.api.atomize_grounding",
        "AtomizeGroundingSessionResult",
    ),
    "MemCommitClient": ("memcommit.api.client", "MemCommitClient"),
    "MeldApplyResult": ("memcommit.api.meld", "MeldApplyResult"),
    "MeldIssueResult": ("memcommit.api.meld", "MeldIssueResult"),
    "MeldOptionResult": ("memcommit.api.meld", "MeldOptionResult"),
    "MeldProposalResult": ("memcommit.api.meld", "MeldProposalResult"),
    "MeldSessionResult": ("memcommit.api.meld", "MeldSessionResult"),
    "GrantedQueryResult": ("memcommit.api.query", "GrantedQueryResult"),
    "OrdinaryQueryResult": ("memcommit.api.query", "OrdinaryQueryResult"),
    "QueryCatalogEntry": ("memcommit.api.query", "QueryCatalogEntry"),
    "QueryCitation": ("memcommit.api.query", "QueryCitation"),
    "QueryProviderConfig": ("memcommit.api.query", "QueryProviderConfig"),
    "QuerySessionReceipt": ("memcommit.api.query", "QuerySessionReceipt"),
    "ReferenceQueryResult": ("memcommit.api.query", "ReferenceQueryResult"),
    "DistillApplyResult": ("memcommit.api.semantic", "DistillApplyResult"),
    "DistillProposal": ("memcommit.api.semantic", "DistillProposal"),
    "DistillRuleProposal": ("memcommit.api.semantic", "DistillRuleProposal"),
    "ElaborateCaseProposal": ("memcommit.api.semantic", "ElaborateCaseProposal"),
    "ElaborateProposal": ("memcommit.api.semantic", "ElaborateProposal"),
    "ElaborateRuleProposal": ("memcommit.api.semantic", "ElaborateRuleProposal"),
    "FitJudgmentResult": ("memcommit.api.semantic", "FitJudgmentResult"),
    "FitPropositionInput": ("memcommit.api.semantic", "FitPropositionInput"),
    **{
        name: ("memcommit.api.errors", name)
        for name in __all__
        if name.endswith("Error") or name.endswith("Failure")
    },
}


def __getattr__(name: str):
    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as error:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from error
    value = getattr(import_module(module_name), attribute_name)
    # Cache the real public object, not a proxy, so identity remains stable.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
