"""Sync requests, document bindings, successful baselines and committed receipts."""

from dataclasses import dataclass
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from memcommit.application.capabilities.import_export.model import (
    ExportFileEffect,
    ExportPlan,
)
from memcommit.application.capabilities.import_export.export_documents import (
    ExportPublicationPort,
)


@dataclass(frozen=True)
class SyncRequest:
    source: str | None = None
    recursive: bool = False
    all_contexts: bool = False
    toggle_always: bool = False
    # Application-only exact automatic selection; argv never supplies this.
    selected_names: tuple[str, ...] | None = None
    automatic: bool = False
    causing_command: str | None = None
    destination: Path | None = None


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
    source_digest: str
    files: tuple[tuple[str, bytes], ...]


@dataclass(frozen=True)
class SyncPlan:
    selection: SyncSelection
    exports: tuple[ExportPlan, ...]
    connections: tuple[SyncConnection, ...]
    baselines: tuple[tuple[str, SyncBaseline], ...]


@dataclass(frozen=True)
class AutomaticSyncChange:
    enabled: bool
    context_names: tuple[str, ...]
    newly_enabled: int = 0
    already_enabled: int = 0


@dataclass(frozen=True)
class SyncResult:
    context_names: tuple[str, ...]
    effects: tuple[ExportFileEffect, ...] = ()
    automatic_change: AutomaticSyncChange | None = None
    run_uid: str | None = None
    automatic: bool = False
    error: str | None = None


class SyncSettingsPort(Protocol):
    def load(self) -> dict: ...
    def save(self, record: dict, *, expected_revision: int) -> dict: ...


class SyncPort(Protocol):
    settings: SyncSettingsPort

    def execution_boundary(self) -> AbstractContextManager: ...
    def freeze_selection(self, request: SyncRequest) -> SyncSelection: ...
    def prepare_plan(self, request, selection, settings) -> SyncPlan: ...
    def agreement_changed(self, plan: SyncPlan) -> bool: ...
    def publisher_for(self, export: ExportPlan) -> ExportPublicationPort: ...
    def begin_publication(self, plan: SyncPlan, run_uid: str) -> None: ...
    def finish_publication(
        self, plan, settings, policies, result, causing_command
    ) -> None: ...
    def record_failure(self, selection, settings, error: str) -> None: ...
