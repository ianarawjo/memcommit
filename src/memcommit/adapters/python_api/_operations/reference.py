"""Public immutable Memory or Context Reference assembly."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.readable import active_client_registry
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.errors import (
    ReferenceAuthorityError,
    ReferenceConflictError,
    ReferenceContextError,
    ReferenceExecutionError,
    ReferenceInputError,
    ReferenceStorageError,
)
from memcommit.application.operations.profiles.profile.config import ProfileConfigError
from memcommit.application.operations.profiles.profile.model import ProfileError
from memcommit.adapters.python_api.reference import ContextReferenceResult, MemoryReferenceResult
from memcommit.application.operations.create_copy_connect.reference.application import (
    ContextReferenceRequest,
    ReferenceError as ApplicationReferenceError,
    ReferenceRequest,
)
from memcommit.application.operations.create_copy_connect.reference.runtime import (
    execute_context_reference,
    execute_reference,
)
from memcommit.persistence.store import ConcurrentContextUpdateError


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
        result = execute_reference(
            request,
            store=runtime.store,
            allow_granted_sources=active_client_registry(runtime) is not None,
        )
    except FileNotFoundError as error:
        raise_public(ReferenceContextError, error)
    except (ProfileConfigError, ProfileError, PermissionError) as error:
        raise_public(ReferenceAuthorityError, error)
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


def reference_context(
    runtime: ClientRuntime,
    source_context: str,
    *,
    into_context: str | None = None,
    recursive: bool = False,
) -> ContextReferenceResult:
    """Retain one immutable direct or recursive Context snapshot."""

    try:
        result = execute_context_reference(
            ContextReferenceRequest(
                source_locator=source_context,
                into_locator=into_context,
                include_descendants=recursive,
                follow_embeds=recursive,
            ),
            store=runtime.store,
        )
    except FileNotFoundError as error:
        raise_public(ReferenceContextError, error)
    except (ProfileConfigError, ProfileError, PermissionError) as error:
        raise_public(ReferenceAuthorityError, error)
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

    return ContextReferenceResult(
        reference_uid=result.reference_uid,
        source_name=result.source_name,
        source_uid=result.source_uid,
        snapshot_content_sha256=result.snapshot_content_sha256,
        include_descendants=result.include_descendants,
        follow_embeds=result.follow_embeds,
        context_count=result.context_count,
        into_name=result.into_name,
        into_uid=result.into_uid,
        checkpoint_uid=result.checkpoint_uid,
    )


__all__ = ["reference_context", "reference_memory"]
