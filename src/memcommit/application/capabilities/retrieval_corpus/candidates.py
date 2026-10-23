"""Provider-free candidate model and collection shared by retrieval operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidCandidate,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory


RetrievalKind = Literal[("memory", "artifact")]


@dataclass(frozen=True)
class RetrievalArtifact:
    """A bounded, profile-local projection of durable non-Memory evidence."""

    uid: str
    artifact_kind: str
    title: str
    content: str
    summary: str = ""

    def __post_init__(self) -> None:
        for label, value in (
            ("artifact uid", self.uid),
            ("artifact kind", self.artifact_kind),
            ("artifact title", self.title),
            ("artifact content", self.content),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Retrieval {label} must be nonblank text.")
        if not isinstance(self.summary, str):
            raise ValueError("Retrieval artifact summary must be text.")


RetrievalItem = Memory | RetrievalArtifact


@dataclass(frozen=True)
class RetrievalCandidate:
    candidate_id: str
    kind: RetrievalKind
    context_uid: str
    context_names: tuple[str, ...]
    item: RetrievalItem
    search_text: str

    @property
    def context_name(self) -> str:
        """Primary owner/provenance Context used for rendering and commands."""
        return self.context_names[0]


def retrieval_candidate_uid_catalog(
    candidates: Sequence[RetrievalCandidate],
) -> tuple[DurableUidCandidate[RetrievalCandidate], ...]:
    """Project one already-authorized retrieval frame into durable identities."""

    identities: list[DurableUidCandidate[RetrievalCandidate]] = []
    for candidate in candidates:
        candidate_uids = [candidate.item.uid]
        identities.extend(
            DurableUidCandidate(
                uid=uid,
                kind=candidate.kind,
                value=candidate,
            )
            for uid in candidate_uids
        )
    return tuple(identities)


def collect_candidates(
    ctx: Context,
    *,
    operation: str = "Retrieval",
) -> list[RetrievalCandidate]:
    """Collect directly owned Memories from one in-memory Context."""
    return collect_candidates_from_roots(
        (ctx,),
        operation=operation,
    )


def collect_candidates_from_roots(
    roots: Sequence[Context],
    *,
    operation: str = "Retrieval",
) -> list[RetrievalCandidate]:
    """Collect each selected local Context once in frozen root order."""
    candidates: list[RetrievalCandidate] = []
    visited_contexts: set[str] = set()
    by_logical_identity: dict[tuple[str, str, str], int] = {}

    def add_candidate(
        kind: RetrievalKind,
        context: Context,
        item: RetrievalItem,
        search_text: str,
        logical_identity: tuple[str, str, str],
    ) -> None:
        existing_index = by_logical_identity.get(logical_identity)
        if existing_index is not None:
            existing = candidates[existing_index]
            if context.name not in existing.context_names:
                candidates[existing_index] = replace(
                    existing,
                    context_names=(*existing.context_names, context.name),
                )
            return
        by_logical_identity[logical_identity] = len(candidates)
        candidates.append(
            RetrievalCandidate(
                candidate_id=f"c{len(candidates) + 1:06d}",
                kind=kind,
                context_uid=context.uid,
                context_names=(context.name,),
                item=item,
                search_text=search_text,
            )
        )

    def visit(current: Context) -> None:
        if current.uid in visited_contexts:
            return
        visited_contexts.add(current.uid)
        for item in current.iter_memories():
            if isinstance(item, Memory):
                add_candidate(
                    "memory",
                    current,
                    item,
                    item.content,
                    ("memory", current.uid, item.uid),
                )

    for root in roots:
        visit(root)
    return candidates


def append_artifact_candidates(
    candidates: Sequence[RetrievalCandidate],
    artifacts: Sequence[tuple[str, str, RetrievalArtifact]],
) -> list[RetrievalCandidate]:
    """Append store-aware artifacts to the shared candidate namespace.

    ``artifacts`` carries canonical Context uid/name pairs because session and
    provenance stores are intentionally not embedded in the in-memory Context
    graph. Keeping this adapter separate preserves ``collect_candidates`` as a
    provider- and storage-free graph operation.
    """
    result = list(candidates)
    seen = {
        (candidate.kind, candidate.context_uid, candidate.item.uid)
        for candidate in result
    }
    for context_uid, context_name, artifact in artifacts:
        identity = ("artifact", context_uid, artifact.uid)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(
            RetrievalCandidate(
                candidate_id=f"c{len(result) + 1:06d}",
                kind="artifact",
                context_uid=context_uid,
                context_names=(context_name,),
                item=artifact,
                search_text=(
                    f"{artifact.artifact_kind}\n{artifact.title}\n{artifact.content}"
                ),
            )
        )
    return result


__all__ = [
    "RetrievalArtifact",
    "RetrievalCandidate",
    "RetrievalItem",
    "RetrievalKind",
    "append_artifact_candidates",
    "collect_candidates",
    "collect_candidates_from_roots",
    "retrieval_candidate_uid_catalog",
]
