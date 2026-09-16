"""Version-1 digest encoding for an operation's frozen transfer facts."""

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
    into_digest: str,
    placement: MemoryTransferPlacement,
    policy: str,
    inbound_links: tuple[dict[str, object], ...] = (),
) -> str:
    payload = {
        "version": 1,
        "kind": kind,
        "policy": policy,
        "into": {
            "name": into_name,
            "uid": into_uid,
            "digest": into_digest,
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
                "source_context_digest": item.source_context_digest,
                "source_memory_uid": item.source_memory_uid,
                "content_sha256": hashlib.sha256(
                    item.content.encode("utf-8")
                ).hexdigest(),
                "output_memory_uid": item.output_memory_uid,
                "source_authority": (
                    item.source_authority.to_dict()
                    if item.source_authority is not None
                    else None
                ),
            }
            for item in memories
        ],
        "inbound_links": list(inbound_links),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
