"""Pure split planning for the Chunk operation."""

from __future__ import annotations

import uuid

from memcommit.context import Context, Memory
from memcommit.application.operations.chunk.domain import ChunkMethod, chunk_content


def chunk(
    ctx: Context,
    uid: str,
    method: str | ChunkMethod,
    *,
    break_on: str | None = None,
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> tuple[Memory, list[Memory]]:
    """Plan one direct-Memory split without mutating the Context.

    The operation owns UID resolution and replacement construction so CLI and
    public compatibility callers cannot acquire subtly different split rules.
    """

    matches = [key for key in ctx.memories if key.startswith(uid)]
    if not matches:
        raise KeyError(f"No item with uid starting with '{uid}'.")
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous prefix '{uid}' matches {len(matches)} items: "
            + ", ".join(match[:8] for match in matches)
        )
    full_uid = matches[0]
    item = ctx.memories[full_uid]
    if not isinstance(item, Memory):
        raise TypeError(
            f"'{uid[:8]}' is not a Memory directly owned by this Context — "
            "cannot chunk."
        )

    raw_chunks = chunk_content(
        item.content,
        method,
        break_on=break_on,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    new_memories = [
        Memory(uid=str(uuid.uuid4()), content=content) for content in raw_chunks
    ]
    return item, new_memories
