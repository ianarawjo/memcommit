"""Direct Memory projection for physical Ground workspaces."""

from __future__ import annotations

from memcommit.models.context import Context
from memcommit.models.memory import Memory


class GroundWorkspaceProjectionError(ValueError):
    """A semantic projection cannot account for every direct Context item."""


def project_ordinary_memories(
    context: Context,
    *,
    operation: str,
) -> tuple[Memory, ...]:
    """Return the complete directly owned Memory frame for this Ground Context."""

    items = tuple(context.iter_memories())
    unsupported = tuple(
        type(item).__name__ for item in items if not isinstance(item, Memory)
    )
    if unsupported:
        kinds = ", ".join(sorted(set(unsupported)))
        raise GroundWorkspaceProjectionError(
            f"{operation} cannot yet project typed item(s) {kinds} from "
            f"Ground Context '{context.name}'. A complete Memory "
            "projection is required; no provider was connected."
        )
    return tuple(item for item in items if isinstance(item, Memory))


__all__ = [
    "GroundWorkspaceProjectionError",
    "project_ordinary_memories",
]
