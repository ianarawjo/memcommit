"""Local evidence projections for three-scope interactive Search answers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Hashable, Literal, Sequence

from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.application.operations.search.answer_references import (
    SearchAnswerEvidence,
)
from memcommit.application.operations.search.model import (
    SearchArtifact,
    SearchCandidate,
    collect_candidates,
)
from memcommit.persistence.store import MemoryStore


OutsideCollectionStatus = Literal["SEARCHED", "PARTIAL"]


class SearchScopeEvidenceError(RuntimeError):
    """Invalid or unavailable local evidence at a Search scope boundary."""


@dataclass(frozen=True)
class OutsideEvidenceCollection:
    """Frozen evidence gathered from searchable Contexts outside one frame."""

    evidence: tuple[SearchAnswerEvidence, ...]
    status: OutsideCollectionStatus


def candidate_logical_identity(
    candidate: SearchCandidate,
) -> tuple[Hashable, ...]:
    """Return the same logical identity used by candidate collection."""
    item = candidate.item
    if isinstance(item, Memory):
        return ("memory", candidate.context_uid, item.uid)
    if isinstance(item, MemoryRef):
        return (
            "memory",
            item.target_context_uid,
            item.target_memory_uid,
        )
    if isinstance(item, QueryContextRef):
        return (
            "query_context",
            item.provider,
            item.target_source_uid,
        )
    if isinstance(item, SearchArtifact):
        return ("artifact", candidate.context_uid, item.uid)
    raise SearchScopeEvidenceError("Unsupported Search evidence candidate.")


def candidate_to_evidence(
    candidate: SearchCandidate,
    alias: str,
) -> SearchAnswerEvidence:
    """Project one local candidate without opening query-only content."""
    item = candidate.item
    if isinstance(item, Memory):
        kind = "memory"
        content = item.content
    elif isinstance(item, MemoryRef):
        if item.target is None:
            raise SearchScopeEvidenceError(
                "A dangling Memory reference cannot become answer evidence."
            )
        kind = "ref"
        content = item.target.content
    elif isinstance(item, QueryContextRef):
        kind = "query"
        content = f"{item.name} (query-only)"
    elif isinstance(item, SearchArtifact):
        kind = "artifact"
        content = f"{item.title}\n{item.content}"
    else:  # pragma: no cover - SearchCandidate validates this union
        raise SearchScopeEvidenceError("Unsupported Search evidence candidate.")
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
    """Project ranked visible candidates as stable ``mN`` evidence."""
    return tuple(
        candidate_to_evidence(candidate, f"m{index}")
        for index, candidate in enumerate(candidates, start=1)
    )


def context_remainder_evidence(
    frame_candidates: Sequence[SearchCandidate],
    visible_candidates: Sequence[SearchCandidate],
) -> tuple[SearchAnswerEvidence, ...]:
    """Project the frozen searched frame minus visible logical results."""
    visible_identities = {
        candidate_logical_identity(candidate) for candidate in visible_candidates
    }
    remainder = [
        candidate
        for candidate in frame_candidates
        if candidate_logical_identity(candidate) not in visible_identities
    ]
    return tuple(
        candidate_to_evidence(candidate, f"c{index}")
        for index, candidate in enumerate(remainder, start=1)
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
    """Bound chat-style Query citations without changing synthesis evidence."""
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


def frame_context_uids(
    root: Context,
    *,
    recursive: bool,
    additional_roots: Sequence[Context] = (),
) -> frozenset[str]:
    """Return Context identities reachable from all selected Search roots."""
    seen: set[str] = set()

    def visit(ctx: Context) -> None:
        if ctx.uid in seen:
            return
        seen.add(ctx.uid)
        if not recursive:
            return
        for item in ctx.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    for additional_root in additional_roots:
        visit(additional_root)
    return frozenset(seen)


def collect_outside_context_evidence(
    store: MemoryStore,
    *,
    excluded_context_uids: frozenset[str],
    excluded_candidates: Sequence[SearchCandidate],
) -> OutsideEvidenceCollection:
    """Collect deduplicated direct candidates from outside the Search frame.

    Every stored Context is read directly exactly once. Memory references are
    resolved against that frozen direct snapshot before candidate collection.
    This prevents embedded graphs from multiplying the same evidence while the
    global logical-identity set still collapses Memory references and
    query-only pointers.
    """
    seen = {candidate_logical_identity(candidate) for candidate in excluded_candidates}
    outside: list[SearchCandidate] = []
    catalog = store.scan_context_catalog()
    # A tolerant navigation catalog omits malformed or unsafe records. Wider
    # Search must retain that omission as evidence that its global scan was not
    # complete; otherwise an empty result could overstate non-existence.
    partial = not catalog.complete
    direct_contexts: list[Context] = []
    for name in catalog.names:
        try:
            direct_contexts.append(store.load_direct(name))
        except (FileNotFoundError, OSError, RuntimeError, ValueError):
            partial = True
    owned_memories = {
        (ctx.uid, item.uid): item
        for ctx in direct_contexts
        for item in ctx.iter_items()
        if isinstance(item, Memory)
    }
    for ctx in direct_contexts:
        if ctx.uid in excluded_context_uids:
            continue
        for item in ctx.iter_items():
            if not isinstance(item, MemoryRef):
                continue
            target = owned_memories.get(
                (item.target_context_uid, item.target_memory_uid)
            )
            if target is not None:
                # Candidate collection requires a detached target projection;
                # persistence continues to serialize only the ref pointer.
                item.target = Memory(uid=target.uid, content=target.content)
        try:
            candidates = collect_candidates(ctx, recursive=False)
        except (RuntimeError, ValueError):
            partial = True
            continue
        for candidate in candidates:
            identity = candidate_logical_identity(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            outside.append(candidate)
    evidence = tuple(
        candidate_to_evidence(candidate, f"x{index}")
        for index, candidate in enumerate(outside, start=1)
    )
    return OutsideEvidenceCollection(
        evidence=evidence,
        status="PARTIAL" if partial else "SEARCHED",
    )
