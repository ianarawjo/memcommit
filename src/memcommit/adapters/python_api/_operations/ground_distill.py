"""Ground-specific public Distill assembly."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api._support.semantic import (
    project_distill,
    raise_semantic_execution_error,
    safe_semantic_provider,
)
from memcommit.adapters.python_api.errors import (
    SemanticContextError,
    SemanticInputError,
    SemanticProviderFailure,
    SemanticStorageError,
)
from memcommit.adapters.python_api.semantic import DistillProposal
from memcommit.application.operations.distill.model import DistillError
from memcommit.application.operations.ground.distill import execute_ground_distill, freeze_ground_distill
from memcommit.providers.subscription import QueryProviderError


def distill_ground(
    runtime: ClientRuntime,
    ground_name: str,
) -> DistillProposal:
    """Distill one exact bound Ground frame without mutating the Ground."""

    if not isinstance(ground_name, str) or not ground_name.strip():
        raise SemanticInputError("ground_name must be nonblank text.")
    try:
        frozen = freeze_ground_distill(runtime.store, ground_name=ground_name)
        result = execute_ground_distill(
            frozen,
            store=runtime.store,
            provider_factory=lambda: safe_semantic_provider(runtime),
        ).distill
    except SemanticProviderFailure:
        raise
    except QueryProviderError as error:
        raise_public(SemanticProviderFailure, error)
    except FileNotFoundError as error:
        raise_public(SemanticContextError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except DistillError as error:
        raise_semantic_execution_error(error)
    return project_distill(result, apply_allowed=False)


__all__ = ["distill_ground"]
