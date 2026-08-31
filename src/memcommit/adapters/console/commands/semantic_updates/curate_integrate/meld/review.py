"""Meld-owned projection and loader for ``mem review meld``."""

from __future__ import annotations

from memcommit.adapters.console.commands.semantic_updates.curate_integrate.meld.sessions import (
    list_meld_session_catalog,
    reload_selected_meld_session,
)
from memcommit.adapters.console.commands.operation_lifecycle.review.report import show_operation_review
from memcommit.adapters.console.commands.operation_lifecycle.review.sessions import select_report_session
from memcommit.adapters.console.terminal.components.operation_launcher.session import (
    SessionPickerEntry,
)
from memcommit.adapters.console.terminal.components.peer_relations.presentation import (
    render_peer_relation_analysis,
)
from memcommit.application.capabilities.reviewing.report import ReviewReportController
from memcommit.application.operations.semantic_updates.curate_integrate.meld.model import MeldSession
from memcommit.application.operations.semantic_updates.curate_integrate.meld.proposal_projection import (
    MeldResolutionWorkbenchAdapter,
)
from memcommit.application.operations.operation_lifecycle.review.model import ReviewError
from memcommit.persistence.store import MemoryStore


def meld_review_report(session: MeldSession) -> ReviewReportController:
    """Expose Meld analysis, issues, and proposals without its Apply capability."""

    compare_text = ""
    if session.mode == "SYMMETRIC" and session.relation_analysis_seed is not None:
        compare_text = (
            render_peer_relation_analysis(
                session.relation_analysis_seed.analysis,
                reused=True,
                durable=True,
                heading="MEM COMPARE · SYMMETRIC PEERS",
            )
            .partition("\nThe complete source-linked relation ledger")[0]
            .rstrip()
        )
    return ReviewReportController.from_resolution(
        MeldResolutionWorkbenchAdapter(session).view,
        kind="RESOLUTION",
        title="MEM REVIEW · MELD",
        summary=(
            "Review the saved Meld assessment and proposed target Memories. "
            "Applying the target remains outside Review."
        ),
        report_text=compare_text,
    )


def open_meld_review(
    store: MemoryStore,
    *,
    session_uid: str | None,
    snapshot: bool,
) -> None:
    catalog = list_meld_session_catalog(store)
    by_key = {entry.session_uid: entry for entry in catalog}
    entries = tuple(
        SessionPickerEntry(
            kind="meld",
            key=entry.session_uid,
            title=entry.title,
            status=entry.status,
            subtitle=entry.subtitle,
            group=entry.group,
            sort_timestamp=entry.modified_timestamp,
            detail=entry.detail,
            reopen_argv=entry.reopen_argv,
        )
        for entry in catalog
    )
    selected = select_report_session(
        entries,
        kind="meld",
        title="MEM REVIEW · MELD REPORTS",
        session_uid=session_uid,
    )
    if selected is None:
        return
    session = reload_selected_meld_session(store, by_key[selected.key])
    if session.state != "APPLIED":
        raise ReviewError(
            "Meld execution is not complete. Resume it with 'mem meld'; "
            "Review opens only terminal application evidence."
        )
    show_operation_review(meld_review_report(session), snapshot=snapshot)


__all__ = ["meld_review_report", "open_meld_review"]
