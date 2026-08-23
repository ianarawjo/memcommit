"""Public application surface for provider-free exact Dedup."""

from memcommit.exact_dedup import (
    EXACT_DEDUP_CONTRACT_VERSION,
    ExactDedupError,
    ExactDedupReceipt,
    ExactDuplicateGroup,
    ExactDuplicateKind,
    apply_exact_dedup,
    find_exact_duplicate_groups,
)


__all__ = [
    "EXACT_DEDUP_CONTRACT_VERSION",
    "ExactDedupError",
    "ExactDedupReceipt",
    "ExactDuplicateGroup",
    "ExactDuplicateKind",
    "apply_exact_dedup",
    "find_exact_duplicate_groups",
]
