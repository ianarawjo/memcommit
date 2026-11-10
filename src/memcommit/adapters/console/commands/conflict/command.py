"""Review conflicts and apply the changes chosen for one Context."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.capabilities import (
    require_interactive_terminal,
)
from memcommit.adapters.console.commands.conflict.receipt import (
    render_conflict_resolution_receipt,
    render_conflict_resolution_status,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.conflict.application import (
    CONFLICT_RESOLUTION_CHECKS,
)
from memcommit.application.operations.conflict.model import ConflictResolutionError, ConflictResolutionRequest
from memcommit.application.operations.conflict.review_round.review_session import (
    ConflictResolutionReviewSession,
)
from memcommit.application.operations.conflict.finalization.proposal import (
    apply_conflict_resolution_proposal,
)
from memcommit.application.operations.conflict.finalization.runtime import (
    ConflictResolutionStoreAdapter,
    analyze_context_conflicts_from_store,
)
from memcommit.application.operations.conflict.analysis.convert_audit_to_issues import (
    all_audit_issue_keys,
)
from memcommit.application.operations.conflict.analysis.resolution_options.generate_resolution_directions import (
    ProviderConflictResolutionOptionsPort,
)
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import ProfileStore
from memcommit.llm_providers.connection import connect_semantic_provider
from memcommit.llm_providers.errors import QueryProviderError


def cmd() -> None:
    """Review conflicts, choose resolutions, and apply the resulting changes."""

    try:
        require_interactive_terminal("Conflict")
        store = ProfileStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        request = ConflictResolutionRequest(context_name=snapshot.current_name)
        resolve_context_conflicts(request, store=store, current_name=snapshot.current_name)
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        ConflictResolutionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        typer.secho(
            "Conflict error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def resolve_context_conflicts(
    request: ConflictResolutionRequest,
    *,
    store: ProfileStore,
    current_name: str | None,
) -> None:
    """Run review and Apply for the parsed Conflict request."""
    port = ConflictResolutionStoreAdapter(
        store,
        current_name=current_name,
    )
    with CommandProgress(
        "CONFLICT",
        "building and checking repair",
        total=1,
    ) as progress:
        analysis = analyze_context_conflicts_from_store(
            request,
            checks=CONFLICT_RESOLUTION_CHECKS,
            store_port=port,
            semantic_port=ProviderConflictResolutionOptionsPort(),
            audit_repository=JsonAuditRecordRepository(store),
            audit_provider_factory=connect_semantic_provider,
            direction_provider_factory=connect_semantic_provider,
        )
        progress.update("Audit directions ready", step=1)

    if not analysis.issues:
        render_conflict_resolution_status(analysis)
        return

    from memcommit.adapters.console.commands.conflict.resolution_rounds import (
        run_resolution_rounds,
    )

    def revalidate_target():
        # Later rounds use post-images while the original Store target stays frozen.
        port.revalidate(analysis.frame)

    proposal = run_resolution_rounds(
        (ConflictResolutionReviewSession(analysis),),
        revalidate_target=revalidate_target,
        provider_factory=connect_semantic_provider,
    )
    if proposal is None:
        return
    (proposal,) = proposal
    receipt = apply_conflict_resolution_proposal(proposal, apply_port=port)
    render_conflict_resolution_receipt(
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


__all__ = ["cmd", "resolve_context_conflicts"]
