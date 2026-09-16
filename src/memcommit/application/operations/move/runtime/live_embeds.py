"""Move's exact live-Embed discovery, policy checks, and in-memory rebinding."""

from __future__ import annotations

from memcommit.application.capabilities.memory_transfer.context_bindings import (
    StoreTransferFrame,
)
from memcommit.application.capabilities.memory_transfer.contracts import (
    FrozenTransferMemory,
    MemoryTransferError,
)
from memcommit.application.operations.move.contracts import (
    FrozenInboundMemoryLink,
    MoveLinkPolicy,
)
from memcommit.core.context import Memory, MemoryRef


def find_inbound_links(
    memories: tuple[FrozenTransferMemory, ...],
    frames: tuple[StoreTransferFrame, ...],
) -> tuple[FrozenInboundMemoryLink, ...]:
    selected = {(item.source_context_uid, item.source_memory_uid) for item in memories}
    links: list[FrozenInboundMemoryLink] = []
    for frame in frames:
        for item in frame.context.iter_items():
            if (
                isinstance(item, MemoryRef)
                and item.is_live
                and (item.target_context_uid, item.target_memory_uid) in selected
            ):
                links.append(
                    FrozenInboundMemoryLink(
                        owner_context_name=frame.context.name,
                        owner_context_uid=frame.context.uid,
                        owner_context_digest=frame.expected_digest,
                        reference_uid=item.uid,
                        source_context_uid=item.target_context_uid,
                        source_memory_uid=item.target_memory_uid,
                    )
                )
    return tuple(links)


def validate_live_embed_policy(
    inbound_links: tuple[FrozenInboundMemoryLink, ...],
    *,
    policy: MoveLinkPolicy,
    into_uid: str,
) -> None:
    if inbound_links and policy == "BLOCK":
        first = inbound_links[0]
        raise MemoryTransferError(
            f"Move is blocked by {len(inbound_links)} inbound live Memory "
            f"Embed(s); first is [{first.reference_uid[:8]}] in "
            f"'{first.owner_context_name}'. Pass --retarget-links to update "
            "local links atomically or --break-links to leave them dangling."
        )
    if policy == "RETARGET":
        target_links = tuple(
            link for link in inbound_links if link.owner_context_uid == into_uid
        )
        if target_links:
            raise MemoryTransferError(
                "Move cannot retarget a live Embed held by the Target Context "
                "because that would create a self-link. Remove the Target "
                "Embed first or explicitly use --break-links."
            )


def retarget_live_embeds(
    frames: dict[str, StoreTransferFrame],
    *,
    into: StoreTransferFrame,
    memories: tuple[FrozenTransferMemory, ...],
    inbound_links: tuple[FrozenInboundMemoryLink, ...],
    policy: MoveLinkPolicy,
) -> None:
    """Rebind only frozen in-memory frames; durable publication stays in Move Apply."""
    if policy == "RETARGET":
        moved = {
            (item.source_context_uid, item.source_memory_uid): item for item in memories
        }
        for link in inbound_links:
            owner = frames[link.owner_context_name].context
            current = owner.memories.get(link.reference_uid)
            key = (link.source_context_uid, link.source_memory_uid)
            source = moved[key]
            if (
                not isinstance(current, MemoryRef)
                or not current.is_live
                or current.target_context_uid != link.source_context_uid
                or current.target_memory_uid != link.source_memory_uid
            ):
                raise MemoryTransferError(
                    "Move inbound-link binding changed inside its frozen plan."
                )
            # A live Embed follows ownership. Preserve its own direct-item
            # identity while rebinding the Source Context atomically with
            # the Copy/Move; immutable snapshots remain untouched.
            owner.memories[link.reference_uid] = MemoryRef(
                uid=current.uid,
                target_context_uid=into.context.uid,
                target_context_name=into.context.name,
                target_memory_uid=source.source_memory_uid,
                target=Memory(
                    uid=source.source_memory_uid,
                    content=source.content,
                ),
            )


def inbound_link_digest_values(
    links: tuple[FrozenInboundMemoryLink, ...],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "owner_context_name": link.owner_context_name,
            "owner_context_uid": link.owner_context_uid,
            "owner_context_digest": link.owner_context_digest,
            "reference_uid": link.reference_uid,
            "source_context_uid": link.source_context_uid,
            "source_memory_uid": link.source_memory_uid,
        }
        for link in links
    )


def inbound_link_checkpoint_values(
    links: tuple[FrozenInboundMemoryLink, ...],
) -> tuple[dict[str, object], ...]:
    # The durable v1 receipt omits the owner digest retained in the plan digest.
    return tuple(
        {key: value for key, value in record.items() if key != "owner_context_digest"}
        for record in inbound_link_digest_values(links)
    )
