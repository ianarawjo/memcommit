"""Interactive adapter from one typed conflict finding into Resolve."""

from __future__ import annotations

from memcommit.adapters.console.clipboard import write_system_clipboard
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.commands.resolve.receipt import render_resolve_receipt
from memcommit.adapters.console.commands.resolve.workbench import run_resolve_tui
from memcommit.application.capabilities.reviewing.memory_issue.resolution.handoff import (
    QualityFindingHandoff,
    conflict_handoff_to_resolve_request,
)
from memcommit.providers.subscription import connect_semantic_provider
from memcommit.application.operations.resolve.application import (
    apply_resolve,
    run_resolve,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
)
from memcommit.persistence.store import MemoryStore


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
            provider_factory=connect_semantic_provider,
        )
        progress.update("repair ready", step=1)
    receipt = run_resolve_tui(
        analysis,
        apply_candidate=lambda selected: apply_resolve(
            analysis,
            selected,
            frame_port=port,
        ),
        clipboard_writer=write_system_clipboard,
    )
    if receipt is not None:
        candidate = next(
            candidate
            for candidate in analysis.candidates
            if candidate.uid == receipt.candidate_uid
        )
        render_resolve_receipt(
            receipt,
            fit_verdict=candidate.fit.verdict,
        )


__all__ = ["run_conflict_resolve_handoff"]
