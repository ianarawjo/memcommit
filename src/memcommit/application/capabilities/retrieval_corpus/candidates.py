"""Provider-free candidate model and collection shared by retrieval operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidCandidate,
)
from memcommit.application.capabilities.semantic.disclosure import (
    SemanticDisclosureError,
    require_semantic_disclosure_authority,
)
from memcommit.application.capabilities.retrieval_corpus.errors import (
    RetrievalCorpusError,
)
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef


RetrievalKind = Literal["memory", "memory_ref", "query_context", "artifact"]


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


RetrievalItem = Memory | MemoryRef | QueryContextRef | RetrievalArtifact


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
        if (
            isinstance(candidate.item, MemoryRef)
            and candidate.item.target_memory_uid != candidate.item.uid
        ):
            # Retrieval consumers expose the reference UID and its Source
            # Memory UID, so both public identities select the same authorized
            # result row.
            candidate_uids.append(candidate.item.target_memory_uid)
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
    recursive: bool = True,
    operation: str = "Retrieval",
) -> list[RetrievalCandidate]:
    """Collect searchable items from one in-memory Context graph."""
    return collect_candidates_from_roots(
        (ctx,),
        recursive=recursive,
        operation=operation,
    )


def collect_candidates_from_roots(
    roots: Sequence[Context],
    *,
    recursive: bool = True,
    operation: str = "Retrieval",
) -> list[RetrievalCandidate]:
    """
    Collect visible searchable items from one or more frozen Context roots.

    QueryContextRefs contribute only their public name. Their concealed source
    is never opened. Shared/cyclic Context graphs are visited once by Context
    identity, including when a materialized namespace Context is also reached
    through an explicit embed.
    """
    try:
        require_semantic_disclosure_authority(
            roots,
            operation=operation,
            follow_contexts=recursive,
        )
    except SemanticDisclosureError as error:
        raise RetrievalCorpusError(str(error)) from error
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
        for item in current.iter_items():
            if isinstance(item, Memory):
                add_candidate(
                    "memory",
                    current,
                    item,
                    item.content,
                    ("memory", current.uid, item.uid),
                )
            elif isinstance(item, MemoryRef):
                if item.target is not None:
                    add_candidate(
                        "memory_ref",
                        current,
                        item,
                        item.target.content,
                        (
                            "memory",
                            item.target_context_uid,
                            item.target_memory_uid,
                        ),
                    )
            elif isinstance(item, QueryContextRef):
                add_candidate(
                    "query_context",
                    current,
                    item,
                    item.name,
                    (
                        "query_context",
                        item.provider,
                        item.target_source_uid,
                    ),
                )
            elif isinstance(item, Context) and recursive:
                visit(item)

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
