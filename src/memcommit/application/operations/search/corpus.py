"""Compatibility facade for the shared readable retrieval corpus."""

from memcommit.application.capabilities.retrieval_corpus.loading import (
    ReadableCorpusStore,
    collect_readable_corpus_candidates,
    load_readable_corpus_roots,
)


SearchScopeStore = ReadableCorpusStore
collect_readable_search_candidates = collect_readable_corpus_candidates
load_readable_search_roots = load_readable_corpus_roots


__all__ = [
    "SearchScopeStore",
    "collect_readable_search_candidates",
    "load_readable_search_roots",
]
