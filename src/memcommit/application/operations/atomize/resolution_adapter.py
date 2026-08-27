"""Operation-owned Atomize projection for the shared resolution UI."""

from __future__ import annotations

from memcommit.application.operations.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.atomize.workbench import (
    AtomizeWorkbenchError,
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
    project_atomize_workbench_findings,
)
from memcommit.application.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionContextLocation,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionMetric,
    ResolutionOption,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
    resolution_overview_text,
)
from memcommit.application.reviewing.result_workbench import ResultRef


def _priority_label(finding: AtomizeWorkbenchFinding) -> str:
    return {
        # Priority describes semantic attention, not whether a response gates
        # application. Atomize can apply its exact current proposal while a
        # high-attention finding remains explicitly unresolved.
        4: "HIGH",
        2: "HELPFUL",
        1: "REVIEW",
    }.get(finding.priority, f"PRIORITY {finding.priority}")


def _overview_sections(
    analysis: AtomizeAnalysisSession,
) -> tuple[ResolutionOverviewSection, ...]:
    if analysis.overview is None:
        return (
            ResolutionOverviewSection(
                "not-recorded",
                "NOT RECORDED",
                "The saved Atomize analysis has no compact overview.",
            ),
        )
    return (
        ResolutionOverviewSection(
            "understood",
            "UNDERSTOOD",
            analysis.overview.understood.text,
        ),
        ResolutionOverviewSection(
            "changed",
            "CHANGED",
            analysis.overview.changed.text,
        ),
        ResolutionOverviewSection(
            "unresolved",
            "UNRESOLVED",
            analysis.overview.unresolved.text,
        ),
    )


def _memory_preview(content: str, *, limit: int = 180) -> str:
    compact = " ".join(content.split()) or "(empty Memory)"
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


