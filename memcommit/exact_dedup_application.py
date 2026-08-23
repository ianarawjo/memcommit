"""Public application surface for provider-free exact Dedup."""

from memcommit.exact_dedup import (
    EXACT_DEDUP_CONTRACT_VERSION,
    ExactDedupError,
    ExactDedupReceipt,
    ExactDedupScopeReceipt,
    ExactDuplicateContextReport,
    ExactDuplicateGroup,
    ExactDuplicateKind,
    ExactDuplicateScopeReport,
    apply_exact_dedup,
    apply_exact_dedup_scope,
    find_exact_duplicate_scope,
    find_exact_duplicate_groups,
)


__all__ = [
    "EXACT_DEDUP_CONTRACT_VERSION",
    "ExactDedupError",
    "ExactDedupReceipt",
    "ExactDedupScopeReceipt",
    "ExactDuplicateContextReport",
    "ExactDuplicateGroup",
    "ExactDuplicateKind",
    "ExactDuplicateScopeReport",
    "apply_exact_dedup",
    "apply_exact_dedup_scope",
    "find_exact_duplicate_scope",
    "find_exact_duplicate_groups",
]
