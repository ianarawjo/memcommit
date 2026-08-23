"""Terminal-independent contracts for one-shot granted Query execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.operations.query.granted_source import AuthorityQueryCatalogEntry


GrantedQueryStage = Literal[
    "AUTHORITY_FROZEN",
    "CONNECTING_PROVIDER",
    "PREPARING_SOURCES",
    "ANSWERING",
    "REVALIDATING",
]


@dataclass(frozen=True)
class GrantedQueryTarget:
    """Public control-plane identity for one QUERY-granted view."""

    grant_uid: str
    public_name: str
    attachment_name: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.grant_uid, self.public_name, self.attachment_name)
        ):
            raise ValueError("Granted Query target fields must be nonblank.")


@dataclass(frozen=True)
class GrantedQueryRequest:
    """One exact process-local query-only read."""

    target: GrantedQueryTarget
    question: str | None
    language: str = "en"
    memory_handle: str | None = None
    federate_descendants: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.target, GrantedQueryTarget):
            raise ValueError("Granted Query requires a typed target.")
        if self.question is not None and (
            not isinstance(self.question, str) or not self.question.strip()
        ):
            raise ValueError("Query question must be nonblank when supplied.")
        if not isinstance(self.language, str) or not self.language:
            raise ValueError("Query language must be nonblank.")
        if self.memory_handle is not None and not self.memory_handle:
            raise ValueError("Query Memory handle must be nonblank.")
        if not isinstance(self.federate_descendants, bool):
            raise ValueError("Query federation choice must be a boolean.")


@dataclass(frozen=True)
class GrantedQueryResponse:
    """One authorized opaque catalog or process-local answer."""

    request: GrantedQueryRequest
    answer: str | None = None
    catalog: tuple[AuthorityQueryCatalogEntry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.request, GrantedQueryRequest):
            raise ValueError("Granted Query response requires its frozen request.")
        if (self.answer is None) == (self.request.question is not None):
            raise ValueError("Granted Query answer does not match its request mode.")
        if self.answer is not None and (
            not isinstance(self.answer, str) or not self.answer.strip()
        ):
            raise ValueError("Granted Query returned an empty answer.")
        if not isinstance(self.catalog, tuple) or any(
            not isinstance(entry, AuthorityQueryCatalogEntry) for entry in self.catalog
        ):
            raise ValueError("Granted Query catalog must contain typed entries.")
        if self.answer is not None and self.catalog:
            raise ValueError("A Query answer cannot also expose a catalog.")


@dataclass(frozen=True)
class PreparedGrantedQuery:
    """Opaque authority preparation completed before provider construction."""

    request: GrantedQueryRequest
    token: object


class GrantedQueryReadPort(Protocol):
    """Open and revalidate concealed read material without persistence."""

    def prepare(self, request: GrantedQueryRequest) -> PreparedGrantedQuery: ...

    def read(
        self,
        prepared: PreparedGrantedQuery,
        provider: object,
        observer: GrantedQueryObserver | None = None,
    ) -> GrantedQueryResponse: ...


class GrantedQueryProviderFactory(Protocol):
    def __call__(self) -> object: ...


class GrantedQueryObserver(Protocol):
    def __call__(self, stage: GrantedQueryStage) -> None: ...


def _observe(
    observer: GrantedQueryObserver | None,
    stage: GrantedQueryStage,
) -> None:
    if observer is not None:
        observer(stage)


def run_granted_query_read(
    request: GrantedQueryRequest,
    *,
    read_port: GrantedQueryReadPort,
    provider_factory: GrantedQueryProviderFactory,
    observer: GrantedQueryObserver | None = None,
) -> GrantedQueryResponse:
    """Execute exactly one revalidated read without publishing durable state."""

    prepared = read_port.prepare(request)
    if prepared.request != request:
        raise ValueError("Granted Query preparation changed the request.")
    _observe(observer, "AUTHORITY_FROZEN")
    _observe(observer, "CONNECTING_PROVIDER")
    provider = provider_factory()
    response = read_port.read(prepared, provider, observer)
    if response.request != request:
        raise ValueError("Granted Query execution changed the request.")
    return response


__all__ = [
    "GrantedQueryObserver",
    "GrantedQueryProviderFactory",
    "GrantedQueryReadPort",
    "GrantedQueryRequest",
    "GrantedQueryResponse",
    "GrantedQueryStage",
    "GrantedQueryTarget",
    "PreparedGrantedQuery",
    "run_granted_query_read",
]
