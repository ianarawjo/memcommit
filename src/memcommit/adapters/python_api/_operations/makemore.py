"""Operation-owned assembly for standalone public Makemore."""

from __future__ import annotations

from collections.abc import Sequence

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.semantic import project_makemore, safe_semantic_provider
from memcommit.adapters.python_api.errors import (
    SemanticExecutionError,
    SemanticInputError,
    SemanticProviderFailure,
)
from memcommit.adapters.python_api.semantic import MakemoreProposal
from memcommit.application.operations.makemore.model import MakemoreError
from memcommit.application.operations.makemore.application import MakemoreRequest
from memcommit.application.operations.makemore.runtime import execute_makemore
from memcommit.providers.subscription import QueryProviderError


def makemore(
    runtime: ClientRuntime,
    *,
    goal: str | None = None,
    rules: Sequence[str] | None = None,
    number: int | None = None,
    strict: bool = False,
) -> MakemoreProposal:
    """Propose unverified Rules from a Goal or Cases from Rules."""

    try:
        if isinstance(rules, (str, bytes)):
            raise TypeError("rules must be a sequence of Rule texts.")
        request = MakemoreRequest(
            goal=goal,
            rules=tuple(rules or ()),
            number=number,
            strict=strict,
        )
    except (MakemoreError, TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    try:
        result = execute_makemore(
            request,
            provider_factory=lambda: safe_semantic_provider(runtime),
        )
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except MakemoreError as error:
        raise_public(SemanticExecutionError, error)
    return project_makemore(result)


__all__ = ["makemore"]
