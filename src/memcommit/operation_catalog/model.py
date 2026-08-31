"""Interface-neutral contracts for the public MemCommit operation surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from memcommit.operation_catalog.families import OperationFamilyId


class ExecutionKind(str, Enum):
    """How an operation reaches its substantive result."""

    DETERMINISTIC = "DETERMINISTIC"
    SEMANTIC = "SEMANTIC"
    MIXED = "MIXED"


class HelpDetailKind(str, Enum):
    """Typed payload families supported by operation Help details."""

    COMPARISON = "COMPARISON"
    LIMITATION = "LIMITATION"
    ACCESS_BOUNDARY = "ACCESS_BOUNDARY"
    SEMANTIC_BOUNDARY = "SEMANTIC_BOUNDARY"


class DetailDiscovery(str, Enum):
    """How much of a detail is needed before an agent chooses a tool."""

    TOOL_SELECTION = "TOOL_SELECTION"
    ON_DEMAND = "ON_DEMAND"


@dataclass(frozen=True)
class OperationComparisonOption:
    """One named alternative in an operation-choice comparison."""

    label: str
    guidance: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("Operation comparison option label must be nonblank.")
        if not self.guidance.strip():
            raise ValueError("Operation comparison option guidance must be nonblank.")


@dataclass(frozen=True)
class OperationHelpDetail:
    """Stable, individually addressable detail for one operation."""

    id: str
    operation: str
    title: str
    use_when: str
    discovery: DetailDiscovery
    discovery_summary: str | None = None

    @property
    def kind(self) -> HelpDetailKind:
        raise NotImplementedError

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.id) is None:
            raise ValueError("Operation Help detail id must be lowercase kebab-case.")
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.operation) is None:
            raise ValueError("Operation Help detail operation must be a public name.")
        for field_name in ("title", "use_when"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Operation Help detail {field_name} must be nonblank."
                )
        if not isinstance(self.discovery, DetailDiscovery):
            raise TypeError("Operation Help detail discovery must be typed.")
        if self.discovery_summary is not None:
            if not self.discovery_summary.strip():
                raise ValueError(
                    "Operation Help detail discovery_summary must be nonblank."
                )
            if "\n" in self.discovery_summary or "\r" in self.discovery_summary:
                raise ValueError(
                    "Operation Help detail discovery_summary must be one line."
                )
            if len(self.discovery_summary) > 240:
                raise ValueError(
                    "Operation Help detail discovery_summary exceeds 240 characters."
                )
        if (
            self.discovery is DetailDiscovery.TOOL_SELECTION
            and self.discovery_summary is None
        ):
            raise ValueError("TOOL_SELECTION Help details require a discovery_summary.")


@dataclass(frozen=True)
class OperationComparisonDetail(OperationHelpDetail):
    """Structured comparison between this operation and adjacent choices."""

    explanation: str = ""
    options: tuple[OperationComparisonOption, ...] = ()

    @property
    def kind(self) -> HelpDetailKind:
        return HelpDetailKind.COMPARISON

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.explanation.strip():
            raise ValueError("Operation comparison explanation must be nonblank.")
        if not isinstance(self.options, tuple) or any(
            not isinstance(item, OperationComparisonOption) for item in self.options
        ):
            raise TypeError("Operation comparison options must be an immutable tuple.")
        if not self.options:
            raise ValueError("Operation comparison must contain at least one option.")


@dataclass(frozen=True)
class OperationTextDetail(OperationHelpDetail):
    """Typed prose for a limitation, access, or semantic boundary."""

    detail_kind: HelpDetailKind = HelpDetailKind.LIMITATION
    body: str = ""

    @property
    def kind(self) -> HelpDetailKind:
        return self.detail_kind

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.detail_kind not in {
            HelpDetailKind.LIMITATION,
            HelpDetailKind.ACCESS_BOUNDARY,
            HelpDetailKind.SEMANTIC_BOUNDARY,
        }:
            raise ValueError("Operation text detail kind must be a prose detail kind.")
        if not self.body.strip():
            raise ValueError("Operation text detail body must be nonblank.")


@dataclass(frozen=True)
class OperationDescriptor:
    """Stable operation affordance shared by applications and adapters."""

    name: str
    family: OperationFamilyId
    summary: str
    flow: str
    execution: ExecutionKind
    effect: str
    best_for: str
    range: str | None = None
    maturity: str | None = None
    details: tuple[OperationHelpDetail, ...] = ()

    @property
    def use_when(self) -> str:
        """Expose the reviewed use case under the public presentation label."""

        return self.best_for

    def __post_init__(self) -> None:
        if not isinstance(self.family, OperationFamilyId):
            raise TypeError("Operation family must use a stable family identity.")
        for field_name in ("name", "summary", "flow", "effect"):
            value = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"Operation Help {field_name} must be nonblank.")
        if self.range is not None and not self.range.strip():
            raise ValueError("Operation Help range must be nonblank when present.")
        if not self.best_for.strip():
            raise ValueError("Operation Help best_for must be nonblank.")
        if self.maturity is not None and not self.maturity.strip():
            raise ValueError("Operation Help maturity must be nonblank when present.")
        if not isinstance(self.details, tuple) or any(
            not isinstance(item, OperationHelpDetail) for item in self.details
        ):
            raise TypeError("Operation Help details must be an immutable tuple.")
        if any(detail.operation != self.name for detail in self.details):
            raise ValueError("Operation Help details must name their owning operation.")
        detail_ids = [detail.id for detail in self.details]
        if len(detail_ids) != len(set(detail_ids)):
            raise ValueError("Operation Help detail ids must be unique per operation.")


# Historical callers used the presentation-oriented name before the catalog
# became the top-level owner of the complete public operation affordance.
OperationHelp = OperationDescriptor

__all__ = [
    "DetailDiscovery",
    "ExecutionKind",
    "HelpDetailKind",
    "OperationComparisonDetail",
    "OperationComparisonOption",
    "OperationDescriptor",
    "OperationHelp",
    "OperationHelpDetail",
    "OperationTextDetail",
]
