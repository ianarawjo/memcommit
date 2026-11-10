"""Frozen quality-finder reports and their presentation projections.

Ordinary Find and Audit routes are read-only reports. Response state exists
only for explicit repair-handoff adapters; Audit never persists or projects it,
and a one-shot finder must not look answerable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from memcommit.models.context import Context
from memcommit.models.memory import Memory
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


QualityFindKind = Literal["duplicates", "ambiguities", "conflicts"]
QualityFindReport = DuplicateReport | AmbiguityReport | ConflictReport
QualityFindWorkbenchError = QualityFindSourceError


@dataclass
class QualityFindResponse:
    """One selected operation-owned option plus an untyped reviewer note."""

    selected_option_uid: str | None = None
    text: str = ""


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
    if handoff_available and items and session.kind == "duplicates":
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
