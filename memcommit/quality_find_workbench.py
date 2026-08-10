"""Process-local review state and Resolution projection for quality finders.

The semantic finder reports remain immutable one-shot results.  This module
adds only an in-memory response layer so a TTY caller can inspect the complete
report through the common Resolution Session without implying persistence or
Memory mutation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from memcommit.context import Context, Memory
from memcommit.findings import (
    AmbiguityFinding,
    AmbiguityReport,
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
)
from memcommit.resolution_workbench import (
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
from memcommit.review import REVIEW_RESPONSE_CHAR_LIMIT, direct_context_digest


QualityFindKind = Literal["duplicates", "ambiguities", "conflicts"]
QualityFindReport = DuplicateReport | AmbiguityReport | ConflictReport


class QualityFindWorkbenchError(ValueError):
    """Invalid process-local quality-finder review state."""


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
    """One immutable finder result with process-local response drafts."""

    uid: str
    kind: QualityFindKind
    context_uid: str
    context_name: str
    context_digest: str
    report: QualityFindReport
    responses: dict[str, QualityFindResponse] = field(default_factory=dict)

    def response_for(self, item_uid: str) -> QualityFindResponse:
        response = self.responses.get(item_uid)
        if response is None:
            response = QualityFindResponse()
            self.responses[item_uid] = response
        return response

    @property
    def answered_count(self) -> int:
        return sum(response.answered for response in self.responses.values())


def _direct_memories(ctx: Context) -> tuple[Memory, ...]:
    return tuple(item for item in ctx.iter_items() if isinstance(item, Memory))


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
    ctx: Context,
    report: QualityFindReport,
) -> QualityFindWorkbenchSession:
    """Bind one validated one-shot report to its exact direct Context frame."""

    expected_type = {
        "duplicates": DuplicateReport,
        "ambiguities": AmbiguityReport,
        "conflicts": ConflictReport,
    }.get(kind)
    if expected_type is None or not isinstance(report, expected_type):
        raise QualityFindWorkbenchError(
            "Quality finder kind does not match its report type."
        )
    memories = _direct_memories(ctx)
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
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=direct_context_digest(ctx),
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
    context_name: str,
    ordinal_by_uid: dict[str, int],
) -> ResolutionIssueSource:
    return ResolutionIssueSource(
        label=label,
        context_name=context_name,
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
        context_name=session.context_name,
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
) -> ResolutionItem:
    item_uid = _pair_item_uid("conflict", finding.left, finding.right)
    state, text, selected = _response_state(session, item_uid)
    sources = (
        _source(
            finding.left,
            label="SOURCE 1",
            context_name=session.context_name,
            ordinal_by_uid=ordinal_by_uid,
        ),
        _source(
            finding.right,
            label="SOURCE 2",
            context_name=session.context_name,
            ordinal_by_uid=ordinal_by_uid,
        ),
    )
    dimensions = " · ".join(finding.scope_dimensions) or "NO SCOPE DIMENSION"
    question = finding.question or (
        "Record any correction or scope distinction needed for this pair."
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
                    classification=f"{finding.conflict} · {dimensions}",
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
) -> ResolutionItem:
    item_uid = _pair_item_uid("duplicate", finding.left, finding.right)
    state, text, selected = _response_state(session, item_uid)
    sources = (
        _source(
            finding.left,
            label="SOURCE 1",
            context_name=session.context_name,
            ordinal_by_uid=ordinal_by_uid,
        ),
        _source(
            finding.right,
            label="SOURCE 2",
            context_name=session.context_name,
            ordinal_by_uid=ordinal_by_uid,
        ),
    )
    options = tuple(
        ResolutionOption(f"{item_uid}:{uid}", label, description)
        for uid, label, description in (
            (
                "confirm",
                "CONFIRM LINK",
                "Retain this pair as positive duplicate evidence.",
            ),
            (
                "reject",
                "REJECT LINK",
                "Reject this evidence link; keep the two Memories distinct.",
            ),
            (
                "defer",
                "DEFER",
                "Leave this duplicate evidence link undecided.",
            ),
        )
    )
    return ResolutionItem(
        uid=item_uid,
        kind="DUPLICATE",
        status=state,
        priority=finding.relation,
        title=f"{_preview(finding.left.content)} ↔ {_preview(finding.right.content)}",
        summary=finding.reason,
        obligation="OPTIONAL",
        response_state=state,
        response_text=text,
        question="Should this emitted duplicate evidence link be retained?",
        options=options,
        selected_option_uid=selected,
        issue_presentation=ResolutionIssuePresentation(
            evidence=(
                ResolutionIssueEvidence(
                    group_heading="",
                    sources_heading="SOURCE MEMORIES",
                    classification=finding.relation,
                    reason_heading="WHY THESE MEMORIES ARE DUPLICATES",
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


def quality_find_resolution_view(
    session: QualityFindWorkbenchSession,
    ctx: Context,
) -> ResolutionWorkbenchView:
    """Project one exact quality report into the common Resolution contract."""

    if (
        ctx.uid != session.context_uid
        or ctx.name != session.context_name
        or direct_context_digest(ctx) != session.context_digest
    ):
        raise QualityFindWorkbenchError(
            "Quality finder workbench no longer matches its Context frame."
        )
    memories = _direct_memories(ctx)
    ordinal_by_uid = {
        memory.uid: index for index, memory in enumerate(memories, start=1)
    }
    if session.kind == "ambiguities":
        assert isinstance(session.report, AmbiguityReport)
        items = tuple(
            _ambiguity_item(session, finding, ordinal_by_uid=ordinal_by_uid)
            for finding in session.report.findings
        )
        finding_label = "ambiguity"
    elif session.kind == "conflicts":
        assert isinstance(session.report, ConflictReport)
        items = tuple(
            _conflict_item(session, finding, ordinal_by_uid=ordinal_by_uid)
            for finding in session.report.findings
        )
        finding_label = "conflict"
    else:
        assert session.kind == "duplicates"
        assert isinstance(session.report, DuplicateReport)
        items = tuple(
            _duplicate_item(session, finding, ordinal_by_uid=ordinal_by_uid)
            for finding in session.report.findings
        )
        finding_label = "duplicate"

    report = session.report
    metrics = [
        ResolutionMetric("SOURCE MEMORIES", str(report.memory_count)),
        ResolutionMetric("FINDINGS", str(len(items))),
        ResolutionMetric("ANSWERED", str(session.answered_count)),
    ]
    if isinstance(report, ConflictReport):
        metrics.insert(1, ResolutionMetric("PAIRS", str(report.pair_count)))
    sections = (
        ResolutionOverviewSection(
            "scope",
            "SCOPE",
            (
                f"Inspected {report.memory_count} direct Memories in "
                f"{session.context_name}. Descendants and embedded Contexts "
                "were not analyzed."
            ),
        ),
        ResolutionOverviewSection(
            "findings",
            "FINDINGS",
            (
                f"Reported {len(items)} actionable {finding_label} "
                f"{'finding' if len(items) == 1 else 'findings'}."
            ),
        ),
        ResolutionOverviewSection(
            "boundary",
            "BOUNDARY",
            (
                "Responses are process-local review notes. No Context or "
                "Memory changes have been applied."
            ),
        ),
    )
    return ResolutionWorkbenchView(
        operation=f"FIND {session.kind.upper()}",
        artifact_uid=session.uid,
        revision=session.context_digest,
        title=f"MEM FIND {session.kind.upper()}",
        route=session.context_name,
        status=f"PROCESS LOCAL · {session.answered_count}/{len(items)} ANSWERED",
        metrics=tuple(metrics),
        context_locations=(ResolutionContextLocation("SOURCE", session.context_name),),
        overview=resolution_overview_text(sections),
        overview_sections=sections,
        list_label="ACTIONABLE FINDINGS",
        items=items,
        empty_message=f"No actionable {finding_label} findings in this analysis.",
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
