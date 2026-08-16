"""Public Add assembly without a dependency on the client facade."""

from __future__ import annotations

from collections.abc import Sequence
import json

from memcommit.add_application import (
    AddError as ApplicationAddError,
    AddRequest,
    AddSource,
    run_add,
    validate_add_request,
)
from memcommit.add_runtime import MemoryStoreAddTargetPort
from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.add import AddMemoriesResult, AddedMemoryResult
from memcommit.api.errors import (
    AddAuthorityError,
    AddConflictError,
    AddContextError,
    AddExecutionError,
    AddInputError,
    AddStorageError,
)
from memcommit.context_locator import resolve_context_locator
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.store import ConcurrentContextUpdateError


def add_memories(
    runtime: ClientRuntime,
    contents: Sequence[str],
    *,
    context_name: str | None = None,
) -> AddMemoriesResult:
    """Append one exact ordered batch and publish one Add checkpoint."""

    try:
        if isinstance(contents, (str, bytes)):
            raise TypeError("contents must be a sequence of Memory texts.")
        values = tuple(contents)
        if context_name is not None and (
            not isinstance(context_name, str) or not context_name
        ):
            raise ValueError("context_name must be nonblank text.")
        request = validate_add_request(
            AddRequest(
                contents=values,
                context_locator=context_name,
                source=AddSource(
                    mode="EXPLICIT_BATCH",
                    kind="python-api",
                    parser="exact-memory-sequence-v1",
                    raw_text=json.dumps(
                        values,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
            )
        )
    except (ApplicationAddError, TypeError, ValueError) as error:
        raise_public(AddInputError, error)

    store = runtime.store
    try:
        current_name = (
            store.current_context_name() if store.state_file.exists() else None
        )
        operand = context_name or current_name
        if operand is None:
            raise FileNotFoundError(
                "No current Context; pass context_name or initialize one."
            )
        canonical = resolve_context_locator(operand, current=current_name)
        target_is_local = store.context_exists(canonical)
        if not target_is_local:
            if runtime.registry is None:
                raise FileNotFoundError(f"Context {canonical!r} not found.")
            registry = load_profile_registry()
            if (
                runtime.profile is None
                or runtime.profile.uid != registry.active.uid
                or runtime.store_root
                != profile_store_dir(registry.active).resolve()
            ):
                raise AddAuthorityError(
                    "CREATE-granted Add requires a client bound to the "
                    "active Profile."
                )
        port = MemoryStoreAddTargetPort(
            store,
            current_name=current_name,
            local_only=target_is_local,
        )
        result = run_add(request, target_port=port)
    except AddAuthorityError:
        raise
    except FileNotFoundError as error:
        raise_public(AddContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(AddAuthorityError, error)
    except ConcurrentContextUpdateError as error:
        raise_public(AddConflictError, error)
    except OSError as error:
        raise_public(AddStorageError, error)
    except (ApplicationAddError, RuntimeError, TypeError, ValueError) as error:
        raise_public(AddExecutionError, error)

    return AddMemoriesResult(
        context_name=result.context_name,
        context_uid=result.context_uid,
        memories=tuple(
            AddedMemoryResult(uid=memory.uid, content=memory.content)
            for memory in result.memories
        ),
        checkpoint_uid=result.checkpoint_uid,
    )


__all__ = ["add_memories"]

