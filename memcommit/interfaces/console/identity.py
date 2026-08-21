"""Collision-safe compact identity projection for human terminal output."""

from __future__ import annotations

from collections.abc import Iterable


DEFAULT_COMPACT_UID_WIDTH = 8


def collision_safe_uid_prefixes(
    uids: Iterable[str],
    *,
    minimum_width: int = DEFAULT_COMPACT_UID_WIDTH,
) -> dict[str, str]:
    """Return the shortest unique prefix at or above ``minimum_width``.

    The supplied UID set is the frozen namespace against which a displayed
    selector must remain unambiguous. If an identity cannot be distinguished
    even at its full length, its full value is retained rather than implying
    a safety guarantee the caller cannot provide.
    """

    if minimum_width < 1:
        raise ValueError("Compact UID width must be positive.")

    frozen = tuple(dict.fromkeys(uids))
    prefixes: dict[str, str] = {}
    for uid in frozen:
        width = min(minimum_width, len(uid))
        while width < len(uid) and any(
            other != uid and other.startswith(uid[:width])
            for other in frozen
        ):
            width += 1
        prefixes[uid] = uid[:width]
    return prefixes


__all__ = [
    "DEFAULT_COMPACT_UID_WIDTH",
    "collision_safe_uid_prefixes",
]
