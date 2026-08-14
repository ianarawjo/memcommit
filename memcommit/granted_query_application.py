"""Terminal-independent application contracts for granted Query execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from memcommit.query_sessions import (
    AuthorityQueryCatalogEntry,
    validate_query_session_name,
)


GrantedQueryStage = Literal[
    "AUTHORITY_FROZEN",
    "CONNECTING_PROVIDER",
    "PREPARING_SOURCES",
    "ANSWERING",
    "REVALIDATING",
    "PUBLISHING_SESSION",
]


@dataclass(frozen=True)
class GrantedQueryTarget:
    """Public control-plane identity for one QUERY-granted view."""

    grant_uid: str
    public_name: str
    attachment_name: str
    session_log_allowed: bool

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (self.grant_uid, self.public_name, self.attachment_name)
        ):
            raise ValueError("Granted Query target fields must be nonblank.")
        if not isinstance(self.session_log_allowed, bool):
            raise ValueError("Granted Query session capability must be boolean.")


@dataclass(frozen=True)
class GrantedQueryRequest:
    """One exact query-only read, with an optional session publication intent."""

    target: GrantedQueryTarget
    question: str | None
    language: str = "en"
    session_name: str | None = None
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
        if self.session_name is not None:
            validate_query_session_name(self.session_name)
            if self.question is None:
                raise ValueError("A saved Query session requires a question.")
        if self.memory_handle is not None and not self.memory_handle:
            raise ValueError("Query Memory handle must be nonblank.")
        if not isinstance(self.federate_descendants, bool):
            raise ValueError("Query federation choice must be a boolean.")


@dataclass(frozen=True)
class GrantedQueryResponse:
    """One authorized catalog or answer, never a durable session receipt."""

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


@dataclass(frozen=True)
class GrantedQuerySessionPublication:
    """One exact answered turn that is prepared but not yet durable."""

    request: GrantedQueryRequest
    answer: str
    token: object

    def __post_init__(self) -> None:
        if self.request.session_name is None or self.request.question is None:
            raise ValueError("Query session publication requires a saved turn intent.")
        if not isinstance(self.answer, str) or not self.answer.strip():
            raise ValueError("Query session publication requires an answer.")


@dataclass(frozen=True)
class GrantedQueryReadOutcome:
    """A revalidated read plus an optional still-unpublished session turn."""

    response: GrantedQueryResponse
    publication: GrantedQuerySessionPublication | None = None

    def __post_init__(self) -> None:
        expected_publication = self.response.request.session_name is not None
        if expected_publication != (self.publication is not None):
            raise ValueError("Granted Query publication does not match its request.")
        if self.publication is not None and (
            self.publication.request != self.response.request
            or self.publication.answer != self.response.answer
        ):
            raise ValueError("Granted Query publication disagrees with its answer.")


@dataclass(frozen=True)
class GrantedQuerySessionPublicationResult:
    """Receipt for exactly one CAS-appended visible Query turn."""

    session_name: str
    revision: int
    turn_count: int

    def __post_init__(self) -> None:
        validate_query_session_name(self.session_name)
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
            or isinstance(self.turn_count, bool)
            or not isinstance(self.turn_count, int)
            or self.turn_count < 1
        ):
            raise ValueError("Query session publication receipt is invalid.")


class GrantedQueryReadPort(Protocol):
    """Open and revalidate concealed read material without persistence."""

    def prepare(self, request: GrantedQueryRequest) -> PreparedGrantedQuery: ...

    def read(
        self,
        prepared: PreparedGrantedQuery,
        provider: object,
        observer: GrantedQueryObserver | None = None,
    ) -> GrantedQueryReadOutcome: ...


class GrantedQuerySessionPublicationPort(Protocol):
    """Publish one prepared turn after independent authority/CAS validation."""

    def publish(
        self,
        publication: GrantedQuerySessionPublication,
    ) -> GrantedQuerySessionPublicationResult: ...


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
) -> GrantedQueryReadOutcome:
    """Execute a revalidated read while leaving any session turn unpublished."""

    prepared = read_port.prepare(request)
    if prepared.request != request:
        raise ValueError("Granted Query preparation changed the request.")
    _observe(observer, "AUTHORITY_FROZEN")
    _observe(observer, "CONNECTING_PROVIDER")
    provider = provider_factory()
    outcome = read_port.read(prepared, provider, observer)
    if outcome.response.request != request:
        raise ValueError("Granted Query execution changed the request.")
    return outcome


def publish_granted_query_session(
    publication: GrantedQuerySessionPublication,
    *,
    publication_port: GrantedQuerySessionPublicationPort,
    observer: GrantedQueryObserver | None = None,
) -> GrantedQuerySessionPublicationResult:
    """Publish only an explicit, already answered session turn."""

    _observe(observer, "PUBLISHING_SESSION")
    return publication_port.publish(publication)


__all__ = [
    "GrantedQueryObserver",
    "GrantedQueryProviderFactory",
    "GrantedQueryReadOutcome",
    "GrantedQueryReadPort",
    "GrantedQueryRequest",
    "GrantedQueryResponse",
    "GrantedQuerySessionPublication",
    "GrantedQuerySessionPublicationPort",
    "GrantedQuerySessionPublicationResult",
    "GrantedQueryStage",
    "GrantedQueryTarget",
    "PreparedGrantedQuery",
    "publish_granted_query_session",
    "run_granted_query_read",
]
