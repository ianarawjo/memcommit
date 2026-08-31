"""Public Python assembly for provider-free exact Dedup."""

from __future__ import annotations

from memcommit.adapters.python_api._runtime import ClientRuntime
from memcommit.adapters.python_api._support.active_profile import (
    active_profile_registry,
)
from memcommit.adapters.python_api._support.errors import raise_public
from memcommit.adapters.python_api.dedup import (
    ExactDedupContextResult,
    ExactDedupGroupResult,
    ExactDedupResult,
)
from memcommit.adapters.python_api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.application.capabilities.authority.context_access import resolve_context_access
from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.operations.dedup.application import (
    ExactDedupConflictError,
    ExactDedupError,
    apply_exact_dedup_scope,
)
from memcommit.application.operations.find_duplicates.application import (
    analyze_exact_duplicate_scope,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError

def dedup(
    runtime: ClientRuntime,
    context_name: str | None = None,
    *,
    include_descendants: bool = False,
) -> ExactDedupResult:
    """Remove exact duplicates from one direct or lexical Context scope."""

    try:
        if type(include_descendants) is not bool:
            raise TypeError("Exact Dedup descendant reach must be a boolean.")
        current_name = runtime.store.current_context_name()
        if context_name is None:
            if current_name is None:
                raise FileNotFoundError("No current Context is available.")
            canonical = current_name
        else:
            canonical = resolve_context_locator(context_name, current=current_name)
        registry = active_profile_registry(runtime)
        access = resolve_context_access(
            runtime.store,
            canonical,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        analysis = analyze_exact_duplicate_scope(
            runtime.store,
            access,
            include_descendants=include_descendants,
            registry=registry,
        )
        receipt = apply_exact_dedup_scope(
            runtime.store,
            access,
            analysis,
            registry=registry,
        )
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except (ConcurrentContextUpdateError, ExactDedupConflictError) as error:
        raise_public(SemanticConflictError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (ExactDedupError, RuntimeError) as error:
        raise_public(SemanticExecutionError, error)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    contexts = tuple(
        ExactDedupContextResult(
            context_name=frame.context_name,
            groups=tuple(
                ExactDedupGroupResult(
                    survivor_uid=group.survivor_uid,
                    absorbed_uids=group.absorbed_uids,
                    content=group.content,
                    item_kind=group.item_kind,
                    summary=group.summary,
                    context_name=frame.context_name,
                )
                for group in frame.groups
            ),
            checkpoint_uid=frame.checkpoint_uid,
        )
        for frame in receipt.contexts
    )
    groups = tuple(group for frame in contexts for group in frame.groups)
    return ExactDedupResult(
        context_name=receipt.root_name,
        groups=groups,
        checkpoint_uid=receipt.checkpoint_uids[0] if receipt.checkpoint_uids else None,
        include_descendants=receipt.include_descendants,
        contexts=contexts,
        checkpoint_uids=receipt.checkpoint_uids,
        operation_uid=receipt.operation_uid,
    )


__all__ = ["dedup"]
