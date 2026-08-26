"""Process-local operation adapters for standalone Impact inspection."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.impact_sessions import (
    ImpactSessionPresentation,
    render_impact_session_snapshot,
    run_impact_session_workbench,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.operations.distill.model import DistillError
from memcommit.operations.distill.application import DistillRequest, DistillResult
from memcommit.operations.distill.runtime import execute_distill, prepare_distill_add
from memcommit.elaborate import ElaborateError, ElaborateMode
from memcommit.operations.elaborate.add_runtime import (
    freeze_elaborate_context_source,
    prepare_elaborate_add,
)
from memcommit.operations.elaborate.application import ElaborateRequest, ElaborateResult
from memcommit.operations.fit.judgment import FitJudgmentError
from memcommit.goal_focus_runtime import freeze_goal_focus_operand
from memcommit.operations.forget.application import (
    ForgetAnalysisRequest,
    ForgetAnalysisResult,
    run_forget_analysis,
)
from memcommit.forget_resolution_adapter import (
    ForgetResolutionWorkbenchAdapter,
    forget_memory_changes,
)
from memcommit.operations.forget.runtime import (
    MemoryStoreForgetSourcePort,
    connect_forget_provider,
)
from memcommit.interfaces.tui.workbenches.impact import ImpactController
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.forget import choose_forget_setup
from memcommit.memory_diff import MemoryChange
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.quality_finding_handoff import (
    QualityFindingHandoffError,
    conflict_handoff_to_resolve_request,
    quality_finding_handoff_from_json,
)
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.operations.resolve.application import (
    ResolveAnalysis,
    ResolveCandidate,
    ResolveError,
    ResolveRequest,
    run_resolve,
)
from memcommit.operations.resolve.runtime import MemoryStoreResolvePort
from memcommit.resolve_semantic import ProviderResolveSemanticPort
from memcommit.operations.add.semantic_runtime import (
    resolve_semantic_add_endpoints,
    resolve_semantic_add_target,
)
from memcommit.resolution_workbench import (
    ResolutionContextLocation,
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.store import MemoryStore


def _interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _show_process_local_impact(
    presentation: ImpactSessionPresentation,
    *,
    operation: str,
) -> None:
    """Render a prepared artifact without manufacturing an Apply handoff."""

    if _interactive_terminal():
        run_impact_session_workbench(
            presentation,
            terminal_label=f"Interactive {operation.title()} Impact",
        )
        typer.echo(f"{operation.title()} Impact closed.")
        return
    typer.echo(render_impact_session_snapshot(presentation))


def _impact_error(operation: str, error: BaseException) -> None:
    typer.secho(
        f"Impact {operation} error: {display_escape_text(str(error))}",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


def forget_impact_presentation(
    result: ForgetAnalysisResult,
) -> ImpactSessionPresentation:
    """Project Forget's complete process-local review as in-place changes."""

    view = ForgetResolutionWorkbenchAdapter(result.snapshot.review).view()
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_memory_changes(
            operation=view.operation,
            artifact_uid=view.artifact_uid,
            revision=view.revision,
            title="IMPACT · FORGET · SAME SOURCE",
            summary=(
                "These are the complete reviewed in-place Source transitions. "
                "This Impact view cannot apply them."
            ),
            changes=forget_memory_changes(result.snapshot.review),
        ),
        handoff_available=False,
    )


