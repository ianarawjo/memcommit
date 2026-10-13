"""Project one frozen ordinary-Query corpus into authorized answer evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.query.reference_document import (
    OrdinaryQueryEvidence,
)
from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalArtifact,
    RetrievalCandidate,
)


class OrdinaryQueryEvidenceError(RuntimeError):
    """A frozen ordinary-Query candidate cannot become answer evidence."""


def _candidate_to_evidence(
    candidate: RetrievalCandidate,
    alias: str,
) -> OrdinaryQueryEvidence:
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
    elif isinstance(item, RetrievalArtifact):
        kind = "artifact"
        content = f"{item.title}\n{item.content}"
    else:  # pragma: no cover - RetrievalCandidate validates this union.
        raise OrdinaryQueryEvidenceError(
            "Unsupported ordinary-Query evidence candidate."
        )
    return OrdinaryQueryEvidence(
        alias=alias,
        context_name=candidate.context_name,
        kind=kind,
        uid=item.uid,
        content=content,
    )


def visible_result_evidence(
    candidates: Sequence[RetrievalCandidate],
) -> tuple[OrdinaryQueryEvidence, ...]:
    """Project the complete frozen Query corpus as stable ``mN`` evidence."""

    return tuple(
        _candidate_to_evidence(candidate, f"m{index}")
        for index, candidate in enumerate(candidates, start=1)
    )


def compact_artifact_references(
    evidence: Sequence[OrdinaryQueryEvidence],
    candidates: Sequence[RetrievalCandidate],
) -> tuple[OrdinaryQueryEvidence, ...]:
    """Use artifact summaries in citations while retaining full answer input."""

    summaries = {
        (candidate.context_name, candidate.item.uid): (
            f"{candidate.item.title}\n"
            f"{candidate.item.summary.strip() or candidate.item.title}"
        )
        for candidate in candidates
        if isinstance(candidate.item, RetrievalArtifact)
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


__all__ = [
    "OrdinaryQueryEvidenceError",
    "compact_artifact_references",
    "visible_result_evidence",
]
