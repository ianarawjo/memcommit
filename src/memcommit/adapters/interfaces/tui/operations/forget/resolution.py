"""Project batch Forget decisions into the shared Resolution Workbench."""

from __future__ import annotations

from memcommit.application.operations.forget.review import ForgetReview
from memcommit.application.reviewing.memory_diff import MemoryChange
from memcommit.application.resolution.workbench import (
    ResolutionDetailBlock,
    ResolutionContextLocation,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOption,
    ResolutionOverviewSection,
    ResolutionResult,
    ResolutionWorkbenchView,
)
from memcommit.application.reviewing.result_workbench import ResultRef


def forget_memory_changes(review: ForgetReview) -> tuple[MemoryChange, ...]:
    """Project every reviewed Source Memory as one exact in-place transition.

    Forget's public mutation API remains sparse, but its review must keep the
    complete frozen Source visible.  In particular, a DROP needs the original
    value as ``before`` so the shared diff surface never replaces evidence with
    a generic "will be removed" sentence.
    """

    changes: list[MemoryChange] = []
    for candidate in review.candidates:
        action, content = candidate.selected_action()
        source = candidate.source
        changes.append(
            MemoryChange(
                marker="−" if action == "DROP" else "=" if action == "KEEP" else "~",
                treatment=action,
                location=review.context_name,
                memory_uid=source.uid,
                before=source.content,
                after=None if action == "DROP" else content,
                reason=candidate.decision.rationale,
            )
        )
    return tuple(changes)


class ForgetResolutionWorkbenchAdapter:
    def __init__(self, review: ForgetReview):
        self.review = review

    def view(self) -> ResolutionWorkbenchView:
        review = self.review
        items: list[ResolutionItem] = []
        results: list[ResolutionResult] = []
        selected_options = {
            "RECOMMENDED": "recommended",
            "KEEP": "keep",
            "DELETE": "delete",
            "CUSTOM": None,
        }
        for position, candidate in enumerate(review.candidates, 1):
            decision = candidate.decision
            source = candidate.source
            selected = selected_options[candidate.selection]
            source_ref = ResultRef("context-memory", f"{review.context_name}:{source.uid}")
            judgment_ref = ResultRef("forget-decision", candidate.uid)
            outcome_ref = ResultRef("forget-result", candidate.uid)
            selected_action, selected_content = candidate.selected_action()
            result_text = (
                "This Source Memory will be removed from its current Context."
                if selected_action == "DROP"
                else selected_content
            )
            items.append(
                ResolutionItem(
                    uid=candidate.uid,
                    kind="FORGET DECISION",
                    status=candidate.selection,
                    priority="REQUIRED",
                    title=" ".join(source.content.split()),
                    summary=decision.rationale,
                    role="DECISION",
                    obligation="REQUIRED",
                    response_state="ANSWERED",
                    response_text=(
                        candidate.custom_content
                        if candidate.selection == "CUSTOM"
                        else ""
                    ),
                    question="Choose what the Source Context should remember.",
                    options=(
                        ResolutionOption(
                            uid=f"{candidate.uid}:recommended",
                            label=f"Use recommendation · {decision.variant}",
                            text=result_text,
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:keep",
                            label="Keep as written",
                            text=source.content,
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:delete",
                            label="Delete",
                            text="Remove this Memory from the Source Context.",
                        ),
                    ),
                    selected_option_uid=(
                        None if selected is None else f"{candidate.uid}:{selected}"
                    ),
                    blocks=(
                        ResolutionDetailBlock(
                            heading="PROPOSED RESULT",
                            text=result_text,
                            refs=(outcome_ref,),
                        ),
                    ),
                    evidence_refs=(source_ref,),
                    judgment_refs=(judgment_ref,),
                    outcome_refs=(outcome_ref,),
                    unresolved_refs=(judgment_ref,),
                    issue_presentation=ResolutionIssuePresentation(
                        evidence=(
                            ResolutionIssueEvidence(
                                group_heading="FORGET ASSESSMENT",
                                sources_heading="SOURCE MEMORY",
                                classification=f"RECOMMENDED ACTION · {decision.variant}",
                                reason_heading="WHY THIS ACTION",
                                reason=decision.rationale,
                                criterion_blocks=(
                                    ResolutionDetailBlock(
                                        heading="FORGET INSTRUCTION",
                                        text=review.instruction,
                                    ),
                                ),
                                sources=(
                                    ResolutionIssueSource(
                                        label="SOURCE 1",
                                        context_name=review.context_name,
                                        memory_uid=source.uid,
                                        content=source.content,
                                        ordinal=position,
                                    ),
                                ),
                            ),
                        ),
                        prompt_heading="FORGET QUESTION",
                        options_heading="PROPOSED MEMORY TREATMENTS",
                        other_option_label="Different retained wording",
                        response_heading="REFINE OR ENTER DIFFERENT RETAINED WORDING",
                    ),
                    commentable=True,
                )
            )
            action, content = selected_action, selected_content
            results.append(
                ResolutionResult(
                    uid=candidate.uid,
                    marker="−" if action == "DROP" else "=" if action == "KEEP" else "~",
                    label=action,
                    text=(
                        "This Source Memory will be removed."
                        if action == "DROP"
                        else content
                    ),
                    reason=decision.rationale,
                )
            )
        changed = sum(result.label != "KEEP" for result in results)
        overview_sections = (
            ResolutionOverviewSection(
                "assessment",
                "ASSESSMENT",
                review.overview,
            ),
        )
        return ResolutionWorkbenchView(
            operation="forget",
            artifact_uid=review.uid,
            revision=str(review.revision),
            title="MEM FORGET · SELECTIVE SOURCE REVISION",
            route=f"SOURCE {review.context_name} × INSTRUCTION → SAME SOURCE",
            status="REVIEWING",
            metrics=(
                ResolutionMetric("SOURCE", str(len(review.candidates))),
                ResolutionMetric("CRITERION", "1 instruction"),
                ResolutionMetric("CHANGES", str(changed)),
            ),
            context_locations=(
                ResolutionContextLocation("SOURCE", review.context_name),
            ),
            overview=review.overview,
            overview_sections=overview_sections,
            list_label="SOURCE MEMORIES TO REVIEW",
            items=tuple(items),
            empty_message="No Source Memories.",
            results_label="PROPOSED SOURCE RESULT",
            results=tuple(results),
            capabilities=frozenset({"SUBMIT_ITEM", "ACCEPT"}),
            accept_enabled=True,
            input_locked=False,
            report_items_summary=ResolutionDetailBlock(
                heading="WHAT APPLIES",
                text=(
                    f"The one Forget instruction was evaluated against all "
                    f"{len(review.candidates)} direct Source Memories in one batch. "
                    f"The current reviewed result changes {changed}; unchanged Memories "
                    "remain explicit and inspectable in Items."
                ),
            ),
        )
