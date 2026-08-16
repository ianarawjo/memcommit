"""Operation-owned assembly for standalone public Elaborate."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import project_elaborate, safe_semantic_provider
from memcommit.api.errors import (
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.api.semantic import ElaborateProposal
from memcommit.elaborate import ElaborateError
from memcommit.elaborate_application import ElaborateRequest
from memcommit.elaborate_runtime import execute_elaborate
from memcommit.query_provider import QueryProviderError


def elaborate(
    runtime: ClientRuntime,
    *,
    goal: str | None = None,
    rules: Sequence[str] | None = None,
) -> ElaborateProposal:
    """Propose unverified Rules from a Goal or Cases from Rules."""

    try:
        if isinstance(rules, (str, bytes)):
            raise TypeError("rules must be a sequence of Rule texts.")
        request = ElaborateRequest(
            goal=goal,
            rules=tuple(rules or ()),
        )
    except (ElaborateError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = execute_elaborate(
            request,
            provider_factory=lambda: safe_semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except ElaborateError as error:
        raise_public(SemanticExecutionError, error)
    return project_elaborate(result)


__all__ = ["elaborate"]
