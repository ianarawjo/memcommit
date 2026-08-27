"""Compose one operation's stable meaning with interface-owned guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from memcommit.application.operations.operation_catalog.model import OperationHelp


@dataclass(frozen=True)
class HelpRow:
    """One label/value row that any Help renderer can project."""

    label: str
    value: str


@dataclass(frozen=True)
class ComposedOperationHelp:
    """Renderer-neutral detail assembled from common and CLI-owned sources."""

    operation: OperationHelp
    overview: tuple[HelpRow, ...]
    cli_forms: tuple[str, ...]


def compose_operation_help(
    operation: OperationHelp,
    *,
    cli_forms: Iterable[str] = (),
) -> ComposedOperationHelp:
    """Combine stable semantics with exact registered-interface projections."""

    rows = [
        HelpRow("FLOW", operation.flow),
        HelpRow("EXECUTION", operation.execution.value),
        HelpRow("EFFECT", operation.effect),
    ]
    if operation.range is not None:
        rows.append(HelpRow("RANGE", operation.range))
    rows.append(HelpRow("BEST FOR", operation.best_for))
    return ComposedOperationHelp(
        operation=operation,
        overview=tuple(rows),
        cli_forms=tuple(cli_forms),
    )
