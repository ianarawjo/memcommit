"""Verify persisted operation and checkpoint evidence before reconstruction.

This facade exposes the exact decoded facts required by History reconstruction;
it neither selects a subject nor constructs a Log, Trace, or Rationale view.
"""

from .checkpoint import _checkpoint_entries
from .frame import (
    _Frame,
    _frame_equal,
    _frame_from_context,
    _frame_from_snapshot,
)
from .model import (
    MemoryHistoryCommandContext,
    MemoryHistoryContextTransition,
    MemoryHistoryReconstructionError,
    MemoryState,
)
from .validators.merge import (
    _RecordedMergeEdge,
    _RecordedMergeTransition,
    _recorded_merge_transition,
)

__all__ = [
    "MemoryHistoryCommandContext",
    "MemoryHistoryContextTransition",
    "MemoryHistoryReconstructionError",
    "MemoryState",
    "_Frame",
    "_RecordedMergeEdge",
    "_RecordedMergeTransition",
    "_checkpoint_entries",
    "_frame_equal",
    "_frame_from_context",
    "_frame_from_snapshot",
    "_recorded_merge_transition",
]
