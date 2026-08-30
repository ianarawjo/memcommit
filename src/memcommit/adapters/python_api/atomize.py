"""Immutable public projections for structural Atomize."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.application.operations.atomize.application import AtomizeSessionSnapshot


@dataclass(frozen=True)
class AtomizeOverviewSectionResult:
    """One compact analysis summary with exact supporting Memory identities."""

    text: str
    source_memory_uids: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeOverviewResult:
    """The understood, changed, and unresolved analysis summary."""

    understood: AtomizeOverviewSectionResult
    changed: AtomizeOverviewSectionResult
    unresolved: AtomizeOverviewSectionResult


@dataclass(frozen=True)
class AtomizeChildResult:
    """One proposed child of a composite source Memory."""

    content: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeItemResult:
    """One complete direct-Memory classification in Source order."""

    memory_uid: str
    content: str
    position: int
    classification: str
    action: str
    reason_codes: tuple[str, ...]
    children: tuple[AtomizeChildResult, ...]
    reason: str
    lint: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeReadingResult:
    """One explicit reading offered by an ambiguity or conflict finding."""

    uid: str
    role: str
    label: str
    text: str


@dataclass(frozen=True)
class AtomizeIssueResult:
    """One traceable read-only issue projected from the saved analysis."""

    uid: str
    kind: str
    source_memory_uids: tuple[str, ...]
    priority: int
    classification: str
    reason: str
    question: str
    readings: tuple[AtomizeReadingResult, ...]


@dataclass(frozen=True)
class AtomizeAnalysisResult:
    """One exact durable structural proposal accepted by the caller.

    ``version`` is an opaque analysis/workbench revision. Proposal-bound Apply
    uses the private typed snapshot. A stateless transport may submit the same
    version through the dedicated saved-Apply method, which reconstitutes only
    the exact locked saved revision before the ordinary Store recheck.
    """

    analysis_uid: str
    version: str
    origin: str
    context_uid: str
    context_name: str
    context_digest: str
    ruleset_version: str
    memory_count: int
    projected_memory_count: int
    overview: AtomizeOverviewResult
    items: tuple[AtomizeItemResult, ...]
    issues: tuple[AtomizeIssueResult, ...]
    workbench_uid: str
    output_context_name: str
    application_completed: bool
    in_place_apply_allowed: bool
    _snapshot: AtomizeSessionSnapshot = field(repr=False, compare=False)


@dataclass(frozen=True)
class AtomizeAppliedItemResult:
    """One source-to-result lineage record from structural Apply."""

    source_memory_uid: str
    classification: str
    result_memory_uids: tuple[str, ...]
    result_contents: tuple[str, ...]
    reason: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class AtomizeStructuralApplyResult:
    """Receipt for one applied or exactly recovered structural proposal."""

    analysis_uid: str
    context_uid: str
    context_name: str
    checkpoint_uid: str
    split_count: int
    child_count: int
    preserved_count: int
    dedun_group_count: int
    absorbed_count: int
    normal_form_verified: bool
    application_mode: str
    unresolved_at_apply_count: int
    items: tuple[AtomizeAppliedItemResult, ...]
    recovered: bool


@dataclass(frozen=True)
class AtomizePlanUpdateResult:
    """One provider-free exact Output-plan edit and its new proposal token."""

    changed: bool
    proposal: AtomizeAnalysisResult


@dataclass(frozen=True)
class AtomizeSaveAsApplyResult:
    """Receipt for one created or exactly recovered structural Output."""

    analysis_uid: str
    source_context_uid: str
    source_context_name: str
    context_uid: str
    context_name: str
    checkpoint_uid: str
    split_count: int
    child_count: int
    preserved_count: int
    dedun_group_count: int
    absorbed_count: int
    normal_form_verified: bool
    application_mode: str
    unresolved_at_apply_count: int
    items: tuple[AtomizeAppliedItemResult, ...]
    recovered: bool
    current_context_name: str


__all__ = [
    "AtomizeAnalysisResult",
    "AtomizeAppliedItemResult",
    "AtomizeChildResult",
    "AtomizeIssueResult",
    "AtomizeItemResult",
    "AtomizeOverviewResult",
    "AtomizeOverviewSectionResult",
    "AtomizeReadingResult",
    "AtomizePlanUpdateResult",
    "AtomizeSaveAsApplyResult",
    "AtomizeStructuralApplyResult",
]
