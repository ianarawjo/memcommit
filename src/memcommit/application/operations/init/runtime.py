"""Production Store composition for ordinary Context initialization."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.models.context import Context
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.core.context_name_validation import validate_context_name
from memcommit.application.operations.init.application import (
    ContextInitError,
    ContextInitPlan,
    ContextInitRequest,
    ContextInitResult,
    CreatedContext,
    run_context_init,
)
from memcommit.persistence.store import ProfileStore


@dataclass(frozen=True)
class ContextInitSnapshot:
    """Current Context captured before one Init request."""

    expected_current: str | None


def prepare_context_init(store: ProfileStore) -> ContextInitSnapshot:
    """Capture the current pointer once for one command turn."""

    return ContextInitSnapshot(
        expected_current=store.current_context_name(),
    )


class MemoryStoreContextInitPort:
    """Publish the application plan through Store locking and rollback."""

    def __init__(self, store: ProfileStore):
        self._store = store

    def apply(self, plan: ContextInitPlan) -> tuple[CreatedContext, ...]:
        validate_context_name(plan.request.name)
        if plan.require_all_new and self._store.context_exists(plan.request.name):
            raise ContextInitError(f"context '{plan.request.name}' already exists.")
        entries = tuple(
            (
                Context.create(entry.name),
                AutoCheckpointRequest(
                    command="init",
                    command_details=entry.checkpoint_command_details,
                ),
            )
            for entry in plan.entries
            if not plan.require_all_new or entry.is_leaf
        )
        created = self._store.create_missing_contexts(
            entries,
            make_current=plan.request.name,
            require_all_new=plan.require_all_new,
            expected_current=plan.request.expected_current,
        )
        return tuple(
            CreatedContext(name=context.name, uid=context.uid) for context in created
        )


def execute_context_init(
    request: ContextInitRequest,
    *,
    store: ProfileStore,
) -> ContextInitResult:
    """Execute one ordinary Context initialization without terminal output."""

    return run_context_init(
        request,
        port=MemoryStoreContextInitPort(store),
    )
