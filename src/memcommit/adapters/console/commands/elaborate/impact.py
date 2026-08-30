"""Elaborate-owned process-local Impact adapter."""

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
    resolve_memorization_target,
    resolve_semantic_result_endpoints,
)
from memcommit.application.operations.elaborate.add_runtime import (
    freeze_elaborate_context_source,
    prepare_elaborate_add,
)
from memcommit.application.operations.elaborate.application import (
    ElaborateRequest,
    ElaborateResult,
)
from memcommit.application.operations.elaborate.model import (
    ElaborateError,
    ElaborateMode,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)


def elaborate_impact_presentation(
    result: ElaborateResult,
    *,
    source_name: str | None,
    target_name: str,
) -> ImpactSessionPresentation:
    """Project the exact unverified Memories Elaborate would add."""

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
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
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
    rules_direction = analysis.mode is ElaborateMode.GOAL_TO_RULES
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
        "GOAL → RULES"
        if analysis.mode is ElaborateMode.GOAL_TO_RULES
        else "RULES → CASES"
    )
    view = ResolutionWorkbenchView(
        operation="elaborate",
        artifact_uid=analysis.uid,
        revision=analysis.digest,
        title="MEM ELABORATE · ADD PROPOSAL",
        route=f"SOURCE {display_source} → TARGET {target_name}",
        status="PROPOSAL · NEEDS REVIEW",
        metrics=(
            ResolutionMetric("INPUTS", str(len(analysis.inputs))),
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
        overview_sections=(
            ResolutionOverviewSection(
                "proposal-overview",
                "PROPOSAL OVERVIEW",
                analysis.overview,
            ),
        ),
        list_label="PROPOSED RULES" if rules_direction else "PROPOSED CASES",
        items=items,
        empty_message="No Elaborate proposals were returned.",
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
            title="IMPACT · ELABORATE ADD",
            summary="Review these proposed Memories before adding them to the Target.",
        ),
        handoff_available=False,
        show_impact_ledger=False,
    )


def elaborate_cmd(
    goal: Annotated[
        Optional[str],
        typer.Option("--goal", "-g", help="Inline Goal to elaborate into Rules"),
    ] = None,
    rule: Annotated[
        Optional[list[str]],
        typer.Option("--rule", help="Inline Rule to elaborate into Cases; repeatable"),
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
        typer.Option("--as", help="Interpret Context Source as rules or one goal"),
    ] = "rules",
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
    """Inspect the Memories Elaborate would add without saving them."""

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
        if source_name is not None and inline_rules:
            raise ElaborateError("Inline --rule input cannot be combined with --from.")
        context_source = source_name is not None or (
            not inline_rules and goal_focus is None
        )
        if not context_source:
            if as_role != "rules":
                raise ElaborateError("--as applies only to a Context Source.")
            if inline_rules:
                request = ElaborateRequest(
                    rules=tuple(rule or ()),
                    goal_focus=goal_focus,
                    number=number,
                    strict=strict,
                )
            else:
                assert goal_focus is not None
                if len(goal_focus.items) != 1:
                    raise ElaborateError(
                        "Standalone --goal requires one Goal item; use --from "
                        "with --as goal for an exact one-Memory Goal Source."
                    )
                request = ElaborateRequest(
                    goal=goal_focus.text,
                    goal_focus=goal_focus,
                    number=number,
                    strict=strict,
                )
            resolved_source = None
            resolved_target = resolve_memorization_target(
                target_locator=target_name,
                current=snapshot.current_name,
            )
        else:
            endpoints = resolve_semantic_result_endpoints(
                source_locator=source_name,
                target_locator=target_name,
                current=snapshot.current_name,
            )
            if as_role not in {"goal", "rules"}:
                raise ElaborateError("Elaborate --as must be 'goal' or 'rules'.")
            frozen_source = freeze_elaborate_context_source(
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
        with CommandProgress(
            "IMPACT · ELABORATE",
            "preparing source and target",
            total=2,
        ) as progress:
            prepared = prepare_elaborate_add(
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
            elaborate_impact_presentation(
                prepared.result,
                source_name=resolved_source,
                target_name=resolved_target,
            ),
            operation="elaborate",
        )
    except (
        ElaborateError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        process_local_impact_error("elaborate", error)


__all__ = ["elaborate_cmd", "elaborate_impact_presentation"]
