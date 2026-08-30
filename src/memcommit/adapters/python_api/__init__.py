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
    "EmbeddedContextResult",
    "EmbeddedMemoryResult",
    "EmbedPlacementResult",
    "EmbedAuthorityError",
    "EmbedConflictError",
    "EmbedContextError",
    "EmbedError",
    "EmbedExecutionError",
    "EmbedInputError",
    "EmbedStorageError",
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
    "AtomizePlanUpdateResult",
    "AtomizeSaveAsApplyResult",
    "AtomizeStorageError",
    "AtomizeStructuralApplyResult",
    "CompareAuthorityError",
    "CompareConflictError",
    "CompareContextError",
    "CompareError",
    "CompareExecutionError",
    "CompareInputError",
    "CompareProviderFailure",
    "CompareStorageError",
    "ComparisonFrameResult",
    "ComparisonIssueResult",
    "ComparisonMemberResult",
    "ComparisonOptionResult",
    "ComparisonRelationResult",
    "ComparisonReportsResult",
    "ComparisonResult",
    "CopyMemoriesReceipt",
    "DedupApplyResult",
    "DedupComponentResult",
    "DedupEvidenceResult",
    "DedupMemberResult",
    "DedupPlanResult",
    "ContextDeletePlanResult",
    "ContextDeleteReceipt",
    "ContextDeleteStatus",
    "DeletedDirectItemResult",
    "DeletedItemKind",
    "DirectItemDeleteReceipt",
    "DeleteAuthorityError",
    "DeleteConflictError",
    "DeleteContextError",
    "DeleteError",
    "DeleteExecutionError",
    "DeleteInputError",
    "DeleteStorageError",
    "DedunApplyResult",
    "DedunComponentResult",
    "DedunEvidenceResult",
    "DedunMemberResult",
    "DedunPlanResult",
    "ExactDedupGroupResult",
    "ExactDedupContextResult",
    "ExactDedupResult",
    "ExactDuplicateContextResult",
    "ExactDuplicateFindResult",
    "GrantedQueryResult",
    "HelpCatalogResult",
    "HelpComparisonOptionResult",
    "HelpComparisonResult",
    "HelpDetailCatalogResult",
    "HelpDetailReferenceResult",
    "HelpDetailResult",
    "HelpTextDetailResult",
    "HelpError",
    "HelpInputError",
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
    "MemoryTransferAuthorityError",
    "MemoryTransferCheckpointResult",
    "MemoryTransferConflictError",
    "MemoryTransferContextError",
    "MemoryTransferError",
    "MemoryTransferExecutionError",
    "MemoryTransferInputError",
    "MemoryTransferItemResult",
    "MemoryTransferPlacementResult",
    "MemoryTransferStorageError",
    "MoveLinkPolicyResult",
    "MoveMemoriesReceipt",
    "MemoryReferenceResult",
    "ContextReferenceResult",
    "OrdinaryQueryResult",
    "OperationHelpResult",
    "QueryAuthorityError",
    "QueryCitation",
    "QueryConfigurationError",
    "QueryContextError",
    "QueryError",
    "QueryExecutionError",
    "QueryInputError",
    "QueryProviderConfig",
    "QueryProviderFailure",
    "QueryStorageError",
    "QualityFindContextResult",
    "QualityFindResult",
    "QualityFindingHandoff",
    "QualityFindingReviewDraft",
    "QualityFindingSource",
    "ReferenceQueryResult",
    "ReferenceAuthorityError",
    "ReferenceConflictError",
    "ReferenceContextError",
    "ReferenceError",
    "ReferenceExecutionError",
    "ReferenceInputError",
    "ReferenceStorageError",
    "ReplaceApplyReceipt",
    "ReplaceAuthorityError",
    "ReplaceCheckpointResult",
    "ReplaceConflictError",
    "ReplaceContextError",
    "ReplaceContextPlanResult",
    "ReplaceError",
    "ReplaceExecutionError",
    "ReplaceInputError",
    "ReplaceMemoryPlanResult",
    "ReplacePlanResult",
    "ReplaceSpanResult",
    "ReplaceStorageError",
    "ResolveAnalysisResult",
    "ResolveApplyResult",
    "ResolveCandidateResult",
    "ResolveEffectResult",
    "ResolveIssueResult",
    "SearchItemResult",
    "SearchResult",
    "DistillApplyResult",
    "DistillProposal",
    "DistillRuleProposal",
    "ElaborateCaseProposal",
    "ElaborateCaseValidationProposal",
    "ElaborateProposal",
    "ElaborateRuleCheckProposal",
    "ElaborateRuleProposal",
    "ElaborateTargetContextItemProposal",
    "FitJudgmentResult",
    "FitPropositionInput",
    "ForgetApplyResult",
    "ForgetAuthorityError",
    "ForgetCandidateResult",
    "ForgetConflictError",
    "ForgetContextError",
    "ForgetError",
    "ForgetExecutionError",
    "ForgetInputError",
    "ForgetProviderFailure",
    "ForgetReviewResult",
    "ForgetStorageError",
    "FindAuthorityError",
    "FindContextError",
    "FindError",
    "FindExecutionError",
    "FindInputError",
    "FindMatchResult",
    "FindResult",
    "FindSpanResult",
    "FindStorageError",
    "SemanticAuthorityError",
    "SemanticConflictError",
    "SemanticContextError",
    "SemanticError",
    "SemanticExecutionError",
    "SemanticInputError",
    "SemanticProviderFailure",
    "SemanticStorageError",
    "ShowAuthorityError",
    "ShowContextError",
    "ShowContextResult",
    "ShowDirectItemResult",
    "ShowEmbeddedContextResult",
    "ShowError",
    "ShowExecutionError",
    "ShowInputError",
    "ShowMemoryReferenceResult",
    "ShowMemoryResult",
    "ShowQueryViewResult",
    "ShowResult",
    "ShowSourceResult",
    "ShowStorageError",
]


