"""Conservative, display-only suggestions for failed canonical-name lookup."""

from __future__ import annotations

from collections.abc import Mapping
from difflib import get_close_matches


def canonical_name_suggestions(
    candidate: str,
    spelling_to_canonical: Mapping[str, str],
    *,
    limit: int = 3,
    cutoff: float = 0.6,
) -> tuple[str, ...]:
    """Rank canonical names without turning fuzzy similarity into execution.

    Callers may include tolerated input spellings in the mapping, but every
    result is the canonical value a person can review and rerun explicitly.
    Duplicate aliases never consume more than one visible suggestion slot.
    """

    if limit < 1:
        raise ValueError("Suggestion limit must be positive.")
    matches = get_close_matches(
        candidate,
        tuple(spelling_to_canonical),
        n=max(limit, len(spelling_to_canonical)),
        cutoff=cutoff,
    )
    suggestions: list[str] = []
    for match in matches:
        canonical = spelling_to_canonical[match]
        if canonical not in suggestions:
            suggestions.append(canonical)
        if len(suggestions) == limit:
            break
    return tuple(suggestions)


def did_you_mean_suffix(suggestions: tuple[str, ...]) -> str:
    """Render one stable diagnostic suffix shared by name resolvers."""

    if len(suggestions) == 1:
        return f" Did you mean {suggestions[0]!r}?"
    if suggestions:
        return " Did you mean one of: " + ", ".join(
            repr(suggestion) for suggestion in suggestions
        ) + "?"
    return ""


__all__ = ["canonical_name_suggestions", "did_you_mean_suffix"]
