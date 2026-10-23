"""Durable transfer checkpoint identities, placement, and affected Contexts."""

from __future__ import annotations

from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferPlacement,
)


def transfer_checkpoint_metadata(
    *,
    kind: str,
    operation_uid: str,
    plan_digest: str,
    policy_name: str,
    policy: str,
    into_name: str,
    into_uid: str,
    placement: MemoryTransferPlacement,
    memories: tuple[FrozenTransferMemory, ...],
    affected_contexts: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    return {
        # This key predates the package rename and is durable checkpoint schema;
        # changing it would make existing Copy/Move history ungroupable.
        "memory_transfer": {
            "version": 2,
            "operation_uid": operation_uid,
            "kind": kind,
            "plan_digest": plan_digest,
            policy_name: policy,
            "target": {
                "name": into_name,
                "uid": into_uid,
            },
            "placement": {
                "position": placement.position,
                "after_uid": placement.previous_uid,
                "before_uid": placement.next_uid,
            },
            "items": [
                {
                    "source_context_name": item.source_context_name,
                    "source_context_uid": item.source_context_uid,
                    "source_memory_uid": item.source_memory_uid,
                    "output_memory_uid": item.output_memory_uid,
                }
                for item in memories
            ],
        },
        "command_contexts": [
            {"uid": uid, "name": name} for name, uid in affected_contexts
        ],
    }
