"""Terminal-independent application contract for retained lineage Trace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeAlias

from memcommit.application.capabilities.history.query.context_history_slicing import (
    ContextHistorySlice,
    build_context_history_slice,
    current_context_history_slice,
)
from memcommit.application.operations.history_recovery.inspection.trace.granted_view import (
    GrantedMemoryTraceReport,
    build_granted_memory_trace,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    MemoryHistory,
    MemoryHistoryCandidate,
    collect_memory_history_candidates,
    reconstruct_memory_history,
)
from memcommit.application.capabilities.history.reconstruction.memory_effect_derivation import (
    MemoryHistoryEvent,
    MemoryHistoryEventKind,
)
from memcommit.application.operations.history_recovery.inspection.trace.reference_lineage import (
    MemoryReferenceTraceReport,
    build_reference_trace,
)


TraceSubjectKind = Literal[
    "CONTEXT",
    "MEMORY",
    "MEMORY_REFERENCE",
    "GRANTED_MEMORY",
]
TraceCandidateStatus = Literal["CURRENT", "HISTORICAL"]
TraceReport: TypeAlias = (
    ContextHistorySlice
    | MemoryHistory
    | MemoryReferenceTraceReport
    | GrantedMemoryTraceReport
)


class TraceError(RuntimeError):
    """Base failure for one read-only Trace request."""


class TraceInputError(TraceError, ValueError):
    """The Trace request does not identify a valid semantic target."""


def _optional_text(value: str | None, *, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise TraceInputError(f"Trace {label} must be nonblank text.")


@dataclass(frozen=True, slots=True)
class TraceContextTarget:
    """One existing Context whose retained Context lineage is requested."""

    context_locator: str | None = None

    def __post_init__(self) -> None:
        _optional_text(self.context_locator, label="Context locator")


@dataclass(frozen=True, slots=True)
class TraceMemoryTarget:
    """One current or historical Memory/MemoryRef selector and optional owner."""

    selector: str
    context_locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, str) or not self.selector.strip():
            raise TraceInputError("Trace Memory selector must be nonblank text.")
        _optional_text(self.context_locator, label="Memory owner locator")


TraceTarget: TypeAlias = TraceContextTarget | TraceMemoryTarget


@dataclass(frozen=True, slots=True)
class TraceRequest:
    """One stable Trace request independent of argv and terminal state."""

    target: TraceTarget
    current_context_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, (TraceContextTarget, TraceMemoryTarget)):
            raise TraceInputError("Trace requires a Context or Memory target.")
        _optional_text(self.current_context_name, label="current Context name")


@dataclass(frozen=True, slots=True)
class TraceTargetCatalogRequest:
    """One local owner range used to choose a Traceable direct Memory."""

    context_locator: str | None = None
    current_context_name: str | None = None
    include_descendants: bool = True

    def __post_init__(self) -> None:
        _optional_text(self.context_locator, label="catalog Context locator")
        _optional_text(self.current_context_name, label="current Context name")
        if type(self.include_descendants) is not bool:
            raise TraceInputError("Trace catalog descendant reach must be boolean.")


@dataclass(frozen=True, slots=True)
class TraceTargetCandidate:
    """One selectable direct Memory in a frozen Trace target catalog."""

    context_name: str
    uid: str
    content: str
    position: int
    status: TraceCandidateStatus
    change_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.context_name, str) or not self.context_name:
            raise TraceInputError("Trace candidate Context name is invalid.")
        if not isinstance(self.uid, str) or not self.uid:
            raise TraceInputError("Trace candidate UID is invalid.")
        if not isinstance(self.content, str):
            raise TraceInputError("Trace candidate content is invalid.")
        if (
            isinstance(self.position, bool)
            or not isinstance(self.position, int)
            or self.position < 0
        ):
            raise TraceInputError("Trace candidate position is invalid.")
        if self.status not in {"CURRENT", "HISTORICAL"}:
            raise TraceInputError("Trace candidate status is invalid.")
        if (
            isinstance(self.change_count, bool)
            or not isinstance(self.change_count, int)
            or self.change_count < 0
        ):
            raise TraceInputError("Trace candidate change count is invalid.")


@dataclass(frozen=True, slots=True)
class TraceTargetCatalog:
    """One authorized local Context range and its traceable direct Memories."""

    root_context_name: str
    context_names: tuple[str, ...]
    candidates: tuple[TraceTargetCandidate, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.root_context_name, str)
            or not self.root_context_name
        ):
            raise TraceInputError("Trace catalog root Context is invalid.")
        if (
            not isinstance(self.context_names, tuple)
            or not self.context_names
            or any(not isinstance(name, str) or not name for name in self.context_names)
            or len(set(self.context_names)) != len(self.context_names)
            or self.root_context_name not in self.context_names
        ):
            raise TraceInputError("Trace catalog Context names are invalid.")
        if not isinstance(self.candidates, tuple) or any(
            not isinstance(candidate, TraceTargetCandidate)
            for candidate in self.candidates
        ):
            raise TraceInputError("Trace catalog candidates are invalid.")
        allowed = set(self.context_names)
        if any(candidate.context_name not in allowed for candidate in self.candidates):
            raise TraceInputError("Trace candidate is outside its frozen catalog.")
        coordinates = tuple(
            (candidate.context_name, candidate.uid) for candidate in self.candidates
        )
        if len(set(coordinates)) != len(coordinates):
            raise TraceInputError("Trace catalog repeats a Memory coordinate.")


@dataclass(frozen=True, slots=True)
class FrozenTraceSubject:
    """Exact authorized Trace subject plus an infrastructure-private binding."""

    kind: TraceSubjectKind
    context_uid: str
    context_name: str
    selected_uid: str | None
    token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.kind not in {
            "CONTEXT",
            "MEMORY",
            "MEMORY_REFERENCE",
            "GRANTED_MEMORY",
        }:
            raise TraceInputError("Frozen Trace subject kind is invalid.")
        if not isinstance(self.context_uid, str) or not self.context_uid:
            raise TraceInputError("Frozen Trace Context UID is invalid.")
        if not isinstance(self.context_name, str) or not self.context_name:
            raise TraceInputError("Frozen Trace Context name is invalid.")
        if self.kind == "CONTEXT":
            if self.selected_uid is not None:
                raise TraceInputError("Context Trace cannot select a Memory UID.")
        elif not isinstance(self.selected_uid, str) or not self.selected_uid:
            raise TraceInputError("Memory Trace requires an exact selected UID.")


@dataclass(frozen=True, slots=True)
class TraceResult:
    """Typed read-only Trace outcome shared by presentation adapters."""

    subject: FrozenTraceSubject
    report: TraceReport

    def to_dict(self) -> dict[str, object]:
        return self.report.to_dict()


class TraceSourcePort(Protocol):
    """Authorize targets and reconstruct retained evidence for Trace."""

    def target_catalog(
        self,
        request: TraceTargetCatalogRequest,
    ) -> TraceTargetCatalog:
        """Return one authorized local selection catalog."""

    def freeze(self, request: TraceRequest) -> FrozenTraceSubject:
        """Resolve and authorize one exact Trace subject."""

    def reconstruct(self, subject: FrozenTraceSubject) -> TraceReport:
        """Reconstruct the report for the exact frozen subject."""


def list_trace_targets(
    request: TraceTargetCatalogRequest,
    *,
    source: TraceSourcePort,
) -> TraceTargetCatalog:
    """List selectable local Memories without exposing storage to the adapter."""

    if not isinstance(request, TraceTargetCatalogRequest):
        raise TraceInputError("Trace target listing requires a catalog request.")
    catalog = source.target_catalog(request)
    if not isinstance(catalog, TraceTargetCatalog):
        raise TraceError("Trace source returned an invalid target catalog.")
    return catalog


def _validate_report(
    subject: FrozenTraceSubject,
    report: TraceReport,
) -> None:
    expected_type = {
        "CONTEXT": ContextHistorySlice,
        "MEMORY": MemoryHistory,
        "MEMORY_REFERENCE": MemoryReferenceTraceReport,
        "GRANTED_MEMORY": GrantedMemoryTraceReport,
    }[subject.kind]
    if not isinstance(report, expected_type):
        raise TraceError(
            f"Trace source returned {type(report).__name__} for {subject.kind}."
        )
    if (
        report.context_uid != subject.context_uid
        or report.context_name != subject.context_name
    ):
        raise TraceError("Trace report does not match its frozen Context identity.")
    if subject.selected_uid is not None and (
        getattr(report, "selected_uid", None) != subject.selected_uid
    ):
        raise TraceError("Trace report does not match its frozen selected UID.")


def run_trace(
    request: TraceRequest,
    *,
    source: TraceSourcePort,
) -> TraceResult:
    """Resolve, authorize, and reconstruct one Trace without terminal effects."""

    if not isinstance(request, TraceRequest):
        raise TraceInputError("Trace requires a TraceRequest.")
    subject = source.freeze(request)
    if not isinstance(subject, FrozenTraceSubject):
        raise TraceError("Trace source returned an invalid frozen subject.")
    report = source.reconstruct(subject)
    _validate_report(subject, report)
    return TraceResult(subject=subject, report=report)


__all__ = [
    "FrozenTraceSubject",
    "MemoryHistory",
    "MemoryHistoryCandidate",
    "MemoryHistoryEvent",
    "MemoryHistoryEventKind",
    "MemoryReferenceTraceReport",
    "ContextHistorySlice",
    "GrantedMemoryTraceReport",
    "TraceCandidateStatus",
    "TraceContextTarget",
    "TraceError",
    "TraceInputError",
    "TraceMemoryTarget",
    "TraceReport",
    "TraceRequest",
    "TraceResult",
    "TraceSourcePort",
    "TraceSubjectKind",
    "TraceTarget",
    "TraceTargetCandidate",
    "TraceTargetCatalog",
    "TraceTargetCatalogRequest",
    "build_context_history_slice",
    "build_granted_memory_trace",
    "build_reference_trace",
    "collect_memory_history_candidates",
    "current_context_history_slice",
    "list_trace_targets",
    "reconstruct_memory_history",
    "run_trace",
]
