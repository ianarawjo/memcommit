"""MemoryStore infrastructure adapter for the local Embed use case."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.ops as ops
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
    """Mark a frozen plan as owned by this local Store adapter instance."""

    owner: object


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
    """Freeze and commit one local Embed against exact source and target CAS."""

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
    def current_context_name(self) -> str | None:
        return self._current_name

    def inspect_local_context(self, name: str) -> Context:
        """Load one local direct-order preview without changing it."""

        return self._store.load_direct(name)

    def _canonical_name(self, locator: str) -> str:
        return resolve_context_locator(locator, current=self._current_name)

    def _freeze_loaded(
        self,
        *,
        request: EmbedRequest,
        child: Context,
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
        ops.validate_embed(child, parent, position=placement.position)
        return FrozenEmbedPlan(
            request=request,
            child_name=child.name,
            child_uid=child.uid,
            child_digest=context_record_digest(child),
            into_name=parent.name,
            into_uid=parent.uid,
            into_digest=context_record_digest(parent),
            placement=placement,
            item_count=len(ordered_uids),
            token=_LocalEmbedToken(self._owner),
        )

    def freeze(self, request: EmbedRequest) -> FrozenEmbedPlan:
        request = validate_embed_request(request)
        child_name = self._canonical_name(request.child_locator)
        into_name = self._canonical_name(request.into_locator)
        for name in (child_name, into_name):
            if not self._store.context_exists(name):
                raise FileNotFoundError(f"Context '{name}' does not exist.")
        child = self._store.load_direct(child_name)
        parent = self._store.load_for_update(into_name)
        placement = _placement_for_context(
            parent,
            before=request.before,
            after=request.after,
        )
        return self._freeze_loaded(
            request=request,
            child=child,
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
        child = self._store.load_direct(child_name)
        parent = self._store.load_for_update(into_name)
        return self._freeze_loaded(
            request=request,
            child=child,
            parent=parent,
            placement=placement,
        )

    def apply(self, plan: FrozenEmbedPlan) -> EmbedResult:
        token = plan.token
        if not isinstance(token, _LocalEmbedToken) or token.owner is not self._owner:
            raise ValueError("The frozen Embed plan belongs to another runtime.")
        child = self._store.load_direct(plan.child_name)
        parent = self._store.load_for_update(plan.into_name)
        if (
            child.uid != plan.child_uid
            or context_record_digest(child) != plan.child_digest
        ):
            raise RuntimeError(
                "The Child Context changed after the exact Embed command was reviewed."
            )
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
        ops.embed(child, parent, position=plan.placement.position)
        checkpoint = self._store.save_context_with_sources(
            parent,
            AutoCheckpoint(
                command="embed",
                args={
                    "child": plan.child_name,
                    "into": plan.into_name,
                    "position": plan.placement.position,
                    "after_uid": plan.placement.previous_uid,
                    "before_uid": plan.placement.next_uid,
                },
                description=(
                    f"Embedded '{plan.child_name}' into '{plan.into_name}' "
                    f"{_gap_description(plan.placement)}"
                ),
            ),
            expected_context_digest=plan.into_digest,
            source_bindings=(
                (plan.child_name, plan.child_uid, plan.child_digest),
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
