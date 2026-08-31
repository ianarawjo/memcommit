"""Authorized durable execution for the Chunk operation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    authorized_context_mutation,
    grant_checkpoint_args,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.application.operations.chunk.domain import ChunkMethod


@dataclass(frozen=True)
class ChunkApplyResult:
    """Exact cardinalities committed by one Chunk command unit."""

    source_count: int
    chunk_count: int


def apply_chunk_proposals(
    *,
    access: ContextAccess,
    context: Context,
    proposals: Sequence[tuple[Memory, Sequence[Memory]]],
    method: str | ChunkMethod,
    settings: str,
    memory_selector: str | None,
    break_on: str | None = None,
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> ChunkApplyResult:
    """Publish one reviewed direct-Memory split plan atomically.

    Target discovery and rendering remain adapter concerns. This boundary owns
    the CREATE+DELETE revalidation, exact lineage receipt, and single save.
    """

    if not proposals:
        raise ValueError("Chunk requires at least one split proposal.")

    split_records: list[dict[str, object]] = []
    for original, chunks in proposals:
        if len(chunks) <= 1:
            raise ValueError("Chunk proposals must contain multiple replacements.")
        original_position = context.ordered_uids().index(original.uid)
        context.remove(original.uid)
        for offset, chunk_memory in enumerate(chunks):
            context.add(chunk_memory, position=original_position + offset)
        split_records.append(
            {
                "uid": original.uid,
                "chunk_uids": [chunk_memory.uid for chunk_memory in chunks],
            }
        )

    method_value = method.value if isinstance(method, ChunkMethod) else method
    checkpoint_args: dict[str, object] = {
        "context": access.context_name,
        "method": method_value,
        **grant_checkpoint_args(access),
    }
    if break_on is not None:
        checkpoint_args["break_on"] = break_on
    if min_chars is not None:
        checkpoint_args["min_chars"] = min_chars
    if max_chars is not None:
        checkpoint_args["max_chars"] = max_chars
    if memory_selector is not None:
        checkpoint_args["uid"] = proposals[0][0].uid
    else:
        # Exact identities let Trace reconstruct every split without guessing
        # from content that may legitimately be repeated.
        checkpoint_args["splits"] = split_records

    source_count = len(proposals)
    chunk_count = sum(len(chunks) for _original, chunks in proposals)
    with authorized_context_mutation(
        access,
        required_permissions=("CREATE", "DELETE"),
    ):
        access.store.save(
            context,
            AutoCheckpoint(
                command="chunk",
                args=checkpoint_args,
                description=(
                    f"Chunked {source_count} Memory(s) into {chunk_count} "
                    f"Memories ({settings})"
                ),
            ),
        )
    return ChunkApplyResult(
        source_count=source_count,
        chunk_count=chunk_count,
    )
