"""Stable public values for operation discovery and Help descriptions."""

from __future__ import annotations

from dataclasses import dataclass


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


@dataclass(frozen=True, slots=True)
class HelpCatalogResult:
    """One immutable alphabetized snapshot of public operation descriptions."""

    operations: tuple[OperationHelpResult, ...]


__all__ = ["HelpCatalogResult", "OperationHelpResult"]
