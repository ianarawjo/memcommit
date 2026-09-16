"""Validated semantic Update planning and persisted review state.

The package preserves the historical ``update.model`` API while assigning
changes, receipts, frozen inputs, sessions, and provider planning to explicit
Update-owned modules.
"""

from .changes import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    SourceReference,
    UpdateError,
    UpdateOperation,
    operation_digest,
    required_grant_permissions,
    required_update_context_uses,
    update_operations_are_authorized,
)
from .inputs import (
    INLINE_UPDATE_CONTEXT_NAME,
    GrantedUpdateTarget,
    SourceCandidate,
    TargetContextCandidate,
    TargetMemoryCandidate,
    UpdateInputs,
    collect_update_inputs,
    granted_target_digest,
    inline_update_context,
)
from .planning import (
    UPDATE_CORPUS_CHAR_LIMIT,
    UPDATE_EXECUTION_POLICY,
    UPDATE_PROVIDER_CONTRACT_VERSION,
    UPDATE_REASON_CHAR_LIMIT,
    UPDATE_RESPONSE_CHAR_LIMIT,
    UpdateProvider,
    plan_update,
)
from .receipts import (
    ContextFingerprint,
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
)
from .plan import UpdatePlan
from .result import AppliedOwner, UpdateResult
from .session import (
    UPDATE_GOAL_FOCUS_SCHEMA_VERSION,
    UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION,
    UPDATE_INLINE_MEMORY_SCHEMA_VERSION,
    UPDATE_SCHEMA_VERSION,
    UpdateSession,
    UpdateStatus,
    applied_session_matches,
    count_operations,
    inline_update_session_source,
    session_matches,
)

__all__ = (
    "UPDATE_CORPUS_CHAR_LIMIT",
    "UPDATE_EXECUTION_POLICY",
    "UPDATE_GOAL_FOCUS_SCHEMA_VERSION",
    "UPDATE_INLINE_GOAL_FOCUS_SCHEMA_VERSION",
    "UPDATE_INLINE_MEMORY_SCHEMA_VERSION",
    "UPDATE_PROVIDER_CONTRACT_VERSION",
    "UPDATE_REASON_CHAR_LIMIT",
    "UPDATE_RESPONSE_CHAR_LIMIT",
    "UPDATE_SCHEMA_VERSION",
    "INLINE_UPDATE_CONTEXT_NAME",
    "AddOperation",
    "AppliedOwner",
    "ContextFingerprint",
    "EditOperation",
    "GrantedUpdateTarget",
    "RemoveOperation",
    "SourceCandidate",
    "SourceReference",
    "TargetContextCandidate",
    "TargetMemoryCandidate",
    "UpdateApplicationReceipt",
    "UpdateCheckpointReceipt",
    "UpdateError",
    "UpdateInputs",
    "UpdateOperation",
    "UpdatePlan",
    "UpdateProvider",
    "UpdateResult",
    "UpdateSession",
    "UpdateStatus",
    "applied_session_matches",
    "collect_update_inputs",
    "count_operations",
    "granted_target_digest",
    "inline_update_context",
    "inline_update_session_source",
    "operation_digest",
    "plan_update",
    "required_grant_permissions",
    "required_update_context_uses",
    "update_operations_are_authorized",
    "session_matches",
)
