"""Process-local values for the Query terminal interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from memcommit.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
)
from memcommit.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)


QueryWorkbenchResponse: TypeAlias = OrdinaryQueryResponse | GrantedQueryResponse
OrdinaryQueryRunner: TypeAlias = Callable[
    [OrdinaryQueryRequest], OrdinaryQueryResponse
]
GrantedQueryRunner: TypeAlias = Callable[
    [GrantedQueryRequest], GrantedQueryResponse
]


@dataclass(frozen=True)
class SavedQueryTranscript:
    """Task-owned visible Q/A projected without reopening its Source."""

    name: str
    requested_name: str
    language: str
    revision: int
    turns: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.name or not self.requested_name or not self.language:
            raise ValueError("Saved Query transcript labels must be nonblank.")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            raise ValueError("Saved Query transcript revision is invalid.")
        if any(
            not isinstance(turn, tuple)
            or len(turn) != 2
            or not all(isinstance(value, str) and value for value in turn)
            for turn in self.turns
        ):
            raise ValueError("Saved Query transcript turns must be nonblank.")


@dataclass(frozen=True)
class QueryWorkbenchResult:
    status: Literal["CLOSED"]
    response: QueryWorkbenchResponse | None = None


@dataclass(frozen=True)
class QueryAnswerClipboardProjection:
    """One focused Answer unit or its complete typed document."""

    text: str
    scope: Literal["FOCUSED", "DOCUMENT"]
    label: str
    reference_count: int = 0
