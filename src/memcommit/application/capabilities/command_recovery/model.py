"""Typed command units and restoration receipts shared by Undo and Redo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.core.context import Checkpoint


RestoreDirection = Literal["undo", "redo"]


class CommandHistoryError(RuntimeError):
    """Retained checkpoints do not describe a safe command stack."""


@dataclass(frozen=True)
class CommandContextChange:
    """One direct Context's pre/post image in an entered command."""

    context_uid: str
    context_name: str
    before: dict[str, object] | None
    after: dict[str, object] | None
    checkpoint_uid: str


@dataclass(frozen=True)
class ContextCommandUnit:
    """One recoverable entered command, possibly spanning Contexts."""

    uid: str
    command: str
    description: str
    started_at: str
    completed_at: str
    changes: tuple[CommandContextChange, ...]
    checkpoint_args: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class CommandStacks:
    undo: tuple[ContextCommandUnit, ...]
    redo: tuple[ContextCommandUnit, ...]


@dataclass(frozen=True)
class CommandRestoreResult:
    unit: ContextCommandUnit
    direction: RestoreDirection
    receipt_uid: str
    checkpoints: tuple[Checkpoint, ...]


@dataclass(frozen=True)
class BranchTreeContext:
    """One Source-to-target identity mapping in a Branch command receipt."""

    source_uid: str
    source_name: str
    target_uid: str
    target_name: str


@dataclass(frozen=True)
class BranchTreeReceipt:
    """Frozen lifecycle identity for one exact or recursive Branch."""

    operation_uid: str
    source_root: str
    target_root: str
    include_descendants: bool
    current_before: str | None
    contexts: tuple[BranchTreeContext, ...]


__all__ = [
    "BranchTreeContext",
    "BranchTreeReceipt",
    "CommandContextChange",
    "CommandHistoryError",
    "CommandRestoreResult",
    "CommandStacks",
    "ContextCommandUnit",
    "RestoreDirection",
]
