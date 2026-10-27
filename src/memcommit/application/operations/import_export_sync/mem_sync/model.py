"""Sync document comparison, change plans and committed receipts."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.operations.import_export_sync.common.model import (
    DocumentSourceRange,
    ExportFileEffect,
    ExportPlan,
    ProjectDocumentSnapshot,
)


@dataclass(frozen=True)
class SyncBaseline:
    """Process-local document comparison value reconstructed from checkpoints."""

    source_digest: str
    files: tuple[tuple[str, bytes], ...]
    members: tuple[dict, ...] = ()
    source_ranges: tuple[tuple[str, tuple[DocumentSourceRange, ...]], ...] = ()


@dataclass(frozen=True)
class SyncMemoryEffect:
    context_name: str
    memory_uid: str | None
    action: str


@dataclass(frozen=True)
class InboundContextChange:
    before: dict
    after: dict
    paths: tuple[str, ...]
    effects: tuple[SyncMemoryEffect, ...]


class SyncConflictError(ValueError):
    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}")


@dataclass(frozen=True)
class SyncVersionConflict:
    context_uids: tuple[str, ...]


class SyncConflictChoiceRequired(ValueError):
    """A whole-version choice is needed before any Sync mutation."""


class SyncCancelled(Exception):
    """The person cancelled a read-only Sync choice."""


@dataclass(frozen=True)
class SyncPlan:
    exports: tuple[ExportPlan, ...]
    baselines: tuple[tuple[str, SyncBaseline], ...]
    profile_changes: ProfileDocumentChanges | None = None
    conflicts: tuple[SyncVersionConflict, ...] = ()
    conflict_choice: str | None = None


@dataclass(frozen=True)
class SyncContextChange:
    before: dict | None
    after: dict | None
    action: str
    paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProfileDocumentChanges:
    snapshot: ProjectDocumentSnapshot | None
    before_records: tuple[dict, ...]
    changes: tuple[SyncContextChange, ...]
    memory_effects: tuple[SyncMemoryEffect, ...]
    excluded_names: tuple[str, ...]


@dataclass(frozen=True)
class SyncResult:
    context_names: tuple[str, ...]
    effects: tuple[ExportFileEffect, ...] = ()
    run_uid: str | None = None
    checkpoint_uids: tuple[tuple[str, str], ...] = ()
    memory_effects: tuple[SyncMemoryEffect, ...] = ()
    direction: str = "outbound"
    context_effects: tuple[tuple[str, str, str | None], ...] = ()
    conflict_choice: str | None = None
