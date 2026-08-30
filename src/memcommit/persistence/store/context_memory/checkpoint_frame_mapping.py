"""Shared traversal of Context frames retained by checkpoint records.

Checkpoint JSON stores the command post-image in ``snapshot`` and, for newer
automatic checkpoints, the exact pre-image in ``command_before``. Revert can
also retain complete checkpoint records recursively in ``args.log_snapshot``.
Any identity-preserving graph migration must visit all of those frames; a
partial traversal can leave Revert readable while making command Undo/Redo
unreconstructable.
"""

from __future__ import annotations

import copy
from collections.abc import Callable


ContextFrameTransform = Callable[[dict[str, object]], dict[str, object]]

# These are persistence roles, not arbitrary command arguments. Keep the list
# here so every checkpoint migration follows schema evolution in one place.
RESTORABLE_CONTEXT_FRAME_FIELDS = (
    "snapshot",
    "command_before",
    # A Revert across an inherited Branch boundary keeps the historical
    # Source snapshot intact and records the exact fresh-UID Target post-image
    # separately. It is equally restorable and must follow graph migrations.
    "restored_snapshot",
)


def map_restorable_checkpoint_frames(
    value: dict[str, object],
    transform: ContextFrameTransform,
) -> dict[str, object]:
    """Return a deep copy with every future-restorable Context frame mapped.

    ``snapshot`` is required by the persisted checkpoint contract but remains
    validated by the owning store/history reader. ``command_before`` is
    optional for legacy and manually-created checkpoints. Nested Revert log
    records use the same complete checkpoint schema and therefore recurse
    through this function rather than maintaining a second field inventory.
    """

    rewritten = copy.deepcopy(value)
    for field in RESTORABLE_CONTEXT_FRAME_FIELDS:
        frame = rewritten.get(field)
        if not isinstance(frame, dict):
            continue
        mapped = transform(frame)
        if not isinstance(mapped, dict):
            raise ValueError(
                "Checkpoint Context frame transform returned invalid data."
            )
        rewritten[field] = mapped

    args = rewritten.get("args")
    if not isinstance(args, dict) or "log_snapshot" not in args:
        return rewritten
    log_snapshot = args["log_snapshot"]
    if not isinstance(log_snapshot, list):
        raise ValueError("Checkpoint log_snapshot must be a list.")
    next_entries: list[dict[str, object]] = []
    for entry in log_snapshot:
        if not isinstance(entry, dict):
            raise ValueError("Checkpoint log_snapshot entry must be an object.")
        next_entries.append(map_restorable_checkpoint_frames(entry, transform))
    args["log_snapshot"] = next_entries
    return rewritten
