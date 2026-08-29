"""Validate retained records used to reconstruct per-Memory history.

This package reads checkpoints, snapshots, and command receipts, then accepts
only claims whose identities, digests, and before/after states agree. It does
not decide which verified changes belong to a requested Memory history.

The package facade preserves the historical import boundary while common
record mechanics and operation-specific validators remain physically separate.
"""

from .checkpoint import _checkpoint_entries, _checkpoint_fields
from .frame import (
    _Frame,
    _empty_frame,
    _frame_equal,
    _frame_from_context,
    _frame_from_snapshot,
    _ordered_states,
)
from .model import (
    MemoryHistoryChildEvidence,
    MemoryHistoryCommandContext,
    MemoryHistoryCommandOperation,
    MemoryHistoryContextTransition,
    MemoryHistoryEvidence,
    MemoryHistoryReconstructionError,
    MemoryState,
    SourceOccurrence,
    TRACE_METADATA_LEGACY_SCHEMA_VERSION,
    TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION,
    TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION,
    TRACE_METADATA_SCHEMA_VERSION,
)
from .validators.add import _source_occurrences
from .validators.atomize import (
    _atomize_evidence,
    _atomize_save_as_source_frame,
    _history_change_matches_snapshot,
)
from .validators.branch import _RecordedBranchTransition, _recorded_branch_transition
from .validators.chunk import _checkpoint_chunk_options, _replay_checkpoint_chunk
from .validators.grounding import _grounding_change_evidence
from .validators.meld import _meld_change_evidence
from .validators.merge import (
    _RecordedMergeEdge,
    _RecordedMergeTransition,
    _recorded_merge_transition,
)

__all__ = [
    "MemoryHistoryChildEvidence",
    "MemoryHistoryCommandContext",
    "MemoryHistoryCommandOperation",
    "MemoryHistoryContextTransition",
    "MemoryHistoryEvidence",
    "MemoryHistoryReconstructionError",
    "MemoryState",
    "SourceOccurrence",
    "TRACE_METADATA_LEGACY_SCHEMA_VERSION",
    "TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION",
    "TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION",
    "TRACE_METADATA_SCHEMA_VERSION",
    "_Frame",
    "_RecordedBranchTransition",
    "_RecordedMergeEdge",
    "_RecordedMergeTransition",
    "_atomize_evidence",
    "_atomize_save_as_source_frame",
    "_checkpoint_chunk_options",
    "_checkpoint_entries",
    "_checkpoint_fields",
    "_empty_frame",
    "_frame_equal",
    "_frame_from_context",
    "_frame_from_snapshot",
    "_grounding_change_evidence",
    "_history_change_matches_snapshot",
    "_meld_change_evidence",
    "_ordered_states",
    "_recorded_branch_transition",
    "_recorded_merge_transition",
    "_replay_checkpoint_chunk",
    "_source_occurrences",
]
