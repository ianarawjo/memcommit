"""Load the readable corpus shared by Find, Search, and ordinary Query."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from memcommit.application.capabilities.retrieval_corpus.artifacts import (
    collect_retrieval_artifacts,
)
from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalCandidate,
    append_artifact_candidates,
    collect_candidates_from_roots,
)
from memcommit.models.context import Context
from memcommit.persistence.store.lookup.context_names import (
    list_context_and_descendant_names,
)

if TYPE_CHECKING:
    from memcommit.persistence.store import ProfileStore


class ReadableCorpusStore(Protocol):
    """Narrow local Context interface shared by retrieval operations."""

    def list_context_names(self) -> list[str]: ...

    def context_exists(self, name: str) -> bool: ...

    def load_direct(self, name: str) -> Context: ...

    def load(self, name: str) -> Context: ...


def load_readable_corpus_roots(
    store: ReadableCorpusStore,
    target_names: Sequence[str],
    *,
    include_descendants: bool,
) -> tuple[Context, ...]:
    """Freeze ordinary local Context roots with explicit lexical reach."""

    catalog_names = tuple(store.list_context_names())
    selected_names = (
        list_context_and_descendant_names(target_names, catalog_names)
        if include_descendants
        else tuple(target_names)
    )
    for target_name in target_names:
        if not store.context_exists(target_name):
            raise FileNotFoundError(
                f"Context '{target_name}' is outside the readable corpus scope."
            )
    load = store.load_direct
    roots: list[Context] = []
    seen_uids: set[str] = set()
    for name in selected_names:
        context = load(name)
        if context.uid in seen_uids:
            continue
        seen_uids.add(context.uid)
        roots.append(context)
    return tuple(roots)


def collect_readable_corpus_candidates(
    active_store: ProfileStore,
    roots: Sequence[Context],
    *,
    artifact_roots: Sequence[Context] = (),
    operation: str = "Retrieval",
) -> tuple[RetrievalCandidate, ...]:
    """Collect ordinary candidates plus explicitly authorized local artifacts."""

    candidates = collect_candidates_from_roots(
        roots,
        operation=operation,
    )
    if artifact_roots:
        candidates = append_artifact_candidates(
            candidates,
            collect_retrieval_artifacts(active_store, artifact_roots),
        )
    return tuple(candidates)
