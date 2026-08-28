"""MemoryStore and Grant infrastructure adapter for Add."""

from __future__ import annotations

import hashlib

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.add.application import (
    AddedMemory,
    AddRequest,
    AddResult,
    AddTargetPort,
    FrozenAddTarget,
    run_add,
)
from memcommit.application.capabilities.authority.access import (
    authorized_context_mutation,
    grant_checkpoint_args,
    resolve_context_access,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store import ConcurrentContextUpdateError


class _StoreAddTargetToken:
    def __init__(self, access):
        self.access = access


def _source_record(request: AddRequest) -> dict[str, str]:
    source = request.source
    return {
        "kind": source.kind,
        "parser": source.parser,
        "sha256": hashlib.sha256(source.raw_text.encode("utf-8")).hexdigest(),
        "raw_text": source.raw_text,
    }


def _checkpoint_args(
    request: AddRequest,
    *,
    memory_uids: list[str],
    access,
) -> dict[str, object]:
    source = request.source
    contents = list(request.contents)
    common = {
        "memory_uids": memory_uids,
        "source": _source_record(request),
        **grant_checkpoint_args(access),
    }
    if source.mode == "SINGLE":
        return {
            "content": contents[0],
            **common,
        }
    if source.mode == "PASTE":
        return {
            "mode": "paste",
            "count": len(contents),
            "contents": contents,
            **common,
        }
    if source.mode == "LINES":
        return {
            "input": source.input_name,
            "mode": "lines",
            "count": len(contents),
            "contents": contents,
            **common,
        }
    return {
        "mode": "explicit" if source.mode == "EXPLICIT_BATCH" else "tui-drafts",
        "count": len(contents),
        "contents": contents,
        **common,
    }


def _checkpoint_description(request: AddRequest) -> str:
    source = request.source
    if source.mode == "SINGLE":
        return f'Added: "{request.contents[0][:80]}"'
    if source.mode == "PASTE":
        return f"Added {len(request.contents)} memories from interactive paste"
    if source.mode == "LINES":
        origin = "stdin" if source.input_name == "-" else repr(source.input_name)
        return f"Added {len(request.contents)} memories from {origin}"
    if source.mode == "EXPLICIT_BATCH":
        return f"Added {len(request.contents)} explicitly supplied memories"
    return f"Added {len(request.contents)} memories from interactive drafts"


class MemoryStoreAddTargetPort(AddTargetPort):
    """Commit Add against one current-Context snapshot and exact target CAS."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        current_name: str | None,
        local_only: bool = False,
    ):
        self._store = store
        # Relative target meaning must not drift if another process switches
        # the global current Context while this request is being composed.
        self._current_name = current_name
        self._local_only = local_only

    @classmethod
    def capture(cls, store: MemoryStore) -> "MemoryStoreAddTargetPort":
        return cls(store, current_name=store.current_context_name())

    def freeze(self, context_locator: str | None) -> FrozenAddTarget:
        if self._local_only:
            operand = context_locator or self._current_name
            if operand is None:
                raise RuntimeError("No current context. Run 'mem init <name>' first.")
            canonical = resolve_context_locator(operand, current=self._current_name)
            if not self._store.context_exists(canonical):
                raise FileNotFoundError(f"Context {canonical!r} not found.")
        access = resolve_context_access(
            self._store,
            context_locator,
            current_name=self._current_name,
            required_permission="CREATE",
        )
        context = access.store.load_direct(access.context_name)
        return FrozenAddTarget(
            context_name=access.display_name,
            context_uid=context.uid,
            token=_StoreAddTargetToken(access),
        )

    def append(
        self,
        target: FrozenAddTarget,
        request: AddRequest,
    ) -> AddResult:
        token = target.token
        if not isinstance(token, _StoreAddTargetToken):
            raise ValueError("The frozen Add target binding is invalid.")
        access = token.access
        store = access.store
        context = store.load_direct(access.context_name)
        if context.uid != target.context_uid:
            open_surface = "paste mode" if request.source.mode == "PASTE" else "Add"
            raise ConcurrentContextUpdateError(
                f"Context '{target.context_name}' was replaced while "
                f"{open_surface} was open; "
                "no changes were made."
            )
        memories = ops.add_many(context, list(request.contents))
        with authorized_context_mutation(access):
            checkpoint = store.save(
                context,
                AutoCheckpoint(
                    command="add",
                    args=_checkpoint_args(
                        request,
                        memory_uids=[memory.uid for memory in memories],
                        access=access,
                    ),
                    description=_checkpoint_description(request),
                ),
            )
        if checkpoint is None:
            raise RuntimeError("Add saved no checkpoint.")
        return AddResult(
            context_name=access.display_name,
            context_uid=context.uid,
            memories=tuple(
                AddedMemory(uid=memory.uid, content=memory.content)
                for memory in memories
            ),
            checkpoint_uid=checkpoint.uid,
        )


def execute_add(request: AddRequest, *, store: MemoryStore) -> AddResult:
    """Execute Add against a real Store with no terminal or provider output."""

    return run_add(
        request,
        target_port=MemoryStoreAddTargetPort.capture(store),
    )
