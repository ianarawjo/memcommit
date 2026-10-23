"""Allocate readable names for one scenario run without owning its lifecycle."""

from uuid import uuid4

from memcommit.application.operations.contexts.runtime import load_contexts_catalog
from memcommit.persistence.store import MemoryStore


def new_context_names(store: MemoryStore, prefixes: tuple[str, ...]) -> tuple[str, ...]:
    """Give every requested role one shared, unoccupied three-hex run code."""
    if not prefixes or len(set(prefixes)) != len(prefixes):
        raise ValueError("Scenario Context prefixes must be nonempty and distinct.")
    context_names, _ = load_contexts_catalog(store)
    existing = set(context_names)
    start = int(uuid4().hex[:3], 16)
    for offset in range(16**3):
        code = f"{(start + offset) % (16**3):03x}"
        names = tuple(f"{prefix}-{code}" for prefix in prefixes)
        if existing.isdisjoint(names):
            # These are candidates, not reservations. Each ordinary Init still
            # enforces require-new under its own lock if another process races us.
            return names
    raise ValueError("No three-character run code is available for this scenario.")
