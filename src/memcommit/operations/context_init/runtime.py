"""Production Store composition for ordinary Context initialization."""

from __future__ import annotations

from dataclasses import dataclass

import memcommit.ops as ops
from memcommit.context import AutoCheckpoint
from memcommit.context_targeting.naming import validate_portable_context_name
from memcommit.operations.context_init.application import (
    ContextInitError,
    ContextInitPlan,
    ContextInitRequest,
    ContextInitResult,
    CreatedContext,
    run_context_init,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class ContextInitSnapshot:
    """Process-local setup state frozen before optional interactive name editing."""

    expected_current: str | None
    context_names: tuple[str, ...]


def prepare_context_init(store: MemoryStore) -> ContextInitSnapshot:
    """Capture the current pointer and local namespace once for one command turn."""

    return ContextInitSnapshot(
        expected_current=store.current_context_name(),
        context_names=tuple(store.list_context_names()),
    )


class MemoryStoreContextInitPort:
    """Publish the application plan through Store locking and rollback."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def apply(self, plan: ContextInitPlan) -> tuple[CreatedContext, ...]:
        validate_portable_context_name(plan.request.name)
        if plan.require_all_new and self._store.context_exists(plan.request.name):
            raise ContextInitError(
                f"context '{plan.request.name}' already exists."
            )
        entries = tuple(
            (
                ops.init(entry.name),
                AutoCheckpoint(
                    command="init",
                    args=entry.checkpoint_args,
                    description=entry.checkpoint_description,
                ),
            )
            for entry in plan.entries
        )
        created = self._store.create_missing_contexts(
            entries,
            make_current=plan.request.name,
            require_all_new=plan.require_all_new,
            expected_current=plan.request.expected_current,
        )
        return tuple(
            CreatedContext(name=context.name, uid=context.uid)
            for context in created
        )


def execute_context_init(
    request: ContextInitRequest,
    *,
    store: MemoryStore,
) -> ContextInitResult:
    """Execute one ordinary Context initialization without terminal output."""

    return run_context_init(
        request,
        port=MemoryStoreContextInitPort(store),
    )