_LAZY_EXPORTS = {
    "AddMemoriesResult": ("memcommit.adapters.python_api.add", "AddMemoriesResult"),
    "AddedMemoryResult": ("memcommit.adapters.python_api.add", "AddedMemoryResult"),
    "EmbeddedContextResult": (
        "memcommit.adapters.python_api.embed",
        "EmbeddedContextResult",
    ),
    "EmbeddedMemoryResult": (
        "memcommit.adapters.python_api.embed",
        "EmbeddedMemoryResult",
    ),
    "EmbedPlacementResult": (
        "memcommit.adapters.python_api.embed",
        "EmbedPlacementResult",
    ),
    "MemoryReferenceResult": (
        "memcommit.adapters.python_api.reference",
        "MemoryReferenceResult",
    ),
    "ContextReferenceResult": (
        "memcommit.adapters.python_api.reference",
        "ContextReferenceResult",
    ),
    **{
        name: ("memcommit.adapters.python_api.memory_transfer", name)
        for name in (
            "CopyMemoriesReceipt",
            "MemoryTransferCheckpointResult",
            "MemoryTransferItemResult",
            "MemoryTransferPlacementResult",
            "MoveLinkPolicyResult",
            "MoveMemoriesReceipt",
        )
    },
    **{
        name: ("memcommit.adapters.python_api.atomize", name)
        for name in (
            "AtomizeAnalysisResult",
            "AtomizeAppliedItemResult",
            "AtomizeChildResult",
            "AtomizeIssueResult",
            "AtomizeItemResult",
            "AtomizeOverviewResult",
            "AtomizeOverviewSectionResult",
            "AtomizeReadingResult",
            "AtomizePlanUpdateResult",
            "AtomizeSaveAsApplyResult",
            "AtomizeStructuralApplyResult",
        )
    },
    "MemCommitClient": ("memcommit.adapters.python_api.client", "MemCommitClient"),
    "HelpCatalogResult": ("memcommit.adapters.python_api.help", "HelpCatalogResult"),
    "HelpComparisonOptionResult": (
        "memcommit.adapters.python_api.help",
        "HelpComparisonOptionResult",
    ),
    "HelpComparisonResult": (
        "memcommit.adapters.python_api.help",
        "HelpComparisonResult",
    ),
    "HelpDetailCatalogResult": (
        "memcommit.adapters.python_api.help",
        "HelpDetailCatalogResult",
    ),
    "HelpDetailReferenceResult": (
        "memcommit.adapters.python_api.help",
        "HelpDetailReferenceResult",
    ),
    "HelpDetailResult": ("memcommit.adapters.python_api.help", "HelpDetailResult"),
    "HelpTextDetailResult": (
        "memcommit.adapters.python_api.help",
        "HelpTextDetailResult",
    ),
    "OperationHelpResult": (
        "memcommit.adapters.python_api.help",
        "OperationHelpResult",
    ),
    **{
        name: ("memcommit.adapters.python_api.show", name)
        for name in (
            "ShowContextResult",
            "ShowDirectItemResult",
            "ShowEmbeddedContextResult",
            "ShowMemoryReferenceResult",
            "ShowMemoryResult",
            "ShowQueryViewResult",
            "ShowResult",
            "ShowSourceResult",
        )
    },
    **{
        f"Comparison{name}": (
            "memcommit.adapters.python_api.compare",
            f"Comparison{name}",
        )
        for name in (
            "FrameResult",
            "IssueResult",
            "MemberResult",
            "OptionResult",
            "RelationResult",
            "ReportsResult",
            "Result",
        )
    },
    "MeldApplyResult": ("memcommit.adapters.python_api.meld", "MeldApplyResult"),
    "MeldIssueResult": ("memcommit.adapters.python_api.meld", "MeldIssueResult"),
    "MeldOptionResult": ("memcommit.adapters.python_api.meld", "MeldOptionResult"),
    "MeldProposalResult": ("memcommit.adapters.python_api.meld", "MeldProposalResult"),
    "MeldSessionResult": ("memcommit.adapters.python_api.meld", "MeldSessionResult"),
    **{
        name: ("memcommit.adapters.python_api.dedun", name)
        for name in (
            "DedupApplyResult",
            "DedupComponentResult",
            "DedupEvidenceResult",
            "DedupMemberResult",
            "DedupPlanResult",
            "DedunApplyResult",
            "DedunComponentResult",
            "DedunEvidenceResult",
            "DedunMemberResult",
            "DedunPlanResult",
        )
    },
    **{
        name: ("memcommit.adapters.python_api.dedup", name)
        for name in (
            "ExactDedupGroupResult",
            "ExactDedupContextResult",
            "ExactDedupResult",
            "ExactDuplicateContextResult",
            "ExactDuplicateFindResult",
        )
    },
    "GrantedQueryResult": ("memcommit.adapters.python_api.query", "GrantedQueryResult"),
    "OrdinaryQueryResult": (
        "memcommit.adapters.python_api.query",
        "OrdinaryQueryResult",
    ),
    "QueryCitation": ("memcommit.adapters.python_api.query", "QueryCitation"),
    "QueryProviderConfig": (
        "memcommit.adapters.python_api.query",
        "QueryProviderConfig",
    ),
    "ReferenceQueryResult": (
        "memcommit.adapters.python_api.query",
        "ReferenceQueryResult",
    ),
    **{
        name: ("memcommit.adapters.python_api.replace", name)
        for name in (
            "ReplaceApplyReceipt",
            "ReplaceCheckpointResult",
            "ReplaceContextPlanResult",
            "ReplaceMemoryPlanResult",
            "ReplacePlanResult",
            "ReplaceSpanResult",
        )
    },
    **{
        name: ("memcommit.adapters.python_api.delete", name)
        for name in (
            "ContextDeletePlanResult",
            "ContextDeleteReceipt",
            "ContextDeleteStatus",
            "DeletedDirectItemResult",
            "DeletedItemKind",
            "DirectItemDeleteReceipt",
        )
    },
    "FindMatchResult": ("memcommit.adapters.python_api.find", "FindMatchResult"),
    "FindResult": ("memcommit.adapters.python_api.find", "FindResult"),
    "FindSpanResult": ("memcommit.adapters.python_api.find", "FindSpanResult"),
    "SearchItemResult": ("memcommit.adapters.python_api.search", "SearchItemResult"),
    "SearchResult": ("memcommit.adapters.python_api.search", "SearchResult"),
    **{
        name: ("memcommit.adapters.python_api.quality_find", name)
        for name in ("QualityFindContextResult", "QualityFindResult")
    },
    **{
        name: (
            "memcommit.application.capabilities.memory_issue_analysis.handoff",
            name,
        )
        for name in (
            "QualityFindingHandoff",
            "QualityFindingReviewDraft",
            "QualityFindingSource",
        )
    },
    "ResolveAnalysisResult": (
        "memcommit.adapters.python_api.resolve",
        "ResolveAnalysisResult",
    ),
    "ResolveApplyResult": (
        "memcommit.adapters.python_api.resolve",
        "ResolveApplyResult",
    ),
    "ResolveCandidateResult": (
        "memcommit.adapters.python_api.resolve",
        "ResolveCandidateResult",
    ),
    "ResolveEffectResult": (
        "memcommit.adapters.python_api.resolve",
        "ResolveEffectResult",
    ),
    "ResolveIssueResult": (
        "memcommit.adapters.python_api.resolve",
        "ResolveIssueResult",
    ),
    "DistillApplyResult": (
        "memcommit.adapters.python_api.semantic",
        "DistillApplyResult",
    ),
    "DistillProposal": ("memcommit.adapters.python_api.semantic", "DistillProposal"),
    "DistillRuleProposal": (
        "memcommit.adapters.python_api.semantic",
        "DistillRuleProposal",
    ),
    "ElaborateCaseProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateCaseProposal",
    ),
    "ElaborateCaseValidationProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateCaseValidationProposal",
    ),
    "ElaborateProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateProposal",
    ),
    "ElaborateRuleCheckProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateRuleCheckProposal",
    ),
    "ElaborateRuleProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateRuleProposal",
    ),
    "ElaborateTargetContextItemProposal": (
        "memcommit.adapters.python_api.semantic",
        "ElaborateTargetContextItemProposal",
    ),
    "FitJudgmentResult": (
        "memcommit.adapters.python_api.semantic",
        "FitJudgmentResult",
    ),
    "FitPropositionInput": (
        "memcommit.adapters.python_api.semantic",
        "FitPropositionInput",
    ),
    "ForgetApplyResult": ("memcommit.adapters.python_api.forget", "ForgetApplyResult"),
    "ForgetCandidateResult": (
        "memcommit.adapters.python_api.forget",
        "ForgetCandidateResult",
    ),
    "ForgetReviewResult": (
        "memcommit.adapters.python_api.forget",
        "ForgetReviewResult",
    ),
    **{
        name: ("memcommit.adapters.python_api.errors", name)
        for name in __all__
        if name.endswith("Error") or name.endswith("Failure")
    },
}


def __getattr__(name: str):
    try:
        module_name, attribute_name = _LAZY_EXPORTS[name]
    except KeyError as error:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from error
    value = getattr(import_module(module_name), attribute_name)
    # Cache the real public object, not a proxy, so identity remains stable.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
