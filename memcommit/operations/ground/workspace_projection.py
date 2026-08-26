"""Safe ordinary-Memory projection for physical Ground workspaces.

Physical ``/contexts`` lanes may durably contain references, embeds, or
grant-backed links.  Semantic operations must not silently discard those
typed items.  Until an operation supplies an authority-aware resolver, its
ordinary-Memory projection therefore fails closed before provider connection.
"""

from __future__ import annotations

from memcommit.context import Context, Memory


class GroundWorkspaceProjectionError(ValueError):
    """A semantic projection cannot account for every direct Context item."""


def project_ordinary_memories(
    context: Context,
    *,
    operation: str,
) -> tuple[Memory, ...]:
    """Return every direct Memory or reject an unhandled typed item.

    Persisting a typed item is valid Ground workspace state.  Treating it as
    absent during inference is not: doing so would make the visible workspace
    and the provider input disagree without an explicit authority decision.
    """

    items = tuple(context.iter_items())
    unsupported = tuple(
        type(item).__name__ for item in items if not isinstance(item, Memory)
    )
    if unsupported:
        kinds = ", ".join(sorted(set(unsupported)))
        raise GroundWorkspaceProjectionError(
            f"{operation} cannot yet project typed item(s) {kinds} from "
            f"Ground Context '{context.name}'. An authority-aware Ground "
            "projection is required; no provider was connected."
        )
    return tuple(item for item in items if isinstance(item, Memory))


__all__ = [
    "GroundWorkspaceProjectionError",
    "project_ordinary_memories",
]