class AtomizeResolutionWorkbenchAdapter:
    """Join immutable findings with their exact durable response state."""

    def __init__(
        self,
        analysis: AtomizeAnalysisSession,
        workbench: AtomizeWorkbenchSession,
    ):
        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        if not isinstance(workbench, AtomizeWorkbenchSession):
            raise TypeError("Expected an AtomizeWorkbenchSession.")
        if not workbench.matches_analysis(
            analysis_uid=analysis.uid,
            context_uid=analysis.context_uid,
            context_name=analysis.context_name,
            context_digest=analysis.context_digest,
            issues=atomize_workbench_issue_projection(analysis),
        ):
            raise AtomizeWorkbenchError(
                "The atomize workbench does not match its saved analysis."
            )
        self._analysis = analysis
        self._workbench = workbench

    def view(self) -> ResolutionWorkbenchView:
        analysis = self._analysis
        workbench = self._workbench
        findings = {
            finding.uid: finding
            for finding in project_atomize_workbench_findings(analysis)
        }
        source_by_uid = {item.memory_uid: item.content for item in analysis.items}
        position_by_uid = {
            item.memory_uid: item.position + 1 for item in analysis.items
        }
        application_complete = workbench.application is not None
        projected: list[ResolutionItem] = []
        for descriptor in workbench.ordered_issues():
            finding = findings[descriptor.uid]
            response = workbench.responses.get(finding.uid)
            source_refs = tuple(
                ResultRef(
                    "context-memory",
                    f"{analysis.context_name}:{source_uid}",
                )
                for source_uid in finding.source_uids
            )
            judgment_ref = ResultRef("atomize-finding", finding.uid)
            issue_sources = tuple(
                ResolutionIssueSource(
                    label=f"SOURCE {index}",
                    context_name=analysis.context_name,
                    memory_uid=source_uid,
                    content=source_by_uid[source_uid],
                    ordinal=position_by_uid[source_uid],
                )
                for index, source_uid in enumerate(
                    finding.source_uids,
                    start=1,
                )
            )
            reason_heading = {
                "AMBIGUITY": "WHY THIS IS UNCLEAR",
                "CONFLICT": "WHY THESE MEMORIES CONFLICT",
                "ATOMIZE_SPLIT": "WHY THIS MEMORY SPLIT",
                "ATOMIZE_UNCERTAINTY": "WHY ATOMIZE IS BLOCKED",
            }[finding.kind]
            conflict = finding.kind == "CONFLICT"
            ambiguity = finding.kind == "AMBIGUITY"
            issue_presentation = ResolutionIssuePresentation(
                evidence=(
                    ResolutionIssueEvidence(
                        group_heading="",
                        sources_heading=(
                            "SOURCE MEMORIES" if conflict else "SOURCE MEMORY"
                        ),
                        sources=issue_sources,
                        classification=finding.classification,
                        reason_heading=reason_heading,
                        reason=finding.reason,
                    ),
                ),
                prompt_heading=(
                    "RESOLUTION QUESTION"
                    if conflict
                    else "CLARIFICATION QUESTION"
                    if ambiguity
                    else "REVIEW QUESTION"
                ),
                options_heading=(
                    "PROPOSED RESOLUTIONS"
                    if conflict
                    else "PROPOSED READINGS"
                    if ambiguity
                    else "PROPOSED RESPONSES"
                ),
                other_option_label=(
                    "Different resolution"
                    if conflict
                    else "Different reading"
                    if ambiguity
                    else "Different direction"
                ),
                response_heading=(
                    "REFINE, COMMENT, OR ENTER A DIFFERENT RESOLUTION"
                    if conflict
                    else "REFINE, COMMENT, OR ENTER A DIFFERENT READING"
                    if ambiguity
                    else "COMMENT OR ENTER A DIFFERENT DIRECTION"
                ),
            )
            blocks: list[ResolutionDetailBlock] = []
            if finding.children:
                child_rows = tuple(
                    ResolutionMemoryRow(
                        ordinal=index,
                        content=child.content,
                        evidence=(*child.source_spans, *child.frame_spans),
                        ref=ResultRef(
                            "atomize-child",
                            f"{finding.uid}:{index}",
                        ),
                    )
                    for index, child in enumerate(finding.children, start=1)
                )
                blocks.append(
                    ResolutionDetailBlock(
                        heading=(
                            "APPLIED CHILD MEMORIES"
                            if application_complete
                            else "PROPOSED CHILDREN"
                        ),
                        text="",
                        memory_rows=child_rows,
                    )
                )
            projected.append(
                ResolutionItem(
                    uid=finding.uid,
                    kind=finding.kind,
                    status=(
                        "ANSWERED"
                        if response is not None and response.answered
                        else "OPEN"
                    ),
                    priority=_priority_label(finding),
                    # Memory has no separate display name. Pair the stable
                    # identity with the content preview so Review never makes
                    # synthetic SOURCE ordinals look like Memory names.
                    title=" ↔ ".join(
                        f"[{source_uid[:8]}] "
                        f"{_memory_preview(source_by_uid[source_uid])}"
                        for source_uid in finding.source_uids
                    ),
                    summary=finding.reason,
                    role=(
                        "OPTIONAL_REVIEW"
                        if finding.kind == "ATOMIZE_SPLIT"
                        else "DECISION"
                    ),
                    # Atomize findings remain answerable, but none requires a
                    # per-item response before the current proposal can apply.
                    obligation="OPTIONAL",
                    response_state=(
                        "ANSWERED"
                        if response is not None and response.answered
                        else "OPEN"
                    ),
                    response_text=(response.text if response is not None else ""),
                    kind_label=(
                        "SUGGESTED SPLIT" if finding.kind == "ATOMIZE_SPLIT" else None
                    ),
                    question=finding.question,
                    options=tuple(
                        ResolutionOption(
                            uid=reading.uid,
                            label=f"[{reading.role}] {reading.label}",
                            text=reading.text,
                        )
                        for reading in finding.readings
                    ),
                    blocks=tuple(blocks),
                    decision_block_index=0,
                    selected_option_uid=(
                        response.selected_choice_uid if response is not None else None
                    ),
                    evidence_refs=source_refs,
                    judgment_refs=(judgment_ref,),
                    outcome_refs=tuple(
                        ResultRef("atomize-child", f"{finding.uid}:{index}")
                        for index, _child in enumerate(
                            finding.children,
                            start=1,
                        )
                    ),
                    unresolved_refs=(ResultRef("atomize-finding", finding.uid),),
                    issue_presentation=issue_presentation,
                    commentable=True,
                )
            )
        # Unary responses can change the atomization proposal and therefore
        # require one batch incorporation turn. An unanswered finding does
        # not imply deferment and does not gate applying the exact proposal.
        # Pairwise Conflict responses remain non-atomizing review evidence;
        # they cannot become a single-Memory declared frame.
        incorporable_response_open = any(
            response is not None
            and response.answered
            and len(findings[issue_uid].source_uids) == 1
            for issue_uid, response in workbench.responses.items()
        )
        ready_to_apply = not incorporable_response_open
        unresolved_at_apply_count = sum(
            finding.kind
            in {
                "AMBIGUITY",
                "CONFLICT",
                "ATOMIZE_UNCERTAINTY",
            }
            for finding in findings.values()
        )
        open_optional_review = any(
            item.effective_obligation == "OPTIONAL" and item.response_state == "OPEN"
            for item in projected
        )
        unresolved_at_apply = unresolved_at_apply_count > 0 or open_optional_review
        capabilities: set[str] = set()
        if not application_complete:
            capabilities.update({"SUBMIT_ITEM", "SUBMIT_ALL"})
        if ready_to_apply and not application_complete:
            capabilities.add("ACCEPT")
        elif not application_complete:
            # Atomize can honor one reviewed compound boundary: incorporate
            # the saved unary response frame, revalidate the new proposal,
            # and apply it without forcing a second approval screen.
            capabilities.add("INCORPORATE_AND_APPLY")
        overview_sections = _overview_sections(analysis)
        return ResolutionWorkbenchView(
            operation="ATOMIZE",
            artifact_uid=workbench.uid,
            # A durable answer edits the current issue; it does not replace
            # the list.  Keep the common navigation revision pinned to the
            # analysis and issue projection so detail/option focus survives.
            revision=f"{analysis.uid}:{workbench.issue_digest}",
            title="MEM ATOMIZE",
            route=(
                f"INPUT {analysis.context_name} → OUTPUT "
                f"{workbench.output_context_name or analysis.context_name}"
            ),
            status=(
                "APPLIED"
                if application_complete
                else "READY_TO_APPLY_AS_IS"
                if ready_to_apply and unresolved_at_apply
                else "READY_TO_APPLY"
                if ready_to_apply
                else "REVIEWING"
            ),
            metrics=(
                ResolutionMetric("SOURCE MEMORIES", str(analysis.memory_count)),
                ResolutionMetric(
                    "PROJECTED MEMORIES",
                    str(analysis.projected_memory_count),
                ),
                ResolutionMetric("FINDINGS", str(len(projected))),
                ResolutionMetric("ANSWERED", str(workbench.answered_count)),
            ),
            context_locations=(
                ResolutionContextLocation("SOURCE", analysis.context_name),
                ResolutionContextLocation(
                    "OUTPUT",
                    workbench.output_context_name or analysis.context_name,
                    (
                        "IN PLACE"
                        if (workbench.output_context_name or analysis.context_name)
                        == analysis.context_name
                        else "CREATE ON APPLY"
                    ),
                ),
            ),
            overview=resolution_overview_text(overview_sections),
            overview_sections=overview_sections,
            list_label="ACTIONABLE FINDINGS",
            items=tuple(projected),
            empty_message="No actionable Atomize findings in this analysis.",
            results_label="EXACT RESULTS",
            # Split children remain source-linked analysis evidence until the
            # separate Apply Changes boundary mutates the Context.
            results=(),
            # The generic Resolution result list is not Atomize's projected
            # output model. Exact proposed children remain adjacent to their
            # source finding, so an empty generic list must not imply that the
            # saved analysis projects zero Memories.
            show_results=False,
            capabilities=frozenset(capabilities),
            accept_enabled=ready_to_apply and not application_complete,
            accept_mode=(
                "AS_IS"
                if ready_to_apply and unresolved_at_apply and not application_complete
                else "CHANGES"
            ),
            unresolved_at_apply_count=(
                unresolved_at_apply_count
                if ready_to_apply and not application_complete
                else 0
            ),
            input_locked=application_complete,
        )


def project_atomize_resolution(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> ResolutionWorkbenchView:
    """Return the common view for one analysis-bound Atomize workbench."""
    return AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()
