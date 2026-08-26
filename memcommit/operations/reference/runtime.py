"""MemoryStore infrastructure for immutable Memory or Context References."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import uuid

import memcommit.ops as ops
from memcommit.authority.access import (
    ContextAccess,
    authorized_context_operation,
    granted_memory_source,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Context, Memory, MemoryRef
from memcommit.retained_history.context_snapshot import (
    CONTEXT_SNAPSHOT_SCHEMA_VERSION,
    ContextSnapshotRef,
    context_snapshot_digest,
    snapshot_record_with_frozen_memory_embeds,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.model import ContextScope
from memcommit.context_targeting.resolution import expand_lexical_context_names
from memcommit.authority.derived_policy import (
    authorize_analysis_save,
    authorize_derived_transfer,
)
from memcommit.operations.reference.application import (
    ContextReferenceRequest,
    ContextReferenceResult,
    FrozenContextReferencePlan,
    FrozenReferencePlan,
    GRANTED_MEMORY_REFERENCE_PERMISSIONS,
    ReferenceError,
    ReferencePort,
    ReferenceRequest,
    ReferenceResult,
    run_context_reference,
    run_reference,
    validate_context_reference_request,
    validate_reference_request,
)
from memcommit.profile_config import profile_store_dir
from memcommit.profiles import authority_grant_snapshot_lock
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _LocalReferenceToken:
    """Bind one frozen Memory snapshot to its exact Source authority."""

    owner: object
    source_access: ContextAccess | None = None


class MemoryStoreReferencePort(ReferencePort):
    """Freeze and publish one local Memory or Context snapshot."""

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

    @property
    def current_context_name(self) -> str | None:
        return self._current_name

    @property
    def store(self) -> MemoryStore:
        """Expose the active Store for read-only TUI catalog freezing."""

        return self._store

    @property
    def allows_granted_sources(self) -> bool:
        """Report whether this runtime may consult active Profile Grants."""

        return self._allow_granted_sources

    @property
    def local_context_names(self) -> tuple[str, ...]:
        return tuple(self._store.list_context_names())

    def inspect_local_context(self, name: str):
        """Load one local direct frame for read-only interactive projection."""

        canonical = self._canonical(name)
        if not self._store.context_exists(canonical):
            raise FileNotFoundError(f"Context '{canonical}' does not exist.")
        return self._store.load_direct(canonical)

    def authorize_memory_source(self, locator: str) -> ContextAccess:
        """Resolve one exact Memory-Reference Source without opening content.

        The TUI freezes public Grant rows before rendering, but visibility is
        not authority to export and retain their bytes.  Reusing the runtime's
        exact permission bundle keeps picker eligibility aligned with Freeze
        and deliberately does not search granted Contexts by Memory UID.
        """

        access = self._source_access(locator)
        with authorized_context_operation(
            ((access, GRANTED_MEMORY_REFERENCE_PERMISSIONS),)
        ):
            return access

    def inspect_memory_source(self, locator: str) -> Context:
        """Load one authorized direct Source frame under its public name."""

        access = self._source_access(locator)
        with authorized_context_operation(
            ((access, GRANTED_MEMORY_REFERENCE_PERMISSIONS),)
        ):
            context = access.store.load_direct(access.context_name)
        # Provider-private names are not valid operands in the grantee's TUI.
        # The loaded object is a process-local snapshot, so relabelling it does
        # not mutate either Store and keeps later selection explicitly public.
        context.name = access.display_name
        return context

    @classmethod
    def capture(
        cls,
        store: MemoryStore,
        *,
        allow_granted_sources: bool = False,
    ) -> "MemoryStoreReferencePort":
        return cls(
            store,
            current_name=store.current_context_name(),
            allow_granted_sources=allow_granted_sources,
        )

    def _canonical(self, locator: str) -> str:
        return resolve_context_locator(locator, current=self._current_name)

    def _source_access(self, locator: str) -> ContextAccess:
        if not self._allow_granted_sources:
            local_name = self._canonical(locator)
            if not self._store.context_exists(local_name):
                raise FileNotFoundError(f"Context '{local_name}' does not exist.")
            return ContextAccess(
                store=self._store,
                context_name=local_name,
                display_name=local_name,
                attachment_name=None,
                permission="READ",
            )
        return resolve_context_access(
            self._store,
            locator,
            current_name=self._current_name,
            required_permission="READ",
        )

    def _local_target_access(self, name: str) -> ContextAccess:
        return ContextAccess(
            store=self._store,
            context_name=name,
            display_name=name,
            attachment_name=None,
            permission="CREATE",
        )

    def _freeze_memory_source(
        self,
        locator: str,
        *,
        target_access: ContextAccess,
    ) -> tuple[ContextAccess, Context]:
        """Resolve, authorize, and read one Source in a single Grant snapshot."""

        local_name = self._canonical(locator)
        if self._store.context_exists(local_name):
            access = self._source_access(locator)
            authorize_derived_transfer(access, target_access)
            authorize_analysis_save((access,), retention="RETAINED")
            return access, access.store.load_direct(access.context_name)
        if not self._allow_granted_sources:
            raise FileNotFoundError(f"Context '{local_name}' does not exist.")

        # Resolving a public name before taking the Profile lock leaves a gap
        # where its Grant can be downgraded before authority bytes are opened.
        # Freeze the current registry revision through resolution, every
        # retained-output permission check, and the exact direct Source read.
        with authority_grant_snapshot_lock() as registry:
            if self._store.store_dir.resolve() != profile_store_dir(
                registry.active
            ).resolve():
                raise FileNotFoundError(f"Context '{local_name}' does not exist.")
            access = resolve_context_access(
                self._store,
                locator,
                current_name=self._current_name,
                required_permission="READ",
                registry=registry,
            )
            authorize_derived_transfer(access, target_access)
            authorize_analysis_save((access,), retention="RETAINED")
            source = access.store.load_direct(access.context_name)
        return access, source

    def freeze(self, request: ReferenceRequest) -> FrozenReferencePlan:
        request = validate_reference_request(request)
        target_locator = request.into_locator or self._current_name
        if target_locator is None:
            raise ReferenceError(
                "No current Context. Pass --into or initialize a Context first."
            )
        into_name = self._canonical(target_locator)
        if not self._store.context_exists(into_name):
            raise FileNotFoundError(
                f"Target Context '{into_name}' does not exist locally."
            )

        # A Reference is retained after its Grant disappears. Validate the
        # export and retention permissions in the same Grant snapshot used to
        # open authority content.
        target_access = self._local_target_access(into_name)
        source_access, source = self._freeze_memory_source(
            request.source_locator,
            target_access=target_access,
        )
        source_name = source_access.display_name
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
            token=_LocalReferenceToken(self._owner, source_access),
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
        local_frames: dict[str, Context] = {}

        def local_frame(name: str) -> Context:
            """Load one local record once for both retained bytes and CAS."""

            if name not in local_frames:
                local_frames[name] = self._store.load_direct(name)
            return local_frames[name]

        index = 0
        while index < len(queue):
            name = queue[index]
            index += 1
            if name in records:
                continue
            direct = local_frame(name)
            # A no-loader round trip retains granted Context/Memory edges as
            # content-free typed placeholders. Ordinary local Memory links are
            # selectively resolved below from their one cached owner frame.
            resolved = Context.from_dict(direct.to_dict())
            bindings[name] = (
                name,
                direct.uid,
                context_record_digest(direct),
            )
            for uid, item in direct.iter_entries():
                if (
                    isinstance(item, MemoryRef)
                    and item.is_live
                    and not item.is_granted
                ):
                    owner_name = item.target_context_name
                    if self._store.context_exists(owner_name):
                        owner = local_frame(owner_name)
                        if owner.uid == item.target_context_uid:
                            bindings.setdefault(
                                owner_name,
                                (
                                    owner_name,
                                    owner.uid,
                                    context_record_digest(owner),
                                ),
                            )
                            target_memory = owner.memories.get(
                                item.target_memory_uid
                            )
                            if isinstance(target_memory, Memory):
                                resolved.memories[uid] = MemoryRef.from_dict(
                                    item.to_dict(),
                                    target=target_memory,
                                )
                elif (
                    recursive
                    and isinstance(item, Context)
                    and item._granted_link is None
                    and self._store.context_exists(item.name)
                ):
                    embedded = local_frame(item.name)
                    if embedded.uid == item.uid and item.name not in records:
                        queue.append(item.name)
            records[name] = snapshot_record_with_frozen_memory_embeds(
                direct,
                resolved,
            )

        root = local_frame(source_name)
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
        target = self._store.load_for_update(plan.into_name)
        if (
            target.uid != plan.into_uid
            or context_record_digest(target) != plan.into_digest
        ):
            raise RuntimeError(
                "The Target Context changed after the Reference was frozen."
            )
        access = token.source_access
        if access is None:
            raise ValueError("The frozen Reference plan has no Source authority.")

        def prepare_snapshot(source: Context) -> tuple[MemoryRef, AutoCheckpoint]:
            if (
                source.uid != plan.source_uid
                or context_record_digest(source) != plan.source_digest
            ):
                raise RuntimeError(
                    "The Source Context changed after the Reference was frozen."
                )
            item = source.memories.get(plan.memory_uid)
            if not isinstance(item, Memory):
                raise RuntimeError(
                    "The frozen Source Memory is no longer available."
                )
            digest = hashlib.sha256(item.content.encode("utf-8")).hexdigest()
            if (
                item.content != plan.memory_content
                or digest != plan.memory_content_sha256
            ):
                raise RuntimeError(
                    "The Source Memory changed after the Reference was frozen."
                )
            # Persist the public Grant name, never the authority-private
            # locator, as the snapshot's historical Source coordinate.
            public_source = Context(uid=source.uid, name=plan.source_name)
            public_source.add(item)
            reference = ops.reference_memory(item, public_source, target)
            granted_source = None
            if access.is_granted:
                granted_source = granted_memory_source(
                    access,
                    context_uid=source.uid,
                    memory_uid=item.uid,
                )
                reference.granted_source = granted_source
            checkpoint_args: dict[str, object] = {
                "reference_uid": reference.uid,
                "source": plan.source_name,
                "source_uid": plan.source_uid,
                "memory_uid": plan.memory_uid,
                "memory_content_sha256": plan.memory_content_sha256,
                "into": plan.into_name,
                "snapshot": True,
            }
            if granted_source is not None:
                checkpoint_args["granted_source"] = granted_source.to_dict()
            return reference, AutoCheckpoint(
                command="reference",
                args=checkpoint_args,
                description=(
                    f"Referenced snapshot [{plan.memory_uid[:8]}] from "
                    f"'{plan.source_name}' as [{reference.uid[:8]}] in "
                    f"'{plan.into_name}'"
                ),
            )

        if access.is_granted:
            # Keep both the Grant and the authority bytes stable through the
            # local commit. The resulting snapshot is intentionally retained
            # and performs no reauthorization on later reads.
            with authorized_context_operation(
                ((access, GRANTED_MEMORY_REFERENCE_PERMISSIONS),)
            ):
                with access.store.locked_context_snapshot(
                    access.context_name,
                    expected_uid=plan.source_uid,
                    expected_digest=plan.source_digest,
                ) as source:
                    reference, checkpoint_record = prepare_snapshot(source)
                    checkpoint = self._store.save(
                        target,
                        checkpoint_record,
                        expected_context_digest=plan.into_digest,
                    )
        else:
            source = access.store.load_direct(access.context_name)
            reference, checkpoint_record = prepare_snapshot(source)
            checkpoint = self._store.save_context_with_sources(
                target,
                checkpoint_record,
                expected_context_digest=plan.into_digest,
                source_bindings=(
                    (
                        access.context_name,
                        plan.source_uid,
                        plan.source_digest,
                    ),
                ),
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
    allow_granted_sources: bool = False,
) -> ReferenceResult:
    """Execute one local snapshot Reference with no terminal dependency."""

    port = MemoryStoreReferencePort.capture(
        store,
        allow_granted_sources=allow_granted_sources,
    )
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
