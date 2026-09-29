"""Errors raised while freezing a shared readable retrieval corpus."""


class RetrievalCorpusError(RuntimeError):
    """A readable candidate frame cannot be disclosed or constructed safely."""


__all__ = ["RetrievalCorpusError"]

