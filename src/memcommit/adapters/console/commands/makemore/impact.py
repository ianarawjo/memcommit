"""Makemore-owned process-local Impact adapter."""

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
from memcommit.adapters.console.commands.impact.projection import ImpactController
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
    resolve_existing_memorization_target,
    resolve_existing_semantic_result_endpoints,
)
from memcommit.application.operations.makemore.add_runtime import (
    freeze_makemore_context_source,
    prepare_makemore_add,
)
from memcommit.application.operations.makemore.distilled_runtime import (
    prepare_distilled_makemore_add,
)
from memcommit.application.operations.distill.application import DistillResult
from memcommit.application.operations.makemore.application import (
    MakemoreRequest,
    MakemoreResult,
)
from memcommit.application.operations.makemore.model import (
    MakemoreError,
    MakemoreMode,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def makemore_impact_presentation(
    result: MakemoreResult,
    *,
    source_name: str | None,
    target_name: str,
    distill_result: DistillResult | None = None,
) -> ImpactSessionPresentation:
    """Project the exact unverified Memories Makemore would add."""

    analysis = result.analysis
    target_context = analysis.target_context

    def target_used(refs: tuple[str, ...]) -> tuple[str, ...]:
        if target_context is None:
            return ()
        return ("TARGET USED · " + (", ".join(refs) or "NONE"),)

    def proposal_blocks(detail: tuple[str, ...]) -> tuple[ResolutionDetailBlock, ...]:
        if not detail:
            return ()
        heading, *body = detail
        if heading.startswith("TARGET USED · "):
            heading, _separator, target_refs = heading.partition(" · ")
            body = [target_refs]
        elif heading.startswith("RULE COVERAGE · "):
            # The typed result retains every provider Rule check. The Impact
            # detail needs the exhaustive boundary and actionable result only.
            body = [
                line
                for line in body
                if line.startswith(("EXPECTED · ", "TARGET USED · "))
            ]
        return (ResolutionDetailBlock(heading=heading, text="\n".join(body)),)

    proposals = (
        tuple(
            (
                item.uid,
                "RULE",
                item.content,
                item.rationale,
                target_used(item.target_context_refs),
            )
            for item in analysis.rules
        )
        if analysis.mode is MakemoreMode.GOAL_TO_RULES
        else tuple(
            (
                item.uid,
                f"CASE · {item.case_role}",
                item.proposition,
                item.rationale,
                (
                    f"RULE COVERAGE · ALL {len(item.rule_checks)}",
                    *(
                        f"RULE {check.source_rule_index} · {check.evidence}"
                        for check in item.rule_checks
                    ),
                    f"EXPECTED · {item.expected or '(open)'}",
                    *target_used(item.target_context_refs),
                ),
            )
            for item in analysis.cases
        )
    )
    rules_direction = analysis.mode is MakemoreMode.GOAL_TO_RULES
    items = tuple(
        ResolutionItem(
            uid=uid,
            kind=kind,
            status="PROPOSED · UNVERIFIED",
            priority="SUGGESTED",
            title=" ".join(content.split()),
            summary=rationale,
            role="OPTIONAL_REVIEW",
            obligation="NONE",
            response_state="NOT_APPLICABLE",
            compact_row_suffix=(
                "SUGGESTED · UNVERIFIED"
                if rules_direction
                else f"ALL {len(analysis.inputs)} RULES · UNVERIFIED"
            ),
            blocks=proposal_blocks(detail),
            show_summary_priority=False,
        )
        for uid, kind, content, rationale, detail in proposals
    )
    results = tuple(
        ResolutionResult(
            uid=uid,
            marker="+",
            label="ADD",
            text=content,
            reason=rationale,
            rules=detail,
        )
        for uid, _kind, content, rationale, detail in proposals
    )
    display_source = source_name or "INLINE INPUT"
    direction = (
        "CONTEXT → RULES → CASES"
        if distill_result is not None
        else (
            "GOAL → RULES"
            if analysis.mode is MakemoreMode.GOAL_TO_RULES
            else "RULES → CASES"
        )
    )
    overview_sections = []
    if distill_result is not None:
        distilled = distill_result.analysis
        overview_sections.append(
            ResolutionOverviewSection(
                "distilled-rules",
                "TRANSIENT DISTILLED RULES",
                "\n".join(
                    f"{index}. {rule.content} · SUPPORT "
                    + (", ".join(uid[:8] for uid in rule.support_memory_uids) or "NONE")
                    + (
                        " · BOUNDARY "
                        + ", ".join(uid[:8] for uid in rule.boundary_memory_uids)
                        if rule.boundary_memory_uids
                        else ""
                    )
                    for index, rule in enumerate(distilled.rules, 1)
                ),
            )
        )
    overview_sections.append(
        ResolutionOverviewSection(
            "proposal-overview",
            "PROPOSAL OVERVIEW",
            analysis.overview,
        )
    )
    view = ResolutionWorkbenchView(
        operation="makemore",
        artifact_uid=analysis.uid,
        revision=analysis.digest,
        title="MEM MAKEMORE · ADD PROPOSAL",
        route=f"SOURCE {display_source} → TARGET {target_name}",
        status="PROPOSAL · NEEDS REVIEW",
        metrics=(
            ResolutionMetric(
                "SOURCE MEMORIES" if distill_result is not None else "INPUTS",
                str(
                    len(distill_result.analysis.source.sources)
                    if distill_result is not None
                    else len(analysis.inputs)
                ),
            ),
            *(
                (
                    ResolutionMetric(
                        "DISTILLED RULES",
                        str(len(distill_result.analysis.rules)),
                    ),
                )
                if distill_result is not None
                else ()
            ),
            ResolutionMetric("PROPOSALS", str(len(proposals))),
            ResolutionMetric("DIRECTION", direction),
            ResolutionMetric(
                "TARGET AMBIENT",
                str(len(target_context.items) if target_context is not None else 0),
            ),
        ),
        context_locations=(
            ResolutionContextLocation("SOURCE", display_source),
            ResolutionContextLocation("TARGET", target_name, "EXISTING"),
        ),
        overview=analysis.overview,
        overview_sections=tuple(overview_sections),
        list_label="PROPOSED RULES" if rules_direction else "PROPOSED CASES",
        items=items,
        empty_message="No Makemore proposals were returned.",
        results_label="PROPOSED ADD MEMORIES",
        results=results,
        # The proposal catalog already contains the exact Memories; a repeated
        # effect ledger adds no separate decision or mutation boundary.
        show_results=False,
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_resolution(
            view,
            title="IMPACT · MAKEMORE ADD",
            summary="Review these proposed Memories before adding them to the Target.",
        ),
        handoff_available=False,
        show_impact_ledger=False,
    )


def makemore_cmd(
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", "-g", help="Inline Goal to expand into Rules"),
    ] = None,
    rule: Annotated[
        Optional[list[str]],
        typer.Option("--rule", help="Inline Rule to expand into Cases; repeatable"),
    ] = None,
    source_name: Annotated[
        Optional[str],
        typer.Option("--from", help="Existing Source Context (defaults to current)"),
    ] = None,
    target_name: Annotated[
        Optional[str],
        typer.Option("--to", help="Existing Target Context (defaults to current)"),
    ] = None,
    as_role: Annotated[
        str,
        typer.Option(
            "--as",
            help=(
                "Interpret Context Source as auto (Distill then Makemore), "
                "existing rules, or one goal"
            ),
        ),
    ] = "auto",
    number: Annotated[
        Optional[int],
        typer.Option(
            "--number",
            "--n",
            "-n",
            min=1,
            help="Exact positive proposal count (default 3; no fixed maximum)",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Preview the independent Conformance/Fit-gated Case result",
        ),
    ] = False,
) -> None:
    """Inspect the Memories Makemore would add without saving them."""

    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        goal_focus = (
            freeze_goal_focus_operand(store, goal, current_name=snapshot.current_name)
            if goal is not None
            else None
        )
        inline_rules = bool(rule)
        frozen_source = None
        distilled_source_name = None
        distill_result = None
        if source_name is not None and inline_rules:
            raise MakemoreError("Inline --rule input cannot be combined with --from.")
        context_source = source_name is not None or (
            not inline_rules and goal_focus is None
        )
        if not context_source:
            if as_role != "auto":
                raise MakemoreError("--as applies only to a Context Source.")
            if inline_rules:
                request = MakemoreRequest(
                    rules=tuple(rule or ()),
                    goal_focus=goal_focus,
                    number=number,
                    strict=strict,
                )
            else:
                assert goal_focus is not None
                if len(goal_focus.items) != 1:
                    raise MakemoreError(
                        "Standalone --goal requires one Goal item; use --from "
                        "with --as goal for an exact one-Memory Goal Source."
                    )
                request = MakemoreRequest(
                    goal=goal_focus.text,
                    goal_focus=goal_focus,
                    number=number,
                    strict=strict,
                )
            resolved_source = None
            resolved_target = resolve_existing_memorization_target(
                store,
                target_locator=target_name,
                current=snapshot.current_name,
            )
        else:
            endpoints = resolve_existing_semantic_result_endpoints(
                store,
                source_locator=source_name,
                target_locator=target_name,
                current=snapshot.current_name,
            )
            if as_role not in {"auto", "goal", "rules"}:
                raise MakemoreError(
                    "Makemore --as must be 'auto', 'goal', or 'rules'."
                )
            if as_role == "auto":
                distilled_source_name = endpoints.source_name
                request = None
            else:
                frozen_source = freeze_makemore_context_source(
                    store,
                    context_name=endpoints.source_name,
                    role=as_role,
                    number=number,
                    strict=strict,
                    goal_focus=goal_focus,
                )
                request = frozen_source.request
            resolved_source = endpoints.source_name
            resolved_target = endpoints.target_name
        pipeline = distilled_source_name is not None
        with CommandProgress(
            "IMPACT · MAKEMORE",
            "preparing source and target",
            total=3 if pipeline else 2,
        ) as progress:
            if pipeline:
                assert distilled_source_name is not None
                provider_call = 0

                def connect_pipeline_provider():
                    nonlocal provider_call
                    provider_call += 1
                    progress.update(
                        "distilling Source Rules"
                        if provider_call == 1
                        else "generating Cases",
                        step=2 if provider_call == 1 else 3,
                    )
                    return connect_semantic_provider()

                distilled = prepare_distilled_makemore_add(
                    store=store,
                    source_name=distilled_source_name,
                    target_name=resolved_target,
                    provider_factory=connect_pipeline_provider,
                    goal_focus=goal_focus,
                    number=number,
                    strict=strict,
                )
                prepared = distilled.makemore
                distill_result = distilled.distill
            else:
                assert request is not None
                prepared = prepare_makemore_add(
                    store=store,
                    request=request,
                    target_name=resolved_target,
                    source=frozen_source,
                    provider_factory=lambda: (
                        progress.update("generating proposals", step=2)
                        or connect_semantic_provider()
                    ),
                )
        show_process_local_impact(
            makemore_impact_presentation(
                prepared.result,
                source_name=resolved_source,
                target_name=resolved_target,
                distill_result=distill_result,
            ),
            operation="makemore",
        )
    except (
        MakemoreError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("makemore", error)


__all__ = ["makemore_cmd", "makemore_impact_presentation"]
