"""Shared public failure and provider projection for semantic operations."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticProviderFailure,
)


class SafeSemanticProvider:
    """Map caller-supplied provider failures into the public error taxonomy."""

    def __init__(self, delegate: object) -> None:
        self._delegate = delegate

    def complete(self, prompt, *, operation, output_schema=None):
        try:
            complete = getattr(self._delegate, "complete")
            return complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        except SemanticProviderFailure:
            raise
        except Exception as error:
            raise_public(SemanticProviderFailure, error)


def semantic_provider(runtime: ClientRuntime) -> object:
    """Construct one caller-configured provider only after operation validation."""

    try:
        return SafeSemanticProvider(runtime.semantic_provider_factory())
    except SemanticProviderFailure:
        raise
    except Exception as error:
        raise_public(SemanticProviderFailure, error)


def raise_semantic_execution_error(error: BaseException) -> None:
    """Project operation failures without leaking private exception classes."""

    message = str(error).casefold()
    if "was not found" in message or "no longer exists" in message:
        raise_public(SemanticContextError, error)
    if "authorized" in message or "granted" in message:
        raise_public(SemanticAuthorityError, error)
    if "changed" in message or "concurrent" in message:
        raise_public(SemanticConflictError, error)
    raise_public(SemanticExecutionError, error)


__all__ = [
    "SafeSemanticProvider",
    "raise_semantic_execution_error",
    "semantic_provider",
]
