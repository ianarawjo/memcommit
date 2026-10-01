"""Update-owned projection and loader for ``mem review update``."""

from __future__ import annotations

from memcommit.adapters.console.commands.review.report import show_operation_review
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.review.model import ReviewError
from memcommit.application.operations.update.model import UpdateReceipt
from memcommit.persistence.operations.update.receipt_repository import (
    UpdateReceiptRepository,
)
from memcommit.adapters.console.commands.update.presentation import (
    UpdateResolutionWorkbenchAdapter,
)
from memcommit.core.context_targeting.uid_locator import (
    UidLocatorError,
    resolve_exact_or_unique_uid,
)
from memcommit.persistence.store import MemoryStore


def update_review_report(receipt: UpdateReceipt) -> ReviewReportController:
    """Keep Update's existing exact change-detail report as Review material."""

    return ReviewReportController.from_resolution(
        UpdateResolutionWorkbenchAdapter(
            receipt.inputs, receipt.plan, completed=True
        ).view,
        kind="CHANGE_PLAN",
        title="MEM REVIEW · UPDATE",
        summary=(
            "Review exact ADD, EDIT, and REMOVE details, reasons, owners, and "
            "source references. This completed evidence cannot be applied again from Review."
        ),
    )


def open_update_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    retained = UpdateReceiptRepository(store).list()
    if not retained:
        raise ReviewError("No completed Update receipt exists.")
    try:
        receipt = (
            retained[0]
            if session_uid is None
            else resolve_exact_or_unique_uid(
                retained, session_uid, uid=lambda item: item.uid, label="Update receipt"
            )
        )
    except UidLocatorError as error:
        raise ReviewError(str(error)) from error
    show_operation_review(update_review_report(receipt), snapshot=snapshot)


__all__ = ["open_update_review", "update_review_report"]
