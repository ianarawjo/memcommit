"""Sync requests, document bindings, successful baselines and committed receipts."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from memcommit.application.capabilities.import_export.model import (
    DocumentSourceRange,
    ExportFileEffect,
    ExportPlan,
    ProjectDocumentSnapshot,
)


@dataclass(frozen=True)
class SyncRequest:
    source: str | None = None
    recursive: bool = False
    all_contexts: bool = False
    destination: Path | None = None
    discover_documents: bool = False


@dataclass(frozen=True)
class SyncSelection:
    names: tuple[str, ...]
    root_name: str | None
    scope: str
    inventory: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SyncConnection:
    context_uid: str
    context_name: str
    base: dict[str, str]
    paths: tuple[str, ...]
    directories: tuple[str, ...] = ()
    member_names: tuple[str, ...] = ()
    recursive: bool = False


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


@dataclass(frozen=True)
class SyncIssue:
    code: str
    path: str
    message: str
    memory_uids: tuple[str, ...] = ()
    byte_ranges: tuple[tuple[int, int], ...] = ()


class SyncConflictError(ValueError):
    def __init__(self, issue: SyncIssue):
        self.issue = issue
        super().__init__(f"{issue.path}: {issue.message}")


@dataclass(frozen=True)
class SyncVersionConflict:
    context_uids: tuple[str, ...]
    paths: tuple[str, ...]


class SyncConflictChoiceRequired(ValueError):
    """A whole-version choice is needed before any Sync mutation."""


class SyncCancelled(Exception):
    """The person cancelled a read-only Sync choice."""


@dataclass(frozen=True)
class SyncPlan:
    selection: SyncSelection
    exports: tuple[ExportPlan, ...]
    connections: tuple[SyncConnection, ...]
    baselines: tuple[tuple[str, SyncBaseline], ...]
    inbound_changes: tuple[InboundContextChange, ...] = ()
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
    snapshot: ProjectDocumentSnapshot
    before_records: tuple[dict, ...]
    changes: tuple[SyncContextChange, ...]
    memory_effects: tuple[SyncMemoryEffect, ...]
    renamed_files: tuple[tuple[str, str, int], ...]
    excluded_names: tuple[str, ...]


@dataclass(frozen=True)
class SyncResult:
    context_names: tuple[str, ...]
    effects: tuple[ExportFileEffect, ...] = ()
    run_uid: str | None = None
    checkpoint_uids: tuple[tuple[str, str], ...] = ()
    memory_effects: tuple[SyncMemoryEffect, ...] = ()
    direction: str = "outbound"
    inbound_paths: tuple[str, ...] = ()
    context_effects: tuple[tuple[str, str, str | None], ...] = ()
    conflict_choice: str | None = None
    revert_checkpoint_uids: tuple[tuple[str, str], ...] = ()


class SyncSettingsPort(Protocol):
    def load(self) -> dict: ...
    def save(self, record: dict, *, expected_revision: int) -> dict: ...


class SyncPort(Protocol):
    settings: SyncSettingsPort

    def execution_boundary(self) -> AbstractContextManager: ...
    def freeze_selection(self, request: SyncRequest) -> SyncSelection: ...
    def prepare_plan(self, request, selection, settings) -> SyncPlan: ...
    def publish_profile_changes(self, plan, request, settings) -> SyncResult: ...
