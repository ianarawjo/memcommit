"""Pure Sever projection into the shared interactive Resolution Workbench."""

from __future__ import annotations

from collections import Counter

from memcommit.memory_diff import MemoryChange
from memcommit.resolution_workbench import (
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
from memcommit.result_workbench import ResultRef
from memcommit.sever import SeverSession, sever_record_digest


_TREATMENT_DISPLAY_LABELS = {
    "KEEP_AS_WRITTEN": "KEEP",
    "KEEP_REDACTED": "REDACT",
    "KEEP_SUMMARY": "SUMMARIZE",
    "KEEP_PREFERENCE_OR_POLICY": "REFRAME",
    "FORGET": "FORGET",
    "CUSTOM": "CUSTOM",
}


def _effective_treatment(candidate) -> str:
    if candidate.selection == "RECOMMENDED":
        return candidate.recommendation
    if candidate.selection == "AS_WRITTEN":
        return "KEEP_AS_WRITTEN"
    if candidate.selection == "FORGET":
        return "FORGET"
    return "CUSTOM"


def sever_memory_changes(session: SeverSession) -> tuple[MemoryChange, ...]:
    """Compare each Source Memory with its reviewed Result representation.

    The location is directional because Sever never edits or deletes Source.
    A missing ``after`` value means omission from the new Result Context, not
    removal from the named Source Context.
    """

    criteria_by_uid = {memory.uid: memory for memory in session.criteria.memories}
    changes: list[MemoryChange] = []
    for candidate in session.candidates:
        source = session.source_memory(candidate.source_memory_uid)
        treatment = _effective_treatment(candidate)
        if treatment == "FORGET":
            after = None
            marker = "−"
        elif candidate.selection == "AS_WRITTEN":
            after = source.content
            marker = "="
        elif candidate.selection == "CUSTOM":
            after = candidate.custom_content
            marker = "~"
        else:
            after = candidate.proposed_content
            marker = "=" if after == source.content else "~"
        changes.append(
            MemoryChange(
                marker=marker,
                treatment=_TREATMENT_DISPLAY_LABELS[treatment],
                location=f"{source.context_name} → {session.output_name}",
                memory_uid=source.uid,
                before=source.content,
                after=after,
                reason=candidate.rationale,
                rules=tuple(
                    criteria_by_uid[uid].content
                    for uid in candidate.criterion_memory_uids
                ),
            )
        )
    return tuple(changes)


def _excerpt(text: str, *, limit: int = 90) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def _named_examples(memories, *, total: int) -> str:
    shown = [f'“{_excerpt(memory.content)}”' for memory in memories]
    if not shown:
        return "none"
    remainder = total - len(shown)
    return ", ".join(shown) + (f", and {remainder} more" if remainder else "")


def _report_items_summary(session: SeverSession) -> str:
    changed = [
        candidate
        for candidate in session.candidates
        if _effective_treatment(candidate) != "KEEP_AS_WRITTEN"
    ]
    affected = [
        session.source_memory(candidate.source_memory_uid)
        for candidate in changed
    ]
    criterion_counts = Counter(
        criterion_uid
        for candidate in changed
        for criterion_uid in candidate.criterion_memory_uids
    )
    criteria_by_uid = {memory.uid: memory for memory in session.criteria.memories}
    influential = [
        criteria_by_uid[uid]
        for uid, _count in criterion_counts.most_common(3)
    ]
    semantic_summary = (
        session.applied_summary.text
        if session.applied_summary is not None
        and all(candidate.selection == "RECOMMENDED" for candidate in session.candidates)
        else (
            "The current reviewed choices change or forget the Source Memories "
            "identified below."
            if changed
            else "The current reviewed choices preserve every Source Memory as written."
        )
    )
    return (
        f"All {len(session.source.memories)} Source Memories were evaluated in one "
        f"contextual batch. {semantic_summary} Affected Source examples: "
        f"{_named_examples(affected[:3], total=len(affected))}. Main Criteria: "
        f"{_named_examples(influential, total=len(criterion_counts))}. Exact Source-to-"
        "Criteria mappings, rationale, and alternatives remain inspectable in "
        "Items; the complete per-Memory outcome appears once in the full result "
        "view. The Source is unchanged, and the Result Context has not been created."
    )


def _overview_sections(session: SeverSession) -> tuple[ResolutionOverviewSection, ...]:
    sections = [ResolutionOverviewSection("understood", "UNDERSTOOD", session.overview)]
    excluded = tuple(
        dict.fromkeys(
            (
                *session.source.excluded_query_context_names,
                *session.criteria.excluded_query_context_names,
            )
        )
    )
    if excluded:
        names = ", ".join(excluded)
        sections.append(
            ResolutionOverviewSection(
                "not-included",
                "NOT INCLUDED",
                f"{names}. These query-only Contexts do not grant readable "
                "Memory access, so they were not part of the Source or "
                "Criteria frame.",
            )
        )
    return tuple(sections)


class SeverResolutionWorkbenchAdapter:
    def __init__(self, session: SeverSession):
        self.session = session

    def view(self) -> ResolutionWorkbenchView:
        session = self.session
        criteria_by_uid = {memory.uid: memory for memory in session.criteria.memories}
        source_position = {
            memory.uid: index
            for index, memory in enumerate(session.source.memories, start=1)
        }
        criterion_position = {
            memory.uid: index
            for index, memory in enumerate(session.criteria.memories, start=1)
        }
        selection_option = {
            "RECOMMENDED": "recommended",
            "AS_WRITTEN": "as-written",
            "FORGET": "forget",
            "CUSTOM": None,
        }
        items: list[ResolutionItem] = []
        for candidate in session.candidates:
            source = session.source_memory(candidate.source_memory_uid)
            cited = [criteria_by_uid[uid] for uid in candidate.criterion_memory_uids]
            evidence_sources = (
                ResolutionIssueSource(
                    label="SOURCE MEMORY",
                    context_name=source.context_name,
                    memory_uid=source.uid,
                    content=source.content,
                    ordinal=source_position[source.uid],
                ),
                *(
                    ResolutionIssueSource(
                        label=f"APPLICABLE CRITERION {index}",
                        context_name=memory.context_name,
                        memory_uid=memory.uid,
                        content=memory.content,
                        ordinal=criterion_position[memory.uid],
                    )
                    for index, memory in enumerate(cited, start=1)
                ),
            )
            evidence_refs = tuple(
                ResultRef(
                    "context-memory",
                    f"{memory.context_name}:{memory.uid}",
                )
                for memory in (source, *cited)
            )
            outcome_ref = ResultRef("sever-result", candidate.uid)
            selected = selection_option[candidate.selection]
            selected_result = (
                "(forgotten)"
                if candidate.selection == "FORGET"
                else candidate.custom_content
                if candidate.selection == "CUSTOM"
                else source.content
                if candidate.selection == "AS_WRITTEN"
                else candidate.proposed_content or "(forgotten)"
            )
            title = " ".join(source.content.split())
            items.append(
                ResolutionItem(
                    uid=candidate.uid,
                    kind="SEVER DECISION",
                    status=candidate.selection,
                    # Every Source Memory needs an explicit, inspectable
                    # treatment. The provider recommendation is staged by
                    # default, so REQUIRED describes review obligation rather
                    # than claiming that no choice exists yet.
                    priority="REQUIRED",
                    title=title,
                    summary=candidate.rationale,
                    role="DECISION",
                    obligation="REQUIRED",
                    response_state="ANSWERED",
                    response_text=(
                        candidate.custom_content
                        if candidate.selection == "CUSTOM"
                        else ""
                    ),
                    question="Choose what the local result should remember.",
                    options=(
                        ResolutionOption(
                            uid=f"{candidate.uid}:recommended",
                            label=(
                                "Use recommendation · "
                                f"{_TREATMENT_DISPLAY_LABELS[candidate.recommendation]}"
                            ),
                            text=(candidate.proposed_content or "Forget this Memory."),
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:as-written",
                            label="Keep",
                            text=source.content,
                        ),
                        ResolutionOption(
                            uid=f"{candidate.uid}:forget",
                            label="Forget",
                            text="Omit this Source Memory from the local result Context.",
                        ),
                    ),
                    selected_option_uid=(
                        None if selected is None else f"{candidate.uid}:{selected}"
                    ),
                    blocks=(
                        ResolutionDetailBlock(
                            heading="PROPOSED RESULT MEMORY",
                            text=selected_result,
                            refs=(outcome_ref,),
                        ),
                    ),
                    decision_block_index=0,
                    evidence_refs=evidence_refs,
                    judgment_refs=(ResultRef("sever-candidate", candidate.uid),),
                    outcome_refs=(outcome_ref,),
                    unresolved_refs=(ResultRef("sever-candidate", candidate.uid),),
                    issue_presentation=ResolutionIssuePresentation(
                        evidence=(
                            ResolutionIssueEvidence(
                                group_heading="SEVER ASSESSMENT",
                                sources_heading="EVIDENCE MEMORIES",
                                sources=evidence_sources,
                                classification=(
                                    "RECOMMENDED RESULT · "
                                    f"{_TREATMENT_DISPLAY_LABELS[candidate.recommendation]}"
                                ),
                                reason_heading="WHY THIS TREATMENT",
                                reason=candidate.rationale,
                            ),
                        ),
                        prompt_heading="SEVER QUESTION",
                        options_heading="PROPOSED RESULT TREATMENTS",
                        other_option_label="Different result wording",
                        response_heading=(
                            "REFINE, COMMENT, OR ENTER DIFFERENT RESULT WORDING"
                        ),
                    ),
                )
            )
        results = tuple(
            ResolutionResult(
                uid=candidate.uid,
                marker=(
                    "−" if _effective_treatment(candidate) == "FORGET" else "+"
                ),
                label=_TREATMENT_DISPLAY_LABELS[_effective_treatment(candidate)],
                text=(
                    "Forgotten from the local result."
                    if candidate.selection == "FORGET"
                    else candidate.custom_content
                    if candidate.selection == "CUSTOM"
                    else session.source_memory(candidate.source_memory_uid).content
                    if candidate.selection == "AS_WRITTEN"
                    else candidate.proposed_content or "Forgotten from the local result."
                ),
                reason=candidate.rationale,
                rules=tuple(
                    criteria_by_uid[uid].content
                    for uid in candidate.criterion_memory_uids
                ),
            )
            for candidate in session.candidates
        )
        overview_sections = _overview_sections(session)
        overview = session.overview
        if len(overview_sections) > 1:
            excluded = overview_sections[1]
            overview += f"\n\n{excluded.heading} · {excluded.text}"
        return ResolutionWorkbenchView(
            operation="sever",
            artifact_uid=session.uid,
            revision=sever_record_digest(session),
            title="MEM SEVER · LOCAL CONTENT REVIEW",
            route=(
                f"SOURCE {session.source.root_name} × CRITERIA "
                f"{session.criteria.root_name} → OUTPUT {session.output_name}"
            ),
            status=session.state,
            metrics=(
                ResolutionMetric(label="SOURCE", value=str(len(session.source.memories))),
                ResolutionMetric(label="CRITERIA", value="1 Context"),
                ResolutionMetric(label="RESULT", value=str(len(session.results()))),
            ),
            context_locations=(
                ResolutionContextLocation("SOURCE", session.source.root_name),
                ResolutionContextLocation("CRITERIA", session.criteria.root_name),
                ResolutionContextLocation(
                    "RESULT",
                    session.output_name,
                    "CREATED" if session.state == "APPLIED" else "NOT CREATED",
                ),
            ),
            overview=overview,
            overview_sections=overview_sections,
            list_label="SOURCE MEMORIES TO REVIEW",
            items=tuple(items),
            empty_message="No source Memories.",
            results_label="LOCAL RESULT DRAFT · SOURCE UNCHANGED",
            results=results,
            capabilities=(
                frozenset()
                if session.state == "APPLIED"
                else frozenset({"SUBMIT_ITEM", "ACCEPT"})
            ),
            accept_enabled=session.state == "REVIEWING",
            input_locked=session.state == "APPLIED",
            report_items_summary=ResolutionDetailBlock(
                heading="WHAT APPLIED",
                text=_report_items_summary(session),
            ),
        )
