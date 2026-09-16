"""Operation-owned contract for saving one completed Query answer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias

from memcommit.application.operations.query.granted_application import (
    GrantedQueryResponse,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryResponse,
)


QueryAnswerResponse: TypeAlias = OrdinaryQueryResponse | GrantedQueryResponse


class SaveQueryAnswerError(RuntimeError):
    """Raised when saving a Query answer fails."""


@dataclass(frozen=True, slots=True)
class SaveQueryAnswerRequest:
    response: QueryAnswerResponse
    destination_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.response, (OrdinaryQueryResponse, GrantedQueryResponse)):
            raise SaveQueryAnswerError(
                "Expected an OrdinaryQueryResponse or GrantedQueryResponse."
            )
        if (
            not isinstance(self.destination_name, str)
            or not self.destination_name.strip()
        ):
            raise SaveQueryAnswerError(
                "Saving a Query answer requires a destination Context name."
            )


@dataclass(frozen=True, slots=True)
class SaveQueryAnswerResult:
    context_name: str
    context_uid: str
    checkpoint_uid: str
    memory_uid: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.context_name,
                self.context_uid,
                self.checkpoint_uid,
                self.memory_uid,
            )
        ):
            raise SaveQueryAnswerError(
                "Query answer save receipt is incomplete: "
                "missing Context name or required identifier."
            )


class SaveQueryAnswerPort(Protocol):
    def save(self, request: SaveQueryAnswerRequest) -> SaveQueryAnswerResult: ...


def save_query_answer(
    request: SaveQueryAnswerRequest,
    *,
    port: SaveQueryAnswerPort,
) -> SaveQueryAnswerResult:
    """Publish exactly the reviewed answer, without reopening its Sources."""

    if not isinstance(request, SaveQueryAnswerRequest):
        raise TypeError("Expected a SaveQueryAnswerRequest.")
    result = port.save(request)
    if result.context_name != request.destination_name:
        raise SaveQueryAnswerError(
            "The Context name returned after saving does not match the requested destination."
        )
    return result


__all__ = [
    "QueryAnswerResponse",
    "SaveQueryAnswerError",
    "SaveQueryAnswerPort",
    "SaveQueryAnswerRequest",
    "SaveQueryAnswerResult",
    "save_query_answer",
]
