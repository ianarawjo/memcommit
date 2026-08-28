"""Stable public request configuration and result values for Query."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.providers.operation_connections import QUERY_PROVIDER_POLICY
from memcommit.providers.types import CODEX_REASONING_EFFORTS


QUERY_REASONING_EFFORTS = tuple(
    dict.fromkeys((QUERY_PROVIDER_POLICY.reasoning_effort, *CODEX_REASONING_EFFORTS))
)


@dataclass(frozen=True)
class QueryProviderConfig:
    """One immutable provider policy snapshot owned by a client instance."""

    model: str = QUERY_PROVIDER_POLICY.model
    reasoning_effort: str = QUERY_PROVIDER_POLICY.reasoning_effort
    timeout_seconds: float = 600.0

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Query provider model must be nonblank.")
        if self.reasoning_effort not in QUERY_REASONING_EFFORTS:
            raise ValueError(
                "Query reasoning effort must be one of: "
                + ", ".join(QUERY_REASONING_EFFORTS)
                + "."
            )
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("Query provider timeout must be positive.")


@dataclass(frozen=True)
class QueryCitation:
    """One used ordinary-Query evidence item with stable local numbering."""

    number: int
    alias: str
    context_name: str
    kind: Literal["memory", "ref", "query", "artifact"]
    uid: str
    content: str


@dataclass(frozen=True)
class OrdinaryQueryResult:
    """Read-only ordinary Query answer and its independently usable citations."""

    answer: str
    grounded: bool
    citations: tuple[QueryCitation, ...] = ()


@dataclass(frozen=True)
class GrantedQueryResult:
    """One process-local granted Query answer."""

    public_name: str
    answer: str


@dataclass(frozen=True)
class ReferenceQueryResult:
    """Unsaved answer from one exact legacy QueryContextRef source."""

    source_name: str
    answer: str


__all__ = [
    "GrantedQueryResult",
    "OrdinaryQueryResult",
    "QueryCitation",
    "QueryProviderConfig",
    "ReferenceQueryResult",
]
