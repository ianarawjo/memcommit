"""MemoryStore adapter for atomic direct-Memory Copy and Move."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.resolution import parse_direct_memory_locator
from memcommit.memory_transfer_application import (
    CopyMemoriesRequest,
    CopyMemoriesResult,
    FrozenCopyMemoriesPlan,
    FrozenInboundMemoryLink,
    FrozenMoveMemoriesPlan,
    FrozenTransferMemory,
    MemoryTransferCheckpoint,
    MemoryTransferError,
    MemoryTransferItemResult,
    MemoryTransferPlacement,
    MemoryTransferPort,
    MemoryTransferStalePlanError,
    MoveMemoriesRequest,
    MoveMemoriesResult,
    run_copy,
    run_move,
    validate_copy_request,
    validate_move_request,
)
from memcommit.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    context_record_digest,
)


@dataclass(frozen=True, slots=True)
class _StoreTransferFrame:
    context: Context
    expected_digest: str


@dataclass(frozen=True, slots=True)
class _StoreTransferToken:
    owner: object
    operation_uid: str
    plan_digest: str
    frames: tuple[_StoreTransferFrame, ...]
    context_catalog: tuple[str, ...]


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
        frames
        if owner_name is None
        else tuple(frame for frame in frames if frame.context.name == owner_name)
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
            f"{frame.context.name}:{memory.uid}"
            for frame, memory in sorted(
                matches,
                key=lambda value: (value[0].context.name.casefold(), value[1].uid),
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
        return next(frame for frame in frames if frame.context.name == name)
    except StopIteration as error:
        raise FileNotFoundError(
            f"Memory transfer Target Context '{name}' does not exist locally."
        ) from error


def _unique_source_frames(
    memories: tuple[FrozenTransferMemory, ...],
    frames_by_name: dict[str, _StoreTransferFrame],
) -> tuple[_StoreTransferFrame, ...]:
    names = tuple(dict.fromkeys(item.source_context_name for item in memories))
    return tuple(frames_by_name[name] for name in names)


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
                    "source_memory_uid": item.source_memory_uid,
                    "output_memory_uid": item.output_memory_uid,
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


class MemoryStoreMemoryTransferPort(MemoryTransferPort):
    """Freeze a strict local graph and publish one Copy or Move command unit."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreMemoryTransferPort":
        return cls(store, current_name=store.current_context_name())

    @property
    def local_context_names(self) -> tuple[str, ...]:
        """Expose the frozen-role catalog needed by interactive adapters."""

        return tuple(self._store.list_context_names())

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
            )
            for context in contexts
        )

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
                    f"Memory '{frame.context.name}:{memory.uid}' was selected "
                    "more than once."
                )
            seen.add(identity)
            resolved.append(
                FrozenTransferMemory(
                    source_context_name=frame.context.name,
                    source_context_uid=frame.context.uid,
                    source_context_digest=frame.expected_digest,
                    source_memory_uid=memory.uid,
                    content=memory.content,
                    output_memory_uid=output_uid,
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
                "Memory transfer plan belongs to a different runtime."
            )
        if plan.plan_digest != token.plan_digest:
            raise MemoryTransferError("Memory transfer frozen plan was modified.")
        kind = "COPY" if isinstance(plan, FrozenCopyMemoriesPlan) else "MOVE"
        policy = (
            plan.request.uid_policy
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
            raise MemoryTransferError("Memory transfer frozen plan was modified.")
        frames = {frame.context.name: frame for frame in token.frames}
        try:
            into = frames[plan.into_name]
        except KeyError as error:
            raise MemoryTransferError("Memory transfer lost its Target binding.") from error
        if (
            into.context.uid != plan.into_uid
            or into.expected_digest != plan.into_digest
        ):
            raise MemoryTransferError("Memory transfer Target binding changed.")
        for item in plan.memories:
            frame = frames.get(item.source_context_name)
            if (
                frame is None
                or frame.context.uid != item.source_context_uid
                or frame.expected_digest != item.source_context_digest
            ):
                raise MemoryTransferError("Memory transfer Source binding changed.")
            memory = frame.context.memories.get(item.source_memory_uid)
            if not isinstance(memory, Memory) or memory.content != item.content:
                raise MemoryTransferError("Memory transfer opaque Source changed.")
        return token

    def freeze_copy(self, request: CopyMemoriesRequest) -> FrozenCopyMemoriesPlan:
        request = validate_copy_request(request)
        frames = self._frames()
        into = _target_frame(
            frames,
            request.into_locator,
            current_name=self._current_name,
        )
        if request.uid_policy == "FRESH":
            # FRESH means a new direct-item identity in the complete local
            # store, not merely a key absent from this Target. Same-UID branch
            # copies remain an explicit PRESERVE concern.
            occupied = {
                uid
                for frame in frames
                for uid in frame.context.memories
            }
            generated: list[str] = []
            while len(generated) < len(request.memory_locators):
                candidate = str(uuid.uuid4())
                if candidate not in occupied and candidate not in generated:
                    generated.append(candidate)
            output_uids = tuple(generated)
        else:
            # Resolve first using temporary one-to-one placeholders; the exact
            # Source UIDs become the reviewed Copy outputs below.
            output_uids = tuple("pending" for _ in request.memory_locators)
        memories = self._resolved_sources(
            request.memory_locators,
            source_locator=request.source_locator,
            frames=frames,
            output_uids=output_uids,
        )
        if request.uid_policy == "PRESERVE":
            memories = tuple(
                FrozenTransferMemory(
                    source_context_name=item.source_context_name,
                    source_context_uid=item.source_context_uid,
                    source_context_digest=item.source_context_digest,
                    source_memory_uid=item.source_memory_uid,
                    content=item.content,
                    output_memory_uid=item.source_memory_uid,
                )
                for item in memories
            )
        collisions = tuple(
            item.output_memory_uid
            for item in memories
            if item.output_memory_uid in into.context.memories
        )
        if collisions:
            raise MemoryTransferError(
                "Copy would reuse direct-item UID(s) already present in Target "
                f"'{into.context.name}': "
                + ", ".join(f"[{uid[:8]}]" for uid in collisions)
                + ". Use the default fresh-UID policy."
            )
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
            policy=request.uid_policy,
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
                context_catalog=tuple(frame.context.name for frame in frames),
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
        frames = self._frames()
        into = _target_frame(
            frames,
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
                context_catalog=tuple(frame.context.name for frame in frames),
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
        frames = {frame.context.name: frame for frame in token.frames}
        into = frames[plan.into_name]
        for offset, item in enumerate(plan.memories):
            into.context.add(
                Memory(uid=item.output_memory_uid, content=item.content),
                position=plan.placement.position + offset,
            )
        affected = (into,)
        description = (
            f"Copied {len(plan.memories)} Memory/ies into "
            f"'{plan.into_name}' with {plan.request.uid_policy.lower()} UIDs."
        )
        args = _checkpoint_args(
            kind="COPY",
            operation_uid=token.operation_uid,
            plan_digest=plan.plan_digest,
            policy_name="uid_policy",
            policy=plan.request.uid_policy,
            into=into,
            placement=plan.placement,
            memories=plan.memories,
            inbound_links=(),
            affected_frames=affected,
        )
        source_frames = _unique_source_frames(plan.memories, frames)
        try:
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
            uid_policy=plan.request.uid_policy,
            placement=plan.placement,
            items=self._items(plan.memories),
            plan_digest=plan.plan_digest,
            checkpoints=receipts,
        )

    def apply_move(self, plan: FrozenMoveMemoriesPlan) -> MoveMemoriesResult:
        token = self._token(plan)
        frames = {frame.context.name: frame for frame in token.frames}
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
                # the Memory transfer; immutable snapshots remain untouched.
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


def execute_copy(
    request: CopyMemoriesRequest,
    *,
    store: MemoryStore,
) -> CopyMemoriesResult:
    return run_copy(request, port=MemoryStoreMemoryTransferPort.capture(store))


def execute_move(
    request: MoveMemoriesRequest,
    *,
    store: MemoryStore,
) -> MoveMemoriesResult:
    return run_move(request, port=MemoryStoreMemoryTransferPort.capture(store))


__all__ = [
    "MemoryStoreMemoryTransferPort",
    "execute_copy",
    "execute_move",
]
