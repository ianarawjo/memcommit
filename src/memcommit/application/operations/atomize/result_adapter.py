"""Operation-owned projection for the shared semantic result workbench.

Atomize remains authoritative for classifications, quality findings, source
linkage, persistence, and application.  This adapter only translates one
already validated analysis into the operation-neutral inspection contract.
It never calls a provider and never mutates either the analysis or a Context.
"""
from __future__ import annotations

from memcommit.core.json_objects import canonical_json_digest

from memcommit.application.operations.atomize.domain import (
    ATOMIZE_CLASSIFICATIONS,
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeQualityIssue,
)
from memcommit.application.capabilities.reviewing.result_workbench import (
    ResultCase,
    ResultMetric,
    ResultRef,
    ResultSection,
    ResultWorkbenchView,
)
from memcommit.application.capabilities.semantic.understanding import UnderstandingSummary


_LEGACY_UNDERSTOOD = (
    "This legacy analysis did not store a semantic comprehension summary; "
    "inspect its source-linked items below."
)
_REPRESENTATIVE_CLASSIFICATIONS = {
    "ATOMIC",
    "COMPOSITE",
    "NON_PROPOSITIONAL",
}


def atomize_result_artifact_digest(
    analysis: AtomizeAnalysisSession,
) -> str:
    """Content-address the normalized complete Atomize analysis artifact."""
    if not isinstance(analysis, AtomizeAnalysisSession):
        raise TypeError("Expected an AtomizeAnalysisSession.")
    return canonical_json_digest(analysis.to_dict())


def _unique_refs(refs: tuple[ResultRef, ...]) -> tuple[ResultRef, ...]:
    return tuple(dict.fromkeys(refs))


def _source_ref(memory_uid: str) -> ResultRef:
    return ResultRef(kind="source-memory", key=memory_uid)


def _result_ref(memory_uid: str) -> ResultRef:
    return ResultRef(kind="atomize-result", key=memory_uid)


def _child_ref(memory_uid: str, index: int) -> ResultRef:
    return ResultRef(
        kind="atomize-child",
        key=f"{memory_uid}:{index}",
    )


def _quality_ref(issue_uid: str) -> ResultRef:
    return ResultRef(kind="atomize-quality-issue", key=issue_uid)


def _uncertain_ref(memory_uid: str) -> ResultRef:
    return ResultRef(kind="atomize-uncertainty", key=memory_uid)


