"""Interactive console entry from one typed finding into Resolve."""

from __future__ import annotations

from memcommit.adapters.console.clipboard import write_system_clipboard
from memcommit.adapters.console.commands.resolve.receipt import render_resolve_receipt
from memcommit.adapters.console.commands.resolve.workbench import run_resolve_tui
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
)
from memcommit.application.operations.resolve.application import (
    run_resolve,
)
from memcommit.application.operations.resolve.decisions import (
    apply_resolve_update,
    plan_resolve_update,
)
from memcommit.application.operations.resolve.finding_handoff import (
    conflict_handoff_to_resolve_request,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
    all_audit_issue_keys,
)
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import connect_semantic_provider


def run_conflict_resolve_handoff(
    store: MemoryStore,
    *,
    current_name: str | None,
    handoff: QualityFindingHandoff,
) -> None:
    """Open normal Resolve review for one freshly revalidated finding."""

    request = conflict_handoff_to_resolve_request(handoff)
    port = MemoryStoreResolvePort(store, current_name=current_name)
    with CommandProgress(
        "RESOLVE",
        "rechecking finding and preparing repair",
        total=1,
    ) as progress:
        analysis = run_resolve(
            request,
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            audit_repository=JsonAuditRecordRepository(store),
            audit_provider_factory=connect_semantic_provider,
            direction_provider_factory=connect_semantic_provider,
        )
        progress.update("repair ready", step=1)
    decisions = run_resolve_tui(
        analysis,
        clipboard_writer=write_system_clipboard,
    )
    if decisions is not None:
        with CommandProgress(
            "RESOLVE",
            "building whole-Context Update plan",
            total=2,
        ) as progress:
            def connect_update():
                progress.update("planning exact memory changes", step=1)
                return connect_semantic_provider()

            def connect_verifier():
                progress.update("checking complete post-image", step=2)
                return connect_semantic_provider()

            proposal = plan_resolve_update(
                analysis,
                decisions,
                frame_port=port,
                update_provider_factory=connect_update,
                audit_provider_factory=connect_verifier,
            )
        if proposal.blocking_audit_keys:
            raise RuntimeError(
                "Resolve Update post-image still contains unforced Audit issues; "
                "nothing was applied."
            )
        receipt = apply_resolve_update(
            proposal,
            frame_port=port,
        )
        render_resolve_receipt(
            receipt,
            verification=(
                f"AUDIT ISSUES {len(all_audit_issue_keys(proposal.post_audit))}"
                + (
                    f" · {len(receipt.unresolved_issue_uids)} FORCED"
                    if receipt.unresolved_issue_uids
                    else ""
                )
            ),
        )


__all__ = ["run_conflict_resolve_handoff"]
