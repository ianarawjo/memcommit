"""Lightweight read-only synthesis for two peer Context frames.

This model intentionally has no exhaustive relation ledger, grounding issues,
Meld readiness, or persistence contract.  Those belong to the deep
``ComparisonAnalysis`` used when a person explicitly requests a ledger or
starts Meld.
"""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.comparison import ComparisonFrame, ComparisonInput
from memcommit.operations.compare.summary_rules import (
    COMPARISON_SUMMARY_RULESET_VERSION,
)
from memcommit.understanding import UnderstandingSummary


class ComparisonSummaryError(ValueError):
    """The lightweight Compare result violated its bounded report contract."""


@dataclass(frozen=True)
class ComparisonSummary:
    """One transient comparison paragraph over exact frozen source frames."""

    uid: str
    created_at: str
    frames: tuple[ComparisonFrame, ComparisonFrame]
    include_descendants: tuple[bool, bool]
    paragraph: UnderstandingSummary
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
            or not isinstance(self.paragraph, UnderstandingSummary)
            or self.ruleset_version != COMPARISON_SUMMARY_RULESET_VERSION
        ):
            raise ComparisonSummaryError("Invalid lightweight Compare summary.")
        available = {
            memory.uid
            for frame in self.frames
            for memory in (*frame.memories, *frame.context_evidence)
        }
        if any(uid not in available for uid in self.paragraph.source_uids):
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
        paragraph: UnderstandingSummary,
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
            paragraph=paragraph,
        )

    def matches_input(self, comparison_input: ComparisonInput) -> bool:
        if not isinstance(comparison_input, ComparisonInput):
            return False
        return (
            self.include_descendants == comparison_input.include_descendants
            and all(
                saved.source_state() == requested.source_state()
                for saved, requested in zip(
                    self.frames,
                    comparison_input.frames,
                    strict=True,
                )
            )
        )


__all__ = [
    "COMPARISON_SUMMARY_RULESET_VERSION",
    "ComparisonSummary",
    "ComparisonSummaryError",
]
