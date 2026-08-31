"""Operation-owned Atomize projection for the shared resolution UI."""

from __future__ import annotations

from memcommit.application.operations.semantic_updates.derive.atomize.domain import AtomizeAnalysisSession
from memcommit.application.operations.semantic_updates.derive.atomize.records import (
    AtomizeRecordError,
    AtomizeReviewFinding,
    AtomizeReviewRecord,
    atomize_review_issue_projection,
    project_atomize_review_findings,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionContextLocation,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMemoryRow,
    ResolutionMetric,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
    resolution_overview_text,
)
from memcommit.application.capabilities.reviewing.result_workbench import ResultRef


def _priority_label(finding: AtomizeReviewFinding) -> str:
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
    """Project immutable Atomize findings into a read-only issue surface."""

    def __init__(
        self,
        analysis: AtomizeAnalysisSession,
        workbench: AtomizeReviewRecord,
    ):
        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")
        if not isinstance(workbench, AtomizeReviewRecord):
            raise TypeError("Expected an AtomizeReviewRecord.")
        if not workbench.matches_analysis(
            analysis_uid=analysis.uid,
            context_uid=analysis.context_uid,
            context_name=analysis.context_name,
            context_digest=analysis.context_digest,
            issues=atomize_review_issue_projection(analysis),
        ):
            raise AtomizeRecordError(
                "The atomize workbench does not match its saved analysis."
            )
        self._analysis = analysis
        self._workbench = workbench

    def view(self) -> ResolutionWorkbenchView:
        analysis = self._analysis
        workbench = self._workbench
        findings = {
            finding.uid: finding
            for finding in project_atomize_review_findings(analysis)
        }
        source_by_uid = {item.memory_uid: item.content for item in analysis.items}
        position_by_uid = {
            item.memory_uid: item.position + 1 for item in analysis.items
        }
        application_complete = workbench.application is not None
        projected: list[ResolutionItem] = []
        for descriptor in workbench.ordered_issues():
            finding = findings[descriptor.uid]
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
                "ATOMIZE_UNCERTAINTY": "WHY THIS IS UNCLEAR",
            }[finding.kind]
            conflict = finding.kind == "CONFLICT"
            ambiguity = finding.kind in {"AMBIGUITY", "ATOMIZE_UNCERTAINTY"}
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
            if finding.readings:
                blocks.append(
                    ResolutionDetailBlock(
                        heading="POSSIBLE READINGS",
                        text="\n".join(
                            f"[{reading.role}] {reading.label} — {reading.text}"
                            for reading in finding.readings
                        ),
                    )
                )
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
                    kind=(
                        "AMBIGUITY"
                        if finding.kind == "ATOMIZE_UNCERTAINTY"
                        else finding.kind
                    ),
                    status="RECORDED",
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
                    role="OPTIONAL_REVIEW",
                    # Atomize records what it could not settle, but it does not
                    # turn those findings into a conversational sub-operation.
                    obligation="NONE",
                    response_state="NOT_APPLICABLE",
                    kind_label=(
                        "SUGGESTED SPLIT" if finding.kind == "ATOMIZE_SPLIT" else None
                    ),
                    question=finding.question,
                    blocks=tuple(blocks),
                    decision_block_index=0,
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
                    commentable=False,
                )
            )
        unresolved_at_apply_count = sum(
            finding.kind
            in {
                "AMBIGUITY",
                "CONFLICT",
                "ATOMIZE_UNCERTAINTY",
            }
            for finding in findings.values()
        )
        unresolved_at_apply = unresolved_at_apply_count > 0
        capabilities = (
            frozenset({"ACCEPT"}) if not application_complete else frozenset()
        )
        overview_sections = _overview_sections(analysis)
        return ResolutionWorkbenchView(
            operation="ATOMIZE",
            artifact_uid=workbench.uid,
            # Review navigation is presentation state only; no response can
            # revise this analysis from inside Atomize.
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
                if unresolved_at_apply
                else "READY_TO_APPLY"
            ),
            metrics=(
                ResolutionMetric("SOURCE MEMORIES", str(analysis.memory_count)),
                ResolutionMetric(
                    "PROJECTED MEMORIES",
                    str(analysis.projected_memory_count),
                ),
                ResolutionMetric("FINDINGS", str(len(projected))),
                ResolutionMetric("UNRESOLVED", str(unresolved_at_apply_count)),
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
            list_label="ATOMIZE FINDINGS",
            items=tuple(projected),
            empty_message="No Atomize findings in this analysis.",
            results_label="EXACT RESULTS",
            # Split children remain source-linked analysis evidence until the
            # separate Apply Changes boundary mutates the Context.
            results=(),
            # The generic Resolution result list is not Atomize's projected
            # output model. Exact proposed children remain adjacent to their
            # source finding, so an empty generic list must not imply that the
            # saved analysis projects zero Memories.
            show_results=False,
            capabilities=capabilities,
            accept_enabled=not application_complete,
            accept_mode=(
                "AS_IS"
                if unresolved_at_apply and not application_complete
                else "CHANGES"
            ),
            unresolved_at_apply_count=(
                unresolved_at_apply_count if not application_complete else 0
            ),
            input_locked=application_complete,
        )


def project_atomize_resolution(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeReviewRecord,
) -> ResolutionWorkbenchView:
    """Return the common view for one analysis-bound Atomize workbench."""
    return AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()
