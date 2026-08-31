"""Process-local Context candidate selection for a blank Ground."""

from .model import GroundContextCandidateKind, GroundContextCandidateRow
from .selection import (
    candidate_row_at,
    initial_candidate_index,
    ordered_context_rows,
    toggle_selected_context,
)

__all__ = [
    "GroundContextCandidateKind",
    "GroundContextCandidateRow",
    "candidate_row_at",
    "initial_candidate_index",
    "ordered_context_rows",
    "toggle_selected_context",
]
