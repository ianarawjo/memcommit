"""Digest encoding for an operation's frozen transfer facts."""

from __future__ import annotations

import hashlib
import json

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferPlacement,
)


def transfer_plan_digest(
    *,
    kind: str,
    memories: tuple[FrozenTransferMemory, ...],
    into_name: str,
    into_uid: str,
    placement: MemoryTransferPlacement,
    policy: str,
) -> str:
    payload = {
        "version": 2,
        "kind": kind,
        "policy": policy,
        "into": {
            "name": into_name,
            "uid": into_uid,
        },
        "placement": {
            "position": placement.position,
            "previous_uid": placement.previous_uid,
            "next_uid": placement.next_uid,
        },
        "memories": [
            {
                "source_context_name": item.source_context_name,
                "source_context_uid": item.source_context_uid,
                "source_memory_uid": item.source_memory_uid,
                "content_sha256": hashlib.sha256(
                    item.content.encode("utf-8")
                ).hexdigest(),
                "output_memory_uid": item.output_memory_uid,
            }
            for item in memories
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
