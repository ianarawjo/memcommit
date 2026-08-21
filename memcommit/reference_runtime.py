"""MemoryStore infrastructure for immutable Memory or Context References."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import uuid

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.context_snapshot import (
    CONTEXT_SNAPSHOT_SCHEMA_VERSION,
    ContextSnapshotRef,
    context_snapshot_digest,
    snapshot_record_with_frozen_memory_embeds,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.reference_application import (
    ContextReferenceRequest,
    ContextReferenceResult,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    ReferenceError,
    ReferencePort,
    ReferenceRequest,
    ReferenceResult,
    run_context_reference,
    run_reference,
    validate_context_reference_request,
    validate_reference_request,
)
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _LocalReferenceToken:
    owner: object


class MemoryStoreReferencePort(ReferencePort):
    """Freeze and publish one local Memory or Context snapshot."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        self._current_name = current_name
        self._owner = object()

    @property
    def current_context_name(self) -> str | None:
        return self._current_name

    @property
    def local_context_names(self) -> tuple[str, ...]:
        return tuple(self._store.list_context_names())

    def inspect_local_context(self, name: str):
        """Load one local direct frame for read-only interactive projection."""

        canonical = self._canonical(name)
        if not self._store.context_exists(canonical):
            raise FileNotFoundError(f"Context '{canonical}' does not exist.")
        return self._store.load_direct(canonical)

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreReferencePort":
        return cls(store, current_name=store.current_context_name())

    def _canonical(self, locator: str) -> str:
        return resolve_context_locator(locator, current=self._current_name)

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        request = validate_reference_request(request)
        source_name = self._canonical(request.source_locator)
        target_locator = request.into_locator or self._current_name
        if target_locator is None:
            raise ReferenceError(
                "No current Context. Pass --into or initialize a Context first."
            )
        into_name = self._canonical(target_locator)
        for name in (source_name, into_name):
            if not self._store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        source = self._store.load_direct(source_name)
        target = self._store.load_for_update(into_name)
        item = ops.resolve(source, request.memory_selector)
        if not isinstance(item, Memory):
            raise TypeError(
                f"'{request.memory_selector}' is not a directly owned Memory "
                f"in '{source_name}'."
            )
        return FrozenReferencePlan(
            request=request,
            source_name=source_name,
            source_uid=source.uid,
            source_digest=context_record_digest(source),
            memory_uid=item.uid,
            memory_content=item.content,
            memory_content_sha256=hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest(),
            into_name=into_name,
            into_uid=target.uid,
            into_digest=context_record_digest(target),
            token=_LocalReferenceToken(self._owner),
        )

    def _context_snapshot_package(
        self,
        source_name: str,
        *,
        recursive: bool,
    ) -> tuple[
        dict[str, object],
        tuple[tuple[str, str, str], ...],
    ]:
        """Freeze local direct records selected by lexical and Embed reach."""

        all_names = tuple(
            sorted(self._store.list_context_names(), key=str.casefold)
        )
        lexical_names = expand_lexical_context_names(
            ContextScope.create(
                (source_name,),
                include_descendants=recursive,
            ),
            all_names,
        )
        queue = list(lexical_names)
        records: dict[str, dict[str, object]] = {}
        bindings: dict[str, tuple[str, str, str]] = {}
        index = 0
        while index < len(queue):
            name = queue[index]
            index += 1
            if name in records:
                continue
            direct = self._store.load_direct(name)
            resolved = self._store.load(name)
            records[name] = snapshot_record_with_frozen_memory_embeds(
                direct,
                resolved,
            )
            bindings[name] = (
                name,
                direct.uid,
                context_record_digest(direct),
            )
            for item in direct.iter_items():
                if isinstance(item, MemoryRef) and item.is_live:
                    owner_name = item.target_context_name
                    if self._store.context_exists(owner_name):
                        owner = self._store.load_direct(owner_name)
                        if owner.uid == item.target_context_uid:
                            bindings.setdefault(
                                owner_name,
                                (
                                    owner_name,
                                    owner.uid,
                                    context_record_digest(owner),
                                ),
                            )
                elif (
                    recursive
                    and isinstance(item, Context)
                    and item._granted_link is None
                    and self._store.context_exists(item.name)
                ):
                    embedded = self._store.load_direct(item.name)
                    if embedded.uid == item.uid and item.name not in records:
                        queue.append(item.name)

        root = self._store.load_direct(source_name)
        package: dict[str, object] = {
            "schema_version": CONTEXT_SNAPSHOT_SCHEMA_VERSION,
            "root": {"uid": root.uid, "name": source_name},
            "recursive": recursive,
            "lexical_context_names": list(lexical_names),
            # Root-first discovery order is stable and preserves the difference
            # between lexical scope and later Embed-reached additions.
            "contexts": [records[name] for name in records],
        }
        return package, tuple(bindings.values())

    def freeze_context(
        self,
        request: ContextReferenceRequest,
    ) -> FrozenContextReferencePlan:
        request = validate_context_reference_request(request)
        source_name = self._canonical(request.source_locator)
        target_locator = request.into_locator or self._current_name
        if target_locator is None:
            raise ReferenceError(
                "No current Context. Pass --into or initialize a Context first."
            )
        into_name = self._canonical(target_locator)
        if source_name == into_name:
            raise ReferenceError(
                "Context Reference Source and Target must be distinct Contexts."
            )
        for name in (source_name, into_name):
            if not self._store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        package, source_bindings = self._context_snapshot_package(
            source_name,
            recursive=request.include_descendants,
        )
        if any(name == into_name for name, _uid, _digest in source_bindings):
            raise ReferenceError(
                "Context Reference Target cannot be inside its frozen Source scope."
            )
        target = self._store.load_for_update(into_name)
        root = package["root"]
        assert isinstance(root, dict)
        digest = context_snapshot_digest(package)
        if any(
            isinstance(item, ContextSnapshotRef)
            and item.target_context_uid == root["uid"]
            and item.snapshot_content_sha256 == digest
            for item in target.iter_items()
        ):
            raise ReferenceError(
                f"Context '{source_name}' already has this exact snapshot in "
                f"'{into_name}'."
            )
        return FrozenContextReferencePlan(
            request=request,
            source_name=source_name,
            source_uid=str(root["uid"]),
            source_bindings=source_bindings,
            snapshot_package=package,
            snapshot_content_sha256=digest,
            into_name=into_name,
            into_uid=target.uid,
            into_digest=context_record_digest(target),
            token=_LocalReferenceToken(self._owner),
        )

    def apply(self, plan: FrozenReferencePlan) -> ReferenceResult:
        token = plan.token
        if (
            not isinstance(token, _LocalReferenceToken)
            or token.owner is not self._owner
        ):
            raise ValueError("The frozen Reference plan belongs to another runtime.")
        source = self._store.load_direct(plan.source_name)
        target = self._store.load_for_update(plan.into_name)
        if (
            source.uid != plan.source_uid
            or context_record_digest(source) != plan.source_digest
        ):
            raise RuntimeError(
                "The Source Context changed after the Reference was frozen."
            )
        if (
            target.uid != plan.into_uid
            or context_record_digest(target) != plan.into_digest
        ):
            raise RuntimeError(
                "The Target Context changed after the Reference was frozen."
            )
        item = source.memories.get(plan.memory_uid)
        if not isinstance(item, Memory):
            raise RuntimeError("The frozen Source Memory is no longer available.")
        digest = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
        if item.content != plan.memory_content or digest != plan.memory_content_sha256:
            raise RuntimeError(
                "The Source Memory changed after the Reference was frozen."
            )
        reference = ops.reference_memory(item, source, target)
        checkpoint = self._store.save_context_with_sources(
            target,
            AutoCheckpoint(
                command="reference",
                args={
                    "reference_uid": reference.uid,
                    "source": plan.source_name,
                    "source_uid": plan.source_uid,
                    "memory_uid": plan.memory_uid,
                    "memory_content_sha256": plan.memory_content_sha256,
                    "into": plan.into_name,
                    "snapshot": True,
                },
                description=(
                    f"Referenced snapshot [{plan.memory_uid[:8]}] from "
                    f"'{plan.source_name}' as [{reference.uid[:8]}] in "
                    f"'{plan.into_name}'"
                ),
            ),
            expected_context_digest=plan.into_digest,
            source_bindings=((plan.source_name, plan.source_uid, plan.source_digest),),
        )
        if checkpoint is None:
            raise RuntimeError("Reference saved no checkpoint.")
        return ReferenceResult(
            reference_uid=reference.uid,
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            memory_uid=plan.memory_uid,
            memory_content_sha256=plan.memory_content_sha256,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            checkpoint_uid=checkpoint.uid,
        )

    def apply_context(
        self,
        plan: FrozenContextReferencePlan,
    ) -> ContextReferenceResult:
        token = plan.token
        if (
            not isinstance(token, _LocalReferenceToken)
            or token.owner is not self._owner
        ):
            raise ValueError(
                "The frozen Context Reference plan belongs to another runtime."
            )
        target = self._store.load_for_update(plan.into_name)
        if (
            target.uid != plan.into_uid
            or context_record_digest(target) != plan.into_digest
        ):
            raise RuntimeError(
                "The Target Context changed after the Context Reference was frozen."
            )
        reference = ContextSnapshotRef(
            uid=str(uuid.uuid4()),
            target_context_uid=plan.source_uid,
            target_context_name=plan.source_name,
            snapshot_package=plan.snapshot_package,
            snapshot_content_sha256=plan.snapshot_content_sha256,
        )
        ops.reference_context(reference, target)
        context_count = len(plan.snapshot_package["contexts"])
        checkpoint = self._store.save_context_with_sources(
            target,
            AutoCheckpoint(
                command="reference",
                args={
                    "kind": "context",
                    "reference_uid": reference.uid,
                    "source": plan.source_name,
                    "source_uid": plan.source_uid,
                    "snapshot_content_sha256": plan.snapshot_content_sha256,
                    "into": plan.into_name,
                    "snapshot": True,
                    "include_descendants": plan.request.include_descendants,
                    "follow_embeds": plan.request.follow_embeds,
                    "context_count": context_count,
                },
                description=(
                    f"Referenced {'recursive' if plan.request.include_descendants else 'direct'} "
                    f"Context snapshot '{plan.source_name}' as "
                    f"[{reference.uid[:8]}] in '{plan.into_name}'"
                ),
            ),
            expected_context_digest=plan.into_digest,
            source_bindings=plan.source_bindings,
        )
        if checkpoint is None:
            raise RuntimeError("Context Reference saved no checkpoint.")
        return ContextReferenceResult(
            reference_uid=reference.uid,
            source_name=plan.source_name,
            source_uid=plan.source_uid,
            snapshot_content_sha256=plan.snapshot_content_sha256,
            include_descendants=plan.request.include_descendants,
            follow_embeds=plan.request.follow_embeds,
            context_count=context_count,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            checkpoint_uid=checkpoint.uid,
        )


def execute_reference(
    request: ReferenceRequest,
    *,
    store: MemoryStore,
) -> ReferenceResult:
    """Execute one local snapshot Reference with no terminal dependency."""

    port = MemoryStoreReferencePort.capture(store)
    return run_reference(request, port=port)


def execute_context_reference(
    request: ContextReferenceRequest,
    *,
    store: MemoryStore,
) -> ContextReferenceResult:
    """Execute one local Context snapshot with no terminal dependency."""

    port = MemoryStoreReferencePort.capture(store)
    return run_context_reference(request, port=port)


__all__ = [
    "MemoryStoreReferencePort",
    "execute_context_reference",
    "execute_reference",
]
