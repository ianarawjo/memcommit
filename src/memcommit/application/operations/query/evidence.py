"""Project one frozen ordinary-Query corpus into bounded answer evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.search.answer_references import (
    SearchAnswerEvidence,
)
from memcommit.application.operations.search.model import (
    SearchArtifact,
    SearchCandidate,
)


class OrdinaryQueryEvidenceError(RuntimeError):
    """A frozen ordinary-Query candidate cannot become answer evidence."""


def _candidate_to_evidence(
    candidate: SearchCandidate,
    alias: str,
) -> SearchAnswerEvidence:
    """Project one candidate without opening concealed query-only content."""

    item = candidate.item
    if isinstance(item, Memory):
        kind = "memory"
        content = item.content
    elif isinstance(item, MemoryRef):
        if item.target is None:
            raise OrdinaryQueryEvidenceError(
                "A dangling Memory reference cannot become Query evidence."
            )
        kind = "ref"
        content = item.target.content
    elif isinstance(item, QueryContextRef):
        kind = "query"
        content = f"{item.name} (query-only)"
    elif isinstance(item, SearchArtifact):
        kind = "artifact"
        content = f"{item.title}\n{item.content}"
    else:  # pragma: no cover - SearchCandidate validates this union.
        raise OrdinaryQueryEvidenceError(
            "Unsupported ordinary-Query evidence candidate."
        )
    return SearchAnswerEvidence(
        alias=alias,
        context_name=candidate.context_name,
        kind=kind,
        uid=item.uid,
        content=content,
    )


def visible_result_evidence(
    candidates: Sequence[SearchCandidate],
) -> tuple[SearchAnswerEvidence, ...]:
    """Project the complete frozen Query corpus as stable ``mN`` evidence."""

    return tuple(
        _candidate_to_evidence(candidate, f"m{index}")
        for index, candidate in enumerate(candidates, start=1)
    )


def compact_artifact_references(
    evidence: Sequence[SearchAnswerEvidence],
    candidates: Sequence[SearchCandidate],
) -> tuple[SearchAnswerEvidence, ...]:
    """Use artifact summaries in citations while retaining full answer input."""

    summaries = {
        (candidate.context_name, candidate.item.uid): (
            f"{candidate.item.title}\n"
            f"{candidate.item.summary.strip() or candidate.item.title}"
        )
        for candidate in candidates
        if isinstance(candidate.item, SearchArtifact)
    }
    return tuple(
        replace(
            item,
            content=summaries.get(
                (item.context_name, item.uid),
                item.content,
            ),
        )
        for item in evidence
    )


def compact_reference_content(
    evidence: Sequence[SearchAnswerEvidence],
    *,
    limit: int = 600,
) -> tuple[SearchAnswerEvidence, ...]:
    """Bound Query citations without changing provider synthesis evidence."""

    if limit < 80:
        raise ValueError("Reference excerpt limit is too small.")
    return tuple(
        replace(
            item,
            content=(
                item.content
                if len(item.content) <= limit
                else item.content[: limit - 1].rstrip() + "…"
            ),
        )
        for item in evidence
    )


__all__ = [
    "OrdinaryQueryEvidenceError",
    "compact_artifact_references",
    "compact_reference_content",
    "visible_result_evidence",
]
