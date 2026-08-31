"""Ground-specific public Makemore assembly."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.semantic import (
    project_makemore,
    raise_semantic_execution_error,
    safe_semantic_provider,
)
from memcommit.adapters.python_api.errors import (
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.python_api.semantic import MakemoreProposal
from memcommit.application.operations.semantic_updates.derive.makemore.model import MakemoreError
from memcommit.application.operations.ground.makemore import (
    execute_ground_makemore,
    freeze_ground_makemore,
)
from memcommit.providers.subscription import QueryProviderError


def makemore_ground(
    runtime: ClientRuntime,
    ground_name: str,
    *,
    direction: str,
    number: int | None = None,
    strict: bool = False,
) -> MakemoreProposal:
    """Project one exact Ground Goal or Rule set through Makemore."""

    if not isinstance(ground_name, str) or not ground_name.strip():
        raise SemanticInputError("ground_name must be nonblank text.")
    if direction not in {"GOAL_TO_RULES", "RULES_TO_CASES"}:
        raise SemanticInputError(
            "direction must be GOAL_TO_RULES or RULES_TO_CASES."
        )
    try:
        frozen = freeze_ground_makemore(
            runtime.store,
            ground_name=ground_name,
            direction=direction,  # type: ignore[arg-type]
            number=number,
            strict=strict,
        )
        result = execute_ground_makemore(
            frozen,
            store=runtime.store,
            provider_factory=lambda: safe_semantic_provider(runtime),
        ).makemore
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except MakemoreError as error:
        raise_semantic_execution_error(error)
    return project_makemore(result)


__all__ = ["makemore_ground"]
