"""Trace result for one retained MemoryRef occurrence and its target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.application.capabilities.history.verification import (
    MemoryHistoryReconstructionError,
)
from memcommit.application.capabilities.history.reconstruction.reference_occurrence_derivation import (
    MemoryReferenceState,
    MemoryReferenceHistoryEvent,
)
from memcommit.application.capabilities.history.reconstruction.history_graph_reconstruction import (
    reconstruct_history_graph,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
    reconstruct_memory_history,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class MemoryReferenceTraceReport:
    """Occurrence provenance plus an independently authorized target Trace."""

    context_uid: str
    context_name: str
    selected_uid: str
    reference: MemoryReferenceState
    current: bool
    events: tuple[MemoryReferenceHistoryEvent, ...]
    target_trace: MemoryHistory | None
    target_history_status: Literal[
        "AVAILABLE",
        "SNAPSHOT_FIXED",
        "UNAVAILABLE",
    ]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "memory_reference",
            "context": {"uid": self.context_uid, "name": self.context_name},
            "selected_uid": self.selected_uid,
            "reference": self.reference.to_dict(),
            "current": self.current,
            "events": [event.to_dict() for event in self.events],
            "target_history_status": self.target_history_status,
            "target_trace": (
                self.target_trace.to_dict() if self.target_trace is not None else None
            ),
            "warnings": list(self.warnings),
        }


def _target_trace(
    store: MemoryStore,
    reference: MemoryReferenceState,
) -> tuple[MemoryHistory | None, str | None]:
    owners = tuple(
        context
        for context in store.load_direct_context_graph_strict()
        if context.uid == reference.target_context_uid
    )
    if len(owners) != 1:
        return None, (
            "The live reference target Context is unavailable or ambiguous in "
            "the local Profile."
        )
    owner = owners[0]
    try:
        return reconstruct_memory_history(store, owner, reference.target_memory_uid), None
    except MemoryHistoryReconstructionError as error:
        return None, f"The live reference target history is unavailable: {error}"


def build_reference_trace(
    store: MemoryStore,
    context: Context,
    selector: str,
) -> MemoryReferenceTraceReport:
    """Build one exact MemoryRef occurrence and its authorized target relation."""

    assembly = reconstruct_history_graph(store, context)
    candidates = tuple(
        evidence.candidate for evidence in assembly.reference_evidence
    )
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate.state.uid.startswith(selector)
    )
    exact = tuple(candidate for candidate in matches if candidate.state.uid == selector)
    if exact:
        matches = exact
    if not matches:
        raise MemoryHistoryReconstructionError(
            f"No Memory reference with uid starting with {selector!r} exists "
            f"in Context {context.name!r} or its retained history."
        )
    if len(matches) != 1:
        raise MemoryHistoryReconstructionError(
            f"Ambiguous prefix {selector!r} matches {len(matches)} Memory references: "
            + ", ".join(candidate.state.uid[:8] for candidate in matches)
        )
    candidate = matches[0]
    evidence = next(
        evidence
        for evidence in assembly.reference_evidence
        if evidence.candidate.state.uid == candidate.state.uid
    )
    events = evidence.events
    current = evidence.current
    warnings: list[str] = []
    target_trace: MemoryHistory | None = None
    target_status: Literal["AVAILABLE", "SNAPSHOT_FIXED", "UNAVAILABLE"]
    if candidate.state.mode == "SNAPSHOT":
        target_status = "SNAPSHOT_FIXED"
    else:
        target_trace, warning = _target_trace(store, candidate.state)
        target_status = "AVAILABLE" if target_trace is not None else "UNAVAILABLE"
        if warning is not None:
            warnings.append(warning)
    return MemoryReferenceTraceReport(
        context_uid=context.uid,
        context_name=context.name,
        selected_uid=candidate.state.uid,
        reference=candidate.state,
        current=current is not None,
        events=events,
        target_trace=target_trace,
        target_history_status=target_status,
        warnings=tuple(warnings),
    )


__all__ = ["MemoryReferenceTraceReport", "build_reference_trace"]
