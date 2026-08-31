"""MemoryStore adapter for atomic direct-Memory Copy and Move."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import ExitStack
from dataclasses import dataclass

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    authorized_context_operation,
    freeze_granted_context_binding,
    resolve_context_access,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.core.context_targeting.resolution import parse_direct_memory_locator
from memcommit.application.capabilities.memory_transfer.application import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
    FrozenCopyMemoriesPlan,
    FrozenInboundMemoryLink,
    FrozenMoveMemoriesPlan,
    FrozenTransferAuthority,
    FrozenTransferMemory,
    MemoryTransferAuthorityError,
    MemoryTransferCheckpoint,
    MemoryTransferError,
    MemoryTransferItemResult,
    MemoryTransferPlacement,
    MemoryTransferStalePlanError,
    MoveMemoriesRequest,
    MoveMemoriesResult,
    validate_copy_request,
    validate_move_request,
)
from memcommit.application.operations.profiles.profile.config import profile_store_dir
from memcommit.application.operations.profiles.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class _StoreTransferFrame:
    context: Context
    expected_digest: str
    display_name: str
    access: ContextAccess


@dataclass(frozen=True, slots=True)
class _StoreTransferToken:
    owner: object
    operation_uid: str
    plan_digest: str
    frames: tuple[_StoreTransferFrame, ...]
    context_catalog: tuple[str, ...]
    authority_checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...] = ()


def _placement_for_context(
    context: Context,
    *,
    before: str | None,
    after: str | None,
) -> MemoryTransferPlacement:
    if before is not None and after is not None:
        raise MemoryTransferError("Pass only one of --before or --after.")
    order = context.ordered_uids()
    if before is None and after is None:
        position = len(order)
    else:
        selector = before if before is not None else after
        assert selector is not None
        anchor = ops.resolve(context, selector)
        position = order.index(anchor.uid) + (1 if after is not None else 0)
    return MemoryTransferPlacement(
        position=position,
        previous_uid=order[position - 1] if position else None,
        next_uid=order[position] if position < len(order) else None,
    )


def _plan_digest(
    *,
    kind: str,
    memories: tuple[FrozenTransferMemory, ...],
    into_name: str,
    into_uid: str,
    into_digest: str,
    placement: MemoryTransferPlacement,
    policy: str,
    inbound_links: tuple[FrozenInboundMemoryLink, ...] = (),
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
        "inbound_links": [
            {
                "owner_context_name": item.owner_context_name,
                "owner_context_uid": item.owner_context_uid,
                "owner_context_digest": item.owner_context_digest,
                "reference_uid": item.reference_uid,
                "source_context_uid": item.source_context_uid,
                "source_memory_uid": item.source_memory_uid,
            }
            for item in inbound_links
        ],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _memory_matches(
    frames: tuple[_StoreTransferFrame, ...],
    selector: str,
    *,
    owner_name: str | None,
) -> tuple[tuple[_StoreTransferFrame, Memory], ...]:
    candidates = (
        tuple(frame for frame in frames if not frame.access.is_granted)
        if owner_name is None
        else tuple(frame for frame in frames if frame.display_name == owner_name)
    )
    if owner_name is not None and not candidates:
        raise FileNotFoundError(f"Context '{owner_name}' does not exist locally.")
    return tuple(
        (frame, item)
        for frame in candidates
        for item in frame.context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )


def _resolve_one_memory(
    frames: tuple[_StoreTransferFrame, ...],
    operand: str,
    *,
    explicit_source: str | None,
    current_name: str | None,
) -> tuple[_StoreTransferFrame, Memory]:
    try:
        locator = parse_direct_memory_locator(
            operand,
            explicit_context=explicit_source,
        )
    except ValueError as error:
        raise MemoryTransferError(str(error)) from error
    owner_name = (
        None
        if locator.context_locator is None
        else resolve_context_locator(locator.context_locator, current=current_name)
    )
    matches = _memory_matches(
        frames,
        locator.memory_selector,
        owner_name=owner_name,
    )
    if not matches:
        if owner_name is None:
            raise MemoryTransferError(
                f"No directly owned Memory with uid starting with "
                f"{locator.memory_selector!r} was found in any local Context."
            )
        raise MemoryTransferError(
            f"No directly owned Memory with uid starting with "
            f"{locator.memory_selector!r} exists in Context {owner_name!r}."
        )
    if len(matches) > 1:
        choices = "; ".join(
            f"{frame.display_name}:{memory.uid}"
            for frame, memory in sorted(
                matches,
                key=lambda value: (value[0].display_name.casefold(), value[1].uid),
            )
        )
        raise MemoryTransferError(
            f"Memory prefix {locator.memory_selector!r} has multiple local "
            f"matches ({len(matches)}): {choices}. Use CONTEXT:UID."
        )
    return matches[0]


def _target_frame(
    frames: tuple[_StoreTransferFrame, ...],
    locator: str | None,
    *,
    current_name: str | None,
) -> _StoreTransferFrame:
    if locator is None:
        if current_name is None:
            raise MemoryTransferError(
                "No current Context. Pass --into TARGET_CONTEXT explicitly."
            )
        name = current_name
    else:
        name = resolve_context_locator(locator, current=current_name)
    try:
        return next(
            frame
            for frame in frames
            if not frame.access.is_granted and frame.display_name == name
        )
    except StopIteration as error:
        raise FileNotFoundError(
            f"Copy/Move Target Context '{name}' does not exist locally."
        ) from error


def _unique_source_frames(
    memories: tuple[FrozenTransferMemory, ...],
    frames_by_name: dict[str, _StoreTransferFrame],
) -> tuple[_StoreTransferFrame, ...]:
    names = tuple(dict.fromkeys(item.source_context_name for item in memories))
    return tuple(
        frames_by_name[name]
        for name in names
        if not frames_by_name[name].access.is_granted
    )


def _checkpoint_args(
    *,
    kind: str,
    operation_uid: str,
    plan_digest: str,
    policy_name: str,
    policy: str,
    into: _StoreTransferFrame,
    placement: MemoryTransferPlacement,
    memories: tuple[FrozenTransferMemory, ...],
    inbound_links: tuple[FrozenInboundMemoryLink, ...],
    affected_frames: tuple[_StoreTransferFrame, ...],
) -> dict[str, object]:
    return {
        # This key predates the package rename and is durable checkpoint schema;
        # changing it would make existing Copy/Move history ungroupable.
        "memory_transfer": {
            "version": 1,
            "operation_uid": operation_uid,
            "kind": kind,
            "plan_digest": plan_digest,
            policy_name: policy,
            "target": {
                "name": into.context.name,
                "uid": into.context.uid,
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
                    "source_context_digest": item.source_context_digest,
                    "source_memory_uid": item.source_memory_uid,
                    "output_memory_uid": item.output_memory_uid,
                    "source_authority": (
                        item.source_authority.to_dict()
                        if item.source_authority is not None
                        else None
                    ),
                }
                for item in memories
            ],
            "inbound_links": [
                {
                    "owner_context_name": link.owner_context_name,
                    "owner_context_uid": link.owner_context_uid,
                    "reference_uid": link.reference_uid,
                    "source_context_uid": link.source_context_uid,
                    "source_memory_uid": link.source_memory_uid,
                }
                for link in inbound_links
            ],
        },
        "command_contexts": [
            {"uid": frame.context.uid, "name": frame.context.name}
            for frame in affected_frames
        ],
    }


def _frozen_transfer_authority(access: ContextAccess) -> FrozenTransferAuthority | None:
    if not access.is_granted:
        return None
    binding = freeze_granted_context_binding(access)
    return FrozenTransferAuthority(
        public_name=binding.public_name,
        grantee_profile_uid=binding.grantee_profile_uid,
        authority_profile_uid=binding.authority_profile_uid,
        attachment_context_uid=binding.attachment_context_uid,
        attachment_context_name=binding.attachment_context_name,
        grant_uid=binding.grant_uid,
        grant_revision=binding.grant_revision,
        grant_digest=binding.grant_digest,
        resource_uid=binding.resource_uid,
        resource_name=binding.resource_name,
        authority_context_name=binding.authority_context_name,
        permissions=binding.permissions,
    )


def _unique_source_accesses(
    memories: tuple[FrozenTransferMemory, ...],
    frames_by_name: dict[str, _StoreTransferFrame],
) -> tuple[ContextAccess, ...]:
    accesses: list[ContextAccess] = []
    seen: set[tuple[str, str, str]] = set()
    for item in memories:
        access = frames_by_name[item.source_context_name].access
        key = (
            str(access.store.store_dir),
            access.context_name,
            access.view.grant.uid if access.view is not None else "",
        )
        if key not in seen:
            seen.add(key)
            accesses.append(access)
    return tuple(accesses)


def _authority_checks(
    accesses: tuple[ContextAccess, ...],
) -> tuple[tuple[ContextAccess, tuple[str, ...]], ...]:
    checks: list[tuple[ContextAccess, tuple[str, ...]]] = []
    for access in accesses:
        if not access.is_granted:
            continue
        checks.append((access, ("READ",)))
    return tuple(checks)


class MemoryStoreCopyAndMovePort:
    """Freeze a strict local graph and publish one Copy or Move command unit."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_name: str | None,
        allow_granted_sources: bool = False,
    ):
        if type(allow_granted_sources) is not bool:
            raise TypeError("allow_granted_sources must be a boolean.")
        self._store = store
        self._current_name = current_name
        self._allow_granted_sources = allow_granted_sources
        self._owner = object()

    @classmethod
    def capture(
        cls,
        store: MemoryStore,
        *,
        allow_granted_sources: bool = False,
    ) -> "MemoryStoreCopyAndMovePort":
        return cls(
            store,
            current_name=store.current_context_name(),
            allow_granted_sources=allow_granted_sources,
        )

    @property
    def local_context_names(self) -> tuple[str, ...]:
        """Expose the frozen-role catalog needed by interactive adapters."""

        return tuple(self._store.list_context_names())

    @property
    def store(self) -> MemoryStore:
        """Expose the active Store for frozen read-only Source catalogs."""

        return self._store

    @property
    def allows_granted_sources(self) -> bool:
        """Report whether this runtime may consult active Profile Grants."""

        return self._allow_granted_sources

    @property
    def current_context_name(self) -> str | None:
        return self._current_name

    def inspect_local_context(self, name: str) -> Context:
        """Load one local direct-order preview without changing it."""

        return self._store.load_direct(name)

    def _frames(self) -> tuple[_StoreTransferFrame, ...]:
        contexts = self._store.load_direct_context_graph_strict()
        return tuple(
            _StoreTransferFrame(
                context=context,
                expected_digest=(
                    context._store_digest or context_record_digest(context)
                ),
                display_name=context.name,
                access=ContextAccess(
                    store=self._store,
                    context_name=context.name,
                    display_name=context.name,
                    attachment_name=None,
                    permission="READ",
                ),
            )
            for context in contexts
        )

    def _source_owner_names(
        self,
        request: CopyMemoriesRequest | MoveMemoriesRequest,
    ) -> tuple[str, ...]:
        names: list[str] = []
        for operand in request.memory_locators:
            try:
                locator = parse_direct_memory_locator(
                    operand,
                    explicit_context=request.source_locator,
                )
            except ValueError as error:
                raise MemoryTransferError(str(error)) from error
            if locator.context_locator is None:
                continue
            name = resolve_context_locator(
                locator.context_locator,
                current=self._current_name,
            )
            if name not in names:
                names.append(name)
        return tuple(names)

    def _with_granted_source_frames(
        self,
        request: CopyMemoriesRequest | MoveMemoriesRequest,
        frames: tuple[_StoreTransferFrame, ...],
        *,
        kind: str,
    ) -> tuple[_StoreTransferFrame, ...]:
        local_names = {frame.display_name for frame in frames}
        external_names = tuple(
            name
            for name in self._source_owner_names(request)
            if name not in local_names
        )
        if not external_names or not self._allow_granted_sources:
            return frames

        with authority_grant_snapshot_lock() as registry:
            if self._store.store_dir.resolve() != profile_store_dir(
                registry.active
            ).resolve():
                # An explicitly rooted Store must not inherit the host Profile's
                # Grants merely because a public-looking locator was supplied.
                return frames
            additions: list[_StoreTransferFrame] = []
            for public_name in external_names:
                access = resolve_context_access(
                    self._store,
                    public_name,
                    current_name=self._current_name,
                    required_permission="READ",
                    registry=registry,
                )
                if not access.is_granted:
                    raise MemoryTransferStalePlanError(
                        "Copy/Move Source ownership changed during selection."
                    )
                if kind == "MOVE":
                    raise MemoryTransferAuthorityError(
                        f"Move cannot use granted Source {public_name!r}: READ "
                        "permits a Copy, not deletion or cross-Profile ownership "
                        "transfer. Copy it into a local Context first, then move "
                        "the local copy."
                    )
                context = access.store.load_direct(access.context_name)
                additions.append(
                    _StoreTransferFrame(
                        context=context,
                        expected_digest=context_record_digest(context),
                        display_name=public_name,
                        access=access,
                    )
                )
        return (*frames, *additions)

    def _resolved_sources(
        self,
        locators: tuple[str, ...],
        *,
        source_locator: str | None,
        frames: tuple[_StoreTransferFrame, ...],
        output_uids: tuple[str, ...],
    ) -> tuple[FrozenTransferMemory, ...]:
        resolved: list[FrozenTransferMemory] = []
        seen: set[tuple[str, str]] = set()
        for operand, output_uid in zip(locators, output_uids, strict=True):
            frame, memory = _resolve_one_memory(
                frames,
                operand,
                explicit_source=source_locator,
                current_name=self._current_name,
            )
            identity = (frame.context.uid, memory.uid)
            if identity in seen:
                raise MemoryTransferError(
                    f"Memory '{frame.display_name}:{memory.uid}' was selected "
                    "more than once."
                )
            seen.add(identity)
            resolved.append(
                FrozenTransferMemory(
                    source_context_name=frame.display_name,
                    source_context_uid=frame.context.uid,
                    source_context_digest=frame.expected_digest,
                    source_memory_uid=memory.uid,
                    content=memory.content,
                    output_memory_uid=output_uid,
                    source_authority=_frozen_transfer_authority(frame.access),
                )
            )
        return tuple(resolved)

    def _token(
        self,
        plan: FrozenCopyMemoriesPlan | FrozenMoveMemoriesPlan,
    ) -> _StoreTransferToken:
        token = plan.token
        if not isinstance(token, _StoreTransferToken) or token.owner is not self._owner:
            raise MemoryTransferError(
                "Copy/Move plan belongs to a different runtime."
            )
        if plan.plan_digest != token.plan_digest:
            raise MemoryTransferError("Copy/Move frozen plan was modified.")
        kind = "COPY" if isinstance(plan, FrozenCopyMemoriesPlan) else "MOVE"
        policy = (
            "NEW_UIDS"
            if isinstance(plan, FrozenCopyMemoriesPlan)
            else plan.request.link_policy
        )
        expected_plan_digest = _plan_digest(
            kind=kind,
            memories=plan.memories,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            into_digest=plan.into_digest,
            placement=plan.placement,
            policy=policy,
            inbound_links=(
                ()
                if isinstance(plan, FrozenCopyMemoriesPlan)
                else plan.inbound_links
            ),
        )
        if expected_plan_digest != plan.plan_digest:
            raise MemoryTransferError("Copy/Move frozen plan was modified.")
        frames = {frame.display_name: frame for frame in token.frames}
        try:
            into = frames[plan.into_name]
        except KeyError as error:
            raise MemoryTransferError("Copy/Move lost its Target binding.") from error
        if (
            into.context.uid != plan.into_uid
            or into.expected_digest != plan.into_digest
        ):
            raise MemoryTransferError("Copy/Move Target binding changed.")
        for item in plan.memories:
            frame = frames.get(item.source_context_name)
            if (
                frame is None
                or frame.context.uid != item.source_context_uid
                or frame.expected_digest != item.source_context_digest
            ):
                raise MemoryTransferError("Copy/Move Source binding changed.")
            memory = frame.context.memories.get(item.source_memory_uid)
            if not isinstance(memory, Memory) or memory.content != item.content:
                raise MemoryTransferError("Copy/Move opaque Source changed.")
        return token

    def freeze_copy(self, request: CopyMemoriesRequest) -> FrozenCopyMemoriesPlan:
        request = validate_copy_request(request)
        local_frames = self._frames()
        frames = self._with_granted_source_frames(
            request,
            local_frames,
            kind="COPY",
        )
        into = _target_frame(
            local_frames,
            request.into_locator,
            current_name=self._current_name,
        )
        # Copy is deliberately not a branching primitive. Every output gets a
        # store-wide fresh identity so two independently editable Memories can
        # never imply synchronization merely because they share a UID.
        occupied = {
            uid
            for frame in local_frames
            for uid in frame.context.memories
        }
        generated: list[str] = []
        while len(generated) < len(request.memory_locators):
            candidate = str(uuid.uuid4())
            if candidate not in occupied and candidate not in generated:
                generated.append(candidate)
        output_uids = tuple(generated)
        memories = self._resolved_sources(
            request.memory_locators,
            source_locator=request.source_locator,
            frames=frames,
            output_uids=output_uids,
        )
        frames_by_name = {frame.display_name: frame for frame in frames}
        accesses = _unique_source_accesses(memories, frames_by_name)
        authority_checks = _authority_checks(accesses)
        placement = _placement_for_context(
            into.context,
            before=request.before,
            after=request.after,
        )
        digest = _plan_digest(
            kind="COPY",
            memories=memories,
            into_name=into.context.name,
            into_uid=into.context.uid,
            into_digest=into.expected_digest,
            placement=placement,
            policy="NEW_UIDS",
        )
        return FrozenCopyMemoriesPlan(
            request=request,
            memories=memories,
            into_name=into.context.name,
            into_uid=into.context.uid,
            into_digest=into.expected_digest,
            placement=placement,
            plan_digest=digest,
            token=_StoreTransferToken(
                owner=self._owner,
                operation_uid=str(uuid.uuid4()),
                plan_digest=digest,
                frames=frames,
                context_catalog=tuple(
                    frame.context.name for frame in local_frames
                ),
                authority_checks=authority_checks,
            ),
        )

    def _inbound_links(
        self,
        memories: tuple[FrozenTransferMemory, ...],
        frames: tuple[_StoreTransferFrame, ...],
    ) -> tuple[FrozenInboundMemoryLink, ...]:
        selected = {
            (item.source_context_uid, item.source_memory_uid) for item in memories
        }
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

    def freeze_move(self, request: MoveMemoriesRequest) -> FrozenMoveMemoriesPlan:
        request = validate_move_request(request)
        local_frames = self._frames()
        frames = self._with_granted_source_frames(
            request,
            local_frames,
            kind="MOVE",
        )
        into = _target_frame(
            local_frames,
            request.into_locator,
            current_name=self._current_name,
        )
        # Resolve first with placeholders, then project the preserved Source UIDs.
        memories = self._resolved_sources(
            request.memory_locators,
            source_locator=request.source_locator,
            frames=frames,
            output_uids=tuple("pending" for _ in request.memory_locators),
        )
        memories = tuple(
            FrozenTransferMemory(
                source_context_name=item.source_context_name,
                source_context_uid=item.source_context_uid,
                source_context_digest=item.source_context_digest,
                source_memory_uid=item.source_memory_uid,
                content=item.content,
                output_memory_uid=item.source_memory_uid,
                source_authority=item.source_authority,
            )
            for item in memories
        )
        same_owner = tuple(
            item for item in memories if item.source_context_uid == into.context.uid
        )
        if same_owner:
            raise MemoryTransferError(
                "Move Target already owns selected Memory/ies: "
                + ", ".join(f"[{item.source_memory_uid[:8]}]" for item in same_owner)
                + ". Use Edit for content or a separate reorder operation."
            )
        collisions = tuple(
            item.source_memory_uid
            for item in memories
            if item.source_memory_uid in into.context.memories
        )
        if collisions:
            raise MemoryTransferError(
                "Move would collide with direct-item UID(s) already present in "
                f"Target '{into.context.name}': "
                + ", ".join(f"[{uid[:8]}]" for uid in collisions)
            )
        placement = _placement_for_context(
            into.context,
            before=request.before,
            after=request.after,
        )
        inbound_links = self._inbound_links(memories, frames)
        if inbound_links and request.link_policy == "BLOCK":
            first = inbound_links[0]
            raise MemoryTransferError(
                f"Move is blocked by {len(inbound_links)} inbound live Memory "
                f"Embed(s); first is [{first.reference_uid[:8]}] in "
                f"'{first.owner_context_name}'. Pass --retarget-links to update "
                "local links atomically or --break-links to leave them dangling."
            )
        if request.link_policy == "RETARGET":
            target_links = tuple(
                link
                for link in inbound_links
                if link.owner_context_uid == into.context.uid
            )
            if target_links:
                raise MemoryTransferError(
                    "Move cannot retarget a live Embed held by the Target Context "
                    "because that would create a self-link. Remove the Target "
                    "Embed first or explicitly use --break-links."
                )
        digest = _plan_digest(
            kind="MOVE",
            memories=memories,
            into_name=into.context.name,
            into_uid=into.context.uid,
            into_digest=into.expected_digest,
            placement=placement,
            policy=request.link_policy,
            inbound_links=inbound_links,
        )
        return FrozenMoveMemoriesPlan(
            request=request,
            memories=memories,
            into_name=into.context.name,
            into_uid=into.context.uid,
            into_digest=into.expected_digest,
            placement=placement,
            inbound_links=inbound_links,
            plan_digest=digest,
            token=_StoreTransferToken(
                owner=self._owner,
                operation_uid=str(uuid.uuid4()),
                plan_digest=digest,
                frames=frames,
                context_catalog=tuple(
                    frame.context.name for frame in local_frames
                ),
            ),
        )

    @staticmethod
    def _items(
        memories: tuple[FrozenTransferMemory, ...],
    ) -> tuple[MemoryTransferItemResult, ...]:
        return tuple(
            MemoryTransferItemResult(
                source_context_name=item.source_context_name,
                source_context_uid=item.source_context_uid,
                source_memory_uid=item.source_memory_uid,
                into_memory_uid=item.output_memory_uid,
            )
            for item in memories
        )

    def apply_copy(self, plan: FrozenCopyMemoriesPlan) -> CopyMemoriesResult:
        token = self._token(plan)
        frames = {frame.display_name: frame for frame in token.frames}
        into = frames[plan.into_name]
        for offset, item in enumerate(plan.memories):
            into.context.add(
                Memory(uid=item.output_memory_uid, content=item.content),
                position=plan.placement.position + offset,
            )
        affected = (into,)
        description = (
            f"Copied {len(plan.memories)} Memory/ies into "
            f"'{plan.into_name}' with new UIDs."
        )
        args = _checkpoint_args(
            kind="COPY",
            operation_uid=token.operation_uid,
            plan_digest=plan.plan_digest,
            policy_name="copy_identity",
            policy="NEW_UIDS",
            into=into,
            placement=plan.placement,
            memories=plan.memories,
            inbound_links=(),
            affected_frames=affected,
        )
        source_frames = _unique_source_frames(plan.memories, frames)
        external_frames: dict[tuple[str, str], _StoreTransferFrame] = {}
        for item in plan.memories:
            frame = frames[item.source_context_name]
            if not frame.access.is_granted:
                continue
            key = (str(frame.access.store.store_dir), frame.access.context_name)
            existing = external_frames.get(key)
            if existing is not None and (
                existing.context.uid != frame.context.uid
                or existing.expected_digest != frame.expected_digest
            ):
                raise MemoryTransferError(
                    "Granted Copy has inconsistent aliases for one authority Source."
                )
            external_frames[key] = frame
        try:
            with authorized_context_operation(token.authority_checks):
                with ExitStack() as stack:
                    # Hold every external Source record through the local Target
                    # commit. Grant revalidation alone cannot close a concurrent
                    # authority-content change after the reviewed Copy plan.
                    grouped: dict[str, list[_StoreTransferFrame]] = {}
                    for (store_dir, _context_name), frame in external_frames.items():
                        grouped.setdefault(store_dir, []).append(frame)
                    for store_dir in sorted(grouped):
                        group = sorted(
                            grouped[store_dir],
                            key=lambda value: value.access.context_name,
                        )
                        first, *remaining = group
                        # One locked snapshot holds that authority Store's global
                        # command lock. Validate the remaining Contexts while the
                        # same lock prevents every cooperative Store write; taking
                        # locked_context_snapshot twice on one Store would attempt
                        # to reacquire its non-reentrant command lock.
                        stack.enter_context(
                            first.access.store.locked_context_snapshot(
                                first.access.context_name,
                                expected_uid=first.context.uid,
                                expected_digest=first.expected_digest,
                            )
                        )
                        for frame in remaining:
                            current = frame.access.store.load_direct(
                                frame.access.context_name
                            )
                            if (
                                current.uid != frame.context.uid
                                or context_record_digest(current)
                                != frame.expected_digest
                            ):
                                raise ConcurrentContextUpdateError(
                                    f"Context {frame.access.context_name!r} changed "
                                    "before it could be published."
                                )
                    checkpoints = self._store.save_context_command_batch(
                        (
                            (
                                into.context,
                                AutoCheckpoint(
                                    command="copy",
                                    args=args,
                                    description=description,
                                ),
                                into.expected_digest,
                            ),
                        ),
                        source_bindings=tuple(
                            (
                                frame.context.name,
                                frame.context.uid,
                                frame.expected_digest,
                            )
                            for frame in source_frames
                        ),
                    )
        except ConcurrentContextUpdateError as error:
            raise MemoryTransferStalePlanError(
                "Copy Source or Target changed before publication; nothing was copied."
            ) from error
        receipts = (
            MemoryTransferCheckpoint(
                context_name=into.context.name,
                context_uid=into.context.uid,
                checkpoint_uid=checkpoints[0].uid,
            ),
        )
        return CopyMemoriesResult(
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            placement=plan.placement,
            items=self._items(plan.memories),
            plan_digest=plan.plan_digest,
            checkpoints=receipts,
        )

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult:
        token = self._token(plan)
        frames = {frame.display_name: frame for frame in token.frames}
        into = frames[plan.into_name]
        for item in plan.memories:
            frames[item.source_context_name].context.remove(item.source_memory_uid)

        if plan.request.link_policy == "RETARGET":
            moved = {
                (item.source_context_uid, item.source_memory_uid): item
                for item in plan.memories
            }
            for link in plan.inbound_links:
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

        for offset, item in enumerate(plan.memories):
            into.context.add(
                Memory(uid=item.source_memory_uid, content=item.content),
                position=plan.placement.position + offset,
            )

        affected_names = list(
            dict.fromkeys(
                [
                    *(item.source_context_name for item in plan.memories),
                    plan.into_name,
                    *(
                        link.owner_context_name
                        for link in plan.inbound_links
                        if plan.request.link_policy == "RETARGET"
                    ),
                ]
            )
        )
        affected = tuple(frames[name] for name in sorted(affected_names))
        description = (
            f"Moved {len(plan.memories)} Memory/ies into '{plan.into_name}' "
            f"with {plan.request.link_policy.lower()} live-link policy."
        )
        args = _checkpoint_args(
            kind="MOVE",
            operation_uid=token.operation_uid,
            plan_digest=plan.plan_digest,
            policy_name="link_policy",
            policy=plan.request.link_policy,
            into=into,
            placement=plan.placement,
            memories=plan.memories,
            inbound_links=plan.inbound_links,
            affected_frames=affected,
        )
        entries = tuple(
            (
                frame.context,
                AutoCheckpoint(command="move", args=args, description=description),
                frame.expected_digest,
            )
            for frame in affected
        )
        try:
            checkpoints = self._store.save_context_command_batch(
                entries,
                # Move's default safety claim depends on the absence or exact
                # disposition of every local inbound live Embed. Bind the full
                # scanned graph until every affected Context has committed.
                source_bindings=tuple(
                    (
                        frame.context.name,
                        frame.context.uid,
                        frame.expected_digest,
                    )
                    for frame in token.frames
                ),
                expected_context_catalog=token.context_catalog,
            )
        except ConcurrentContextUpdateError as error:
            raise MemoryTransferStalePlanError(
                "Move Source, Target, or inbound-link graph changed before "
                "publication; nothing was moved."
            ) from error
        receipts = tuple(
            MemoryTransferCheckpoint(
                context_name=frame.context.name,
                context_uid=frame.context.uid,
                checkpoint_uid=checkpoint.uid,
            )
            for frame, checkpoint in zip(affected, checkpoints, strict=True)
        )
        inbound_count = len(plan.inbound_links)
        return MoveMemoriesResult(
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            link_policy=plan.request.link_policy,
            placement=plan.placement,
            items=self._items(plan.memories),
            inbound_link_count=inbound_count,
            retargeted_link_count=(
                inbound_count if plan.request.link_policy == "RETARGET" else 0
            ),
            dangling_link_count=(
                inbound_count if plan.request.link_policy == "BREAK" else 0
            ),
            plan_digest=plan.plan_digest,
            checkpoints=receipts,
        )


__all__ = ["MemoryStoreCopyAndMovePort"]
