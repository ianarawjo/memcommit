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


def quality_find_category_label(kind: QualityFindReportKind) -> str:
    """Return the stable user-facing category name for one finder."""

    try:
        return {
            "ambiguities": "AMBIGUITIES",
            "conflicts": "CONFLICTS",
            "duplicates": "REDUNDANCIES",
        }[kind]
    except KeyError as error:
        raise QualityFindReportError("Unsupported quality finding category.") from error


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
    category: QualityFindReportKind
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
        if self.category not in {"ambiguities", "conflicts", "duplicates"}:
            raise QualityFindReportError("Unsupported quality finding category.")
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


def quality_finding_label_parts(
    item: QualityFindingReportItem,
) -> tuple[str, str, str]:
    """Return the shared marker, category label, and compact classification."""

    if item.category == "ambiguities":
        label = (
            "UNDERSPECIFIED"
            if item.classification.startswith("SINGLE ·")
            else "AMBIGUOUS"
        )
        return "?", label, ""
    if item.category == "conflicts":
        label = "POSSIBLE CONFLICT" if item.classification == "MAY" else "CONFLICT"
        return "!", label, ""
    relation_labels = {
        "EXACT": ("=", "DUPLICATE", "EXACT"),
        "SURFACE_EQUIVALENT": ("≈", "REDUNDANT", "SURFACE EQUIVALENT"),
        "SEMANTIC_EQUIVALENT": ("≈", "REDUNDANT", "SEMANTIC EQUIVALENT"),
    }
    try:
        return relation_labels[item.classification]
    except KeyError as error:
        raise QualityFindReportError(
            "Unsupported positive redundancy classification."
        ) from error


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
    pair_count: int | None
    group_count: int | None
    redundant_item_count: int | None
    items: tuple[QualityFindingReportItem, ...]
    empty_message: str
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
        for value, label in (
            (self.pair_count, "finding pair count"),
            (self.group_count, "finding group count"),
            (self.redundant_item_count, "redundant item count"),
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise QualityFindReportError(f"Invalid {label}.")
        if self.kind == "ambiguities":
            if (
                any(
                    value is not None
                    for value in (
                        self.pair_count,
                        self.group_count,
                        self.redundant_item_count,
                    )
                )
                or len(self.items) > self.memory_count
            ):
                raise QualityFindReportError("Invalid Ambiguity report counts.")
        elif self.kind == "conflicts":
            if (
                self.pair_count is None
                or self.group_count is not None
                or self.redundant_item_count is not None
                or len(self.items) > self.pair_count
            ):
                raise QualityFindReportError("Invalid Conflict report counts.")
        elif (
            self.pair_count is not None
            or self.group_count is None
            or self.redundant_item_count is None
        ):
            raise QualityFindReportError("Invalid Redundancy report counts.")
        if any(item.category != self.kind for item in self.items):
            raise QualityFindReportError("Finding item category does not match report.")
        if len({item.uid for item in self.items}) != len(self.items):
            raise QualityFindReportError("Duplicate quality finding uid.")
        if self.handoff_label is not None:
            _text(self.handoff_label, "finding handoff label")

    @property
    def involved_memory_count(self) -> int:
        """Return distinct Memory identities represented by positive findings."""

        return len(
            {source.memory_uid for item in self.items for source in item.sources}
        )


def quality_find_report_summary_text(view: QualityFindReportView) -> str:
    """Return counts whose denominators match each finder's execution unit."""

    if view.kind == "ambiguities":
        return f"{len(view.items)}/{view.memory_count} MEMORIES FLAGGED"
    if view.kind == "conflicts":
        assert view.pair_count is not None
        return (
            f"{view.involved_memory_count}/{view.memory_count} MEMORIES INVOLVED · "
            f"{len(view.items)}/{view.pair_count} PAIRS FLAGGED"
        )
    assert view.group_count is not None
    assert view.redundant_item_count is not None
    group_label = "GROUP" if view.group_count == 1 else "GROUPS"
    absorption_label = "ABSORPTION" if view.redundant_item_count == 1 else "ABSORPTIONS"
    return (
        f"{view.memory_count} MEMORIES CHECKED · "
        f"{view.group_count} {group_label} · "
        f"{view.redundant_item_count} PROPOSED {absorption_label}"
    )


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
    "quality_find_category_label",
    "quality_find_report_summary_text",
    "quality_finding_label_parts",
]
