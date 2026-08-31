"""Terminal-independent application contract for a QueryContextRef read."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


QueryReferenceStage = Literal[
    "CONNECTING_PROVIDER",
    "OPENING_SOURCE",
    "ANSWERING",
]


@dataclass(frozen=True)
class QueryReferenceRequest:
    """One exact question against one concealed QueryContextRef Source."""

    source_uid: str
    source_name: str
    provider_name: str
    question: str
    language: str = "en"

    def __post_init__(self) -> None:
        for field, value in (
            ("Source uid", self.source_uid),
            ("Source name", self.source_name),
            ("provider name", self.provider_name),
            ("question", self.question),
            ("language", self.language),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Query reference {field} must be nonblank.")


@dataclass(frozen=True)
class FrozenQueryReferenceSource:
    """Provider-facing Source opened only after provider construction."""

    name: str
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Query reference Source name must be nonblank.")
        if not isinstance(self.content, str) or not self.content:
            raise ValueError("Query reference Source content must be nonblank.")


@dataclass(frozen=True)
class QueryReferenceResponse:
    """One unsaved answer bound to the exact reference request."""

    request: QueryReferenceRequest
    answer: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, QueryReferenceRequest):
            raise ValueError("Query reference response requires its exact request.")
        if not isinstance(self.answer, str):
            raise ValueError("Query reference provider answer must be text.")


class QueryReferenceSourcePort(Protocol):
    """Open the exact concealed Source selected by a frozen request."""

    def open(self, request: QueryReferenceRequest) -> FrozenQueryReferenceSource: ...


class QueryReferenceProvider(Protocol):
    def query(self, source_name: str, source_content: str, question: str) -> str: ...


class QueryReferenceProviderFactory(Protocol):
    def __call__(self, provider_name: str) -> QueryReferenceProvider: ...


class QueryReferenceObserver(Protocol):
    def __call__(self, stage: QueryReferenceStage) -> None: ...


def _observe(
    observer: QueryReferenceObserver | None,
    stage: QueryReferenceStage,
) -> None:
    if observer is not None:
        observer(stage)


def run_query_reference(
    request: QueryReferenceRequest,
    *,
    source_port: QueryReferenceSourcePort,
    provider_factory: QueryReferenceProviderFactory,
    observer: QueryReferenceObserver | None = None,
) -> QueryReferenceResponse:
    """Authenticate first, then open one concealed Source and answer once."""

    _observe(observer, "CONNECTING_PROVIDER")
    provider = provider_factory(request.provider_name)
    _observe(observer, "OPENING_SOURCE")
    source = source_port.open(request)
    _observe(observer, "ANSWERING")
    answer = provider.query(source.name, source.content, request.question)
    return QueryReferenceResponse(request, answer)


__all__ = [
    "FrozenQueryReferenceSource",
    "QueryReferenceObserver",
    "QueryReferenceProvider",
    "QueryReferenceProviderFactory",
    "QueryReferenceRequest",
    "QueryReferenceResponse",
    "QueryReferenceSourcePort",
    "QueryReferenceStage",
    "run_query_reference",
]
