"""Grant-authorized cross-Profile delivery of one reviewed Context scope."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import uuid

from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.application.operations.profile.config import ProfileRegistry, profile_store_dir
from memcommit.application.operations.profile.model import (
    ShareEndpoint,
    authority_grant_snapshot_lock,
    resolve_share_endpoint,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


class ShareError(RuntimeError):
    """A selected delivery cannot complete without changing its meaning."""


@dataclass(frozen=True)
class ShareDelivery:
    """Stable receipt for one direct Context or recursive Context bundle."""

    uid: str
    endpoint: str
    receiver_profile: str
    receiver_context: str
    source_context: str
    context_count: int
    memory_count: int
    consent_digest: str
    include_descendants: bool
    created: bool


@dataclass(frozen=True)
class ShareMemoryPreview:
    """One immutable Memory row shown before disclosure."""

    uid: str
    content: str


@dataclass(frozen=True)
class ShareContextPreview:
    """One exact Context member inside a frozen Share unit."""

    source_context: str
    source_context_uid: str
    source_digest: str
    receiver_context: str
    memories: tuple[ShareMemoryPreview, ...]


@dataclass(frozen=True)
class SharePreview:
    """Frozen direct Context or recursive Context bundle shown before Send."""

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
    include_descendants: bool
    contexts: tuple[ShareContextPreview, ...]


@dataclass(frozen=True)
class _PreparedShare:
    preview: SharePreview
    receiver_entries: tuple[tuple[Context, AutoCheckpoint], ...]


def _direct_memories(
    source: Context,
    *,
    allow_empty: bool = False,
) -> tuple[Memory, ...]:
    memories: list[Memory] = []
    for item in source.iter_items():
        if not isinstance(item, Memory):
            raise ShareError(
                "A shared Context may contain only directly owned Memories."
            )
        memories.append(item)
    if not memories and not allow_empty:
        raise ShareError("An empty Context cannot be shared.")
    return tuple(memories)


def _source_scope_names(
    store: MemoryStore,
    source_root: str,
    *,
    include_descendants: bool,
) -> tuple[str, ...]:
    if not include_descendants:
        return (source_root,)
    return expand_lexical_context_names(
        ContextScope.create(
            (source_root,),
            include_descendants=True,
        ),
        store.list_context_names(),
    )


def _source_bindings(
    store: MemoryStore,
    source_root: str,
    *,
    include_descendants: bool,
) -> tuple[tuple[str, str, str], ...]:
    bindings: list[tuple[str, str, str]] = []
    for name in _source_scope_names(
        store,
        source_root,
        include_descendants=include_descendants,
    ):
        source = store.load_direct(name)
        bindings.append((source.name, source.uid, context_record_digest(source)))
    return tuple(bindings)


def _consent_digest(
    *,
    endpoint: ShareEndpoint,
    source_root: str,
    include_descendants: bool,
    sources: tuple[Context, ...],
    source_digests: tuple[str, ...],
    memories_by_context: tuple[tuple[Memory, ...], ...],
) -> str:
    if not include_descendants:
        # Preserve the version-1 exact Share identity. Upgrading must not make a
        # previously delivered exact consent unit appear to be a new delivery.
        source = sources[0]
        record = {
            "endpoint_grant_uid": endpoint.grant.uid,
            "recipient": endpoint.public_name,
            "sender_profile_uid": endpoint.sender.uid,
            "source_context_uid": source.uid,
            "source_digest": source_digests[0],
            "memories": [
                {"source_memory_uid": memory.uid, "content": memory.content}
                for memory in memories_by_context[0]
            ],
        }
    else:
        record = {
            "schema_version": 2,
            "endpoint_grant_uid": endpoint.grant.uid,
            "recipient": endpoint.public_name,
            "sender_profile_uid": endpoint.sender.uid,
            "source_root": source_root,
            "include_descendants": True,
            "contexts": [
                {
                    "source_context_uid": source.uid,
                    "source_context_name": source.name,
                    "source_digest": source_digest,
                    "memories": [
                        {
                            "source_memory_uid": memory.uid,
                            "content": memory.content,
                        }
                        for memory in memories
                    ],
                }
                for source, source_digest, memories in zip(
                    sources,
                    source_digests,
                    memories_by_context,
                    strict=True,
                )
            ],
        }
    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _share_uid(
    *,
    endpoint: ShareEndpoint,
    source_root: Context,
    source_root_digest: str,
    include_descendants: bool,
    consent_digest: str,
) -> str:
    parts = [
        endpoint.sender.uid,
        source_root.uid,
        source_root_digest,
        consent_digest,
    ]
    if include_descendants:
        parts.insert(2, "recursive-v2")
    return str(uuid.uuid5(uuid.UUID(endpoint.grant.uid), "\0".join(parts)))


def _prepare_delivery(
    *,
    endpoint: ShareEndpoint,
    source_root: str,
    include_descendants: bool,
    sources: tuple[Context, ...],
) -> _PreparedShare:
    if not sources or sources[0].name != source_root:
        raise ShareError("The Share Source root is missing from its frozen scope.")
    if not include_descendants and len(sources) != 1:
        raise ShareError("A direct Share must contain exactly one Context.")
    if any(
        source.name != source_root and not source.name.startswith(source_root + "/")
        for source in sources
    ):
        raise ShareError("The Share bundle contains a Context outside its root.")

    memories_by_context = tuple(
        _direct_memories(source, allow_empty=include_descendants) for source in sources
    )
    if include_descendants and not any(memories_by_context):
        raise ShareError("An empty Context bundle cannot be shared.")
    source_digests = tuple(context_record_digest(source) for source in sources)
    consent_digest = _consent_digest(
        endpoint=endpoint,
        source_root=source_root,
        include_descendants=include_descendants,
        sources=sources,
        source_digests=source_digests,
        memories_by_context=memories_by_context,
    )
    share_uid = _share_uid(
        endpoint=endpoint,
        source_root=sources[0],
        source_root_digest=source_digests[0],
        include_descendants=include_descendants,
        consent_digest=consent_digest,
    )
    receiver_root = f"{endpoint.receiver_context_name}/received-shares/{share_uid}"

    received_contexts: list[Context] = []
    mappings_by_context: list[list[dict[str, str]]] = []
    context_previews: list[ShareContextPreview] = []
    all_memories: list[ShareMemoryPreview] = []
    for index, (source, source_digest, memories) in enumerate(
        zip(sources, source_digests, memories_by_context, strict=True)
    ):
        receiver_name = receiver_root + source.name[len(source_root) :]
        receiver_uid = (
            share_uid
            if index == 0
            else str(uuid.uuid5(uuid.UUID(share_uid), source.uid))
        )
        received = Context(uid=receiver_uid, name=receiver_name)
        mappings: list[dict[str, str]] = []
        memory_previews: list[ShareMemoryPreview] = []
        for memory in memories:
            received_uid = str(uuid.uuid5(uuid.UUID(receiver_uid), memory.uid))
            received.add(Memory(uid=received_uid, content=memory.content))
            mappings.append(
                {
                    "source_memory_uid": memory.uid,
                    "received_memory_uid": received_uid,
                }
            )
            preview = ShareMemoryPreview(uid=memory.uid, content=memory.content)
            memory_previews.append(preview)
            all_memories.append(preview)
        received_contexts.append(received)
        mappings_by_context.append(mappings)
        context_previews.append(
            ShareContextPreview(
                source_context=source.name,
                source_context_uid=source.uid,
                source_digest=source_digest,
                receiver_context=receiver_name,
                memories=tuple(memory_previews),
            )
        )

    bundle_contexts = [
        {
            "source_context_uid": source.uid,
            "source_context_name": source.name,
            "source_context_digest": source_digest,
            "received_context_uid": received.uid,
            "received_context_name": received.name,
            "memories": mappings,
        }
        for source, source_digest, received, mappings in zip(
            sources,
            source_digests,
            received_contexts,
            mappings_by_context,
            strict=True,
        )
    ]
    receiver_entries: list[tuple[Context, AutoCheckpoint]] = []
    for index, (source, source_digest, received, mappings) in enumerate(
        zip(
            sources,
            source_digests,
            received_contexts,
            mappings_by_context,
            strict=True,
        )
    ):
        if include_descendants:
            share_record = {
                "schema_version": 2,
                "share_uid": share_uid,
                "consent_unit_digest": consent_digest,
                "endpoint": endpoint.public_name,
                "endpoint_grant_uid": endpoint.grant.uid,
                "endpoint_grant_revision": endpoint.grant.revision,
                "sender_profile_uid": endpoint.sender.uid,
                "sender_profile_name": endpoint.sender.name,
                "source_root_context_uid": sources[0].uid,
                "source_root_context_name": source_root,
                "source_context_uid": source.uid,
                "source_context_name": source.name,
                "source_context_digest": source_digest,
                "receiver_root_context_name": receiver_root,
                "include_descendants": True,
                "context_index": index,
                "context_count": len(sources),
                "contexts": bundle_contexts,
                "memories": mappings,
            }
            description = (
                f"Received Context bundle member {index + 1}/{len(sources)} "
                f"with {len(memories_by_context[index])} Memories from Profile "
                f"'{endpoint.sender.name}' through '{endpoint.public_name}'."
            )
        else:
            # Keep the version-1 exact receipt byte contract compatible with
            # already delivered Share units.
            share_record = {
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
            description = (
                f"Received one Context with {len(memories_by_context[index])} "
                f"Memories from Profile '{endpoint.sender.name}' through "
                f"'{endpoint.public_name}'."
            )
        receiver_entries.append(
            (
                received,
                AutoCheckpoint(
                    command="share-receive",
                    args={"share": share_record},
                    description=description,
                ),
            )
        )

    preview = SharePreview(
        uid=share_uid,
        endpoint=endpoint.public_name,
        endpoint_grant_uid=endpoint.grant.uid,
        endpoint_grant_revision=endpoint.grant.revision,
        sender_profile_uid=endpoint.sender.uid,
        receiver_profile=endpoint.authority.name,
        receiver_context=receiver_root,
        source_context=source_root,
        source_context_uid=sources[0].uid,
        source_digest=source_digests[0],
        memories=tuple(all_memories),
        consent_digest=consent_digest,
        include_descendants=include_descendants,
        contexts=tuple(context_previews),
    )
    return _PreparedShare(preview=preview, receiver_entries=tuple(receiver_entries))


def _is_same_delivery(
    store: MemoryStore,
    entries: tuple[tuple[Context, AutoCheckpoint], ...],
    *,
    share_uid: str,
) -> bool:
    present = 0
    for expected, _checkpoint in entries:
        try:
            existing = store.load_direct(expected.name)
        except FileNotFoundError:
            continue
        present += 1
        if existing.uid != expected.uid or context_record_digest(
            existing
        ) != context_record_digest(expected):
            raise ShareError("A receiver delivery path is occupied by other data.")
        checkpoints = store.list_checkpoints(existing.name)
        if not checkpoints:
            raise ShareError("A receiver copy has no delivery receipt.")
        args = checkpoints[0].get("args")
        share = args.get("share") if isinstance(args, dict) else None
        if (
            checkpoints[0].get("command") != "share-receive"
            or not isinstance(share, dict)
            or share.get("share_uid") != share_uid
        ):
            raise ShareError("A receiver copy has an invalid delivery receipt.")
    if present not in {0, len(entries)}:
        raise ShareError("The receiver contains only part of this Share bundle.")
    return present == len(entries)


def _publish_prepared(
    store: MemoryStore,
    prepared: _PreparedShare,
) -> bool:
    if _is_same_delivery(
        store,
        prepared.receiver_entries,
        share_uid=prepared.preview.uid,
    ):
        return False
    # One receiver command lock and one complete target lock set keep the
    # recursive bundle exception-atomic. A failed member cannot leave a
    # successfully reported partial disclosure behind.
    store.create_missing_contexts(
        prepared.receiver_entries,
        require_all_new=True,
    )
    return True


def _deliver_locked(
    *,
    registry: ProfileRegistry,
    source_name: str,
    endpoint_name: str,
    include_descendants: bool,
    expected: SharePreview | None = None,
) -> ShareDelivery:
    endpoint = resolve_share_endpoint(endpoint_name, registry=registry)
    if expected is not None and (
        endpoint.public_name != expected.endpoint
        or endpoint.grant.uid != expected.endpoint_grant_uid
        or endpoint.grant.revision != expected.endpoint_grant_revision
        or endpoint.sender.uid != expected.sender_profile_uid
        or endpoint.authority.name != expected.receiver_profile
        or include_descendants is not expected.include_descendants
    ):
        raise ShareError(
            "The selected Share endpoint or range changed; reopen Share before sending."
        )
    source_store = MemoryStore(
        root=profile_store_dir(registry.active),
        create=False,
    )
    bindings = _source_bindings(
        source_store,
        source_name,
        include_descendants=include_descendants,
    )
    receiver_store = MemoryStore(root=endpoint.receiver_root, create=False)
    with source_store.locked_context_snapshots(
        bindings,
        source_root=source_name,
        include_descendants=include_descendants,
    ) as frozen:
        prepared = _prepare_delivery(
            endpoint=endpoint,
            source_root=source_name,
            include_descendants=include_descendants,
            sources=frozen,
        )
        if expected is not None and prepared.preview != expected:
            # Send belongs to the complete Context scope visible in review,
            # including recursive membership, order, bytes, and destination.
            raise ShareError(
                "The selected Share content changed; reopen Share before sending."
            )
        created = _publish_prepared(receiver_store, prepared)

    preview = prepared.preview
    return ShareDelivery(
        uid=preview.uid,
        endpoint=preview.endpoint,
        receiver_profile=preview.receiver_profile,
        receiver_context=preview.receiver_context,
        source_context=preview.source_context,
        context_count=len(preview.contexts),
        memory_count=len(preview.memories),
        consent_digest=preview.consent_digest,
        include_descendants=preview.include_descendants,
        created=created,
    )


def deliver_context(
    source_locator: str | None,
    endpoint_name: str,
    *,
    include_descendants: bool = False,
) -> ShareDelivery:
    """Deliver one exact local Context scope through a frozen SHARE grant."""

    if type(include_descendants) is not bool:
        raise TypeError("Share descendant scope must be a boolean.")
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
            include_descendants=include_descendants,
        )


def prepare_share(
    source_locator: str | None,
    endpoint_name: str,
    *,
    include_descendants: bool = False,
) -> SharePreview:
    """Freeze one display-safe Share unit without changing receiver state."""

    if type(include_descendants) is not bool:
        raise TypeError("Share descendant scope must be a boolean.")
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
        bindings = _source_bindings(
            source_store,
            source_name,
            include_descendants=include_descendants,
        )
        with source_store.locked_context_snapshots(
            bindings,
            source_root=source_name,
            include_descendants=include_descendants,
        ) as frozen:
            return _prepare_delivery(
                endpoint=endpoint,
                source_root=source_name,
                include_descendants=include_descendants,
                sources=frozen,
            ).preview


def deliver_prepared_share(preview: SharePreview) -> ShareDelivery:
    """Deliver only if the exact unit shown by the viewer is still current."""

    if not isinstance(preview, SharePreview):
        raise TypeError("Expected a SharePreview.")
    with authority_grant_snapshot_lock() as registry:
        return _deliver_locked(
            registry=registry,
            source_name=preview.source_context,
            endpoint_name=preview.endpoint,
            include_descendants=preview.include_descendants,
            expected=preview,
        )


def list_share_sources(
    *,
    include_descendants: bool = False,
) -> tuple[str | None, tuple[str, ...]]:
    """List ordinary Context roots eligible for the requested Share range."""

    if type(include_descendants) is not bool:
        raise TypeError("Share descendant scope must be a boolean.")
    with authority_grant_snapshot_lock() as registry:
        store = MemoryStore(root=profile_store_dir(registry.active), create=False)
        current = store.current_context_name()
        catalog = store.list_context_names()
        names: list[str] = []
        for candidate in catalog:
            try:
                scope_names = (
                    expand_lexical_context_names(
                        ContextScope.create(
                            (candidate,),
                            include_descendants=True,
                        ),
                        catalog,
                    )
                    if include_descendants
                    else (candidate,)
                )
                memory_count = 0
                for name in scope_names:
                    context = store.load_direct(name)
                    memory_count += len(
                        _direct_memories(
                            context,
                            allow_empty=include_descendants,
                        )
                    )
                if memory_count == 0:
                    raise ShareError("An empty Context bundle cannot be shared.")
            except (FileNotFoundError, OSError, ShareError, RuntimeError, ValueError):
                continue
            names.append(candidate)
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
