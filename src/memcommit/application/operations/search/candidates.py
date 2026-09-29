"""Compatibility facade for the shared retrieval-corpus candidate owner."""

from memcommit.application.capabilities.retrieval_corpus.candidates import (
    RetrievalArtifact,
    RetrievalCandidate,
    RetrievalItem,
    RetrievalKind,
    append_artifact_candidates,
    collect_candidates,
    collect_candidates_from_roots,
    retrieval_candidate_uid_catalog,
)


SearchArtifact = RetrievalArtifact
SearchCandidate = RetrievalCandidate
SearchItem = RetrievalItem
SearchKind = RetrievalKind
search_candidate_uid_catalog = retrieval_candidate_uid_catalog


__all__ = [
    "SearchArtifact",
    "SearchCandidate",
    "SearchItem",
    "SearchKind",
    "append_artifact_candidates",
    "collect_candidates",
    "collect_candidates_from_roots",
    "search_candidate_uid_catalog",
]

