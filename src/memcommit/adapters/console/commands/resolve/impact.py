"""Resolve-owned process-local Impact adapter."""

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
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoffError,
    conflict_handoff_to_resolve_request,
    quality_finding_handoff_from_json,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.application.operations.fit.judgment import FitJudgmentError
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.application.operations.resolve.application import (
    ResolveAnalysis,
    ResolveCandidate,
    ResolveError,
    ResolveRequest,
    run_resolve,
)
from memcommit.application.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.resolve.semantic import (
    ProviderResolveSemanticPort,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def _resolve_change(effect) -> MemoryChange:
    marker = {"CREATE": "+", "UPDATE": "~", "DELETE": "−"}[effect.kind]
    return MemoryChange(
        marker=marker,
        treatment=effect.kind,
        location=effect.owner_context_name,
        memory_uid=effect.memory_uid,
        before=effect.old_content,
        after=effect.new_content,
        reason=effect.reason,
        rules=tuple(f"SOURCE MEMORY · {uid[:8]}" for uid in effect.source_memory_uids),
    )


def _resolve_candidate_view(
    analysis: ResolveAnalysis,
    candidate: ResolveCandidate,
) -> ResolutionWorkbenchView:
    results = tuple(
        ResolutionResult(
            uid=effect.memory_uid,
            marker={"CREATE": "+", "UPDATE": "~", "DELETE": "−"}[effect.kind],
            label=effect.kind,
            text=effect.new_content or effect.old_content or "",
            reason=effect.reason,
            rules=tuple(
                f"SOURCE MEMORY · {uid[:8]}" for uid in effect.source_memory_uids
            ),
        )
        for effect in candidate.effects
    )
    items = tuple(
        ResolutionItem(
            uid=f"{candidate.uid}:{position}",
            kind=f"RESOLVE {effect.kind}",
            status="VERIFIED",
            priority="CHANGE",
            title=" ".join((effect.new_content or effect.old_content or "").split()),
            summary=effect.reason,
            role="CHANGE",
            obligation="NONE",
            response_state="NOT_APPLICABLE",
        )
        for position, effect in enumerate(candidate.effects, 1)
    )
    return ResolutionWorkbenchView(
        operation="resolve",
        artifact_uid=analysis.frame.context_uid,
        revision=analysis.frame.revision,
        title="MEM RESOLVE · AUTOMATIC INTERPRETATION PLAN",
        route=f"SOURCE {analysis.frame.display_name} → SAME SOURCE",
        status="GROUNDED PLAN" if candidate.grounded else "ASSUMED WORKING VIEW",
        metrics=(
            ResolutionMetric("EFFECTS", str(len(candidate.effects))),
            ResolutionMetric("FIT", candidate.fit.verdict),
            ResolutionMetric(
                "COST",
                f"D{candidate.cost.deletes} C{candidate.cost.creates} "
                f"U{candidate.cost.updates}",
            ),
        ),
        context_locations=(
            ResolutionContextLocation("SOURCE", analysis.frame.display_name),
        ),
        overview=candidate.summary,
        overview_sections=(
            *(
                ResolutionOverviewSection(
                    f"issue-{position}",
                    f"ISSUE · {issue.kind}",
                    issue.selected_interpretation
                    + (
                        "\nASSUMPTIONS · " + "; ".join(issue.assumptions)
                        if issue.assumptions
                        else ""
                    ),
                )
                for position, issue in enumerate(candidate.issues, 1)
            ),
            ResolutionOverviewSection("candidate", "AUTOMATIC PLAN", candidate.summary),
            ResolutionOverviewSection(
                "verification",
                "INDEPENDENT FIT VERIFICATION",
                candidate.verification_reason,
            ),
        ),
        list_label="EXACT EFFECTS",
        items=items,
        empty_message="No effects in this candidate.",
        results_label="PROPOSED SOURCE RESULT",
        results=results,
    )


def resolve_impact_presentation(
    analysis: ResolveAnalysis,
    *,
    candidate_uid: str | None,
) -> ImpactSessionPresentation:
    """Project the automatic Resolve plan or a terminal read-only outcome."""

    candidate: ResolveCandidate | None = None
    if candidate_uid is not None:
        matches = tuple(
            item for item in analysis.candidates if item.uid == candidate_uid
        )
        if len(matches) != 1:
            raise ResolveError(
                f"No verified Resolve candidate has exact id '{candidate_uid}'."
            )
        candidate = matches[0]
    elif analysis.status in {"PROPOSAL", "ASSUMED"}:
        candidate = analysis.candidates[0]

    if candidate is not None:
        view = _resolve_candidate_view(analysis, candidate)
        return ImpactSessionPresentation(
            view=view,
            controller=ImpactController.from_memory_changes(
                operation=view.operation,
                artifact_uid=view.artifact_uid,
                revision=view.revision,
                title="IMPACT · RESOLVE · SAME SOURCE",
                summary=(
                    "These are the exact effects of one automatic, independently "
                    "Fit-verified interpretation plan. This Impact view cannot "
                    "apply them."
                ),
                changes=tuple(_resolve_change(effect) for effect in candidate.effects),
            ),
            handoff_available=False,
        )

    detail = analysis.question or (
        analysis.initial_fit.reason
        if analysis.initial_fit is not None
        else analysis.status
    )
    view = ResolutionWorkbenchView(
        operation="resolve",
        artifact_uid=analysis.frame.context_uid,
        revision=analysis.frame.revision,
        title="MEM RESOLVE · NO EFFECT PROPOSAL",
        route=f"SOURCE {analysis.frame.display_name} → SAME SOURCE",
        status=analysis.status,
        metrics=(
            ResolutionMetric("SOURCE", str(len(analysis.frame.memories))),
            ResolutionMetric("EFFECTS", "0"),
        ),
        context_locations=(
            ResolutionContextLocation("SOURCE", analysis.frame.display_name),
        ),
        overview=detail,
        overview_sections=(ResolutionOverviewSection("status", "ASSESSMENT", detail),),
        list_label="EXACT EFFECTS",
        items=(),
        empty_message="No Resolve effects are available.",
        results_label="PROPOSED SOURCE RESULT",
        results=(),
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_text(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · RESOLVE · NO EFFECTS",
            summary="Resolve produced no applicable effect set.",
            detail=detail,
        ),
        handoff_available=False,
    )


def resolve_cmd(
    memory_selectors: Annotated[
        Optional[list[str]],
        typer.Argument(help="Direct Memory UID prefixes allowed to change"),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context", "-c", help="Exact local or readable granted Source Context"
        ),
    ] = None,
    allow_create: Annotated[
        bool,
        typer.Option(
            "--allow-create/--no-create",
            help="Include information-preserving CREATE in the automatic plan",
        ),
    ] = True,
    allow_delete: Annotated[
        bool,
        typer.Option("--allow-delete", help="Permit grounded DELETE candidates"),
    ] = False,
    guidance: Annotated[
        Optional[str],
        typer.Option("--guidance", help="Grounding available to candidate generation"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Require an exact YES resolution whose post-image also Fits as YES",
        ),
    ] = False,
    finding_handoff: Annotated[
        Optional[str],
        typer.Option(
            "--finding-handoff",
            help="Canonical conflict handoff JSON emitted by find-conflicts",
        ),
    ] = None,
    candidate_uid: Annotated[
        Optional[str],
        typer.Option(
            "--candidate",
            help="Exact full id of the verified automatic plan to project as a diff",
        ),
    ] = None,
) -> None:
    """Prepare and inspect Resolve effects without crossing its Apply boundary."""

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
                target_fit="YES" if yes else "MAY",
            )
        else:
            request = ResolveRequest(
                context_name=snapshot.resolve_or_current(context_name),
                memory_selectors=tuple(memory_selectors or ()),
                allow_create=allow_create,
                allow_delete=allow_delete,
                guidance=guidance or "",
                target_fit="YES" if yes else "MAY",
            )
        port = MemoryStoreResolvePort(store, current_name=snapshot.current_name)
        with CommandProgress(
            "IMPACT · RESOLVE", "preparing source", total=2
        ) as progress:
            analysis = run_resolve(
                request,
                frame_port=port,
                semantic_port=ProviderResolveSemanticPort(),
                provider_factory=lambda: (
                    progress.update("generating and verifying candidates", step=2)
                    or connect_semantic_provider()
                ),
            )
        show_process_local_impact(
            resolve_impact_presentation(analysis, candidate_uid=candidate_uid),
            operation="resolve",
        )
    except (
        FileNotFoundError,
        FitJudgmentError,
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
