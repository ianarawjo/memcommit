"""Compatibility import for the consolidated Context-targeting loader."""

from __future__ import annotations

from memcommit.core.context_targeting.loading import (
    ReadableContextScopeStore,
    load_context_scope,
)


__all__ = ["ReadableContextScopeStore", "load_context_scope"]
