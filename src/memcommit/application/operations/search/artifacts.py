"""Compatibility facade for shared retrieval artifact projections."""

from memcommit.application.capabilities.retrieval_corpus.artifacts import (
    RetrievalArtifactRecord,
    collect_retrieval_artifacts,
)


SearchArtifactRecord = RetrievalArtifactRecord
collect_search_artifacts = collect_retrieval_artifacts


__all__ = ["SearchArtifactRecord", "collect_search_artifacts"]
