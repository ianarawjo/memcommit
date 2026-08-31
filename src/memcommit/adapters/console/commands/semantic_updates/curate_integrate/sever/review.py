"""Sever-owned projection and loader for ``mem review sever``."""

from __future__ import annotations

from memcommit.adapters.console.commands.operation_lifecycle.review.report import show_operation_review
from memcommit.adapters.console.commands.operation_lifecycle.review.sessions import select_report_session
from memcommit.adapters.console.commands.semantic_updates.curate_integrate.sever.sessions import (
    list_sever_session_catalog,
    reload_selected_sever_session,
)
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.operation_lifecycle.review.model import ReviewError
from memcommit.application.operations.semantic_updates.curate_integrate.sever.model import SeverSession
from memcommit.application.operations.semantic_updates.curate_integrate.sever.resolution_adapter import (
    SeverResolutionWorkbenchAdapter,
)
from memcommit.application.operations.semantic_updates.curate_integrate.sever.session_store import SeverSessionStore
from memcommit.persistence.store import MemoryStore


def sever_review_report(session: SeverSession) -> ReviewReportController:
    """Expose content-severing decisions and the proposed local result."""

    result_boundary = (
        "The retained local Result has already been created; this Review "
        "does not create or apply it again."
        if session.state == "APPLIED"
        else "Review leaves the Source unchanged and creates no result Context."
    )
    return ReviewReportController.from_resolution(
        SeverResolutionWorkbenchAdapter(session).view,
        kind="CONTENT_SEVERING",
        title="MEM REVIEW · SEVER",
        summary=(
            "Review what the local result keeps, rewrites, or forgets. "
            + result_boundary
        ),
    )


def open_sever_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    sessions = SeverSessionStore(store)
    catalog = list_sever_session_catalog(sessions)
    by_key = {entry.picker_entry.key: entry for entry in catalog}
    selected = select_report_session(
        tuple(entry.picker_entry for entry in catalog),
        kind="sever",
        title="MEM REVIEW · SEVER REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = reload_selected_sever_session(sessions, by_key[selected.key])
    if session.state != "APPLIED":
        raise ReviewError(
            "Sever execution is not complete. Resume it with 'mem sever'; "
            "Review opens only terminal application evidence."
        )
    show_operation_review(sever_review_report(session), snapshot=snapshot)


__all__ = ["open_sever_review", "sever_review_report"]
