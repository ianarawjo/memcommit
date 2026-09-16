"""Process-local values for the Query workbench."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
)
from memcommit.application.operations.query.ordinary_application import (
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
    status: Literal["CLOSED", "SAVE"]
    response: QueryWorkbenchResponse | None = None
    save_location: str | None = None

    def __post_init__(self) -> None:
        if self.status == "CLOSED":
            if self.save_location is not None:
                raise ValueError("A closed Query workbench cannot request a save.")
            return
        if (
            self.response is None
            or not isinstance(self.save_location, str)
            or not self.save_location.strip()
        ):
            raise ValueError("Query SAVE requires an answer and exact location.")


@dataclass(frozen=True)
class QueryAnswerClipboardProjection:
    """One focused Answer unit or its complete typed document."""

    text: str
    scope: Literal["FOCUSED", "DOCUMENT"]
    label: str
    reference_count: int = 0
