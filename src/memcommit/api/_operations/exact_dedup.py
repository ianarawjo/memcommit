"""Public Python assembly for provider-free exact Dedup."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.dedup import (
    ExactDedupContextResult,
    ExactDedupGroupResult,
    ExactDedupResult,
)
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticConflictError,
    SemanticContextError,
    SemanticExecutionError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.authority.access import resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.operations.exact_dedup.application import (
    ExactDedupError,
    apply_exact_dedup_scope,
)
from memcommit.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.operations.profile.model import ProfileError
from memcommit.persistence.store import ConcurrentContextUpdateError


def _active_registry(runtime: ClientRuntime):
    if runtime.registry is None or runtime.profile is None:
        return None
    try:
        registry = load_profile_registry()
        if (
            runtime.profile.uid == registry.active.uid
            and runtime.store_root == profile_store_dir(registry.active).resolve()
        ):
            return registry
        return None
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)


def dedup_exact(
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
        registry = _active_registry(runtime)
        access = resolve_context_access(
            runtime.store,
            canonical,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
        receipt = apply_exact_dedup_scope(
            runtime.store,
            access,
            include_descendants=include_descendants,
            registry=registry,
        )
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except ConcurrentContextUpdateError as error:
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


__all__ = ["dedup_exact"]
