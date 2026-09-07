"""Read-only Impact projection for Resolve Audit decision inputs."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.impact.sessions import (
    ImpactSessionPresentation,
    process_local_impact_error,
    show_process_local_impact,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.adapters.console.commands.impact.projection import ImpactController
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoffError,
    quality_finding_handoff_from_json,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveError,
    ResolveRequest,
    run_resolve,
)
from memcommit.application.operations.resolve.finding_handoff import (
    conflict_handoff_to_resolve_request,
)
from memcommit.application.operations.resolve.runtime import (
    MemoryStoreResolvePort,
)
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
)
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.providers.subscription import QueryProviderError, connect_semantic_provider


def resolve_impact_presentation(analysis: ResolveAnalysis) -> ImpactSessionPresentation:
    """Show decision inputs while making the absent mutation plan explicit."""

    memory_by_uid = {memory.uid: memory.content for memory in analysis.frame.memories}
    items = tuple(
        ResolutionItem(
            uid=issue.uid,
            kind=issue.kind,
            status="NEEDS DECISION",
            priority="REQUIRED",
            title=" ↔ ".join(
                f"[{uid[:8]}] {' '.join(memory_by_uid[uid].split())}"
                for uid in issue.memory_uids
            ),
            summary=issue.proposed_direction,
            obligation="REQUIRED",
            response_state="OPEN",
            question=issue.question or issue.reason,
        )
        for issue in analysis.review_issues
    )
    detail = analysis.question or analysis.status
    view = ResolutionWorkbenchView(
        operation="resolve",
        artifact_uid=analysis.frame.context_uid,
        revision=analysis.frame.revision,
        title="MEM RESOLVE · DECISION INPUTS",
        route=f"TARGET {analysis.frame.display_name}",
        status=analysis.status,
        metrics=(
            ResolutionMetric("MEMORIES", str(len(analysis.frame.memories))),
            ResolutionMetric("AUDIT ITEMS", str(len(items))),
            ResolutionMetric("UPDATE PLAN", "NOT BUILT"),
        ),
        context_locations=(
            ResolutionContextLocation("TARGET", analysis.frame.display_name),
        ),
        overview=detail,
        overview_sections=(
            ResolutionOverviewSection(
                "boundary",
                "PLANNING BOUNDARY",
                "Resolve has not created edit, add, or remove effects. The Update "
                "planner runs only after every Audit item has a finalized decision.",
            ),
        ),
        list_label="AUDIT ITEMS",
        items=items,
        empty_message="No actionable Audit issue was found.",
        results_label="UPDATE PLAN",
        results=(),
        show_results=False,
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_text(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · RESOLVE · DECISIONS FIRST",
            summary="No mutation plan exists before Resolve decisions are finalized.",
            detail=detail,
        ),
        handoff_available=False,
    )


def resolve_cmd(
    memory_selectors: Annotated[
        Optional[list[str]],
        typer.Argument(help="Direct Memory UID prefixes to include in Resolve"),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context", "-c", help="Exact local or readable granted Target Context"
        ),
    ] = None,
    allow_create: Annotated[
        bool,
        typer.Option(
            "--allow-create/--no-create",
            help="Allow a later finalized UpdatePlan to add supported Memories",
        ),
    ] = True,
    allow_delete: Annotated[
        bool,
        typer.Option(
            "--allow-delete",
            help="Allow a later finalized UpdatePlan to remove supported Memories",
        ),
    ] = False,
    guidance: Annotated[
        Optional[str],
        typer.Option("--guidance", help="Additional Audit direction context"),
    ] = None,
    finding_handoff: Annotated[
        Optional[str],
        typer.Option(
            "--finding-handoff",
            help="Canonical conflict handoff JSON emitted by find-conflicts",
        ),
    ] = None,
) -> None:
    """Inspect Resolve directions without collecting decisions or building Update."""

    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        if finding_handoff is not None:
            if context_name is not None or memory_selectors:
                raise ResolveError(
                    "--finding-handoff cannot be combined with a Context or "
                    "Memory selector."
                )
            request = conflict_handoff_to_resolve_request(
                quality_finding_handoff_from_json(finding_handoff),
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
            )
        else:
            request = ResolveRequest(
                context_name=(
                    resolve_existing_context_access(
                        store,
                        context_name,
                        current_name=snapshot.current_name,
                        required_permission="READ",
                    ).name
                    if context_name is not None
                    else snapshot.current_name
                ),
                memory_selectors=tuple(memory_selectors or ()),
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
            )
        port = MemoryStoreResolvePort(store, current_name=snapshot.current_name)
        with CommandProgress(
            "IMPACT · RESOLVE", "identifying Audit decisions", total=1
        ) as progress:
            analysis = run_resolve(
                request,
                frame_port=port,
                semantic_port=ProviderResolveSemanticPort(),
                audit_repository=JsonAuditRecordRepository(store),
                audit_provider_factory=connect_semantic_provider,
                direction_provider_factory=connect_semantic_provider,
            )
            progress.update("decision inputs ready", step=1)
        show_process_local_impact(
            resolve_impact_presentation(analysis),
            operation="resolve",
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        QualityFindingHandoffError,
        ResolveError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("resolve", error)


__all__ = ["resolve_cmd", "resolve_impact_presentation"]