def forget_cmd(
    instruction: Annotated[
        Optional[str],
        typer.Argument(
            show_default=False,
            help=(
                "Description of Memories to forget; omit in a terminal to "
                "choose one direct Source and enter the instruction"
            ),
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact readable Source Context (defaults to current)",
        ),
    ] = None,
) -> None:
    """Prepare Forget decisions and inspect them without changing the Source."""

    if instruction is None and not _interactive_terminal():
        _impact_error(
            "forget",
            ValueError("INSTRUCTION is required outside a terminal."),
        )
    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        source_locator = context_name
        if instruction is None:
            access = resolve_context_access(
                store,
                context_name,
                current_name=snapshot.current_name,
                required_permission="READ",
            )
            catalog = freeze_profile_readable_context_catalog(
                store,
                access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = {
                name: context_access_display_facts(catalog.access_for(name))
                for name in names
                if catalog.access_for(name).is_granted
            }
            receipt = choose_forget_setup(
                names,
                current=access.display_name,
                annotations=annotations,
            )
            if receipt is None:
                typer.echo("Forget Impact cancelled.")
                return
            source_locator = receipt.context_name
            instruction = receipt.instruction
        assert instruction is not None
        request = ForgetAnalysisRequest(source_locator, instruction)
        source_port = MemoryStoreForgetSourcePort(
            store,
            current_name=snapshot.current_name,
        )
        with CommandProgress(
            "IMPACT · FORGET",
            "preparing source",
            total=2,
        ) as progress:
            result = run_forget_analysis(
                request,
                source_port=source_port,
                provider_factory=lambda: (
                    progress.update("analyzing decisions", step=2)
                    or connect_forget_provider()
                ),
            )
        _show_process_local_impact(
            forget_impact_presentation(result),
            operation="forget",
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        _impact_error("forget", error)


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
                "IMPACT · DISTILL ADD"
                if existing_target
                else "IMPACT · DISTILL RESULT"
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
            hidden=True,
            help="Existing local Source Context (defaults to current)",
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
    """Inspect the Rules Distill would add while leaving both endpoints untouched."""

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
            freeze_goal_focus_operand(
                store,
                goal,
                current_name=snapshot.current_name,
            )
            if goal is not None
            else None
        )
        with CommandProgress(
            "IMPACT · DISTILL",
            "preparing source",
            total=2,
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
                endpoints = resolve_semantic_add_endpoints(
                    source_locator=(
                        source_name if source_name is not None else context_name
                    ),
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
        _show_process_local_impact(
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
        _impact_error("distill", error)


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
            # detail only needs the exhaustive-coverage boundary and the
            # actionable result; replaying one model explanation per Rule made
            # the proposal harder to inspect without strengthening it.
            body = [
                line
                for line in body
                if line.startswith(("EXPECTED · ", "TARGET USED · "))
            ]
        return (
            ResolutionDetailBlock(
                heading=heading,
                text="\n".join(body),
            ),
        )

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
        list_label=("PROPOSED RULES" if rules_direction else "PROPOSED CASES"),
        items=items,
        empty_message="No Elaborate proposals were returned.",
        results_label="PROPOSED ADD MEMORIES",
        results=results,
        # The proposal catalog already contains the exact Memories. Repeating
        # them in a generic effect ledger does not add a separate decision or
        # mutation boundary in either derivation direction.
        show_results=False,
    )
    return ImpactSessionPresentation(
        view=view,
        controller=ImpactController.from_resolution(
            view,
            title="IMPACT · ELABORATE ADD",
            summary=(
                "Review these proposed Memories before adding them to the Target."
            ),
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
            freeze_goal_focus_operand(
                store,
                goal,
                current_name=snapshot.current_name,
            )
            if goal is not None
            else None
        )
        inline_rules = bool(rule)
        frozen_source = None
        if source_name is not None and inline_rules:
            raise ElaborateError(
                "Inline --rule input cannot be combined with --from."
            )
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
            resolved_target = resolve_semantic_add_target(
                target_locator=target_name,
                current=snapshot.current_name,
            )
        else:
            endpoints = resolve_semantic_add_endpoints(
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
        _show_process_local_impact(
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
        _impact_error("elaborate", error)


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
        status=(
            "GROUNDED PLAN"
            if candidate.grounded
            else "ASSUMED WORKING VIEW"
        ),
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
            ResolutionOverviewSection(
                "candidate",
                "AUTOMATIC PLAN",
                candidate.summary,
            ),
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
        typer.Argument(
            help="Direct Memory UID prefixes allowed to change",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact local or readable granted Source Context",
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
            "IMPACT · RESOLVE",
            "preparing source",
            total=2,
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
        _show_process_local_impact(
            resolve_impact_presentation(
                analysis,
                candidate_uid=candidate_uid,
            ),
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
        _impact_error("resolve", error)


__all__ = [
    "distill_cmd",
    "distill_impact_presentation",
    "elaborate_cmd",
    "elaborate_impact_presentation",
    "forget_cmd",
    "forget_impact_presentation",
    "resolve_cmd",
    "resolve_impact_presentation",
]