def _preview(text: str, *, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if not compact:
        return 'Content: ""'
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _outcome_refs(item: AtomizeAnalysisItem) -> tuple[ResultRef, ...]:
    if item.classification == "COMPOSITE":
        return tuple(
            _child_ref(item.memory_uid, index)
            for index, _ in enumerate(item.children, start=1)
        )
    return (_result_ref(item.memory_uid),)


def _is_actionable_quality_issue(issue: AtomizeQualityIssue) -> bool:
    return (
        issue.kind == "CONFLICT"
        or issue.clarification in {"HELPFUL", "REQUIRED"}
    )


class AtomizeResultWorkbenchAdapter:
    """Project one immutable Atomize analysis without broadening its claims."""

    def __init__(self, analysis: AtomizeAnalysisSession):
        if not isinstance(analysis, AtomizeAnalysisSession):
            raise TypeError("Expected an AtomizeAnalysisSession.")

        # The round trip rechecks all item ordering, counts, source identities,
        # spans, and Context digest invariants before common UI code sees them.
        # Preserve this bit first because serialization deliberately supplies a
        # compatibility overview for artifacts that never recorded one.
        overview_was_recorded = (
            analysis.overview is not None
            and analysis.overview.understood.text != _LEGACY_UNDERSTOOD
        )
        self._analysis = AtomizeAnalysisSession.from_dict(analysis.to_dict())
        self._overview_was_recorded = overview_was_recorded
        self._artifact_digest = atomize_result_artifact_digest(self._analysis)
        self._item_by_uid = {
            item.memory_uid: item for item in self._analysis.items
        }
        self._cases = self._build_cases()
        self._view = self._build_view()

    def view(self) -> ResultWorkbenchView:
        """Return the immutable common result projection."""
        return self._view

    def _source_refs(
        self,
        section: UnderstandingSummary,
    ) -> tuple[ResultRef, ...]:
        return tuple(_source_ref(uid) for uid in section.source_uids)

    def _frame_ref(self) -> ResultRef:
        return ResultRef(
            kind="atomize-context-frame",
            key=self._analysis.context_digest,
        )

    def _understood_section(self) -> ResultSection:
        overview = self._analysis.overview
        assert overview is not None
        if not self._overview_was_recorded:
            return ResultSection(
                state="NOT_RECORDED",
                text=(
                    "This analysis did not record a source-linked semantic "
                    "understanding summary."
                ),
            )
        section = overview.understood
        if not section.text.strip():
            return ResultSection(
                state="NOT_RECORDED",
                text=(
                    "The saved analysis contains no semantic understanding "
                    "summary."
                ),
            )
        refs = self._source_refs(section)
        if not refs and not self._analysis.items:
            refs = (self._frame_ref(),)
        if not refs:
            return ResultSection(
                state="NOT_RECORDED",
                text=(
                    "The saved understanding summary has no source links and "
                    "cannot be projected as a supported claim."
                ),
            )
        return ResultSection(
            state="PRESENT",
            text=section.text,
            refs=refs,
        )

    def _derived_happened_section(self) -> ResultSection:
        counts = {
            classification: sum(
                item.classification == classification
                for item in self._analysis.items
            )
            for classification in ATOMIZE_CLASSIFICATIONS
        }
        child_count = sum(
            len(item.children)
            for item in self._analysis.items
            if item.classification == "COMPOSITE"
        )
        text = (
            "Validated item records keep "
            f"{counts['ATOMIC']} atomic, split {counts['COMPOSITE']} "
            f"composite into {child_count} children, retain "
            f"{counts['NON_PROPOSITIONAL']} non-propositional, and leave "
            f"{counts['UNCERTAIN']} uncertain for reconciliation."
        )
        refs = _unique_refs(
            tuple(
                ref
                for item in self._analysis.items
                for ref in _outcome_refs(item)
            )
        )
        if not refs:
            refs = (self._frame_ref(),)
            text = (
                "The validated empty Context produces no atomization "
                "outcome records."
            )
        return ResultSection(state="PRESENT", text=text, refs=refs)

    def _happened_section(self) -> ResultSection:
        overview = self._analysis.overview
        assert overview is not None
        section = overview.changed
        if self._overview_was_recorded and section.text.strip():
            refs = _unique_refs(
                tuple(
                    ref
                    for uid in section.source_uids
                    for ref in _outcome_refs(self._item_by_uid[uid])
                )
            )
            if not refs and not self._analysis.items:
                refs = (self._frame_ref(),)
            if refs:
                return ResultSection(
                    state="PRESENT",
                    text=section.text,
                    refs=refs,
                )
        # Legacy artifacts still prove their exact item outcomes.  Deriving
        # this account locally is safer than presenting compatibility prose as
        # though it were a provider-authored semantic summary.
        return self._derived_happened_section()

    def _actual_unresolved_refs(self) -> tuple[ResultRef, ...]:
        return _unique_refs(
            tuple(
                _quality_ref(issue.uid)
                for issue in self._analysis.quality_issues
                if _is_actionable_quality_issue(issue)
            )
            + tuple(
                _uncertain_ref(item.memory_uid)
                for item in self._analysis.items
                if item.classification == "UNCERTAIN"
            )
        )

    def _unresolved_section(self) -> ResultSection:
        overview = self._analysis.overview
        assert overview is not None
        section = overview.unresolved
        actual_refs = self._actual_unresolved_refs()

        if actual_refs:
            quality_count = sum(
                _is_actionable_quality_issue(issue)
                for issue in self._analysis.quality_issues
            )
            uncertain_count = sum(
                item.classification == "UNCERTAIN"
                for item in self._analysis.items
            )
            text = section.text.strip()
            if not self._overview_was_recorded or not text:
                text = (
                    "The saved analysis retains "
                    f"{quality_count} actionable quality "
                    f"{'finding' if quality_count == 1 else 'findings'} and "
                    f"{uncertain_count} uncertain atomization "
                    f"{'item' if uncertain_count == 1 else 'items'} for "
                    "review rather than resolving them by inference."
                )
            refs = _unique_refs(self._source_refs(section) + actual_refs)
            return ResultSection(state="PRESENT", text=text, refs=refs)

        if not self._overview_was_recorded:
            return ResultSection(
                state="NOT_RECORDED",
                text=(
                    "This legacy analysis did not record a complete "
                    "unresolved-finding scan."
                ),
            )

        text = section.text.strip()
        refs = self._source_refs(section)
        if text and refs:
            return ResultSection(state="PRESENT", text=text, refs=refs)
        if not text or not self._analysis.items:
            return ResultSection(
                state="NONE_REPORTED",
                text=(
                    text
                    or "The atomize analysis reported no unresolved finding "
                    "in this bounded Context frame."
                ),
            )
        return ResultSection(
            state="NOT_RECORDED",
            text=(
                "The saved unresolved summary has no source links and cannot "
                "be projected as a supported finding."
            ),
        )

    def _build_view(self) -> ResultWorkbenchView:
        count = lambda classification: sum(  # noqa: E731
            item.classification == classification
            for item in self._analysis.items
        )
        split_count = count("COMPOSITE")
        child_count = sum(
            len(item.children)
            for item in self._analysis.items
            if item.classification == "COMPOSITE"
        )
        review_issue_count = (
            split_count
            + count("UNCERTAIN")
            + len(self._analysis.quality_issues)
        )
        return ResultWorkbenchView(
            operation="atomize",
            artifact_uid=self._analysis.uid,
            artifact_digest=self._artifact_digest,
            title=self._analysis.context_name,
            status="ANALYSIS COMPLETE",
            metrics=(
                ResultMetric(
                    key="source_memories",
                    label="sources",
                    value=self._analysis.memory_count,
                ),
                ResultMetric(
                    key="projected_memories",
                    label="projected",
                    value=self._analysis.projected_memory_count,
                ),
                ResultMetric(
                    key="proposed_splits",
                    label="splits",
                    value=split_count,
                ),
                ResultMetric(
                    key="split_children",
                    label="children",
                    value=child_count,
                ),
                ResultMetric(
                    key="review_issues",
                    label="review issues",
                    value=review_issue_count,
                ),
            ),
            understood=self._understood_section(),
            happened=self._happened_section(),
            unresolved=self._unresolved_section(),
            cases=self._cases,
        )

    def _representative_case(
        self,
        item: AtomizeAnalysisItem,
    ) -> ResultCase:
        case_uid = (
            f"representative:{item.classification.lower()}:"
            f"{item.memory_uid}"
        )
        return ResultCase(
            uid=case_uid,
            role="REPRESENTATIVE",
            title=f"{item.classification} · {item.action}",
            summary=f"{item.action}: {_preview(item.content)}",
            why_selected=(
                "This is the earliest validated source-order example of the "
                f"{item.action} outcome. It represents outcome coverage, not "
                "a statistical claim of typicality."
            ),
        )

    def _quality_case(
        self,
        issue: AtomizeQualityIssue,
    ) -> ResultCase:
        case_uid = f"boundary:quality:{issue.uid}"
        if issue.kind == "AMBIGUITY":
            title = (
                f"AMBIGUITY · {issue.interpretation} / "
                f"{issue.clarification}"
            )
        else:
            title = f"CONFLICT · {issue.conflict}"
        return ResultCase(
            uid=case_uid,
            role="BOUNDARY",
            title=title,
            summary=_preview(issue.reason),
            why_selected=(
                "This is the first source-order example of this saved quality "
                "issue kind, with actionable findings preferred. Atomize "
                "validated the issue; the adapter did not synthesize it."
            ),
        )

    def _uncertain_case(
        self,
        item: AtomizeAnalysisItem,
    ) -> ResultCase:
        case_uid = f"boundary:uncertain:{item.memory_uid}"
        return ResultCase(
            uid=case_uid,
            role="BOUNDARY",
            title="UNCERTAIN · RECONCILE",
            summary=_preview(item.reason),
            why_selected=(
                "This is the first source-order UNCERTAIN item not already "
                "covered by a selected quality case. Atomize retained it; the "
                "adapter did not infer an additional issue."
            ),
        )

    def _build_cases(self) -> tuple[ResultCase, ...]:
        cases: list[ResultCase] = []

        selected_classifications: set[str] = set()
        for item in sorted(
            self._analysis.items,
            key=lambda candidate: candidate.position,
        ):
            if (
                item.classification not in _REPRESENTATIVE_CLASSIFICATIONS
                or item.classification in selected_classifications
            ):
                continue
            selected_classifications.add(item.classification)
            cases.append(self._representative_case(item))

        position_by_uid = {
            item.memory_uid: item.position for item in self._analysis.items
        }
        # Cases are inspection samples, not the complete actionable issue
        # ledger rendered by the Atomize workbench.  Keep at most one saved
        # example per boundary kind so a large analysis does not recreate the
        # full issue list under a new heading.  Prefer actionable findings,
        # then preserve canonical source order for deterministic selection.
        selected_issue_kinds: set[str] = set()
        selected_source_uids: set[str] = set()
        quality_candidates = sorted(
            self._analysis.quality_issues,
            key=lambda issue: (
                0 if _is_actionable_quality_issue(issue) else 1,
                min(position_by_uid[uid] for uid in issue.source_uids),
                0 if issue.kind == "AMBIGUITY" else 1,
                issue.uid,
            ),
        )
        for issue in quality_candidates:
            if issue.kind in selected_issue_kinds:
                continue
            selected_issue_kinds.add(issue.kind)
            selected_source_uids.update(issue.source_uids)
            cases.append(self._quality_case(issue))

        uncertain = next(
            (
                item
                for item in sorted(
                    self._analysis.items,
                    key=lambda candidate: candidate.position,
                )
                if item.classification == "UNCERTAIN"
                and item.memory_uid not in selected_source_uids
            ),
            None,
        )
        if uncertain is not None:
            cases.append(self._uncertain_case(uncertain))

        return tuple(cases)
