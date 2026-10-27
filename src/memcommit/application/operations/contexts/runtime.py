"""Read-only Store and Profile projection for Contexts."""

from __future__ import annotations

from memcommit.persistence.store import ProfileStore


def load_contexts_catalog(store: ProfileStore) -> tuple[tuple[str, ...], str | None]:
    """Read the ordered Context names and current Context name."""

    current_context_name = store.current_context_name()
    context_names = tuple(store.list_context_names())
    return context_names, current_context_name
