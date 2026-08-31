"""Operation-owned immutable persistence for Ground Fit reports."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import uuid

from memcommit.application.operations.quality_resolution.validate.fit.ground_report import FitError, FitReport
from memcommit.application.operations.ground.workspace_model import GroundWorkspace
from memcommit.application.operations.ground.workspace_fit import (
    load_ground_workspace_fit_contexts,
    workspace_fit_report_is_current,
)
from memcommit.application.operations.ground.workspace_runtime import (
    load_ground_workspace,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class GroundFitReceipt:
    """The newest receipt for one Ground and whether it still describes it."""

    report: FitReport
    current: bool


class FitStore:
    """Create-only Fit reports; Ground mutation makes a receipt stale, not mutable."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.directory = store.store_dir / "ground-fit-receipts"

    def _path(self, uid: str) -> Path:
        try:
            canonical = str(uuid.UUID(uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise FitError("Invalid Fit report uid.") from error
        if canonical != uid:
            raise FitError("Invalid Fit report uid.")
        return self.directory / f"{uid}.json"

    def path(self, uid: str) -> Path:
        return self._path(uid)

    def save(self, report: FitReport) -> None:
        """Publish once only while the frozen Ground revision remains exact."""

        restored = FitReport.from_dict(report.to_dict())
        path = self._path(restored.uid)
        with self.store._context_graph_lock(exclusive=False):  # noqa: SLF001
            workspace = load_ground_workspace(self.store, restored.ground_name)
            context_scope = load_ground_workspace_fit_contexts(
                self.store,
                workspace,
            )
            lock_names = (
                workspace.root.name,
                workspace.goals.name,
                workspace.rules.name,
                workspace.examples.name,
                *(context.name for context in context_scope),
            )
            with self.store._context_write_locks(lock_names):  # noqa: SLF001
                with self.store.profile_write_guard():
                    if not workspace_fit_report_is_current(
                        self.store,
                        restored,
                    ):
                        raise FitError(
                            "The consumed Ground workspace Memories changed "
                            "before its Fit receipt could be saved."
                        )
                    self._write_new_report(restored, path)

    def _write_new_report(self, report: FitReport, path: Path) -> None:
        """Create one immutable report while the caller owns freshness locks."""

        if self.directory.exists() and (
            not self.directory.is_dir() or self.directory.is_symlink()
        ):
            raise FitError("Fit receipt storage is invalid.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.exists() or path.is_symlink():
            raise FitError("A Fit receipt with this uid already exists.")
        temporary = self.directory / f".{path.name}.write-{uuid.uuid4().hex}"
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def load(self, uid: str) -> FitReport:
        path = self._path(uid)
        if not path.is_file() or path.is_symlink():
            raise FitError(f"Fit receipt '{uid}' was not found.")
        try:
            with open(path, encoding="utf-8") as handle:
                return FitReport.from_dict(
                    json.load(handle, object_pairs_hook=_strict_json_object)
                )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise FitError("Saved Fit receipt is invalid.") from error

    def list(self, *, ground_uid: str | None = None) -> tuple[FitReport, ...]:
        if not self.directory.exists():
            if self.directory.is_symlink():
                raise FitError("Fit receipt storage is invalid.")
            return ()
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise FitError("Fit receipt storage is invalid.")
        reports: list[FitReport] = []
        for path in self.directory.iterdir():
            if path.name.startswith(".") and ".json.write-" in path.name:
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise FitError("Fit receipt storage is invalid.")
            report = self.load(path.stem)
            if ground_uid is None or report.ground_uid == ground_uid:
                reports.append(report)
        return tuple(sorted(reports, key=lambda item: (item.created_at, item.uid)))

    def latest_for_workspace(
        self,
        workspace: GroundWorkspace,
    ) -> GroundFitReceipt | None:
        reports = self.list(ground_uid=workspace.uid)
        if not reports:
            return None
        report = reports[-1]
        return GroundFitReceipt(
            report=report,
            current=workspace_fit_report_is_current(self.store, report),
        )


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
