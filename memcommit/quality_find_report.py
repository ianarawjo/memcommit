"""Read-only presentation contract for process-local quality findings.

Finders report model-assisted evidence.  They do not create review obligations,
collect answers, or own a later mutation.  Operation handoffs remain explicit
navigation receipts and never change this report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QualityFindReportKind = Literal["ambiguities", "conflicts", "duplicates"]


class QualityFindReportError(ValueError):
    """Invalid read-only quality finding projection."""


def _text(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise QualityFindReportError(f"Invalid {label}.")
    if any(character in value for character in "\r"):
        raise QualityFindReportError(f"Invalid {label}.")
    return value


@dataclass(frozen=True)
class QualityFindingSource:
    """One exact source Memory displayed by a finding."""

    label: str
    context_name: str
    memory_uid: str
    content: str
    ordinal: int

    def __post_init__(self) -> None:
        _text(self.label, "finding Source label")
        _text(self.context_name, "finding Source Context")
        _text(self.memory_uid, "finding Source Memory uid")
        _text(self.content, "finding Source content", empty=True)
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
            raise QualityFindReportError("Invalid finding Source ordinal.")
        if self.ordinal < 1:
            raise QualityFindReportError("Invalid finding Source ordinal.")


@dataclass(frozen=True)
class QualityFindingReading:
    """One provider-reported possible reading, never a selectable answer."""

    label: str
    text: str

    def __post_init__(self) -> None:
        _text(self.label, "finding reading label")
        _text(self.text, "finding reading")


@dataclass(frozen=True)
class QualityFindingReportItem:
    """One immutable finding and its complete source-linked explanation."""

    uid: str
    kind: str
    classification: str
    title: str
    reason_heading: str
    reason: str
    sources: tuple[QualityFindingSource, ...]
    follow_up: str = ""
    readings: tuple[QualityFindingReading, ...] = ()

    def __post_init__(self) -> None:
        _text(self.uid, "finding uid")
        _text(self.kind, "finding kind")
        _text(self.classification, "finding classification")
        _text(self.title, "finding title")
        _text(self.reason_heading, "finding reason heading")
        _text(self.reason, "finding reason")
        _text(self.follow_up, "finding follow-up", empty=True)
        if not self.sources:
            raise QualityFindReportError("A finding requires exact Source evidence.")
        if len({source.memory_uid for source in self.sources}) != len(self.sources):
            raise QualityFindReportError("A finding repeats a Source Memory.")


@dataclass(frozen=True)
class QualityFindReportView:
    """One bounded read-only finding browser projection."""

    kind: QualityFindReportKind
    operation: str
    artifact_uid: str
    revision: str
    route: str
    source_count: int
    memory_count: int
    items: tuple[QualityFindingReportItem, ...]
    empty_message: str
    handoff_key: str | None = None
    handoff_label: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"ambiguities", "conflicts", "duplicates"}:
            raise QualityFindReportError("Unsupported quality finding kind.")
        for value, label in (
            (self.operation, "finding operation"),
            (self.artifact_uid, "finding artifact uid"),
            (self.revision, "finding revision"),
            (self.route, "finding route"),
            (self.empty_message, "finding empty message"),
        ):
            _text(value, label)
        for value, label in (
            (self.source_count, "finding Source count"),
            (self.memory_count, "finding Memory count"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise QualityFindReportError(f"Invalid {label}.")
        if len({item.uid for item in self.items}) != len(self.items):
            raise QualityFindReportError("Duplicate quality finding uid.")
        if (self.handoff_key is None) != (self.handoff_label is None):
            raise QualityFindReportError("Finding handoff key and label must agree.")
        if self.handoff_key is not None:
            key = _text(self.handoff_key, "finding handoff key")
            if len(key) != 1:
                raise QualityFindReportError("Finding handoff key must be one key.")
            _text(self.handoff_label, "finding handoff label")


@dataclass(frozen=True)
class QualityFindBrowserReceipt:
    """Read-only close or explicit transition to another operation."""

    action: Literal["CLOSE", "HANDOFF"]
    item_uid: str | None = None

    def __post_init__(self) -> None:
        if self.action == "CLOSE" and self.item_uid is not None:
            raise QualityFindReportError("A closed finding browser has no target.")
        if self.action == "HANDOFF":
            if self.item_uid is None:
                raise QualityFindReportError(
                    "A finding handoff requires one exact target."
                )
            _text(self.item_uid, "finding handoff target")


__all__ = [
    "QualityFindBrowserReceipt",
    "QualityFindReportError",
    "QualityFindReportKind",
    "QualityFindReportView",
    "QualityFindingReading",
    "QualityFindingReportItem",
    "QualityFindingSource",
]
