"""MemoryStore and Grant infrastructure adapter for Embed."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.ops as ops
from memcommit.authority.access import (
    ContextAccess,
    authorized_context_operation,
    grant_checkpoint_args,
    granted_context_link,
    resolve_context_access,
)
from memcommit.context import AutoCheckpoint, Context
from memcommit.context_locator import resolve_context_locator
from memcommit.embed_application import (
    EmbedPlacement,
    EmbedPort,
    EmbedRequest,
    EmbedResult,
    FrozenEmbedPlan,
    run_embed,
    validate_embed_request,
)
from memcommit.store import MemoryStore, context_record_digest


@dataclass(frozen=True)
class _LocalEmbedToken:
    """Bind a frozen plan to this runtime and its exact source authority."""

    owner: object
    source_access: ContextAccess


def _placement_for_context(
    parent: Context,
    *,
    before: str | None,
    after: str | None,
) -> EmbedPlacement:
    if before is not None and after is not None:
        raise ValueError("Pass only one of --before or --after.")
    ordered_uids = parent.ordered_uids()
    if before is None and after is None:
        position = len(ordered_uids)
    else:
        selector = before if before is not None else after
        assert selector is not None
        anchor = ops.resolve(parent, selector)
        position = ordered_uids.index(anchor.uid) + (1 if after is not None else 0)
    return EmbedPlacement(
        position=position,
        previous_uid=ordered_uids[position - 1] if position else None,
        next_uid=ordered_uids[position] if position < len(ordered_uids) else None,
    )


def _placement_selectors(
    placement: EmbedPlacement,
) -> tuple[str | None, str | None]:
    """Encode a reviewed gap with one stable adjacent direct-item identity."""

    if placement.next_uid is not None:
        return placement.next_uid, None
    if placement.previous_uid is not None:
        return None, placement.previous_uid
    return None, None


def _gap_description(placement: EmbedPlacement) -> str:
    if placement.previous_uid is not None and placement.next_uid is not None:
        return (
            f"between [{placement.previous_uid[:8]}] "
            f"and [{placement.next_uid[:8]}]"
        )
    if placement.next_uid is not None:
        return f"before [{placement.next_uid[:8]}] at the start"
    if placement.previous_uid is not None:
        return f"after [{placement.previous_uid[:8]}] at the end"
    return "as the only direct item"


class MemoryStoreEmbedPort(EmbedPort):
    """Freeze and commit local or granted Child into one owned local target."""

    def __init__(self, store: MemoryStore, *, current_name: str | None):
        self._store = store
        # Relative Child and Into locators share one command-start snapshot.
        self._current_name = current_name
        self._owner = object()

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreEmbedPort":
        return cls(store, current_name=store.current_context_name())

    @property
    def local_context_names(self) -> tuple[str, ...]:
        return tuple(self._store.list_context_names())

    @property
    def store(self) -> MemoryStore:
        """Expose the composed active Store to presentation catalog adapters."""

        return self._store

    @property
    def current_context_name(self) -> str | None:
        return self._current_name

    def inspect_local_context(self, name: str) -> Context:
        """Load one local direct-order preview without changing it."""

        return self._store.load_direct(name)

    def _canonical_local_name(self, locator: str) -> str:
        return resolve_context_locator(locator, current=self._current_name)

    def _source_access(self, locator: str) -> ContextAccess:
        return resolve_context_access(
            self._store,
            locator,
            current_name=self._current_name,
            required_permission="EMBED",
        )

    @staticmethod
    def _source_snapshot(access: ContextAccess) -> tuple[Context, Context]:
        """Return raw identity bytes and the public Context used for validation."""

        raw = access.store.load_direct(access.context_name)
        public = Context(uid=raw.uid, name=access.display_name)
        return raw, public

    def _freeze_loaded(
        self,
        *,
        request: EmbedRequest,
        child_record: Context,
        public_child: Context,
        source_access: ContextAccess,
        parent: Context,
        placement: EmbedPlacement,
    ) -> FrozenEmbedPlan:
        ordered_uids = parent.ordered_uids()
        expected = EmbedPlacement(
            position=placement.position,
            previous_uid=(
                ordered_uids[placement.position - 1]
                if placement.position
                else None
            ),
            next_uid=(
                ordered_uids[placement.position]
                if placement.position < len(ordered_uids)
                else None
            ),
        )
        if placement != expected:
            raise RuntimeError(
                "The reviewed Embed insertion gap does not match the target order."
            )
        ops.validate_embed(public_child, parent, position=placement.position)
        return FrozenEmbedPlan(
            request=request,
            child_name=public_child.name,
            child_uid=child_record.uid,
            child_digest=context_record_digest(child_record),
            into_name=parent.name,
            into_uid=parent.uid,
            into_digest=context_record_digest(parent),
            placement=placement,
            item_count=len(ordered_uids),
            token=_LocalEmbedToken(self._owner, source_access),
        )

    def freeze(self, request: EmbedRequest) -> FrozenEmbedPlan:
        request = validate_embed_request(request)
        source_access = self._source_access(request.child_locator)
        into_name = self._canonical_local_name(request.into_locator)
        if not self._store.context_exists(into_name):
            raise FileNotFoundError(
                f"Embed target Context '{into_name}' does not exist locally."
            )
        child_record, public_child = self._source_snapshot(source_access)
        parent = self._store.load_for_update(into_name)
        placement = _placement_for_context(
            parent,
            before=request.before,
            after=request.after,
        )
        return self._freeze_loaded(
            request=request,
            child_record=child_record,
            public_child=public_child,
            source_access=source_access,
            parent=parent,
            placement=placement,
        )

    def freeze_exact_gap(
        self,
        child_name: str,
        into_name: str,
        placement: EmbedPlacement,
    ) -> FrozenEmbedPlan:
        """Freeze the exact canonical gap reviewed by the interactive adapter."""

        before, after = _placement_selectors(placement)
        request = EmbedRequest(
            child_locator=child_name,
            into_locator=into_name,
            before=before,
            after=after,
        )
        source_access = self._source_access(child_name)
        into_name = self._canonical_local_name(into_name)
        if not self._store.context_exists(into_name):
            raise FileNotFoundError(
                f"Embed target Context '{into_name}' does not exist locally."
            )
        child_record, public_child = self._source_snapshot(source_access)
        parent = self._store.load_for_update(into_name)
        return self._freeze_loaded(
            request=request,
            child_record=child_record,
            public_child=public_child,
            source_access=source_access,
            parent=parent,
            placement=placement,
        )

    def apply(self, plan: FrozenEmbedPlan) -> EmbedResult:
        token = plan.token
        if not isinstance(token, _LocalEmbedToken) or token.owner is not self._owner:
            raise ValueError("The frozen Embed plan belongs to another runtime.")
        parent = self._store.load_for_update(plan.into_name)
        if (
            parent.uid != plan.into_uid
            or context_record_digest(parent) != plan.into_digest
        ):
            raise RuntimeError(
                "The Into Context or its direct-item order changed after the "
                "insertion gap was reviewed."
            )
        before, after = _placement_selectors(plan.placement)
        rebuilt = _placement_for_context(parent, before=before, after=after)
        if rebuilt != plan.placement:
            raise RuntimeError(
                "The reviewed Embed insertion gap no longer resolves to the "
                "same direct-item neighbors."
            )
        access = token.source_access
        checkpoint_args = {
            "child": plan.child_name,
            "into": plan.into_name,
            "position": plan.placement.position,
            "after_uid": plan.placement.previous_uid,
            "before_uid": plan.placement.next_uid,
            **grant_checkpoint_args(access),
        }
        checkpoint_record = AutoCheckpoint(
            command="embed",
            args=checkpoint_args,
            description=(
                f"Embedded '{plan.child_name}' into '{plan.into_name}' "
                f"{_gap_description(plan.placement)}"
            ),
        )
        if access.is_granted:
            # The registry lock closes revoke-after-check, while the authority
            # source lock keeps the reviewed identity exact through local CAS.
            with authorized_context_operation(((access, ("EMBED",)),)):
                with access.store.locked_context_snapshot(
                    access.context_name,
                    expected_uid=plan.child_uid,
                    expected_digest=plan.child_digest,
                ) as source_record:
                    child = Context(uid=source_record.uid, name=plan.child_name)
                    child._granted_link = granted_context_link(
                        access,
                        context_uid=source_record.uid,
                    )
                    ops.embed(child, parent, position=plan.placement.position)
                    checkpoint = self._store.save(parent, checkpoint_record)
        else:
            child = access.store.load_direct(access.context_name)
            if (
                child.uid != plan.child_uid
                or context_record_digest(child) != plan.child_digest
            ):
                raise RuntimeError(
                    "The Child Context changed after the exact Embed command "
                    "was reviewed."
                )
            child.name = plan.child_name
            ops.embed(child, parent, position=plan.placement.position)
            checkpoint = self._store.save_context_with_sources(
                parent,
                checkpoint_record,
                expected_context_digest=plan.into_digest,
                source_bindings=(
                    (access.context_name, plan.child_uid, plan.child_digest),
                ),
            )
        if checkpoint is None:
            raise RuntimeError("Embed saved no checkpoint.")
        return EmbedResult(
            child_name=plan.child_name,
            child_uid=plan.child_uid,
            into_name=plan.into_name,
            into_uid=plan.into_uid,
            placement=plan.placement,
            checkpoint_uid=checkpoint.uid,
        )


def execute_embed(
    request: EmbedRequest,
    *,
    store: MemoryStore,
) -> EmbedResult:
    """Execute local Embed with no terminal or provider dependency."""

    port = MemoryStoreEmbedPort.capture(store)
    return run_embed(request, port=port)
