"""Immutable, Ground-revision-bound persistence for Fit reports."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import json
import os
from pathlib import Path
import uuid

from memcommit.fit import FitError, FitReport
from memcommit.ground import GroundSession, context_frame_digest
from memcommit.store import MemoryStore, ground_session_record_digest


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
        # Fit publication shares the Ground lock and, for v2, every exact
        # Context input lock so no mutation can land between freshness
        # validation and this receipt.
        with ExitStack() as locks:
            if restored.coherence is not None:
                # Context inputs are part of a v2 receipt. Preserve the Store's
                # graph -> Context -> Ground -> profile lock order so a Context
                # edit cannot race between revalidation and receipt publication.
                locks.enter_context(  # noqa: SLF001
                    self.store._context_graph_lock(exclusive=False)
                )
                locks.enter_context(  # noqa: SLF001
                    self.store._context_write_locks(
                        item.name for item in restored.coherence.contexts
                    )
                )
            locks.enter_context(  # noqa: SLF001
                self.store._ground_session_write_lock(restored.ground_name)
            )
            locks.enter_context(self.store.profile_write_guard())
            current = self.store.load_ground_session(restored.ground_name)
            if current is None or not _report_is_current(
                restored,
                current,
                store=self.store,
            ):
                raise FitError(
                    "The Ground or a bound Context changed before its Fit "
                    "receipt could be saved."
                )
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
                    json.dump(restored.to_dict(), handle, ensure_ascii=False, indent=2)
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

    def latest_for_ground(self, session: GroundSession) -> GroundFitReceipt | None:
        reports = self.list(ground_uid=session.uid)
        if not reports:
            return None
        report = reports[-1]
        return GroundFitReceipt(
            report=report,
            current=_report_is_current(report, session, store=self.store),
        )


def _report_is_current(
    report: FitReport,
    session: GroundSession,
    *,
    store: MemoryStore | None = None,
) -> bool:
    ground_current = (
        report.ground_uid == session.uid
        and report.ground_name == session.contract_name
        and report.ground_revision == session.revision
        and report.ground_digest == ground_session_record_digest(session)
    )
    if not ground_current or report.coherence is None:
        return ground_current
    if store is None:
        return False
    report_by_name = {
        context.name: context for context in report.coherence.contexts
    }
    if set(report_by_name) != {frame.context_name for frame in session.frames}:
        return False
    frame_by_name = {frame.context_name: frame for frame in session.frames}
    try:
        for name, reported in report_by_name.items():
            frame = frame_by_name[name]
            current = store.load_direct(name)
            if (
                current.uid != frame.context_uid
                or current.uid != reported.uid
                or context_frame_digest(current) != frame.context_digest
                or frame.context_digest != reported.digest
            ):
                return False
    except (FileNotFoundError, OSError, ValueError):
        return False
    return True


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result
