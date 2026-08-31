"""Distill-owned process-local Impact adapter."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.operation_lifecycle.impact.sessions import (
    ImpactSessionPresentation,
    process_local_impact_error,
    show_process_local_impact,
)
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.terminal.components.impact import ImpactController
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    freeze_goal_focus_operand,
)
from memcommit.application.capabilities.semantic_result_memorization import (
    resolve_semantic_result_endpoints,
)
from memcommit.application.operations.semantic_updates.derive.distill.application import (
    DistillRequest,
    DistillResult,
)
from memcommit.application.operations.semantic_updates.derive.distill.model import DistillError
from memcommit.application.operations.semantic_updates.derive.distill.runtime import (
    execute_distill,
    prepare_distill_add,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def distill_impact_presentation(
    result: DistillResult,
    *,
    target_name: str | None = None,
    save_as: str | None = None,
) -> ImpactSessionPresentation:
    """Project one exact Distill proposal without publishing its Add."""

    analysis = result.analysis
    result_name = target_name or save_as or "UNNAMED TARGET"
    existing_target = target_name is not None
    scope = (
        "CONTEXT + DESCENDANTS/EMBEDS"
        if analysis.source.include_descendants or analysis.source.follow_embeds
        else "THIS CONTEXT ONLY"
    )
    items = tuple(
        ResolutionItem(
            uid=rule.uid,
            kind="DISTILLED RULE",
            status="PROPOSED",
            priority="CHANGE",
            title=" ".join(rule.content.split()),
            summary=rule.rationale,
            role="CHANGE",
            obligation="NONE",
            response_state="NOT_APPLICABLE",
            compact_row_suffix=(
                f"SUPPORT {len(rule.support_memory_uids)} · "
                f"BOUNDARY {len(rule.boundary_memory_uids)}"
            ),
            blocks=(
                ResolutionDetailBlock(
                    heading="EVIDENCE BOUNDARY",
                    text=(
                        "SUPPORT · "
                        + ", ".join(uid[:8] for uid in rule.support_memory_uids)
                        + (
                            "\nBOUNDARY · "
                            + ", ".join(uid[:8] for uid in rule.boundary_memory_uids)
                            if rule.boundary_memory_uids
                            else "\nBOUNDARY · none"
                        )
                    ),
                ),
            ),
        )
        for rule in analysis.rules
    )
    results = tuple(
        ResolutionResult(
            uid=rule.uid,
            marker="+",
            label="ADD",
            text=rule.content,
            reason=rule.rationale,
            rules=tuple(
                f"SUPPORT MEMORY · {uid[:8]}" for uid in rule.support_memory_uids
            ),
        )
        for rule in analysis.rules
    )
    sections = (
        *(
            (ResolutionOverviewSection("goal", "GOAL", analysis.goal),)
            if analysis.goal is not None
            else ()
        ),
        ResolutionOverviewSection(
            "source-overview",
            "SOURCE OVERVIEW",
            analysis.overview,
        ),
    )
    view = ResolutionWorkbenchView(
        operation="distill",
        artifact_uid=analysis.uid,
        revision=analysis.digest,
        title="MEM DISTILL · RULE PROPOSAL",
        route=(
            f"SOURCE {analysis.source.context_name} → TARGET {result_name}"
            if existing_target
            else f"SOURCE {analysis.source.context_name} → NEW RESULT {result_name}"
        ),
        status="PROPOSAL",
        metrics=(
            ResolutionMetric("SOURCE", str(len(analysis.source.sources))),
            ResolutionMetric("RULES", str(len(analysis.rules))),
            ResolutionMetric("RANGE", scope),
        ),
        context_locations=(
            ResolutionContextLocation("SOURCE", analysis.source.context_name),
            ResolutionContextLocation(
                "TARGET" if existing_target else "RESULT",
                result_name,
                "EXISTING" if existing_target else "CREATE ON APPLY",
            ),
        ),
        overview=analysis.overview,
        overview_sections=sections,
        list_label="PROPOSED RULES",
        items=items,
        empty_message="No evidence-supported Rules were proposed.",
        results_label="PROPOSED RESULT MEMORIES",
        results=results,
        # The Rule catalog is the proposal itself. Repeating the same Memories
        # below as an effect ledger obscures the content without adding a
        # distinct decision or mutation boundary.
        show_results=False,
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_resolution(
            view,
            title=(
                "IMPACT · DISTILL ADD" if existing_target else "IMPACT · DISTILL RESULT"
            ),
            summary=(
                "Apply would add these Rules to the existing Target Context."
                if existing_target
                else "Apply would create a Result Context with these Rules."
            ),
        ),
        handoff_available=False,
        show_impact_ledger=False,
    )


def distill_cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            hidden=True, help="Existing local Source Context (defaults to current)"
        ),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option("--from", help="Existing Source Context (defaults to current)"),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option("--to", help="Existing Target Context (defaults to current)"),
    ] = None,
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", "-g", help="Optional Rule relevance Goal"),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option("-d", "--direct", help="Use only directly owned Memories"),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include readable lexical descendants and embedded Contexts",
        ),
    ] = False,
    save_as: Annotated[
        Optional[str],
        typer.Option(
            "--save-as",
            hidden=True,
            help="Proposed fresh Result Context name (shown but never created)",
        ),
    ] = None,
) -> None:
    """Inspect the Rules Distill would add while leaving endpoints untouched."""

    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        if context_name is not None and source_name is not None:
            raise DistillError("Use either positional Context or --from, not both.")
        if save_as is not None and (source_name is not None or target_name is not None):
            raise DistillError(
                "Legacy --save-as cannot be combined with --from or --to."
            )
        if save_as is not None:
            store.assert_context_creatable(save_as)
        goal_focus = (
            freeze_goal_focus_operand(store, goal, current_name=snapshot.current_name)
            if goal is not None
            else None
        )
        with CommandProgress(
            "IMPACT · DISTILL", "preparing source", total=2
        ) as progress:
            if save_as is not None:
                result = execute_distill(
                    DistillRequest(
                        context_locator=context_name,
                        goal_focus=goal_focus,
                        include_descendants=traversal.include_descendants,
                        follow_embeds=traversal.follow_embeds,
                    ),
                    store=store,
                    provider_factory=lambda: (
                        progress.update("distilling Rules", step=2)
                        or connect_semantic_provider()
                    ),
                )
                resolved_target = None
            else:
                endpoints = resolve_semantic_result_endpoints(
                    source_locator=source_name
                    if source_name is not None
                    else context_name,
                    target_locator=target_name,
                    current=snapshot.current_name,
                )
                prepared = prepare_distill_add(
                    DistillRequest(
                        context_locator=endpoints.source_name,
                        goal_focus=goal_focus,
                        include_descendants=traversal.include_descendants,
                        follow_embeds=traversal.follow_embeds,
                    ),
                    store=store,
                    target_name=endpoints.target_name,
                    provider_factory=lambda: (
                        progress.update("distilling Rules", step=2)
                        or connect_semantic_provider()
                    ),
                )
                result = prepared.result
                resolved_target = endpoints.target_name
        show_process_local_impact(
            distill_impact_presentation(
                result,
                target_name=resolved_target,
                save_as=save_as,
            ),
            operation="distill",
        )
    except (
        DistillError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("distill", error)


__all__ = ["distill_cmd", "distill_impact_presentation"]
