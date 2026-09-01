"""Search-facing compatibility name for safe retrieval errors."""

from memcommit.application.capabilities.retrieval_corpus.errors import (
    RetrievalCorpusError,
)


# Search historically exposed one safe error for both corpus disclosure and
# semantic ranking. Keep that public identity while the corpus owner is shared.
SearchError = RetrievalCorpusError


__all__ = ["SearchError"]
