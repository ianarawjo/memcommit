"""Execution mechanics for restoring an exact checkpoint unit."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.checkpoint_catalog import (
    CheckpointUnitRevertResult,
    ResolvedCheckpointUnit,
)
from memcommit.core.context import Checkpoint
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class SingleCheckpointRestoration:
    """Result of restoring one ordinary physical checkpoint."""

    context_name: str
    recovery: Checkpoint
    target: Checkpoint


@dataclass(frozen=True)
class RecursiveCheckpointRestoration:
    """Result of atomically restoring one recursive checkpoint unit."""

    result: CheckpointUnitRevertResult


CheckpointRestoration = SingleCheckpointRestoration | RecursiveCheckpointRestoration


def restore_checkpoint_unit(
    store: MemoryStore,
    unit: ResolvedCheckpointUnit,
    *,
    keep_history: bool,
) -> CheckpointRestoration:
    """Restore one frozen physical or recursive checkpoint unit."""

    if not unit.members:
        raise ValueError("Checkpoint recovery unit has no members.")
    if not unit.is_recursive_set:
        if len(unit.members) != 1:
            raise ValueError("A direct checkpoint recovery unit must have one member.")
        member = unit.members[0]
        recovery, target = store.revert(
            member.context_name,
            member.checkpoint_uid,
            keep_history=keep_history,
            expected_context_uid=member.context_uid,
            expected_context_digest=member.expected_context_digest,
            expected_history_digest=member.expected_history_digest,
        )
        return SingleCheckpointRestoration(
            context_name=member.context_name,
            recovery=recovery,
            target=target,
        )
    return RecursiveCheckpointRestoration(
        result=store.revert_checkpoint_unit(unit, keep_history=keep_history)
    )


__all__ = [
    "CheckpointRestoration",
    "RecursiveCheckpointRestoration",
    "SingleCheckpointRestoration",
    "restore_checkpoint_unit",
]
