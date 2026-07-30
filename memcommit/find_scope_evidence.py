"""Local evidence projections for three-scope interactive Find answers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Literal, Sequence

from memcommit.context import Context, Memory, MemoryRef, QueryContextRef
from memcommit.find_answer_references import FindAnswerEvidence
from memcommit.search import SearchCandidate, collect_candidates
from memcommit.store import MemoryStore


OutsideCollectionStatus = Literal["SEARCHED", "PARTIAL"]


class FindScopeEvidenceError(RuntimeError):
    """Invalid or unavailable local evidence at a Find scope boundary."""


@dataclass(frozen=True)
class OutsideEvidenceCollection:
    """Frozen evidence gathered from searchable Contexts outside one frame."""

    evidence: tuple[FindAnswerEvidence, ...]
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
    raise FindScopeEvidenceError("Unsupported Find evidence candidate.")


def candidate_to_evidence(
    candidate: SearchCandidate,
    alias: str,
) -> FindAnswerEvidence:
    """Project one local candidate without opening query-only content."""
    item = candidate.item
    if isinstance(item, Memory):
        kind = "memory"
        content = item.content
    elif isinstance(item, MemoryRef):
        if item.target is None:
            raise FindScopeEvidenceError(
                "A dangling Memory reference cannot become answer evidence."
            )
        kind = "ref"
        content = item.target.content
    elif isinstance(item, QueryContextRef):
        kind = "query"
        content = f"{item.name} (query-only)"
    else:  # pragma: no cover - SearchCandidate validates this union
        raise FindScopeEvidenceError("Unsupported Find evidence candidate.")
    return FindAnswerEvidence(
        alias=alias,
        context_name=candidate.context_name,
        kind=kind,
        uid=item.uid,
        content=content,
    )


def visible_result_evidence(
    candidates: Sequence[SearchCandidate],
) -> tuple[FindAnswerEvidence, ...]:
    """Project ranked visible candidates as stable ``mN`` evidence."""
    return tuple(
        candidate_to_evidence(candidate, f"m{index}")
        for index, candidate in enumerate(candidates, start=1)
    )


def context_remainder_evidence(
    frame_candidates: Sequence[SearchCandidate],
    visible_candidates: Sequence[SearchCandidate],
) -> tuple[FindAnswerEvidence, ...]:
    """Project the frozen searched frame minus visible logical results."""
    visible_identities = {
        candidate_logical_identity(candidate)
        for candidate in visible_candidates
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


def frame_context_uids(
    root: Context,
    *,
    recursive: bool,
) -> frozenset[str]:
    """Return loaded Context identities reachable in the selected Find frame."""
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
    return frozenset(seen)


def collect_outside_context_evidence(
    store: MemoryStore,
    *,
    excluded_context_uids: frozenset[str],
    excluded_candidates: Sequence[SearchCandidate],
) -> OutsideEvidenceCollection:
    """Collect deduplicated direct candidates from outside the Find frame.

    Every stored Context is read directly exactly once. Memory references are
    resolved against that frozen direct snapshot before candidate collection.
    This prevents embedded graphs from multiplying the same evidence while the
    global logical-identity set still collapses Memory references and
    query-only pointers.
    """
    seen = {
        candidate_logical_identity(candidate)
        for candidate in excluded_candidates
    }
    outside: list[SearchCandidate] = []
    partial = False
    direct_contexts: list[Context] = []
    for name in store.list_context_names():
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
