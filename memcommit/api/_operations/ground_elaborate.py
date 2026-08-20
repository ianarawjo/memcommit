"""Ground-specific public Elaborate assembly."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api._support.semantic import (
    project_elaborate,
    raise_semantic_execution_error,
    safe_semantic_provider,
)
from memcommit.api.errors import (
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.api.semantic import ElaborateProposal
from memcommit.elaborate import ElaborateError
from memcommit.ground_elaborate import (
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.query_provider import QueryProviderError


def elaborate_ground(
    runtime: ClientRuntime,
    ground_name: str,
    *,
    direction: str,
    number: int | None = None,
) -> ElaborateProposal:
    """Project one exact Ground Goal or Rule set through Elaborate."""

    if not isinstance(ground_name, str) or not ground_name.strip():
        raise SemanticInputError("ground_name must be nonblank text.")
    if direction not in {"GOAL_TO_RULES", "RULES_TO_CASES"}:
        raise SemanticInputError(
            "direction must be GOAL_TO_RULES or RULES_TO_CASES."
        )
    try:
        frozen = freeze_ground_elaborate(
            runtime.store,
            ground_name=ground_name,
            direction=direction,  # type: ignore[arg-type]
            number=number,
        )
        result = execute_ground_elaborate(
            frozen,
            store=runtime.store,
            provider_factory=lambda: safe_semantic_provider(runtime),
        ).elaborate
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except ElaborateError as error:
        raise_semantic_execution_error(error)
    return project_elaborate(result)


__all__ = ["elaborate_ground"]
