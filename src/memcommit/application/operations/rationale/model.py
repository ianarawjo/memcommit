"""Rationale evidence types, provider ports, and presentation-bound values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from memcommit.application.capabilities.history.model.memory_event import (
    MemoryHistoryEvent,
    MemoryHistoryRecord,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
)
from memcommit.application.capabilities.history.verification import MemoryState
from memcommit.application.capabilities.semantic_execution import (
    SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT,
)
from memcommit.core.context import Memory

RATIONALE_INPUT_CHAR_LIMIT = SEMANTIC_PROVIDER_INPUT_CHAR_LIMIT


RATIONALE_RESPONSE_CHAR_LIMIT = 100_000


RATIONALE_EXPLANATION_CHAR_LIMIT = 480


RATIONALE_PROVENANCE_CHAR_LIMIT = 160


RATIONALE_MIN_EXPLANATION_CHAR_LIMIT = 16


RATIONALE_SUPPORT_LIMIT = 8


RATIONALE_FALLBACK_RADIUS = 4


class RationaleError(RuntimeError):
    """Safe failure while constructing or validating rationale evidence."""


class RationaleEvidenceTooSmall(RationaleError):
    """The frozen evidence cannot support useful bounded inference."""


class RationaleProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured contextual explanation."""


@dataclass(frozen=True)
class ContextEvidence:
    candidate_id: str
    memory: Memory
    context_name: str
    position: int
    distance: int

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "memory_uid": self.memory.uid,
            "content": self.memory.content,
            "context_name": self.context_name,
            "position": self.position,
            "distance": self.distance,
        }


@dataclass(frozen=True)
class SavedAnalysis:
    session_uid: str
    interpretation: str
    clarification: str
    reason: str
    question: str
    readings: tuple[tuple[str, str], ...]
    selected_reading: str | None
    response: str

    def to_dict(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "interpretation": self.interpretation,
            "clarification": self.clarification,
            "reason": self.reason,
            "question": self.question,
            "readings": [
                {"label": label, "text": text} for label, text in self.readings
            ],
            "selected_reading": self.selected_reading,
            "response": self.response,
        }


@dataclass(frozen=True)
class UpdateProposalEvidence:
    session_uid: str
    status: str
    role: str
    operation: str
    reason: str
    owner_context_name: str
    memory_uid: str
    source_memory_uids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_uid": self.session_uid,
            "status": self.status,
            "role": self.role,
            "operation": self.operation,
            "reason": self.reason,
            "owner_context_name": self.owner_context_name,
            "memory_uid": self.memory_uid,
            "source_memory_uids": list(self.source_memory_uids),
        }


@dataclass(frozen=True)
class ContextInference:
    explanation: str
    evidence: tuple[ContextEvidence, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "explanation": self.explanation,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class RationaleReport:
    trace: MemoryHistory
    target: MemoryState
    origin_events: tuple[MemoryHistoryEvent, ...]
    recorded_reason_events: tuple[MemoryHistoryRecord, ...]
    saved_analysis: SavedAnalysis | None
    stale_analysis: bool
    proposals: tuple[UpdateProposalEvidence, ...]
    inference: ContextInference | None
    inference_cached: bool
    fallback_evidence: tuple[ContextEvidence, ...]
    inference_error: str | None
    warnings: tuple[str, ...]
    inference_scope_name: str
    inference_scope_context_count: int
    inference_scope_include_descendants: bool
    recorded_evidence_available: bool
    provenance_source_character_count: int
    provenance_character_limit: int
    inference_source_character_count: int
    inference_character_limit: int
    inference_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "trace": self.trace.to_dict(),
            "target": self.target.to_dict(),
            "origin_events": [event.to_dict() for event in self.origin_events],
            "recorded_reason_events": [
                event.to_dict() for event in self.recorded_reason_events
            ],
            "saved_analysis": (
                self.saved_analysis.to_dict()
                if self.saved_analysis is not None
                else None
            ),
            "stale_analysis": self.stale_analysis,
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "inference": (
                self.inference.to_dict() if self.inference is not None else None
            ),
            "inference_cached": self.inference_cached,
            "fallback_evidence": [item.to_dict() for item in self.fallback_evidence],
            "inference_error": self.inference_error,
            "warnings": list(self.warnings),
            "inference_scope": {
                "context_name": self.inference_scope_name,
                "context_count": self.inference_scope_context_count,
                "include_descendants": self.inference_scope_include_descendants,
            },
            "recorded_evidence_available": self.recorded_evidence_available,
            "character_budgets": {
                "provenance_source": self.provenance_source_character_count,
                "provenance_limit": self.provenance_character_limit,
                "inference_source": self.inference_source_character_count,
                "inference_limit": self.inference_character_limit,
            },
            "inference_status": self.inference_status,
        }


DEFAULT_RATIONALE_PROVENANCE_LIMIT = 40


MAX_RATIONALE_PROVENANCE_LIMIT = 100_000


class RationaleRulesError(ValueError):
    """The checked-in Rationale rules or one narrative bound is invalid."""


class RationaleLimitUnit(str, Enum):
    """Supported bounds for the complete natural-language receipt."""

    CHARACTERS = "characters"
    BYTES = "bytes"
    WORDS = "words"


class RationaleNarrativeStatus(str, Enum):
    """Whether a grounded natural-language provenance may be shown."""

    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    HIDDEN = "HIDDEN"


class RationaleSynthesisError(RuntimeError):
    """A grounded provenance narrative could not be planned or validated."""


class RationaleSemanticProvider(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one structured provenance narrative."""
