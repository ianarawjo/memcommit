"""Verify persisted operation and checkpoint evidence before reconstruction.

This facade exposes the exact decoded facts required by History reconstruction;
it neither selects a subject nor constructs a Log, Trace, or Rationale view.
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
    "_history_change_matches_snapshot",
    "_meld_change_evidence",
    "_ordered_states",
    "_recorded_branch_transition",
    "_recorded_merge_transition",
    "_replay_checkpoint_chunk",
    "_source_occurrences",
]
