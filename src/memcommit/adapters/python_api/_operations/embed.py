"""Public live Context and Memory Embed assembly."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.readable import active_client_registry
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.embed import (
    EmbeddedContextResult,
    EmbeddedMemoryResult,
    EmbedPlacementResult,
)
from memcommit.adapters.python_api.errors import (
    EmbedAuthorityError,
    EmbedConflictError,
    EmbedContextError,
    EmbedExecutionError,
    EmbedInputError,
    EmbedStorageError,
)
from memcommit.application.operations.create_copy_connect.embed.application import (
    EmbedError as ApplicationEmbedError,
    EmbedRequest,
    MemoryEmbedRequest,
)
from memcommit.application.operations.create_copy_connect.embed.runtime import execute_embed, execute_memory_embed
from memcommit.application.operations.profiles.profile.config import ProfileConfigError
from memcommit.application.operations.profiles.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError


def _placement(result) -> EmbedPlacementResult:
    value = result.placement
    return EmbedPlacementResult(
        position=value.position,
        previous_uid=value.previous_uid,
        next_uid=value.next_uid,
    )


def embed_context(
    runtime: ClientRuntime,
    child_context: str,
    *,
    into_context: str,
    before: str | None = None,
    after: str | None = None,
) -> EmbeddedContextResult:
    """Create one live Context relationship at an exact direct-item gap."""

    try:
        result = execute_embed(
            EmbedRequest(
                child_locator=child_context,
                into_locator=into_context,
                before=before,
                after=after,
            ),
            store=runtime.store,
            allow_granted_sources=active_client_registry(runtime) is not None,
        )
    except FileNotFoundError as error:
        raise_public(EmbedContextError, error)
    except (ProfileConfigError, ProfileError, PermissionError) as error:
        raise_public(EmbedAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(EmbedConflictError, error)
    except OSError as error:
        raise_public(EmbedStorageError, error)
    except (ApplicationEmbedError, KeyError, TypeError, ValueError) as error:
        raise_public(EmbedInputError, error)
    except RuntimeError as error:
        raise_public(EmbedConflictError, error)
    except Exception as error:
        raise_public(EmbedExecutionError, error)

    return EmbeddedContextResult(
        child_name=result.child_name,
        child_uid=result.child_uid,
        into_name=result.into_name,
        into_uid=result.into_uid,
        placement=_placement(result),
        checkpoint_uid=result.checkpoint_uid,
    )


def embed_memory(
    runtime: ClientRuntime,
    memory_selector: str,
    *,
    source_context: str,
    into_context: str,
    before: str | None = None,
    after: str | None = None,
) -> EmbeddedMemoryResult:
    """Create one live Memory relationship at an exact direct-item gap."""

    try:
        result = execute_memory_embed(
            MemoryEmbedRequest(
                memory_selector=memory_selector,
                source_locator=source_context,
                into_locator=into_context,
                before=before,
                after=after,
            ),
            store=runtime.store,
            allow_granted_sources=active_client_registry(runtime) is not None,
        )
    except FileNotFoundError as error:
        raise_public(EmbedContextError, error)
    except (ProfileConfigError, ProfileError, PermissionError) as error:
        raise_public(EmbedAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(EmbedConflictError, error)
    except OSError as error:
        raise_public(EmbedStorageError, error)
    except (ApplicationEmbedError, KeyError, TypeError, ValueError) as error:
        raise_public(EmbedInputError, error)
    except RuntimeError as error:
        raise_public(EmbedConflictError, error)
    except Exception as error:
        raise_public(EmbedExecutionError, error)

    return EmbeddedMemoryResult(
        embed_uid=result.embed_uid,
        source_name=result.source_name,
        source_uid=result.source_uid,
        memory_uid=result.memory_uid,
        into_name=result.into_name,
        into_uid=result.into_uid,
        placement=_placement(result),
        checkpoint_uid=result.checkpoint_uid,
    )


__all__ = ["embed_context", "embed_memory"]
