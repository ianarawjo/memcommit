"""Public immutable Memory Reference assembly."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.errors import (
    ReferenceConflictError,
    ReferenceContextError,
    ReferenceExecutionError,
    ReferenceInputError,
    ReferenceStorageError,
)
from memcommit.api.reference import MemoryReferenceResult
from memcommit.reference_application import (
    ReferenceError as ApplicationReferenceError,
    ReferenceRequest,
)
from memcommit.reference_runtime import execute_reference
from memcommit.store import ConcurrentContextUpdateError


def reference_memory(
    runtime: ClientRuntime,
    memory_selector: str,
    *,
    source_context: str,
    into_context: str | None = None,
) -> MemoryReferenceResult:
    """Retain one exact immutable snapshot of a directly owned Memory."""

    try:
        request = ReferenceRequest(
            memory_selector=memory_selector,
            source_locator=source_context,
            into_locator=into_context,
        )
        result = execute_reference(request, store=runtime.store)
    except FileNotFoundError as error:
        raise_public(ReferenceContextError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(ReferenceConflictError, error)
    except OSError as error:
        raise_public(ReferenceStorageError, error)
    except (ApplicationReferenceError, KeyError, TypeError, ValueError) as error:
        raise_public(ReferenceInputError, error)
    except RuntimeError as error:
        raise_public(ReferenceConflictError, error)
    except Exception as error:
        raise_public(ReferenceExecutionError, error)

    return MemoryReferenceResult(
        reference_uid=result.reference_uid,
        source_name=result.source_name,
        source_uid=result.source_uid,
        memory_uid=result.memory_uid,
        memory_content_sha256=result.memory_content_sha256,
        into_name=result.into_name,
        into_uid=result.into_uid,
        checkpoint_uid=result.checkpoint_uid,
    )


__all__ = ["reference_memory"]
