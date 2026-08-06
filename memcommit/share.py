"""Grant-authorized cross-Profile delivery of one selected ordinary Context."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid

from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.profile_config import ProfileRegistry, profile_store_dir
from memcommit.profiles import (
    ShareEndpoint,
    authority_grant_snapshot_lock,
    resolve_share_endpoint,
)
from memcommit.store import MemoryStore, context_record_digest


class ShareError(RuntimeError):
    """A selected delivery cannot complete without changing its meaning."""


@dataclass(frozen=True)
class ShareDelivery:
    """Stable receipt for one Context delivery."""

    uid: str
    endpoint: str
    receiver_profile: str
    receiver_context: str
    source_context: str
    memory_count: int
    consent_digest: str
    created: bool


@dataclass(frozen=True)
class ShareMemoryPreview:
    """One immutable Memory row shown before disclosure."""

    uid: str
    content: str


@dataclass(frozen=True)
class SharePreview:
    """Frozen Context selection shown by the interactive Share viewer."""

    uid: str
    endpoint: str
    endpoint_grant_uid: str
    endpoint_grant_revision: int
    sender_profile_uid: str
    receiver_profile: str
    receiver_context: str
    source_context: str
    source_context_uid: str
    source_digest: str
    memories: tuple[ShareMemoryPreview, ...]
    consent_digest: str


def _direct_memories(source: Context) -> tuple[Memory, ...]:
    memories: list[Memory] = []
    for item in source.iter_items():
        if not isinstance(item, Memory):
            raise ShareError(
                "A shared Context may contain only directly owned Memories."
            )
        memories.append(item)
    if not memories:
        raise ShareError("An empty Context cannot be shared.")
    return tuple(memories)


def _consent_digest(
    *,
    endpoint: ShareEndpoint,
    source: Context,
    source_digest: str,
    memories: tuple[Memory, ...],
) -> str:
    record = {
        "endpoint_grant_uid": endpoint.grant.uid,
        "recipient": endpoint.public_name,
        "sender_profile_uid": endpoint.sender.uid,
        "source_context_uid": source.uid,
        "source_digest": source_digest,
        "memories": [
            {"source_memory_uid": memory.uid, "content": memory.content}
            for memory in memories
        ],
    }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _delivery_context(
    *,
    endpoint: ShareEndpoint,
    source: Context,
    source_digest: str,
    memories: tuple[Memory, ...],
) -> tuple[Context, AutoCheckpoint, str, str]:
    consent_digest = _consent_digest(
        endpoint=endpoint,
        source=source,
        source_digest=source_digest,
        memories=memories,
    )
    share_uid = str(
        uuid.uuid5(
            uuid.UUID(endpoint.grant.uid),
            "\0".join(
                (
                    endpoint.sender.uid,
                    source.uid,
                    source_digest,
                    consent_digest,
                )
            ),
        )
    )
    receiver_name = f"{endpoint.receiver_context_name}/received-shares/{share_uid}"
    received = Context(uid=share_uid, name=receiver_name)
    mappings: list[dict[str, str]] = []
    for memory in memories:
        received_uid = str(uuid.uuid5(uuid.UUID(share_uid), memory.uid))
        received.add(Memory(uid=received_uid, content=memory.content))
        mappings.append(
            {
                "source_memory_uid": memory.uid,
                "received_memory_uid": received_uid,
            }
        )
    checkpoint = AutoCheckpoint(
        command="share-receive",
        args={
            "share": {
                "schema_version": 1,
                "share_uid": share_uid,
                "consent_unit_digest": consent_digest,
                "endpoint": endpoint.public_name,
                "endpoint_grant_uid": endpoint.grant.uid,
                "endpoint_grant_revision": endpoint.grant.revision,
                "sender_profile_uid": endpoint.sender.uid,
                "sender_profile_name": endpoint.sender.name,
                "source_context_uid": source.uid,
                "source_context_name": source.name,
                "source_context_digest": source_digest,
                "memories": mappings,
            }
        },
        description=(
            f"Received one Context with {len(memories)} Memories from Profile "
            f"'{endpoint.sender.name}' through '{endpoint.public_name}'."
        ),
    )
    return received, checkpoint, share_uid, consent_digest


def _is_same_delivery(
    store: MemoryStore,
    expected: Context,
    *,
    share_uid: str,
) -> bool:
    try:
        existing = store.load_direct(expected.name)
    except FileNotFoundError:
        return False
    if existing.uid != expected.uid or context_record_digest(
        existing
    ) != context_record_digest(expected):
        raise ShareError("The receiver delivery path is occupied by other data.")
    checkpoints = store.list_checkpoints(existing.name)
    if not checkpoints:
        raise ShareError("The receiver copy has no delivery receipt.")
    args = checkpoints[0].get("args")
    share = args.get("share") if isinstance(args, dict) else None
    if (
        checkpoints[0].get("command") != "share-receive"
        or not isinstance(share, dict)
        or share.get("share_uid") != share_uid
    ):
        raise ShareError("The receiver copy has an invalid delivery receipt.")
    return True


def _deliver_locked(
    *,
    registry: ProfileRegistry,
    source_name: str,
    endpoint_name: str,
    expected: SharePreview | None = None,
) -> ShareDelivery:
    endpoint = resolve_share_endpoint(endpoint_name, registry=registry)
    if expected is not None and (
        endpoint.public_name != expected.endpoint
        or endpoint.grant.uid != expected.endpoint_grant_uid
        or endpoint.grant.revision != expected.endpoint_grant_revision
        or endpoint.sender.uid != expected.sender_profile_uid
        or endpoint.authority.name != expected.receiver_profile
    ):
        raise ShareError(
            "The selected Share endpoint changed; reopen Share before sending."
        )
    source_store = MemoryStore(
        root=profile_store_dir(registry.active),
        create=False,
    )
    source = source_store.load_direct(source_name)
    source_digest = context_record_digest(source)
    _direct_memories(source)

    receiver_store = MemoryStore(root=endpoint.receiver_root, create=False)
    with source_store.locked_context_snapshot(
        source.name,
        expected_uid=source.uid,
        expected_digest=source_digest,
    ) as frozen:
        # Re-derive the complete payload under the source lock. The earlier
        # validation is only a helpful error boundary, not the publish proof.
        memories = _direct_memories(frozen)
        received, checkpoint, share_uid, consent_digest = _delivery_context(
            endpoint=endpoint,
            source=frozen,
            source_digest=source_digest,
            memories=memories,
        )
        if expected is not None and (
            frozen.name != expected.source_context
            or frozen.uid != expected.source_context_uid
            or source_digest != expected.source_digest
            or share_uid != expected.uid
            or received.name != expected.receiver_context
            or consent_digest != expected.consent_digest
            or tuple(
                ShareMemoryPreview(uid=memory.uid, content=memory.content)
                for memory in memories
            )
            != expected.memories
        ):
            # Send belongs to the exact Context snapshot and endpoint that
            # were visible, never merely to resources with the same names.
            raise ShareError(
                "The selected Share content changed; reopen Share before sending."
            )
        if _is_same_delivery(receiver_store, received, share_uid=share_uid):
            created = False
        else:
            receiver_store.create_context(received, checkpoint)
            created = True

    return ShareDelivery(
        uid=share_uid,
        endpoint=endpoint.public_name,
        receiver_profile=endpoint.authority.name,
        receiver_context=received.name,
        source_context=source.name,
        memory_count=len(memories),
        consent_digest=consent_digest,
        created=created,
    )


def deliver_context(source_locator: str | None, endpoint_name: str) -> ShareDelivery:
    """Deliver one exact local Context through a frozen SHARE grant."""

    with authority_grant_snapshot_lock() as registry:
        source_store = MemoryStore(
            root=profile_store_dir(registry.active),
            create=False,
        )
        current = source_store.current_context_name()
        raw_source = source_locator if source_locator is not None else current
        if raw_source is None:
            raise ShareError("No current Context is available to share.")
        source_name = resolve_context_locator(raw_source, current=current)
        return _deliver_locked(
            registry=registry,
            source_name=source_name,
            endpoint_name=endpoint_name,
        )


def prepare_share(source_locator: str | None, endpoint_name: str) -> SharePreview:
    """Freeze one display-safe Share unit without changing receiver state."""

    with authority_grant_snapshot_lock() as registry:
        endpoint = resolve_share_endpoint(endpoint_name, registry=registry)
        source_store = MemoryStore(
            root=profile_store_dir(registry.active),
            create=False,
        )
        current = source_store.current_context_name()
        raw_source = source_locator if source_locator is not None else current
        if raw_source is None:
            raise ShareError("No current Context is available to share.")
        source_name = resolve_context_locator(raw_source, current=current)
        source = source_store.load_direct(source_name)
        source_digest = context_record_digest(source)
        with source_store.locked_context_snapshot(
            source.name,
            expected_uid=source.uid,
            expected_digest=source_digest,
        ) as frozen:
            memories = _direct_memories(frozen)
            received, _checkpoint, share_uid, consent_digest = _delivery_context(
                endpoint=endpoint,
                source=frozen,
                source_digest=source_digest,
                memories=memories,
            )
            return SharePreview(
                uid=share_uid,
                endpoint=endpoint.public_name,
                endpoint_grant_uid=endpoint.grant.uid,
                endpoint_grant_revision=endpoint.grant.revision,
                sender_profile_uid=endpoint.sender.uid,
                receiver_profile=endpoint.authority.name,
                receiver_context=received.name,
                source_context=frozen.name,
                source_context_uid=frozen.uid,
                source_digest=source_digest,
                memories=tuple(
                    ShareMemoryPreview(uid=memory.uid, content=memory.content)
                    for memory in memories
                ),
                consent_digest=consent_digest,
            )


def deliver_prepared_share(preview: SharePreview) -> ShareDelivery:
    """Deliver only if the exact unit shown by the viewer is still current."""

    if not isinstance(preview, SharePreview):
        raise TypeError("Expected a SharePreview.")
    with authority_grant_snapshot_lock() as registry:
        return _deliver_locked(
            registry=registry,
            source_name=preview.source_context,
            endpoint_name=preview.endpoint,
            expected=preview,
        )


def list_share_sources() -> tuple[str | None, tuple[str, ...]]:
    """List ordinary Context names that Share can copy directly."""

    with authority_grant_snapshot_lock() as registry:
        store = MemoryStore(root=profile_store_dir(registry.active), create=False)
        current = store.current_context_name()
        names: list[str] = []
        for name in store.list_context_names():
            try:
                context = store.load_direct(name)
                _direct_memories(context)
            except (FileNotFoundError, OSError, ShareError, RuntimeError, ValueError):
                continue
            names.append(context.name)
        ordered = tuple(sorted(names))
        return (current if current in ordered else None), ordered


def list_share_endpoints() -> tuple[str, ...]:
    """List exact validated SHARE endpoint names without opening their contents."""

    with authority_grant_snapshot_lock() as registry:
        names = sorted(
            {
                grant.public_name
                for grant in registry.grants
                if grant.grantee_profile_uid == registry.active.uid
                and "SHARE" in grant.permissions
            }
        )
        # Validate the frozen attachment and receiver-root identities now so a
        # dead endpoint never becomes a selectable disclosure target.
        return tuple(
            resolve_share_endpoint(name, registry=registry).public_name
            for name in names
        )
