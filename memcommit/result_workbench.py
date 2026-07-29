"""Operation-neutral, read-only projection for semantic result inspection.

The owning operation remains authoritative for semantic judgments, provider
calls, persistence, reanalysis, and mutation.  This module only defines the
small immutable view that common result-workbench presentation may consume.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol


RESULT_TEXT_LIMIT = 20_000
RESULT_LABEL_LIMIT = 500
RESULT_KEY_LIMIT = 500

ResultSectionState = Literal[
    "PRESENT",
    "NONE_REPORTED",
    "NOT_RECORDED",
]
ResultCaseRole = Literal["REPRESENTATIVE", "BOUNDARY"]

_SECTION_STATES = {"PRESENT", "NONE_REPORTED", "NOT_RECORDED"}
_CASE_ROLES = {"REPRESENTATIVE", "BOUNDARY"}
_METRIC_KEY = re.compile(r"[a-z][a-z0-9_]*\Z")


class ResultWorkbenchError(ValueError):
    """Invalid or internally inconsistent result-workbench projection."""


def _text(
    value: object,
    label: str,
    *,
    empty: bool = False,
    limit: int = RESULT_TEXT_LIMIT,
    one_line: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not empty and not value.strip())
        or len(value) > limit
        or (one_line and any(character in value for character in "\r\n"))
    ):
        raise ResultWorkbenchError(f"Invalid {label}.")
    return value


def _digest(value: object, label: str) -> str:
    text = _text(value, label, limit=64, one_line=True)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ResultWorkbenchError(f"Invalid {label}.")
    return text


def _tuple(value: object, label: str) -> tuple:
    if not isinstance(value, tuple):
        raise ResultWorkbenchError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class ResultMetric:
    """One locally computed count shown only in the compact header."""

    key: str
    label: str
    value: int

    def __post_init__(self) -> None:
        _text(self.key, "result metric key", limit=80, one_line=True)
        if _METRIC_KEY.fullmatch(self.key) is None:
            raise ResultWorkbenchError("Invalid result metric key.")
        _text(
            self.label,
            "result metric label",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, int)
            or self.value < 0
        ):
            raise ResultWorkbenchError("Invalid result metric value.")


@dataclass(frozen=True, order=True)
class ResultRef:
    """Opaque operation-owned address retained for traceable drill-down."""

    kind: str
    key: str

    def __post_init__(self) -> None:
        _text(
            self.kind,
            "result reference kind",
            limit=RESULT_KEY_LIMIT,
            one_line=True,
        )
        _text(
            self.key,
            "result reference key",
            limit=RESULT_KEY_LIMIT,
            one_line=True,
        )


def _refs(value: object, label: str) -> tuple[ResultRef, ...]:
    refs = _tuple(value, label)
    if any(not isinstance(item, ResultRef) for item in refs):
        raise ResultWorkbenchError(f"Invalid {label}.")
    if len(set(refs)) != len(refs):
        raise ResultWorkbenchError(f"Duplicate {label}.")
    return refs


@dataclass(frozen=True)
class ResultSection:
    """One source-linked overview claim with an explicit evidence state."""

    state: ResultSectionState
    text: str
    refs: tuple[ResultRef, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in _SECTION_STATES:
            raise ResultWorkbenchError("Invalid result section state.")
        _text(
            self.text,
            "result section text",
            empty=self.state != "PRESENT",
        )
        refs = _refs(self.refs, "result section references")
        if self.state == "PRESENT" and not refs:
            raise ResultWorkbenchError(
                "A present result section requires traceable references."
            )
        if self.state != "PRESENT" and refs:
            raise ResultWorkbenchError(
                "An absent result section cannot cite result references."
            )


@dataclass(frozen=True)
class ResultCase:
    """One compact representative or boundary inspection row."""

    uid: str
    role: ResultCaseRole
    title: str
    summary: str
    why_selected: str

    def __post_init__(self) -> None:
        _text(
            self.uid,
            "result case uid",
            limit=RESULT_KEY_LIMIT,
            one_line=True,
        )
        if self.role not in _CASE_ROLES:
            raise ResultWorkbenchError("Invalid result case role.")
        _text(
            self.title,
            "result case title",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        _text(self.summary, "result case summary")
        _text(self.why_selected, "result case selection reason")


@dataclass(frozen=True)
class ResultDetailBlock:
    """One operation-authored detail block rendered without reinterpretation."""

    heading: str
    text: str
    refs: tuple[ResultRef, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.heading,
            "result detail heading",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        _text(self.text, "result detail text")
        _refs(self.refs, "result detail references")


@dataclass(frozen=True)
class ResultCaseDetail:
    """Expanded evidence, judgment, and outcome for one compact case."""

    case_uid: str
    artifact_digest: str
    blocks: tuple[ResultDetailBlock, ...]
    evidence_refs: tuple[ResultRef, ...]
    judgment_refs: tuple[ResultRef, ...]
    outcome_refs: tuple[ResultRef, ...] = ()
    unresolved_refs: tuple[ResultRef, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.case_uid,
            "result case detail uid",
            limit=RESULT_KEY_LIMIT,
            one_line=True,
        )
        _digest(self.artifact_digest, "result case artifact digest")
        blocks = _tuple(self.blocks, "result detail blocks")
        if (
            not blocks
            or any(not isinstance(item, ResultDetailBlock) for item in blocks)
        ):
            raise ResultWorkbenchError("Invalid result detail blocks.")
        _refs(self.evidence_refs, "result evidence references")
        _refs(self.judgment_refs, "result judgment references")
        _refs(self.outcome_refs, "result outcome references")
        _refs(self.unresolved_refs, "result unresolved references")
        if not self.evidence_refs:
            raise ResultWorkbenchError(
                "A result case detail requires source evidence."
            )


@dataclass(frozen=True)
class ResultWorkbenchView:
    """Complete immutable overview shown by the shared result workbench."""

    operation: str
    artifact_uid: str
    artifact_digest: str
    title: str
    status: str
    metrics: tuple[ResultMetric, ...]
    understood: ResultSection
    happened: ResultSection
    unresolved: ResultSection
    cases: tuple[ResultCase, ...] = ()

    def __post_init__(self) -> None:
        _text(
            self.operation,
            "result operation",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        _text(
            self.artifact_uid,
            "result artifact uid",
            limit=RESULT_KEY_LIMIT,
            one_line=True,
        )
        _digest(self.artifact_digest, "result artifact digest")
        _text(
            self.title,
            "result title",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        _text(
            self.status,
            "result status",
            limit=RESULT_LABEL_LIMIT,
            one_line=True,
        )
        metrics = _tuple(self.metrics, "result metrics")
        if any(not isinstance(item, ResultMetric) for item in metrics):
            raise ResultWorkbenchError("Invalid result metrics.")
        if len({metric.key for metric in metrics}) != len(metrics):
            raise ResultWorkbenchError("Duplicate result metric key.")
        for section in (self.understood, self.happened, self.unresolved):
            if not isinstance(section, ResultSection):
                raise ResultWorkbenchError("Invalid result overview section.")
        cases = _tuple(self.cases, "result cases")
        if any(not isinstance(item, ResultCase) for item in cases):
            raise ResultWorkbenchError("Invalid result cases.")
        if len({case.uid for case in cases}) != len(cases):
            raise ResultWorkbenchError("Duplicate result case uid.")

    def case(self, case_uid: str) -> ResultCase:
        """Resolve one exact compact case without prefix ambiguity."""
        matches = [case for case in self.cases if case.uid == case_uid]
        if len(matches) != 1:
            raise ResultWorkbenchError(
                f"No result inspection case matches '{case_uid}'."
            )
        return matches[0]

    def validate_detail(self, detail: ResultCaseDetail) -> ResultCaseDetail:
        """Bind operation-authored detail to this exact immutable view."""
        if not isinstance(detail, ResultCaseDetail):
            raise ResultWorkbenchError("Invalid result case detail.")
        case = self.case(detail.case_uid)
        if detail.artifact_digest != self.artifact_digest:
            raise ResultWorkbenchError(
                "Result case detail belongs to a stale operation artifact."
            )
        if not detail.judgment_refs:
            raise ResultWorkbenchError(
                "A result case detail requires an operation judgment."
            )
        if case.role == "REPRESENTATIVE" and not detail.outcome_refs:
            raise ResultWorkbenchError(
                "A representative case requires a supported outcome."
            )
        if (
            case.role == "BOUNDARY"
            and not detail.outcome_refs
            and not detail.unresolved_refs
        ):
            raise ResultWorkbenchError(
                "A boundary case requires an outcome or unresolved finding."
            )
        return detail


class ResultWorkbenchAdapter(Protocol):
    """Operation-owned projection and detail lookup for common presentation."""

    def view(self) -> ResultWorkbenchView:
        """Return one immutable result projection."""

    def case_detail(self, case_uid: str) -> ResultCaseDetail:
        """Return detail bound to the same operation artifact."""
