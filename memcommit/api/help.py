"""Stable public values for operation discovery and Help descriptions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HelpComparisonOptionResult:
    """One machine-readable alternative in a Help comparison."""

    label: str
    guidance: str


@dataclass(frozen=True, slots=True)
class HelpComparisonResult:
    """One detailed comparison exposed by operation discovery."""

    id: str
    operation: str
    kind: str
    title: str
    use_when: str
    discovery: str
    discovery_summary: str | None
    explanation: str
    options: tuple[HelpComparisonOptionResult, ...]


@dataclass(frozen=True, slots=True)
class HelpTextDetailResult:
    """One typed limitation or access-boundary Help detail."""

    id: str
    operation: str
    kind: str
    title: str
    use_when: str
    discovery: str
    discovery_summary: str | None
    body: str


@dataclass(frozen=True, slots=True)
class HelpDetailReferenceResult:
    """Compact index entry for one individually retrievable Help detail."""

    id: str
    operation: str
    kind: str
    title: str
    use_when: str
    discovery: str
    discovery_summary: str | None


HelpDetailResult = HelpComparisonResult | HelpTextDetailResult


@dataclass(frozen=True, slots=True)
class HelpDetailCatalogResult:
    """Compact detail index for one exact operation."""

    operation: str
    details: tuple[HelpDetailReferenceResult, ...]


@dataclass(frozen=True, slots=True)
class OperationHelpResult:
    """One interface-neutral public operation description."""

    name: str
    summary: str
    flow: str
    execution: str
    effect: str
    best_for: str
    range: str | None
    maturity: str | None = None
    details: tuple[HelpDetailReferenceResult, ...] = ()

    @property
    def use_when(self) -> str:
        """Return the reviewed use case under its public discovery name."""

        return self.best_for


@dataclass(frozen=True, slots=True)
class HelpCatalogResult:
    """One immutable alphabetized snapshot of public operation descriptions."""

    operations: tuple[OperationHelpResult, ...]


__all__ = [
    "HelpCatalogResult",
    "HelpComparisonOptionResult",
    "HelpComparisonResult",
    "HelpDetailCatalogResult",
    "HelpDetailReferenceResult",
    "HelpDetailResult",
    "HelpTextDetailResult",
    "OperationHelpResult",
]
