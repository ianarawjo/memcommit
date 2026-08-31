"""Frozen quality-finder reports and their presentation projections.

Ordinary Find and Audit routes are read-only reports. Response state exists
only for explicit repair-handoff adapters; Audit never persists or projects it,
and a one-shot finder must not look answerable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.application.capabilities.memory_issue_analysis.report import (
    QualityFindReportView,
    QualityFindingReading,
    QualityFindingReportItem,
    QualityFindingSource,
)
from memcommit.application.capabilities.memory_issue_analysis.source import (
    QualityFindSourceError,
    QualityFindSourceFrame,
    _direct_memories,
)
from memcommit.application.capabilities.resolution.workbench import (
    ResolutionContextLocation,
    ResolutionIssueEvidence,
    ResolutionIssuePresentation,
    ResolutionIssueSource,
    ResolutionItem,
    ResolutionMetric,
    ResolutionOption,
    ResolutionOverviewSection,
    ResolutionWorkbenchView,
    resolution_overview_text,
)
from memcommit.application.operations.operation_lifecycle.review.model import (
    REVIEW_RESPONSE_CHAR_LIMIT,
)


QualityFindKind = Literal["duplicates", "ambiguities", "conflicts"]
QualityFindReport = DuplicateReport | AmbiguityReport | ConflictReport
QualityFindWorkbenchError = QualityFindSourceError


@dataclass
class QualityFindResponse:
    """One selected operation-owned option plus an untyped reviewer note."""

    selected_option_uid: str | None = None
    text: str = ""

    @property
    def answered(self) -> bool:
        return self.selected_option_uid is not None or bool(self.text.strip())


@dataclass
class QualityFindWorkbenchSession:
    """One immutable finder result plus legacy response compatibility state."""

    uid: str
    kind: QualityFindKind
    source: QualityFindSourceFrame
    report: QualityFindReport
    responses: dict[str, QualityFindResponse] = field(default_factory=dict)

    @property
    def context_uid(self) -> str:
        return self.source.analysis_context().uid

    @property
    def context_name(self) -> str:
        return self.source.route

    @property
    def context_digest(self) -> str:
        return self.source.digest

    def response_for(self, item_uid: str) -> QualityFindResponse:
        response = self.responses.get(item_uid)
        if response is None:
            response = QualityFindResponse()
            self.responses[item_uid] = response
        return response

    @property
    def answered_count(self) -> int:
        return sum(response.answered for response in self.responses.values())


def _memory_key(memory: Memory) -> tuple[str, str]:
    return memory.uid, memory.content


def _report_memories(report: QualityFindReport) -> tuple[Memory, ...]:
    values: list[Memory] = []
    for finding in report.findings:
        if isinstance(finding, AmbiguityFinding):
            values.append(finding.memory)
        elif isinstance(finding, (ConflictFinding, DuplicateFinding)):
            values.extend((finding.left, finding.right))
        else:  # pragma: no cover - report construction validates this union.
            raise QualityFindWorkbenchError("Unsupported quality finding type.")
    return tuple(values)


def create_quality_find_workbench(
    kind: QualityFindKind,
    source: Context | QualityFindSourceFrame,
    report: QualityFindReport,
) -> QualityFindWorkbenchSession:
    """Bind one validated one-shot report to its exact aggregate source frame."""

    expected_type = {
        "duplicates": DuplicateReport,
        "ambiguities": AmbiguityReport,
        "conflicts": ConflictReport,
    }.get(kind)
    if expected_type is None or not isinstance(report, expected_type):
        raise QualityFindWorkbenchError(
            "Quality finder kind does not match its report type."
        )
    frame = (
        QualityFindSourceFrame.create((source,))
        if isinstance(source, Context)
        else source
    )
    if not isinstance(frame, QualityFindSourceFrame):
        raise QualityFindWorkbenchError("Invalid quality finder source frame.")
    memories = _direct_memories(frame.analysis_context())
    if report.memory_count != len(memories):
        raise QualityFindWorkbenchError(
            "Quality finder report does not match its direct Context frame."
        )
    if isinstance(report, ConflictReport) and report.pair_count != (
        len(memories) * (len(memories) - 1) // 2
    ):
        raise QualityFindWorkbenchError(
            "Conflict report does not cover its direct Context pair frame."
        )
    memory_keys = {_memory_key(memory) for memory in memories}
    if any(
        _memory_key(memory) not in memory_keys for memory in _report_memories(report)
    ):
        raise QualityFindWorkbenchError(
            "Quality finder report references a Memory outside its Context frame."
        )
    return QualityFindWorkbenchSession(
        uid=str(uuid.uuid4()),
        kind=kind,
        source=frame,
        report=report,
    )


def _preview(content: str, *, limit: int = 120) -> str:
    value = " ".join(content.split()) or "(empty Memory)"
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _reading_roles(finding: AmbiguityFinding) -> tuple[str, ...]:
    count = len(finding.ordinary_readings)
    if finding.interpretation == "SINGLE":
        return ("SINGLE",) * count
    if finding.interpretation == "DOMINANT":
        return ("DOMINANT", *("ALTERNATIVE" for _ in range(count - 1)))
    return ("COMPETING",) * count


def _ambiguity_item_uid(finding: AmbiguityFinding) -> str:
    return f"ambiguity:{finding.memory.uid}"


def _pair_item_uid(kind: str, left: Memory, right: Memory) -> str:
    return f"{kind}:{left.uid}:{right.uid}"


def _source(
    memory: Memory,
    *,
    label: str,
    context_name_by_uid: dict[str, str],
    ordinal_by_uid: dict[str, int],
) -> ResolutionIssueSource:
    return ResolutionIssueSource(
        label=label,
        context_name=context_name_by_uid[memory.uid],
        memory_uid=memory.uid,
        content=memory.content,
        ordinal=ordinal_by_uid[memory.uid],
    )


def _response_state(
    session: QualityFindWorkbenchSession,
    item_uid: str,
) -> tuple[str, str, str | None]:
    response = session.responses.get(item_uid)
    if response is None:
        return "OPEN", "", None
    return (
        "ANSWERED" if response.answered else "OPEN",
        response.text,
        response.selected_option_uid,
    )


def _ambiguity_item(
    session: QualityFindWorkbenchSession,
    finding: AmbiguityFinding,
    *,
    ordinal_by_uid: dict[str, int],
    context_name_by_uid: dict[str, str],
) -> ResolutionItem:
    item_uid = _ambiguity_item_uid(finding)
    state, text, selected = _response_state(session, item_uid)
    options = tuple(
        ResolutionOption(
            uid=f"{item_uid}:reading:{index}",
            label=role,
            text=reading,
        )
        for index, (role, reading) in enumerate(
            zip(_reading_roles(finding), finding.ordinary_readings),
            start=1,
        )
    )
    source = _source(
        finding.memory,
        label="SOURCE 1",
        context_name_by_uid=context_name_by_uid,
        ordinal_by_uid=ordinal_by_uid,
    )
    return ResolutionItem(
        uid=item_uid,
        kind="AMBIGUITY",
        status=state,
        priority=finding.clarification,
        title=_preview(finding.memory.content),
        summary=finding.reason,
        obligation="OPTIONAL",
        response_state=state,
        response_text=text,
        question=finding.question,
        options=options,
        selected_option_uid=selected,
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    group_heading="",
                    sources_heading="SOURCE MEMORY",
                    classification=(
                        f"{finding.interpretation} · {finding.clarification}"
                    ),
                    reason_heading="WHY THIS IS UNCLEAR",
                    reason=finding.reason,
                    sources=(source,),
                ),
            ),
            prompt_heading="CLARIFICATION QUESTION",
            options_heading="PROPOSED READINGS",
            other_option_label="Different reading",
            response_heading="RESPONSE",
        ),
    )


def _conflict_item(
    session: QualityFindWorkbenchSession,
    finding: ConflictFinding,
    *,
    ordinal_by_uid: dict[str, int],
    context_name_by_uid: dict[str, str],
) -> ResolutionItem:
    item_uid = _pair_item_uid("conflict", finding.left, finding.right)
    state, text, selected = _response_state(session, item_uid)
    sources = (
        _source(
            finding.left,
            label="SOURCE 1",
            context_name_by_uid=context_name_by_uid,
            ordinal_by_uid=ordinal_by_uid,
        ),
        _source(
            finding.right,
            label="SOURCE 2",
            context_name_by_uid=context_name_by_uid,
            ordinal_by_uid=ordinal_by_uid,
        ),
    )
    question = finding.question or (
        "Record any correction or decision needed for this pair."
    )
    return ResolutionItem(
        uid=item_uid,
        kind="CONFLICT",
        status=state,
        priority=finding.conflict,
        title=f"{_preview(finding.left.content)} ↔ {_preview(finding.right.content)}",
        summary=finding.reason,
        obligation="OPTIONAL",
        response_state=state,
        response_text=text,
        question=question,
        options=(),
        selected_option_uid=selected,
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    group_heading="",
                    sources_heading="SOURCE MEMORIES",
                    classification=finding.conflict,
                    reason_heading="WHY THESE MEMORIES CONFLICT",
                    reason=finding.reason,
                    sources=sources,
                ),
            ),
            prompt_heading="CONFLICT QUESTION",
            options_heading="PROPOSED RESOLUTIONS",
            other_option_label="Different resolution",
            response_heading="RESPONSE",
        ),
    )


def _duplicate_item(
    session: QualityFindWorkbenchSession,
    finding: DuplicateFinding,
    *,
    ordinal_by_uid: dict[str, int],
    context_name_by_uid: dict[str, str],
) -> ResolutionItem:
    item_uid = _pair_item_uid("duplicate", finding.left, finding.right)
    exact = finding.relation == "EXACT"
    if exact:
        state, text, selected = "NOT_APPLICABLE", "", None
    else:
        state, text, selected = _response_state(session, item_uid)
    sources = (
        _source(
            finding.left,
            label="SOURCE 1",
            context_name_by_uid=context_name_by_uid,
            ordinal_by_uid=ordinal_by_uid,
        ),
        _source(
            finding.right,
            label="SOURCE 2",
            context_name_by_uid=context_name_by_uid,
            ordinal_by_uid=ordinal_by_uid,
        ),
    )
    options = (
        ()
        if exact
        else tuple(
            ResolutionOption(f"{item_uid}:{uid}", label, description)
            for uid, label, description in (
                (
                    "confirm",
                    "CONFIRM LINK",
                    "Retain this pair as positive semantic-DUN evidence.",
                ),
                (
                    "reject",
                    "REJECT LINK",
                    "Reject this semantic evidence link; keep the two Memories "
                    "distinct.",
                ),
                (
                    "defer",
                    "DEFER",
                    "Leave this semantic-DUN evidence link undecided.",
                ),
            )
        )
    )
    return ResolutionItem(
        uid=item_uid,
        kind="DUP / EXACT" if exact else "SEMANTIC DUN",
        status=state,
        priority=finding.relation,
        title=f"{_preview(finding.left.content)} ↔ {_preview(finding.right.content)}",
        summary=finding.reason,
        obligation="NONE" if exact else "OPTIONAL",
        response_state=state,
        response_text=text,
        question=(
            ""
            if exact
            else "Should this emitted semantic-DUN evidence link be retained?"
        ),
        options=options,
        selected_option_uid=selected,
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    group_heading="",
                    sources_heading="SOURCE MEMORIES",
                    classification=finding.relation,
                    reason_heading=(
                        "WHY THESE MEMORIES ARE EXACT DUPLICATES"
                        if exact
                        else "WHY THESE MEMORIES ARE SEMANTICALLY REDUNDANT"
                    ),
                    reason=finding.reason,
                    sources=sources,
                ),
            ),
            prompt_heading="REVIEW DECISION",
            options_heading="EVIDENCE LINK DISPOSITION",
            other_option_label="Different assessment",
            response_heading="RESPONSE",
        ),
    )


def quality_find_report_view(
    session: QualityFindWorkbenchSession,
    source: Context | QualityFindSourceFrame,
    *,
    operation_label: str | None = None,
    handoff_available: bool = False,
) -> QualityFindReportView:
    """Project one immutable finder result without review or response state."""

    current_contexts = (
        source.contexts if isinstance(source, QualityFindSourceFrame) else (source,)
    )
    if (
        isinstance(source, QualityFindSourceFrame)
        and source.digest != session.source.digest
    ) or not session.source.matches(current_contexts):
        raise QualityFindWorkbenchError(
            "Quality finder report no longer matches its Context frame."
        )

    ordinal_by_uid = session.source.memory_ordinals
    context_name_by_uid = session.source.memory_context_names

    def report_source(memory: Memory, label: str) -> QualityFindingSource:
        return QualityFindingSource(
            label=label,
            context_name=context_name_by_uid[memory.uid],
            memory_uid=memory.uid,
            content=memory.content,
            ordinal=ordinal_by_uid[memory.uid],
        )

    items: list[QualityFindingReportItem] = []
    if session.kind == "ambiguities":
        assert isinstance(session.report, AmbiguityReport)
        for finding in session.report.findings:
            classification = (
                f"{finding.interpretation} · CLARIFICATION {finding.clarification}"
            )
            items.append(
                QualityFindingReportItem(
                    uid=_ambiguity_item_uid(finding),
                    category="ambiguities",
                    kind="AMBIGUITY",
                    classification=classification,
                    title=_preview(finding.memory.content),
                    reason_heading="WHY THIS IS UNCLEAR",
                    reason=finding.reason,
                    sources=(report_source(finding.memory, "SOURCE MEMORY"),),
                    follow_up=finding.question,
                    readings=tuple(
                        QualityFindingReading(role, reading)
                        for role, reading in zip(
                            _reading_roles(finding),
                            finding.ordinary_readings,
                        )
                    ),
                )
            )
        empty_message = "No ambiguity findings in this analysis."
    elif session.kind == "conflicts":
        assert isinstance(session.report, ConflictReport)
        for finding in session.report.findings:
            items.append(
                QualityFindingReportItem(
                    uid=_pair_item_uid("conflict", finding.left, finding.right),
                    category="conflicts",
                    kind="CONFLICT",
                    classification=finding.conflict,
                    title=(
                        f"{_preview(finding.left.content)} ↔ "
                        f"{_preview(finding.right.content)}"
                    ),
                    reason_heading="WHY THESE MEMORIES CONFLICT",
                    reason=finding.reason,
                    sources=(
                        report_source(finding.left, "SOURCE 1"),
                        report_source(finding.right, "SOURCE 2"),
                    ),
                    follow_up=finding.question,
                )
            )
        empty_message = "No conflict findings in this analysis."
    else:
        assert session.kind == "duplicates"
        assert isinstance(session.report, DuplicateReport)
        for finding in session.report.findings:
            exact = finding.relation == "EXACT"
            items.append(
                QualityFindingReportItem(
                    uid=_pair_item_uid("duplicate", finding.left, finding.right),
                    category="duplicates",
                    kind="DUP / EXACT" if exact else "SEMANTIC DUN",
                    classification=finding.relation,
                    title=(
                        f"{_preview(finding.left.content)} ↔ "
                        f"{_preview(finding.right.content)}"
                    ),
                    reason_heading=(
                        "WHY THESE MEMORIES ARE EXACT DUPLICATES"
                        if exact
                        else "WHY THESE MEMORIES ARE SEMANTICALLY REDUNDANT"
                    ),
                    reason=finding.reason,
                    sources=(
                        report_source(finding.left, "SOURCE 1"),
                        report_source(finding.right, "SOURCE 2"),
                    ),
                )
            )
        empty_message = "No redundancy evidence in this analysis."

    default_operation_label = (
        "DEDUN" if session.kind == "duplicates" else f"FIND {session.kind.upper()}"
    )
    label = default_operation_label if operation_label is None else operation_label
    if (
        not isinstance(label, str)
        or not label.strip()
        or label != label.strip()
        or any(character in label for character in "\r\n")
    ):
        raise QualityFindWorkbenchError(
            "Quality finder operation label must be exact nonblank text."
        )

    handoff_label: str | None = None
    if handoff_available and items:
        if session.kind == "conflicts":
            handoff_label = "open Resolve"
        elif session.kind == "duplicates":
            handoff_label = "open Dedun"

    return QualityFindReportView(
        kind=session.kind,
        operation=label,
        artifact_uid=session.uid,
        revision=session.context_digest,
        route=session.source.route,
        source_count=len(session.source.contexts),
        memory_count=session.report.memory_count,
        pair_count=(
            session.report.pair_count
            if isinstance(session.report, ConflictReport)
            else None
        ),
        group_count=(
            session.report.group_count
            if isinstance(session.report, DuplicateReport)
            else None
        ),
        redundant_item_count=(
            session.report.redundancy_count
            if isinstance(session.report, DuplicateReport)
            else None
        ),
        items=tuple(items),
        empty_message=empty_message,
        handoff_label=handoff_label,
    )


def quality_find_resolution_view(
    session: QualityFindWorkbenchSession,
    source: Context | QualityFindSourceFrame,
    *,
    operation_label: str | None = None,
) -> ResolutionWorkbenchView:
    """Project one exact aggregate quality report into the Resolution contract."""

    current_contexts = (
        source.contexts if isinstance(source, QualityFindSourceFrame) else (source,)
    )
    if (
        isinstance(source, QualityFindSourceFrame)
        and source.digest != session.source.digest
    ) or not session.source.matches(current_contexts):
        raise QualityFindWorkbenchError(
            "Quality finder workbench no longer matches its Context frame."
        )
    ordinal_by_uid = session.source.memory_ordinals
    context_name_by_uid = session.source.memory_context_names
    if session.kind == "ambiguities":
        assert isinstance(session.report, AmbiguityReport)
        items = tuple(
            _ambiguity_item(
                session,
                finding,
                ordinal_by_uid=ordinal_by_uid,
                context_name_by_uid=context_name_by_uid,
            )
            for finding in session.report.findings
        )
        finding_label = "ambiguity"
    elif session.kind == "conflicts":
        assert isinstance(session.report, ConflictReport)
        items = tuple(
            _conflict_item(
                session,
                finding,
                ordinal_by_uid=ordinal_by_uid,
                context_name_by_uid=context_name_by_uid,
            )
            for finding in session.report.findings
        )
        finding_label = "conflict"
    else:
        assert session.kind == "duplicates"
        assert isinstance(session.report, DuplicateReport)
        items = tuple(
            _duplicate_item(
                session,
                finding,
                ordinal_by_uid=ordinal_by_uid,
                context_name_by_uid=context_name_by_uid,
            )
            for finding in session.report.findings
        )
        finding_label = "redundancy"

    report = session.report
    reviewable_count = sum(item.effective_obligation != "NONE" for item in items)
    metrics = [
        ResolutionMetric("CONTEXTS", str(len(session.source.contexts))),
        ResolutionMetric("SOURCE MEMORIES", str(report.memory_count)),
    ]
    if isinstance(report, ConflictReport):
        involved_memory_count = len(
            {
                memory.uid
                for finding in report.findings
                for memory in (finding.left, finding.right)
            }
        )
        metrics.extend(
            (
                ResolutionMetric("MEMORIES INVOLVED", str(involved_memory_count)),
                ResolutionMetric("PAIRS CHECKED", str(report.pair_count)),
                ResolutionMetric("PAIRS FLAGGED", str(len(items))),
            )
        )
    elif isinstance(report, DuplicateReport):
        metrics.extend(
            (
                ResolutionMetric("GROUPS", str(report.group_count)),
                ResolutionMetric(
                    "PROPOSED ABSORPTIONS",
                    str(report.redundancy_count),
                ),
            )
        )
    else:
        metrics.append(ResolutionMetric("MEMORIES FLAGGED", str(len(items))))
    metrics.append(ResolutionMetric("ANSWERED", str(session.answered_count)))
    reach = (
        "INCLUDE DESCENDANTS"
        if session.source.include_descendants
        else "THIS CONTEXT ONLY"
    )
    target_mode = (
        "PROFILE"
        if session.source.profile_selected
        else f"{session.source.selection_mode} TARGET SELECTION"
    )
    if isinstance(report, DuplicateReport):
        result_heading = "REDUNDANCIES"
        result_summary = (
            f"Reported {report.group_count} cleanup "
            f"{'group' if report.group_count == 1 else 'groups'} and "
            f"{report.redundancy_count} proposed "
            f"{'absorption' if report.redundancy_count == 1 else 'absorptions'}."
        )
    elif isinstance(report, ConflictReport):
        result_heading = "CONFLICTS"
        result_summary = (
            f"Flagged {len(items)} of {report.pair_count} checked "
            f"{'pair' if report.pair_count == 1 else 'pairs'}."
        )
    else:
        result_heading = "AMBIGUITIES"
        result_summary = (
            f"Flagged {len(items)} of {report.memory_count} checked "
            f"{'Memory' if report.memory_count == 1 else 'Memories'}."
        )
    sections = (
        ResolutionOverviewSection(
            "scope",
            "SCOPE",
            (
                f"Inspected {report.memory_count} direct Memories across "
                f"{len(session.source.contexts)} selected readable "
                f"{'Context' if len(session.source.contexts) == 1 else 'Contexts'} "
                f"as one analysis frame. {target_mode} · {reach}. "
                "Embedded Context edges were not followed."
            ),
        ),
        ResolutionOverviewSection(
            "findings",
            result_heading,
            result_summary,
        ),
        ResolutionOverviewSection(
            "boundary",
            "BOUNDARY",
            ("Responses are review notes for this report."),
        ),
    )
    default_operation_label = (
        "DEDUN" if session.kind == "duplicates" else f"FIND {session.kind.upper()}"
    )
    if operation_label is None:
        operation_label = default_operation_label
    elif (
        not isinstance(operation_label, str)
        or not operation_label.strip()
        or operation_label != operation_label.strip()
        or any(character in operation_label for character in "\r\n")
    ):
        raise QualityFindWorkbenchError(
            "Quality finder operation label must be exact nonblank text."
        )
    return ResolutionWorkbenchView(
        operation=operation_label,
        artifact_uid=session.uid,
        revision=session.context_digest,
        title=f"MEM {operation_label}",
        route=session.source.route,
        status=(
            f"PROCESS LOCAL · {session.answered_count}/{reviewable_count} ANSWERED"
        ),
        metrics=tuple(metrics),
        context_locations=tuple(
            ResolutionContextLocation(
                "SOURCE"
                if len(session.source.context_names) == 1
                else f"SOURCE {index}",
                name,
            )
            for index, name in enumerate(session.source.context_names, start=1)
        ),
        overview=resolution_overview_text(sections),
        overview_sections=sections,
        list_label=("REDUNDANCIES" if session.kind == "duplicates" else result_heading),
        items=items,
        empty_message=(
            "No redundancy evidence in this analysis."
            if session.kind == "duplicates"
            else f"No {finding_label} results in this analysis."
        ),
        results_label="EXACT RESULTS",
        results=(),
        capabilities=(frozenset({"SUBMIT_ITEM"}) if items else frozenset()),
        show_results=False,
    )


def validate_quality_find_response(text: str) -> None:
    """Apply the existing semantic-review response size boundary."""

    if len(text) > REVIEW_RESPONSE_CHAR_LIMIT:
        raise QualityFindWorkbenchError(
            "Response is too long to keep in this workbench "
            f"({len(text):,}/{REVIEW_RESPONSE_CHAR_LIMIT:,} characters)."
        )
