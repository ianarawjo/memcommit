"""Process-local values for the Query workbench."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from memcommit.application.operations.search_explain.retrieve_answer.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
)
from memcommit.application.operations.search_explain.retrieve_answer.query.ordinary_application import (
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
