"""Coordinate common Copy and Move receipt mechanics."""

from __future__ import annotations

from memcommit.application.operations.memory_transfer.application import (
    CopyMemoriesResult,
    MoveMemoriesResult,
)


def placement_text(result: CopyMemoriesResult | MoveMemoriesResult) -> str:
    """Describe the exact direct-item gap used by one transfer."""

    placement = result.placement
    if placement.previous_uid is not None and placement.next_uid is not None:
        return (
            f"between [{placement.previous_uid[:8]}] and "
            f"[{placement.next_uid[:8]}]"
        )
    if placement.next_uid is not None:
        return f"before [{placement.next_uid[:8]}] at the start"
    if placement.previous_uid is not None:
        return f"after [{placement.previous_uid[:8]}] at the end"
    return "as the only direct item"


__all__ = ["placement_text"]
