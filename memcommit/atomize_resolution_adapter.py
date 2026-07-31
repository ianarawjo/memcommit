"""Pure Atomize analysis/workbench projection for shared resolution UI."""
from __future__ import annotations

from memcommit.atomize import AtomizeAnalysisSession
from memcommit.atomize_workbench import (
    AtomizeWorkbenchError,
    AtomizeWorkbenchFinding,
    AtomizeWorkbenchSession,
    atomize_workbench_issue_projection,
    project_atomize_workbench_findings,
)
from memcommit.resolution_workbench import (
    ResolutionDetailBlock,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOption,
    ResolutionWorkbenchView,
)


_KIND_LABELS = {
    "AMBIGUITY": "AMBIGUITY",
    "CONFLICT": "CONFLICT",
    "ATOMIZE_SPLIT": "ATOMIZE SPLIT",
    "ATOMIZE_UNCERTAINTY": "ATOMIZE UNCERTAINTY",
}


def _priority_label(finding: AtomizeWorkbenchFinding) -> str:
    return {
        4: "REQUIRED",
        2: "HELPFUL",
        1: "REVIEW",
    }.get(finding.priority, f"PRIORITY {finding.priority}")


def _overview(analysis: AtomizeAnalysisSession) -> str:
    if analysis.overview is None:
        return "The saved Atomize analysis has no compact overview."
    return "\n\n".join(
        (
            f"UNDERSTOOD\n{analysis.overview.understood.text}",
            f"CHANGED\n{analysis.overview.changed.text}",
            f"UNRESOLVED\n{analysis.overview.unresolved.text}",
        )
    )


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
        source_by_uid = {
            item.memory_uid: item.content for item in analysis.items
        }
        projected: list[ResolutionItem] = []
        for descriptor in workbench.ordered_issues():
            finding = findings[descriptor.uid]
            response = workbench.responses.get(finding.uid)
            arity = "UNARY" if len(finding.source_uids) == 1 else "PAIR"
            source_text = "\n\n".join(
                f"SOURCE {index} [{source_uid}]\n{source_by_uid[source_uid]}"
                for index, source_uid in enumerate(
                    finding.source_uids,
                    start=1,
                )
            )
            blocks: list[ResolutionDetailBlock] = [
                ResolutionDetailBlock(
                    heading=f"SOURCES · {arity}",
                    text=source_text,
                ),
                ResolutionDetailBlock(
                    heading="CLASSIFICATION",
                    text=finding.classification,
                ),
                ResolutionDetailBlock(
                    heading="REASON",
                    text=finding.reason,
                ),
            ]
            if finding.children:
                child_lines: list[str] = []
                for index, child in enumerate(finding.children, start=1):
                    line = f"{index}. {child.content}"
                    evidence = (*child.source_spans, *child.frame_spans)
                    if evidence:
                        line += "\nEvidence: " + " | ".join(evidence)
                    child_lines.append(line)
                blocks.append(
                    ResolutionDetailBlock(
                        heading="PROPOSED CHILDREN",
                        text="\n\n".join(child_lines),
                    )
                )
            if response is not None and response.answered:
                response_parts: list[str] = []
                if response.selected_choice_uid is not None:
                    response_parts.append(
                        "Selected reading: " + response.selected_choice_uid
                    )
                if response.text:
                    response_parts.append("Comment:\n" + response.text)
                blocks.append(
                    ResolutionDetailBlock(
                        heading="SAVED RESPONSE",
                        text="\n\n".join(response_parts),
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
                    title=_KIND_LABELS[finding.kind],
                    summary=finding.reason,
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
                    selected_option_uid=(
                        response.selected_choice_uid
                        if response is not None
                        else None
                    ),
                )
            )
        return ResolutionWorkbenchView(
            operation="ATOMIZE",
            artifact_uid=workbench.uid,
            # A durable answer edits the current issue; it does not replace
            # the list.  Keep the common navigation revision pinned to the
            # analysis and issue projection so detail/option focus survives.
            revision=f"{analysis.uid}:{workbench.issue_digest}",
            title="MEM ATOMIZE",
            route=f"CONTEXT {analysis.context_name}",
            status="REVIEWING",
            metrics=(
                ResolutionMetric("SOURCE MEMORIES", str(analysis.memory_count)),
                ResolutionMetric(
                    "PROJECTED MEMORIES",
                    str(analysis.projected_memory_count),
                ),
                ResolutionMetric("FINDINGS", str(len(projected))),
                ResolutionMetric("ANSWERED", str(workbench.answered_count)),
            ),
            overview=_overview(analysis),
            list_label="ACTIONABLE FINDINGS",
            items=tuple(projected),
            empty_message="No actionable Atomize findings in this analysis.",
            results_label="EXACT RESULTS",
            # Split children are analysis evidence, not an approved mutation.
            results=(),
            capabilities=frozenset({"SUBMIT_ITEM"}),
            accept_enabled=False,
            input_locked=False,
        )


def project_atomize_resolution(
    analysis: AtomizeAnalysisSession,
    workbench: AtomizeWorkbenchSession,
) -> ResolutionWorkbenchView:
    """Return the common view for one analysis-bound Atomize workbench."""
    return AtomizeResolutionWorkbenchAdapter(analysis, workbench).view()
