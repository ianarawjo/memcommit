"""Update-owned projection and loader for ``mem review update``."""

from __future__ import annotations

from memcommit.adapters.console.commands.review.report import show_operation_review
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.review.model import ReviewError
from memcommit.application.operations.update.model import UpdateSession
from memcommit.persistence.operations.update.receipt_repository import (
    UpdateReceiptRepository,
)
from memcommit.adapters.console.commands.update.workbench.presentation import (
    UpdateResolutionWorkbenchAdapter,
)
from memcommit.core.context_targeting.uid_locator import (
    UidLocatorError,
    resolve_exact_or_unique_uid,
)
from memcommit.persistence.store import MemoryStore


def update_review_report(session: UpdateSession) -> ReviewReportController:
    """Keep Update's existing exact change-detail report as Review material."""

    return ReviewReportController.from_resolution(
        UpdateResolutionWorkbenchAdapter(session).view,
        kind="CHANGE_PLAN",
        title="MEM REVIEW · UPDATE",
        summary=(
            "Review exact ADD, EDIT, and REMOVE details, reasons, owners, and "
            "source references. Applying the staged plan remains outside Review."
        ),
    )


def open_update_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    current = store.load_staged_update() or store.load_impact_plan()
    retained = UpdateReceiptRepository(store).list()
    if current is None and not retained:
        raise ReviewError(
            "No saved Update or Impact plan exists. Run 'mem impact' first."
        )
    if session_uid is None:
        session = current or retained[0]
    else:
        candidates = retained
        if current is not None and current.uid not in {
            candidate.uid for candidate in retained
        }:
            candidates = (*retained, current)
        try:
            session = resolve_exact_or_unique_uid(
                candidates,
                session_uid,
                uid=lambda candidate: candidate.uid,
                label="Saved Update artifact",
            )
        except UidLocatorError as error:
            raise ReviewError(str(error)) from error
    if session.status not in {"applied", "undone"}:
        raise ReviewError(
            "Update execution is not complete. Resume it with 'mem update'; "
            "Review opens only terminal application evidence."
        )
    show_operation_review(update_review_report(session), snapshot=snapshot)


__all__ = ["open_update_review", "update_review_report"]
