"""Content-free Context discovery for an unsaved Ground.

The catalog deliberately reports storage locators, not validated Context
records.  Binding remains responsible for opening the selected record and
checking its identity, content, and current digest.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
import unicodedata

import memcommit.persistence.store as store_module
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class GroundContextLocator:
    """One ordinary Context path found without opening ``context.json``."""

    name: str
    verification: str = "LOCATOR_ONLY"


GROUND_CONTEXT_PROVIDER_CATALOG_LIMIT = 64


def _search_terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return {
        term
        for term in re.split(r"[^\w]+", normalized)
        if term and (len(term) > 1 or term.isdigit())
    }


def discover_ground_context_locators(
    store: MemoryStore,
) -> tuple[GroundContextLocator, ...]:
    """Return ordinary Context locators without reading any Context record.

    A locator may point at a malformed or stale record.  That is intentional:
    discovery is allowed to be helpful but cannot become an authority check.
    ``MemoryStore.load`` remains the validation boundary before any binding.
    """
    contexts_dir = store_module.CONTEXTS_DIR
    if not contexts_dir.exists() or contexts_dir.is_symlink():
        return ()

    names: set[str] = set()
    try:
        candidates = contexts_dir.rglob("context.json")
        for context_file in candidates:
            if not context_file.is_file() or context_file.is_symlink():
                continue
            try:
                name = context_file.parent.relative_to(
                    contexts_dir
                ).as_posix()
            except (OSError, ValueError):
                continue
            # context_exists validates the path namespace and every parent
            # symlink, but it intentionally does not open or parse the file.
            if store.context_exists(name):
                names.add(name)
    except OSError:
        return ()

    return tuple(
        GroundContextLocator(name=name)
        for name in sorted(names)
    )


def select_ground_context_locators(
    request: str,
    locators: Sequence[GroundContextLocator],
    *,
    limit: int = GROUND_CONTEXT_PROVIDER_CATALOG_LIMIT,
) -> tuple[GroundContextLocator, ...]:
    """Bound a large locator catalog using deterministic name-only ranking."""
    if limit < 1:
        raise ValueError("Ground Context catalog limit must be positive.")
    candidates = tuple(locators)
    if len(candidates) <= limit:
        return candidates

    request_terms = _search_terms(request)

    def rank(locator: GroundContextLocator) -> tuple[int, int, str]:
        name_terms = _search_terms(locator.name)
        overlap = len(request_terms & name_terms)
        partial = sum(
            1
            for request_term in request_terms
            for name_term in name_terms
            if (
                len(request_term) >= 3
                and (
                    request_term in name_term
                    or name_term in request_term
                )
            )
        )
        return (-overlap, -partial, locator.name)

    return tuple(sorted(candidates, key=rank)[:limit])
