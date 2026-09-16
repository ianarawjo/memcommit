"""Current candidate Meld values and session contract."""

from .apply_effects import MeldApplication
from .candidate import (
    MELD_CANDIDATE_CONTRACT_VERSION,
    MeldCandidateReview,
    MeldSourceClaim,
    build_lossless_meld_candidate,
    candidate_revision,
)
from .candidate_session import MeldSession
from .source_snapshot import (
    INLINE_MELD_CONTEXT_NAME,
    MELD_CANDIDATE_SCHEMA_VERSION,
    MELD_TEXT_LIMIT,
    MELD_NAME_LIMIT,
    MELD_ID_LIMIT,
    MeldError,
    MeldFrame,
    MeldMemory,
    MeldMode,
    MeldRole,
    MeldState,
    MeldTarget,
    meld_canonical_digest,
)

__all__ = [
    "MeldApplication",
    "MELD_CANDIDATE_CONTRACT_VERSION",
    "MeldCandidateReview",
    "MeldSourceClaim",
    "build_lossless_meld_candidate",
    "candidate_revision",
    "MeldSession",
    "INLINE_MELD_CONTEXT_NAME",
    "MELD_CANDIDATE_SCHEMA_VERSION",
    "MELD_TEXT_LIMIT",
    "MELD_NAME_LIMIT",
    "MELD_ID_LIMIT",
    "MeldError",
    "MeldFrame",
    "MeldMemory",
    "MeldMode",
    "MeldRole",
    "MeldState",
    "MeldTarget",
    "meld_canonical_digest",
]
