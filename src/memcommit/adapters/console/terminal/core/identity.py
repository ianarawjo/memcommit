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
    ordered = sorted(frozen)

    def common_prefix_length(left: str, right: str) -> int:
        for index, (left_character, right_character) in enumerate(zip(left, right)):
            if left_character != right_character:
                return index
        return min(len(left), len(right))

    required_widths: dict[str, int] = {}
    for index, uid in enumerate(ordered):
        # In lexical order, a value's nearest prefix competitor must be one of
        # its two neighbors; comparing every pair would make large lists quadratic.
        shared_with_previous = (
            common_prefix_length(uid, ordered[index - 1]) if index else 0
        )
        shared_with_next = (
            common_prefix_length(uid, ordered[index + 1])
            if index + 1 < len(ordered)
            else 0
        )
        required_widths[uid] = min(
            len(uid),
            max(minimum_width, shared_with_previous + 1, shared_with_next + 1),
        )

    prefixes: dict[str, str] = {}
    for uid in frozen:
        prefixes[uid] = uid[: required_widths[uid]]
    return prefixes


__all__ = [
    "DEFAULT_COMPACT_UID_WIDTH",
    "collision_safe_uid_prefixes",
]
