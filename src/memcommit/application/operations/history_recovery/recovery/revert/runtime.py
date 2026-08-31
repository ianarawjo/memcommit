"""MemoryStore binding for the Revert application boundary."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from memcommit.application.capabilities.checkpoint_catalog import (
    ResolvedCheckpointUnit,
    freeze_checkpoint_catalog,
)
from memcommit.application.operations.history_recovery.recovery.revert.restoration import (
    CheckpointRestoration,
    restore_checkpoint_unit,
)
from memcommit.application.operations.history_recovery.recovery.revert.application import (
    RevertRequest,
    run_revert,
)
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore


class MemoryStoreRevertPort:
    """Adapt retained-history restoration to one concrete Profile store."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def restore(self, request: RevertRequest) -> CheckpointRestoration:
        return restore_checkpoint_unit(
            self._store,
            request.unit,
            keep_history=request.keep_history,
        )


def resolve_revert_unit(
    store: MemoryStore,
    selector: str,
    *,
    context_name: str | None = None,
    expected_context_uid: str | None = None,
    expected_context_digest: str | None = None,
    expected_history_digest: str | None = None,
    expected_checkpoint: Mapping[str, Any] | None = None,
) -> ResolvedCheckpointUnit:
    """Resolve and optionally bind one Revert unit to a reviewed local frame."""

    unit = freeze_checkpoint_catalog(store).resolve(
        selector,
        context_name=context_name,
    )
    if any(
        value is not None
        for value in (
            expected_context_uid,
            expected_context_digest,
            expected_history_digest,
            expected_checkpoint,
        )
    ):
        if len(unit.members) != 1:
            raise ConcurrentContextUpdateError(
                "The selected checkpoint changed while selection was open."
            )
        member = unit.members[0]
        if (
            (expected_context_uid is not None and member.context_uid != expected_context_uid)
            or (
                expected_context_digest is not None
                and member.expected_context_digest != expected_context_digest
            )
            or (
                expected_history_digest is not None
                and member.expected_history_digest != expected_history_digest
            )
            or (
                expected_checkpoint is not None
                and member.checkpoint != dict(expected_checkpoint)
            )
        ):
            raise ConcurrentContextUpdateError(
                "The Context or checkpoint history changed while selection was open."
            )
    return unit


def execute_revert(
    store: MemoryStore,
    request: RevertRequest,
) -> CheckpointRestoration:
    """Execute one Revert through its application port."""

    return run_revert(request, port=MemoryStoreRevertPort(store))
