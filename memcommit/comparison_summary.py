"""Lightweight read-only synthesis for two peer Context frames.

This model intentionally has no exhaustive relation ledger, grounding issues,
Meld readiness, or persistence contract.  Those belong to the deep
``ComparisonAnalysis`` used when a person explicitly requests a ledger or
starts Meld.
"""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.comparison import ComparisonFrame, ComparisonInput
from memcommit.understanding import UnderstandingSummary


COMPARISON_SUMMARY_RULESET_VERSION = "peer-summary-v1"


class ComparisonSummaryError(ValueError):
    """The lightweight Compare result violated its bounded report contract."""


@dataclass(frozen=True)
class ComparisonSummaryReports:
    """Four human-facing slices without a hidden relation graph."""

    both: UnderstandingSummary
    differences: UnderstandingSummary
    reference_only: UnderstandingSummary
    compared_only: UnderstandingSummary

    def __post_init__(self) -> None:
        if any(
            not isinstance(section, UnderstandingSummary)
            for section in (
                self.both,
                self.differences,
                self.reference_only,
                self.compared_only,
            )
        ):
            raise ComparisonSummaryError("Invalid lightweight Compare reports.")


@dataclass(frozen=True)
class ComparisonSummary:
    """One transient comparison report over exact frozen source frames."""

    uid: str
    created_at: str
    frames: tuple[ComparisonFrame, ComparisonFrame]
    include_descendants: tuple[bool, bool]
    overview: UnderstandingSummary
    reports: ComparisonSummaryReports
    ruleset_version: str = COMPARISON_SUMMARY_RULESET_VERSION

    def __post_init__(self) -> None:
        if (
            not isinstance(self.uid, str)
            or not self.uid
            or not isinstance(self.created_at, str)
            or not self.created_at
            or len(self.frames) != 2
            or tuple(frame.side for frame in self.frames)
            != ("REFERENCE", "COMPARED")
            or len(self.include_descendants) != 2
            or any(type(value) is not bool for value in self.include_descendants)
            or not isinstance(self.overview, UnderstandingSummary)
            or not isinstance(self.reports, ComparisonSummaryReports)
            or self.ruleset_version != COMPARISON_SUMMARY_RULESET_VERSION
        ):
            raise ComparisonSummaryError("Invalid lightweight Compare summary.")
        available = {
            memory.uid
            for frame in self.frames
            for memory in (*frame.memories, *frame.context_evidence)
        }
        for section in (
            self.overview,
            self.reports.both,
            self.reports.differences,
            self.reports.reference_only,
            self.reports.compared_only,
        ):
            if any(uid not in available for uid in section.source_uids):
                raise ComparisonSummaryError(
                    "Lightweight Compare cited evidence outside its frozen frames."
                )

    @property
    def source_count(self) -> int:
        return sum(len(frame.memories) for frame in self.frames)

    @classmethod
    def from_input(
        cls,
        comparison_input: ComparisonInput,
        *,
        overview: UnderstandingSummary,
        reports: ComparisonSummaryReports,
    ) -> "ComparisonSummary":
        if not isinstance(comparison_input, ComparisonInput):
            raise ComparisonSummaryError(
                "Lightweight Compare requires a frozen ComparisonInput."
            )
        comparison_input.validate()
        return cls(
            uid=comparison_input.uid,
            created_at=comparison_input.created_at,
            frames=comparison_input.frames,
            include_descendants=comparison_input.include_descendants,
            overview=overview,
            reports=reports,
        )

    def matches_input(self, comparison_input: ComparisonInput) -> bool:
        if not isinstance(comparison_input, ComparisonInput):
            return False
        return (
            self.include_descendants == comparison_input.include_descendants
            and tuple(
                (
                    frame.context_uid,
                    frame.context_name,
                    frame.context_digest,
                    frame.selected_memory_uid,
                    tuple(
                        (memory.uid, memory.position, memory.content_digest)
                        for memory in frame.memories
                    ),
                    tuple(
                        (memory.uid, memory.position, memory.content_digest)
                        for memory in frame.context_evidence
                    ),
                )
                for frame in self.frames
            )
            == tuple(
                (
                    frame.context_uid,
                    frame.context_name,
                    frame.context_digest,
                    frame.selected_memory_uid,
                    tuple(
                        (memory.uid, memory.position, memory.content_digest)
                        for memory in frame.memories
                    ),
                    tuple(
                        (memory.uid, memory.position, memory.content_digest)
                        for memory in frame.context_evidence
                    ),
                )
                for frame in comparison_input.frames
            )
        )


__all__ = [
    "COMPARISON_SUMMARY_RULESET_VERSION",
    "ComparisonSummary",
    "ComparisonSummaryError",
    "ComparisonSummaryReports",
]
