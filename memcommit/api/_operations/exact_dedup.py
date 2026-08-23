"""Public Python assembly for provider-free exact Dedup."""

from __future__ import annotations

from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.dedup import ExactDedupGroupResult, ExactDedupResult
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
from memcommit.exact_dedup_application import ExactDedupError, apply_exact_dedup
from memcommit.profile_config import (
    ProfileConfigError,
    load_profile_registry,
    profile_store_dir,
)
from memcommit.profiles import ProfileError
from memcommit.store import ConcurrentContextUpdateError


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
) -> ExactDedupResult:
    """Remove same-role exact duplicate direct items without provider inference."""

    try:
        current_name = runtime.store.current_context_name()
        if context_name is None:
            if current_name is None:
                raise FileNotFoundError("No current Context is available.")
            canonical = current_name
        else:
            canonical = resolve_context_locator(context_name, current=current_name)
        access = resolve_context_access(
            runtime.store,
            canonical,
            current_name=current_name,
            required_permission="READ",
            registry=_active_registry(runtime),
        )
        receipt = apply_exact_dedup(
            access,
            access.store.load_direct(access.context_name),
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
    return ExactDedupResult(
        context_name=receipt.context_name,
        groups=tuple(
            ExactDedupGroupResult(
                survivor_uid=group.survivor_uid,
                absorbed_uids=group.absorbed_uids,
                content=group.content,
                item_kind=group.item_kind,
                summary=group.summary,
            )
            for group in receipt.groups
        ),
        checkpoint_uid=receipt.checkpoint_uid,
    )


__all__ = ["dedup_exact"]
