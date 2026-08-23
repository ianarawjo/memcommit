"""Public Python assembly for provider-free read-only Find Duplicates."""

from __future__ import annotations

from memcommit.api._operations.exact_dedup import _active_registry
from memcommit.api._runtime import ClientRuntime
from memcommit.api._support.errors import raise_public
from memcommit.api.dedup import ExactDedupGroupResult, ExactDuplicateFindResult
from memcommit.api.errors import (
    SemanticAuthorityError,
    SemanticContextError,
    SemanticInputError,
    SemanticStorageError,
)
from memcommit.authority.access import GrantedReadStore, resolve_context_access
from memcommit.context_locator import resolve_context_locator
from memcommit.exact_dedup import find_exact_duplicates
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError


def find_duplicates_exact(
    runtime: ClientRuntime,
    context_name: str | None = None,
) -> ExactDuplicateFindResult:
    """Return same-role exact direct-item groups without provider mutation."""

    try:
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
        context = (
            GrantedReadStore(access, registry=registry).load_direct(access.display_name)
            if access.is_granted
            else access.store.load_direct(access.context_name)
        )
        report = find_exact_duplicates(context)
    except (FileNotFoundError, KeyError) as error:
        raise_public(SemanticContextError, error)
    except (ProfileConfigError, ProfileError) as error:
        raise_public(SemanticAuthorityError, error)
    except OSError as error:
        raise_public(SemanticStorageError, error)
    except (TypeError, ValueError) as error:
        raise_public(SemanticInputError, error)
    return ExactDuplicateFindResult(
        context_name=access.display_name,
        memory_count=report.memory_count,
        item_count=report.item_count,
        groups=tuple(
            ExactDedupGroupResult(
                survivor_uid=group.survivor_uid,
                absorbed_uids=group.absorbed_uids,
                content=group.content,
                item_kind=group.item_kind,
                summary=group.summary,
            )
            for group in report.groups
        ),
    )


__all__ = ["find_duplicates_exact"]
