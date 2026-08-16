"""Interactive adapter from one typed conflict finding into Resolve."""

from __future__ import annotations

from memcommit.clipboard import write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.interfaces.tui.operations.resolve import run_resolve_tui
from memcommit.quality_finding_handoff import (
    QualityFindingHandoff,
    conflict_handoff_to_resolve_request,
)
from memcommit.query_provider import connect_semantic_provider
from memcommit.resolve_application import apply_resolve, run_resolve
from memcommit.resolve_runtime import MemoryStoreResolvePort
from memcommit.resolve_semantic import ProviderResolveSemanticPort
from memcommit.store import MemoryStore


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
        "rechecking the finding and verifying the complete repair frame",
        total=1,
    ) as progress:
        analysis = run_resolve(
            request,
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            provider_factory=connect_semantic_provider,
        )
        progress.update("verified proposal ready", step=1)
    run_resolve_tui(
        analysis,
        apply_candidate=lambda selected: apply_resolve(
            analysis,
            selected,
            frame_port=port,
        ),
        clipboard_writer=write_system_clipboard,
    )


__all__ = ["run_conflict_resolve_handoff"]
